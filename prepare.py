"""Read a supplied QR symbol and build the corresponding relief geometry."""

import base64
import hashlib
import io
import math
import json
import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlsplit

import cv2
import numpy as np
from PIL import Image, ImageOps
import zxingcpp

from showcase import LOOKS, character_style, minifigure_mesh, sculpture
from brand_scene import SCENES, authored_scene
from image_character import IMAGE_FORM
from studio_scene import GRAPHIC_FORMS, build_studio

MAX_FILE = 8 * 1024 * 1024
MAX_PIXELS = 18_000_000
DESIGNQR_REVISION = "a75f5749a8abef289899b1b87898af7124b054a4"
BRICK_INK = (155, 32, 25)
PALETTES = {
    "navy-red": ((22, 50, 98), (165, 29, 48)),
    "umber-rust": ((75, 43, 28), (131, 68, 30)),
    "brick-red": ((103, 30, 33), (158, 40, 32)),
    "webb-copper": ((73, 37, 26), (130, 63, 31), (151, 89, 43)),
    "minifig-primary": ((19, 66, 136), (178, 27, 50), (144, 96, 0)),
    "kitty": ((20, 60, 118), (177, 23, 57), (194, 37, 67)),
    "saturn-gold": ((77, 47, 25), (136, 76, 29), (149, 98, 43)),
    "slate-steel": ((37, 49, 62), (47, 82, 104)),
    "night-flight": ((19, 40, 101), (137, 68, 20), (0, 119, 122)),
    "dropbox-blue": ((0, 69, 202), (40, 55, 80), (120, 40, 110)),
    "pixel-amber": ((53, 39, 30), (131, 74, 16), (152, 95, 24)),
    "instant-film": ((42, 37, 56), (157, 52, 30), (109, 44, 99)),
    "image": (),
}
DEFAULT_EFFECTS = {"webb-copper": "nebula", "minifig-primary": "bricks",
                   "kitty": "petals", "saturn-gold": "rings"}
EFFECT_OPTIONS = {"none", "brand-sheen", "product-studio", "flight-grid", "file-stack", "print-development", "crank-pixels"}


def open_image(raw):
    if not raw or len(raw) > MAX_FILE:
        raise ValueError("每张图片须小于 8 MiB。")
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            if opened.format not in ("JPEG", "PNG") or math.prod(opened.size) > MAX_PIXELS:
                raise ValueError("请上传 PNG 或 JPEG，且每张不超过 1800 万像素。")
            extension = "png" if opened.format == "PNG" else "jpg"
            return ImageOps.exif_transpose(opened).convert("RGBA"), extension
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError("图片无法读取，请重新导出为 PNG 或 JPEG。") from error


def read_opencv(image):
    try:
        return cv2.QRCodeDetector().detectAndDecodeBytes(image)[0]
    except cv2.error:
        return b""


def read_vision(image):
    root = Path(__file__).resolve().parent
    executable = root / ".deps" / "read-vision"
    if not executable.exists():
        return b""
    work = root / ".work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as local:
        path = Path(local) / "vision-input.png"
        Image.fromarray(image).save(path)
        try:
            reply = subprocess.run([str(executable), str(path)], check=True,
                                   capture_output=True, timeout=10)
            values = json.loads(reply.stdout)
            return values[0].encode("utf-8") if len(values) == 1 else b""
        except (OSError, ValueError, subprocess.SubprocessError):
            return b""


def flat_image(matrix, module=12):
    print_grid = np.pad(np.where(matrix, 0, 255).astype(np.uint8), 4, constant_values=255)
    return print_grid.repeat(module, axis=0).repeat(module, axis=1)


def decode_zxing(image, *, aligned=False):
    return zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode, is_pure=aligned)


def generate_qr(value):
    if not isinstance(value, str):
        raise ValueError("请输入包含 https:// 或 http:// 的完整网址。")
    value = value.strip()
    try:
        address = urlsplit(value)
        valid = (
            address.scheme in ("http", "https") and bool(address.hostname)
            and not any(char.isspace() or ord(char) < 32 or char == "\x7f" for char in value)
        )
        payload = value.encode("utf-8")
    except (ValueError, UnicodeEncodeError):
        valid = False
    if not valid:
        raise ValueError("请输入包含 https:// 或 http:// 的完整网址，网址中不能有空格。")
    return encode_qr(value, payload, "网址")


def generate_text_qr(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("请输入要写入二维码的文字。")
    try:
        payload = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("请输入有效的 UTF-8 文字。") from error
    return encode_qr(value, payload, "文字")


def encode_qr(value, payload, label):
    if len(payload) <= 512:
        for correction in (4, 2, 1):
            raster = np.asarray(zxingcpp.write_barcode(
                zxingcpp.BarcodeFormat.QRCode, value, quiet_zone=4, ec_level=correction
            ))
            if raster.shape[0] <= 65 + 8:
                original = Image.fromarray(raster.repeat(12, axis=0).repeat(12, axis=1))
                with io.BytesIO() as stream:
                    original.save(stream, format="PNG")
                    return original.convert("RGBA"), stream.getvalue(), payload
    raise ValueError(f"{label}超出本地演示的二维码容量，请缩短内容。")


def read_original(original, *, allow_center_overlay=False):
    white = Image.new("RGBA", original.size, "white")
    white.alpha_composite(original)
    gray = np.asarray(white.convert("L"))
    codes = decode_zxing(gray)
    if len(codes) != 1:
        raise ValueError("请上传一张黑白对比清晰、只含一个完整标准二维码的图片。")
    code = codes[0]
    payload = bytes(code.bytes)
    if not payload:
        raise ValueError("原二维码没有可核对的载荷，请保留原图并换一张清晰图片。")
    # Use the detected orientation to sample module centers from the uploaded image.
    detected_grid = np.asarray(code.to_image(with_quiet_zones=False)) != 0
    n = detected_grid.shape[0]
    if not 21 <= n <= 65 or (n - 21) % 4:
        raise ValueError("本地演示支持 21×21 至 65×65 的标准二维码。")
    pos = code.position
    corners = np.float32([[p.x, p.y] for p in (pos.top_left, pos.top_right, pos.bottom_right, pos.bottom_left)])
    grid = np.float32([[0, 0], [n, 0], [n, n], [0, n]])
    transform = cv2.getPerspectiveTransform(grid, corners)
    centers = np.float32([[[c + .5, r + .5] for r in range(n) for c in range(n)]])
    xs, ys = np.floor(cv2.perspectiveTransform(centers, transform)[0]).astype(int).T
    if np.any(xs < 0) or np.any(ys < 0) or np.any(xs >= gray.shape[1]) or np.any(ys >= gray.shape[0]):
        raise ValueError("二维码超出图片边界，请换用四边完整的原图。")
    matrix = gray[ys, xs].reshape(n, n) < 128
    differing_rows, differing_cols = np.nonzero(matrix != detected_grid)
    if differing_rows.size:
        center = n // 2
        radius = n // 6
        center_only = (np.all(np.abs(differing_rows - center) <= radius)
                       and np.all(np.abs(differing_cols - center) <= radius))
        if not (allow_center_overlay and center_only):
            raise ValueError("原图抽取结果与检测到的二维码网格不一致，请换用清晰原图。")
        # The center badge can obscure the sampled values. Verify the detected
        # grid and the source pixels independently against the same payload below.
        matrix = detected_grid

    # Try the original image first. For tightly cropped / off-axis prints, decode a
    # grayscale rectification of those same pixels with an added white margin.
    cv_input = gray
    if max(gray.shape) > 1800:
        factor = 1800 / max(gray.shape)
        cv_input = cv2.resize(gray, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
    source_check = "OpenCV · 原图灰度"
    if read_opencv(cv_input) != payload:
        side = n * 9
        upright = np.float32([[0, 0], [side, 0], [side, side], [0, side]])
        rectified = cv2.warpPerspective(gray, cv2.getPerspectiveTransform(corners, upright), (side, side))
        rectified = cv2.copyMakeBorder(rectified, 36, 36, 36, 36, cv2.BORDER_CONSTANT, value=255)
        if read_opencv(rectified) == payload:
            source_check = "OpenCV · 原图二维码区灰度透视校正并补四模块白边"
        elif read_vision(gray) == payload:
            source_check = "Apple Vision · 原图灰度，UTF-8 文本回读"
        else:
            raise ValueError("两套解码器未能独立核对原图，请换一张对比清楚的原码。")

    flat = flat_image(matrix)
    checks = decode_zxing(flat) or decode_zxing(flat, aligned=True)
    independent = "OpenCV"
    if read_opencv(flat) != payload:
        independent = "Apple Vision"
        if read_vision(flat) != payload:
            raise ValueError("第二套解码器未能从抽取网格读回原载荷。")
    if len(checks) != 1 or bytes(checks[0].bytes) != payload:
        raise ValueError("从原图抽取的网格未通过双解码，请换一张清晰原码。")
    return code.text, payload, matrix, flat, corners.astype(int).tolist(), source_check, independent


def gradient_foreground(rgb):
    # Treat the outer side strips as the backdrop only when the top and side
    # strips are coherent. This catches studio gradients without cutting sky
    # or other natural backgrounds out of arbitrary photographs.
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    height, width = lab.shape[:2]
    if min(height, width) < 32:
        return None
    strip = max(3, round(width * .035))
    sigma = max(3, height * .022)
    left = cv2.GaussianBlur(np.median(lab[:, :strip], axis=1)[:, None, :], (1, 0), sigma)
    right = cv2.GaussianBlur(np.median(lab[:, -strip:], axis=1)[:, None, :], (1, 0), sigma)
    ramp = np.linspace(0, 1, width)[None, :, None]
    backdrop = left + (right - left) * ramp
    distance = np.linalg.norm((lab - backdrop) * [.55, 1.9, 1.9], axis=2)
    rim = np.concatenate([distance[:, :strip].ravel(), distance[:, -strip:].ravel(),
                          distance[:strip].ravel()])
    if np.percentile(rim, 90) >= 8:
        return None
    mask = (distance > 15).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), dtype=np.uint8))
    count, labels, sizes, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        return None
    main = int(np.argmax(sizes[1:, cv2.CC_STAT_AREA])) + 1
    size = sizes[main, cv2.CC_STAT_AREA]
    if not .045 * mask.size < size < .73 * mask.size or size < mask.sum() * .6:
        return None
    return labels == main


def foreground(original):
    image = original.copy()
    image.thumbnail((800, 800))
    rgba = np.array(image)
    if np.any(rgba[:, :, 3] < 64):
        label = "按图片透明通道取轮廓"
        mask = rgba[:, :, 3] >= 92
    else:
        pixels = rgba[:, :, :3].astype(float)
        rim = np.concatenate([pixels[0], pixels[-1], pixels[:, 0], pixels[:, -1]])
        background = np.median(rim, axis=0)
        mask = np.linalg.norm(pixels - background, axis=2) > 42
        if .025 < mask.mean() < .84 and np.mean(np.linalg.norm(rim - background, axis=1) < 42) > .63:
            label = "按边缘底色取轮廓"
            _, labels, areas, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
            kept = np.flatnonzero(areas[1:, cv2.CC_STAT_AREA] >= max(6, mask.sum() * .004)) + 1
            mask = np.isin(labels, kept)
        else:
            mask = gradient_foreground(rgba[:, :, :3])
            if mask is None:
                label = "完整照片浅浮雕，保留背景"
                mask = np.ones(rgba.shape[:2], dtype=bool)
            else:
                label = "按渐变背景取轮廓"
    rgba[:, :, 3] = mask.astype(np.uint8) * 255
    cutout = Image.fromarray(rgba)
    box = cutout.getbbox()
    if not box:
        raise ValueError("主体图没有可用轮廓，请换一张图片。")
    return cutout.crop(box), label


def relief(cutout, n):
    width, height = cutout.size

    def sample(grid):
        ratio = grid / max(width, height)
        size = max(1, round(width * ratio)), max(1, round(height * ratio))
        raster = np.array(cutout.resize(size, Image.Resampling.LANCZOS))
        return raster, raster[:, :, 3] > 110

    grid = n
    raster, valid = sample(grid)
    while grid < 3 * n:
        next_raster, next_valid = sample(grid + 1)
        if next_valid.sum() > n * n:
            break
        grid += 1
        raster, valid = next_raster, next_valid
    if not valid.any():
        raise ValueError("主体过细，缩小到方块后没有可用轮廓。请换一张占幅更大的图片。")
    edge = cv2.distanceTransform(np.pad(valid.astype(np.uint8), 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    edge /= edge.max()
    h, w = valid.shape
    spacing = .93 / grid
    pieces = []
    for row, col in zip(*np.nonzero(valid)):
        color = raster[row, col, :3].astype(float)
        depth = .018 + .172 * float(edge[row, col]) ** .7
        depth += .026 * (float(color.mean()) / 255.0 - .5)
        pieces.append(dict(x=float((col - (w - 1) / 2) * spacing),
                           z=float((row - (h - 1) / 2) * spacing),
                           h=depth / 2 - .044, w=spacing * .94, d=depth,
                           color=np.clip(color * [.98, 1.02, 1.04] + [1, 3, 5], 0, 255).astype(int).tolist(),
                           group=f"{row//4}:{col//4}"))
    # Fill any surplus QR cells by partitioning existing columns in depth.
    splits, remainder = divmod(n * n, len(pieces))
    columns = []
    for index, piece in enumerate(pieces):
        layers = splits + (index < remainder)
        thickness = piece["d"] / layers
        for layer in range(layers):
            center = piece["h"] + (layer - (layers - 1) / 2) * thickness
            columns.append({**piece, "id": len(columns), "h": center, "d": thickness})
    return columns, grid


def planet(n):
    # Fill the visible surfaces first, then reuse interior space for any spare
    # QR modules. The sphere, tilted rings and moon each have real depth.
    budget = n * n
    candidate = None
    for grid in range(12, 100):
        coords = (np.arange(grid) - (grid - 1) / 2) / grid
        x, y, z = np.ix_(coords, coords, coords)
        radius = np.sqrt(x*x + y*y)
        band_height = z - .25*x - .07*y
        globe = (x+.034)**2 + y*y + z*z <= .258**2
        bands = ((radius >= .307) & (radius <= .357)) | ((radius >= .385) & (radius <= .473))
        rings = bands & (np.abs(band_height) <= .70/grid)
        moon = (x-.328)**2 + (y+.132)**2 + (z+.345)**2 <= .054**2
        solid = globe | rings | moon
        inner = solid.copy()
        for axis in range(3):
            inner &= np.roll(solid, 1, axis) & np.roll(solid, -1, axis)
        exterior = np.argwhere(solid & ~inner)
        if len(exterior) > budget:
            break
        candidate = grid, coords, globe, moon, exterior, np.argwhere(inner)

    grid, coords, globe, moon, exterior, interior = candidate
    indexes = np.concatenate((exterior, interior))[:budget]
    # Coarse lattices can leave too few interior voxels for a particular QR
    # size. Subdivide selected existing cubes without changing their silhouette.
    extra = budget - len(indexes)
    pieces = []
    for index, (i, j, k) in enumerate(indexes):
        x, y, z = (float(coords[t]) for t in (i, j, k))
        if globe[i, j, k]:
            stripe = .5 + .5 * math.sin(49*z + 2.4*y + .68*math.sin(20*z))
            light = .77 + .23*math.tanh((-x + y*.28 - z*.78) * 7)
            rgb = tuple(light*channel for channel in (254, 157+39*stripe, 94+47*stripe))
        elif moon[i, j, k]:
            rgb = (211, 219, 246)
        else:
            radius = math.hypot(x, y)
            light = .87 + .13*math.tanh((-x + y*.25) * 4)
            rgb = tuple(light*channel for channel in (
                (230, 182, 132) if radius < .37 else (246, 211, 160)
            ))
        layers = 1 + extra // len(indexes) + (index < extra % len(indexes))
        depth = 1.003 / grid / layers
        for layer in range(layers):
            pieces.append(dict(
                id=len(pieces), x=x, z=z, h=y+(layer-(layers-1)/2)*depth,
                w=1.003/grid, d=depth, color=[round(v) for v in rgb],
                group=f"{i//4}:{j//4}:{k//4}",
            ))
    return pieces, grid


def brick(n):
    """Build a hollow 2-by-4 brick with eight studs and three underside tubes."""
    budget = n * n
    for grid in range(12, 100):
        coords = (np.arange(grid) - (grid - 1) / 2) / grid
        x, y, z = np.ix_(coords, coords, coords)
        across = np.abs(x % .22 - .11)
        stud_radius = across**2 + (np.abs(y) - .11)**2
        studs = (stud_radius <= .073**2) & (np.abs(x) < .41) & (z < -.09) & (z > -.178)
        outside = (np.abs(x) < .44) & (np.abs(y) < .222) & (z >= -.09) & (z < .166)
        well = (np.abs(x) < .386) & (np.abs(y) < .167) & (z > -.034)
        nearest_tube = np.minimum(np.abs(x), np.abs(np.abs(x) - .22))
        tube_radius = nearest_tube**2 + y*y
        tubes = well & (tube_radius <= .078**2) & (tube_radius >= .043**2) & (z < .148)
        solid = studs | (outside & ~well) | tubes
        surface = solid.copy()
        for axis in range(3):
            surface &= np.roll(solid, 1, axis) & np.roll(solid, -1, axis)
        exterior = np.argwhere(solid & ~surface)
        if len(exterior) > budget:
            break
        candidate = grid, coords, studs, tubes, solid, exterior, np.argwhere(surface)

    grid, coords, studs, tubes, solid, exterior, interior = candidate
    indexes = np.concatenate((exterior, interior))[:budget]
    extra = budget - len(indexes)
    pieces = []
    # Face order matches the renderer: -y, +y, -z, +x, +z, -x.
    neighbors = ((0,-1,0), (0,1,0), (0,0,-1), (1,0,0), (0,0,1), (-1,0,0))
    for index, (i, j, k) in enumerate(indexes):
        x, y, z = (float(coords[t]) for t in (i, j, k))
        if studs[i, j, k]:
            base = (245, 66, 44)
        elif tubes[i, j, k]:
            base = (177, 36, 32)
        else:
            base = (214, 44, 33)
        light = .88 + .12 * math.tanh((-x*.44 + y*.4 - z*.65) * 5)
        layers = 1 + extra // len(indexes) + (index < extra % len(indexes))
        depth = 1 / grid / layers
        joined_faces = sum(1 << side for side, (dx, dy, dz) in enumerate(neighbors)
                           if solid[i+dx, j+dy, k+dz])
        for layer in range(layers):
            hidden_faces = joined_faces | (1 if layer > 0 else 0) | (2 if layer < layers - 1 else 0)
            pieces.append(dict(
                id=len(pieces), x=x, z=z, h=y+(layer-(layers-1)/2)*depth,
                w=1/grid, d=depth, hiddenFaces=hidden_faces, color=[round(channel*light) for channel in base],
                group=f"{i//4}:{j//4}:{k//4}",
            ))
    return pieces, grid


def assign_tiles(pieces, matrix):
    # DesignQR City correspondence (MIT, see bundled license). Keep the
    # group assignments and locally swap crossings in two bounded passes.
    n = len(matrix)
    targets = [dict(r=r, c=c, x=(c + .5) / n - .5, z=(r + .5) / n - .5, dark=bool(matrix[r, c]))
               for r in range(n) for c in range(n)]
    xy = np.array([(cell["x"], cell["z"]) for cell in targets])
    used = np.zeros(len(targets), dtype=bool)
    groups = defaultdict(list)
    tiles = []
    for piece in pieces:
        distances = ((xy - [piece["x"], piece["z"]]) ** 2).sum(axis=1)
        distances[used] = np.inf
        nearest = int(distances.argmin())
        used[nearest] = True
        pair = dict(source=piece, target=targets[nearest])
        groups[piece["group"]].append(pair)
        tiles.append(pair)

    def distance(source, target):
        return (source["x"] - target["x"]) ** 2 + (source["z"] - target["z"]) ** 2

    for group in groups.values():
        for _ in range(2):
            for i, first in enumerate(group):
                a, x = first["source"], first["target"]
                for second in group[i + 1:]:
                    b, y = second["source"], second["target"]
                    if distance(a, y) + distance(b, x) + 1e-12 < distance(a, x) + distance(b, y):
                        first["target"], second["target"] = y, x
                        x = y
        motion = dict(
            x=sum(p["target"]["x"] - p["source"]["x"] for p in group) / len(group),
            z=sum(p["target"]["z"] - p["source"]["z"] for p in group) / len(group),
            settle=.50,
        )
        for pair in group:
            pair["motion"] = motion
    return tiles


def image_inks(cutout, pieces):
    if cutout is None:
        sample = np.asarray([item["color"] for item in pieces], dtype=np.uint8)
    else:
        image = cutout.copy()
        image.thumbnail((144, 144))
        rgba = np.asarray(image)
        sample = rgba[rgba[:, :, 3] >= 200, :3]
    if not len(sample):
        return [(35, 35, 35)]
    hsv = cv2.cvtColor(sample.reshape(1, -1, 3), cv2.COLOR_RGB2HSV)[0]
    solid = (hsv[:, 1] > 70) & (hsv[:, 2] > 48)
    if not solid.any():
        return [(35, 35, 35)]
    hue = ((hsv[solid, 0].astype(int) + 7) % 180) // 15
    order = np.argsort(-np.bincount(hue, minlength=12), kind="stable")
    selected, inks = [], []
    for sector in order:
        mask = hue == sector
        if mask.sum() < max(3, len(hue) * .055):
            break
        if any(min(abs(sector - other), 12 - abs(sector - other)) <= 1 for other in selected):
            continue
        value = np.median(sample[solid][mask], axis=0)
        # Keep even bright yellow modules dark enough against white.
        luma = float(value @ (0.2126, 0.7152, 0.0722))
        scale = min(1, [78, 105, 112][len(inks)] / max(1, luma))
        inks.append(tuple(int(v) for v in np.rint(value * scale)))
        selected.append(sector)
        if len(inks) == 3:
            break
    return inks or [(35, 35, 35)]


def copper_logo(cutout):
    rgba = np.asarray(cutout).copy()
    r, g, b = rgba[:, :, :3].astype(float).transpose(2, 0, 1)
    details = np.clip((r + g + b - 380) / 335, 0, 1)[..., None]
    body = np.stack((r * .40 + b * .36 + 44, g * .43 + 35, b * .10 + 19), axis=-1)
    foil = np.where((r > b * 1.2)[..., None], [251, 156, 72], body)
    rgba[:, :, :3] = (foil * (1 - details) + np.array([255, 228, 178]) * details).astype(np.uint8)
    return Image.fromarray(rgba)


def camera_body(cutout, n):
    """Use the straight-on official photo for the face and build the housing behind it."""
    budget = n * n
    photo = np.asarray(cutout)
    best = None
    for grid in range(10, 65):
        coords = (np.arange(grid) - (grid - 1) / 2) / grid
        x, depth, z = np.ix_(coords, coords, coords)
        photo_x = np.rint((coords / .86 + .5) * (cutout.width - 1)).astype(int)
        photo_z = np.rint(((coords + .059) / .81 + .5) * (cutout.height - 1)).astype(int)
        surface = photo[photo_z.clip(0, cutout.height-1)[None, :],
                        photo_x.clip(0, cutout.width-1)[:, None]]
        mask = (surface[:, :, 3] > 100) & (np.abs(x[:, 0, :]) < .43) & (np.abs(z[:, 0, :] + .059) < .405)
        lid = z < -.240
        rim = np.maximum(np.abs(x) - .335, 0) * .74
        front = np.where(lid, .148, .195) - rim
        lens = (x-.01)**2 + (z+.09)**2 < .092**2
        front = front + .048 * lens
        back = np.where(lid, -.108, -.261) + rim
        solid = mask[:, None, :] & (depth <= front) & (depth >= back)
        exposed = solid.copy()
        interior = solid.copy()
        for axis in range(3):
            interior &= np.roll(solid, 1, axis) & np.roll(solid, -1, axis)
        exposed &= ~interior
        boundary = np.argwhere(exposed)
        if len(boundary) > budget:
            break
        if len(boundary):
            best = grid, coords, surface, solid, boundary, np.argwhere(interior)

    if best is None:
        raise ValueError("主体图轮廓无法用于相机立体造型。")
    grid, coords, surface, solid, boundary, inner = best
    sites = np.concatenate((boundary, inner))[:budget]
    splits, remainder = divmod(budget - len(sites), len(sites))
    pieces = []
    for index, (i, j, k) in enumerate(sites):
        x, h, z = (float(coords[axis]) for axis in (i, j, k))
        is_front = not solid[i, j + 1, k]
        if is_front:
            rgb = np.clip(surface[i, k, :3].astype(float) * 1.045 + [2, 2, 3], 0, 255)
        elif z < -.24:
            rgb = (218, 219, 219) if h < .07 else (46, 47, 48)
        elif z < .058 and h < -.149:
            rgb = (54, 55, 54)
        else:
            rgb = (221, 217, 207) if z < .25 or h > .065 else (160, 157, 150)
        layers = 1 + splits + (index < remainder)
        spacing = 1.002 / grid
        thickness = spacing / layers
        for layer in range(layers):
            pieces.append(dict(id=len(pieces), x=x, z=z, h=h+(layer-(layers-1)/2)*thickness,
                               w=spacing, d=thickness, color=[round(value) for value in rgb],
                               group=f"{i//4}:{j//4}:{k//4}"))
    return pieces, grid


def handheld_body(cutout, n):
    """Rebuild the round-corner housing and sample the casing color from the product photo."""
    pixels = np.asarray(cutout).reshape(-1, 4).astype(int)
    yellow = (pixels[:, 3] > 180) & (pixels[:, 0] > 175) & (pixels[:, 1] > 120) & (
        pixels[:, 0] - pixels[:, 2] > 100)
    if not np.any(yellow):
        raise ValueError("手摇像素台造型需要能辨认出黄色机身的产品图。")
    paint = np.median(pixels[yellow, :3], axis=0)
    budget = n * n
    grid = n
    coords = (np.arange(grid) - (grid - 1) / 2) * .84 / grid
    sites = [(i, j, x, z) for i, x in enumerate(coords) for j, z in enumerate(coords)
             if math.hypot(max(0, abs(x) - .332), max(0, abs(z) - .324)) < .073]
    splits, remainder = divmod(budget, len(sites))
    pieces = []
    for index, (i, j, x, z) in enumerate(sites):
        layers = splits + (index < remainder)
        width = .842 / grid
        bevel = max(0, abs(x) - .35, abs(z) - .34)
        half = .143 - bevel * .32
        for layer in range(layers):
            depth = 2 * half / layers
            h = -half + (layer + .5) * depth
            brightness = 1.03 + .16 * h - .16 * z - bevel * 1.9
            color = np.rint(np.clip(paint * brightness, 0, 255)).astype(int)
            pieces.append(dict(id=len(pieces), x=float(x), z=float(z), h=h,
                               w=width, d=depth, color=color.tolist(), group=f"{i//4}:{j//4}"))
    return pieces, grid


def build_scene(subject, qr, subject_bytes, qr_bytes, *, preset="photo", brief="", palette="", effect="",
                wechat=False, art_scene="", studio_form="", character=None):
    text, payload, matrix, flat, corners, source_check, independent = read_original(
        qr, allow_center_overlay=wechat or bool(studio_form)
    )
    n = len(matrix)
    style = character_style(brief) if preset == "character" else preset
    appearance = LOOKS.get(style)
    ink = BRICK_INK if preset == "brick" else appearance[1] if appearance else None
    finder_ink = accent_ink = None
    if studio_form:
        mesh, pieces, studio, shape, theme, pose, flare = build_studio(subject, studio_form, n, character)
        cutout, grid = None, n
        foreground_method = ("根据原图识别角色比例、部件和标志特征，构建可旋转全身网格与部件动作"
                             if studio_form == IMAGE_FORM else
                             "以原图的轮廓、镂空和颜色生成可环视的双面有厚度图形"
                             if studio_form in GRAPHIC_FORMS else
                             "以参考图可见轮廓和颜色生成有厚度的双面浮雕"
                             if studio_form == "medallion" else
                             "按原图取色，重建全身立体、头发和耳机、四肢关节与星星手牌"
                             if studio_form == "blue-bob" else
                             "从参考图取色，并按主体特征搭建立体材质、空间和操作部件")
    elif art_scene:
        mesh, pieces = authored_scene(art_scene, n)
        cutout, grid = None, n
        shape = SCENES[art_scene][0]
        foreground_method = "按主体用途构建立体场景，以连贯的空间轨迹把三维构件展开到二维码格"
    elif effect == "crank-pixels":
        if preset != "volume":
            raise ValueError("手摇像素台适用于正面或正面偏侧的黄色掌机图，请选择体积造型。")
        cutout, _ = foreground(subject)
        pieces, grid = handheld_body(cutout, n)
        foreground_method = "官网产品图取机身黄，重建方形外壳、像素屏和侧边摇柄"
        shape = "手摇像素掌机"
    elif effect in ("file-stack", "print-development"):
        if preset != "volume":
            raise ValueError("文件台和相机显影适用于上传图的体积造型。")
        cutout, foreground_method = foreground(subject)
        if effect == "print-development":
            pieces, grid = camera_body(cutout, n)
            foreground_method = "官网正面图取色，手工重建翻盖与机身侧背体积"
            shape = "拍立得相机"
        else:
            pieces, grid = relief(cutout, n)
            for piece in pieces:
                piece["x"] *= .79
                piece["z"] = piece["z"] * .79 - .018
                piece["w"] *= .79
                piece["h"] *= 1.72
                piece["d"] *= 1.72
            shape = "立体标志与叠层文件台"
    elif preset == "planet":
        cutout, foreground_method = None, "球体、星环与卫星"
        pieces, grid = planet(n)
        shape = "环形行星"
    elif preset == "brick":
        cutout, foreground_method = None, "八颗凸点、空心底座与三根连接管"
        pieces, grid = brick(n)
        shape = "2×4 积木"
    elif appearance:
        shape = appearance[0]
        cutout, foreground_method = foreground(subject) if subject is not None else (None, brief)
        if style == "minifig":
            foreground_method = "LDraw 零件模型、原版笑脸、圆柱头、手爪与分体双腿"
        pieces, grid = sculpture(style, n, cutout, brief)
    else:
        cutout, foreground_method = foreground(subject)
        pieces, grid = relief(copper_logo(cutout) if preset == "nasa" else cutout, n)
        shape = "铜色 NASA 徽章" if preset == "nasa" else "单图浅浮雕"
    if studio_form and not wechat and not palette:
        base, edge = studio["background"]
        ink = tuple(min(102, round(value * .86)) for value in base)
        finder_ink = tuple(min(92, round(value * .76)) for value in edge)
    if palette:
        colors = image_inks(cutout, pieces) if palette == "image" else PALETTES[palette]
        ink, finder_ink, accent_ink = (*colors, None, None)[:3]
    ink_gradient = palette == "night-flight"
    if ink:
        cells = np.where(matrix[..., None], ink, (255, 255, 255)).astype(np.uint8)
        if ink_gradient:
            row, column = np.ogrid[:n, :n]
            weight = np.clip((2 * column + row - .60*n) / (1.82*n), 0, 1)[..., None]
            gradient = np.floor(np.array(ink) + weight * (np.array(accent_ink) - ink) + .5)
            cells[matrix] = gradient[matrix]
        elif accent_ink:
            row, column = np.ogrid[:n, :n]
            cells[matrix & (2 * column + row >= 2 * n)] = accent_ink
        if finder_ink:
            for row, column in ((0, 0), (0, n - 7), (n - 7, 0)):
                region = slice(row, row + 7), slice(column, column + 7)
                cells[region][matrix[region]] = finder_ink
        module = flat.shape[0] // (n + 8)
        flat = np.pad(cells, ((4, 4), (4, 4), (0, 0)), constant_values=255)
        flat = flat.repeat(module, axis=0).repeat(module, axis=1)
        gray = cv2.cvtColor(flat, cv2.COLOR_RGB2GRAY)
        checks = decode_zxing(gray)
        independent = "OpenCV"
        if read_opencv(gray) != payload:
            independent = "Apple Vision"
            if read_vision(gray) != payload:
                raise ValueError("着色二维码未通过独立解码检查。")
        if len(checks) != 1 or bytes(checks[0].bytes) != payload:
            raise ValueError("着色二维码未能读回完整载荷。")
    if effect == "flight-grid":
        if preset not in ("photo", "volume"):
            raise ValueError("飞行灯阵适用于主体图造型，请选择图片造型。")
        for piece in pieces:
            x, z = piece["x"], piece["z"]
            # Mount the light cells on a curved formation with open air between rows.
            piece["z"] = z * .89 - .098
            piece["h"] = .92 * piece["h"] + .05 * math.cos(8 * x) - .17 * x * x
            piece["w"] *= .55
            piece["d"] *= .51
            band = .5 + .5 * math.sin(9 * x + z * 5)
            piece["color"] = [round(154 + 82 * band), round(213 + 31 * band), 255]
        shape = "字标飞行灯阵"
    tiles = assign_tiles(pieces, matrix)
    scene = dict(n=n, matrix=matrix.astype(int).tolist(), tiles=tiles, foreground=foreground_method,
                 shape=shape, sampleGrid=grid, payload=text,
                 payloadBase64=base64.b64encode(payload).decode("ascii"), sourceCorners=corners,
                 sourceSecondDecoder=source_check, flatSecondDecoder=independent, designQRRevision=DESIGNQR_REVISION,
                 subjectSha256=hashlib.sha256(subject_bytes).hexdigest() if subject_bytes is not None else None,
                 qrSha256=hashlib.sha256(qr_bytes).hexdigest())
    if preset in ("planet", "brick"):
        scene["style"] = preset
    if ink:
        scene["ink"] = list(ink)
    if finder_ink:
        scene["finderInk"] = list(finder_ink)
    if accent_ink:
        scene["accentInk"] = list(accent_ink)
    if ink_gradient:
        scene["inkGradient"] = True
    if appearance:
        scene.update(style=style, solid=True, theme=list(appearance[2]), pose=list(appearance[3]),
                     flare=list(appearance[4]))
    selected_effect = effect or DEFAULT_EFFECTS.get(palette)
    if selected_effect and selected_effect != "none":
        scene["effect"] = selected_effect
    if selected_effect == "flight-grid":
        scene.update(theme=[6, 17, 27], pose=[-.19, -.31], flare=[177, 255, 249])
    if selected_effect == "file-stack":
        scene.update(theme=[216, 225, 238], pose=[-.22, -.10], flare=[140, 196, 255])
    if selected_effect == "print-development":
        scene.update(theme=[198, 169, 145], pose=[-.24, -.19], flare=[255, 208, 167])
    if selected_effect == "crank-pixels":
        scene.update(theme=[172, 192, 172], pose=[-.29, -.17], flare=[255, 211, 117])
    if preset == "nasa":
        scene.update(style="nasa", theme=[26, 16, 21], pose=[-.26, .13], flare=[255, 189, 106])
    if preset == "minifig":
        scene.update(mesh=minifigure_mesh(), theme=[231, 221, 190], pose=[-.27, -.105])
    if studio_form:
        scene.update(artScene="studio", studio=studio, mesh=mesh, theme=theme, pose=pose, flare=flare)
    elif art_scene:
        _, theme, pose, flare = SCENES[art_scene]
        scene.update(artScene=art_scene, mesh=mesh, theme=theme, pose=pose, flare=flare)
    if wechat and "theme" not in scene:
        light_tiles = sum(min(tile["source"]["color"]) >= 185 for tile in tiles)
        if light_tiles > len(tiles) / 2:
            scene["theme"] = [32, 43, 61]
    return scene, flat, cutout
