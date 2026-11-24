"""Create the hero's 2D endpoint from its exact QR grid and source artwork."""
import base64
import hashlib
import io
import math

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from prepare import decode_zxing, read_opencv, read_vision
from studio_forms import star_points
from studio_scene import palette


def make_hero_art(scene, subject):
    cells = scene["matrix"]
    n = scene["n"]
    pad = max(10, round(n * .16))
    units = n + 2 * pad
    module = max(12, 960 // units)
    size = units * module
    offset = pad * module
    studio = scene["studio"]
    composition = studio["composition"]
    primary, accent = palette(subject, studio["family"])

    def tint(base, color, weight):
        return tuple(round(a + (b - a) * weight) for a, b in zip(base, color))

    if studio["form"] == "tentacles":
        primary, accent = composition["hue"], composition["accent"]
    elif studio["family"] == "instrument":
        accent = tint(primary, accent, .30)

    paper = tint((255, 255, 255), primary, .17)
    image = Image.new("RGB", (size, size), paper)
    draw = ImageDraw.Draw(image)
    # The brand art sits entirely outside the four-module white quiet zone.
    quiet = (pad - 4) * module
    draw.rectangle((quiet, quiet, size - quiet - 1, size - quiet - 1), fill=(255, 255, 255))
    outline = tint(paper, accent, .72)
    margin = module // 2
    draw.rounded_rectangle((margin, margin, size - margin - 1, size - margin - 1),
                           radius=2 * module, outline=outline, width=max(2, module // 5))

    if studio["form"] == "blue-bob":
        # Use the star on the hand-held sign in the margin, clear of the scan grid.
        for x, z, radius in ((2.6, 2.6, .87), (units - 2.6, units - 2.6, .72)):
            draw.polygon(star_points(x*module, z*module, radius*module), fill=tuple(accent))
        pixels = np.zeros((n, n, 4))
    else:
        mark = subject
        if studio["form"] == "tentacles":
            w, h = mark.size
            # Favor the character's head over the surrounding tentacles and reflection.
            mark = mark.crop((round(w * .19), round(h * .041), round(w * .80), round(h * .53)))
        alpha = mark.getchannel("A")
        content = alpha.point(lambda a: 255 if a > 40 else 0).getbbox()
        if alpha.getextrema() == (255, 255):
            gray = mark.convert("L")
            w, h = mark.size
            corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
            if all(gray.getpixel(point) >= 247 for point in corners):
                content = gray.point(lambda value: 255 if value < 239 else 0).getbbox()
        if studio["form"] == "horned":
            # Frame the illustrated head, leaving the desk or typography out of the badge.
            # The most saturated subject-color patch excludes neutral backgrounds and props.
            reference = np.asarray(mark)
            rgb = reference[:,:,:3].astype(float)
            color_patch = (np.linalg.norm(rgb - primary,axis=2) < 56) & (reference[:,:,3] > 180)
            rows, columns = np.nonzero(color_patch)
            if len(rows) > mark.width * mark.height * .018:
                w, h = mark.size
                l,r = np.percentile(columns,[32,90])
                t,b = np.percentile(rows,[4,55])
                content = (max(0,int(l-w*.14)), max(0,int(t-h*.12)),
                           min(w,int(r+w*.12)), min(h,int(b+h*.13)))
        if content:
            mark = mark.crop(content)
        if studio["family"] in ("sky", "lightbox", "dawn"):
            inset = quiet - module
            if mark.height > mark.width * 1.47:
                mark = ImageOps.contain(mark, (inset, quiet * 2), Image.Resampling.LANCZOS)
                x, y = (quiet - mark.width) // 2, (size - mark.height) // 2
            else:
                mark = ImageOps.contain(mark, (round(size * .58), inset), Image.Resampling.LANCZOS)
                x, y = (size - mark.width) // 2, (quiet - mark.height) // 2
        else:
            mark = ImageOps.contain(mark, (round(size * .41), quiet - 5 * module // 2),
                                   Image.Resampling.LANCZOS)
            x, y = module * 2, (quiet - mark.height) // 2
        badge_padding = module // 2
        # Transparent logos often include white wordmarks. Use a dark backing so they read.
        backing = (tint((16, 20, 34), accent, .24)
                   if mark.getchannel("A").getextrema()[0] < 200 else (255, 255, 255))
        draw.rounded_rectangle((x - badge_padding, y - badge_padding,
                                x + mark.width + badge_padding, y + mark.height + badge_padding),
                               radius=badge_padding, fill=backing)
        image.paste(mark, (x, y), mark.getchannel("A"))

        motif = ImageOps.contain(subject, (round(n*.93), round(n*.89)), Image.Resampling.LANCZOS)
        tile_motif = Image.new("RGBA", (n,n))
        tile_motif.alpha_composite(motif, ((n-motif.width)//2, (n-motif.height)//2))
        pixels = np.asarray(tile_motif).astype(float) / 255
    ink = tint((17, 18, 25), primary, .44)
    alternate = tint((16, 20, 32), accent, .43)
    for row, line in enumerate(cells):
        for col, dark in enumerate(line):
            red, green, blue, alpha = pixels[row, col]
            silhouette = alpha * (.40 + .60*(1-(red+green+blue)/3))
            wave = (.5 + .5 * math.sin((row - col) * .43)) * .56
            color = (tint(ink, alternate, min(1, silhouette * .48 + wave)) if dark else
                     tint((255, 255, 255), primary, silhouette * .16))
            x, y = offset + col * module, offset + row * module
            draw.rectangle((x,y,x+module-1,y+module-1), fill=color)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    png = buffer.getvalue()
    expected = base64.b64decode(scene["payloadBase64"])
    checks = {}
    for width in (size, 240, 320):
        gray = np.asarray(image.resize((width, width), Image.Resampling.LANCZOS).convert("L"))
        results = decode_zxing(gray)
        second = ("OpenCV" if read_opencv(gray) == expected else
                  "Apple Vision" if read_vision(gray) == expected else None)
        if len(results) != 1 or bytes(results[0].bytes) != expected or not second:
            raise ValueError(f"彩色艺术码未通过 {width} 像素双路读码。请检查原码和展示尺寸。")
        checks[str(width)] = ["ZXing-C++", second]

    return png, {"png": "art-qr.png", "matrixFraction": n / units, "checks": checks,
                 "sha256": hashlib.sha256(png).hexdigest(), "payload": scene["payload"]}
