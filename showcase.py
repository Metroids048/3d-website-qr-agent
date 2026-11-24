"""Geometry for uploaded silhouettes and the gallery's authored shapes."""

import json
import math
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

LOOKS = {
    "mascot": ("球面机器人", (16, 89, 57), (204, 245, 223), (-.39, .18), (139, 255, 218)),
    "logo-site": ("双层 Logo", (22, 69, 128), (238, 241, 250), (-.48, .25), (255, 224, 118)),
    "bottle": ("曲线回转瓶", (137, 34, 40), (250, 221, 218), (-.32, .15), (255, 178, 137)),
    "volume": ("按图片轮廓造型", (29, 47, 78), (237, 231, 248), (-.19, .095), (175, 213, 255)),
    "avatar": ("原创数字人", (25, 78, 91), (205, 227, 246), (-.29, .11), (172, 236, 255)),
    "fox": ("原创动漫狐狸", (117, 49, 30), (250, 227, 182), (-.34, .22), (255, 201, 101)),
    "minifig": ("经典人仔", (103, 30, 33), (250, 231, 163), (-.22, .10), (255, 224, 98)),
}
IMAGE_PRESETS = {"mascot", "logo-site", "bottle", "volume"}
PYTHON_SITE = "https://www.python.org/"


def character_style(brief):
    if any(word in brief for word in ("狐狸", "狐")):
        return "fox"
    if any(word in brief for word in ("数字人", "接待员")):
        return "avatar"
    raise ValueError("当前文字造型支持原创数字人和狐狸。请在描述中写明角色。")


def image_surface(kind, cutout, x, y, z):
    rgba = np.asarray(cutout)
    height, width = rgba.shape[:2]
    mask = rgba[:, :, 3] > 0
    ratio = .89 / max(width, height)
    px = np.clip(((x[:, 0, 0] / ratio) + width / 2).astype(int), 0, width - 1)
    pz = np.clip(((z[0, 0, :] / ratio) + height / 2).astype(int), 0, height - 1)
    if kind == "bottle":
        span = (np.max(np.where(mask, np.arange(width), 0), axis=1)
                - np.min(np.where(mask, np.arange(width), width), axis=1) + 1)
        radius = np.maximum(span[pz], 0)[None, None, :] * ratio / 2
        angle = np.arctan2(x, y)
        flutes = .003 * np.cos(12 * angle) * np.clip((z + .04) * 5, 0, 1)
        solid = (x*x + y*y <= (radius + flutes)**2) & (np.abs(z) < .445)
        color = rgba[pz, width // 2, :3][None, None, :, :].astype(float)
        highlights = 1 + .19 * np.sin(angle * 3 + .8) + .08 * np.cos(angle * 12)
        rgb = np.clip(color * highlights[..., None], 0, 255)
        return solid, np.broadcast_to(rgb, (*solid.shape, 3))

    silhouette = mask.T[np.ix_(px, pz)][:, None, :]
    silhouette &= (np.abs(x) < width * ratio / 2) & (np.abs(z) < height * ratio / 2)
    edge_depth = cv2.distanceTransform(np.pad(mask.astype(np.uint8), 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    edge_depth = edge_depth.T[np.ix_(px, pz)][:, None, :]
    if kind == "mascot":
        depth = .052 + .21 * np.sqrt(np.clip(edge_depth / (height * .21), 0, 1))
    elif kind == "volume":
        # Taper the outline and keep wide, thin artwork from hiding its own strokes.
        aspect = min(width, height) / max(width, height)
        depth = .035 + (.10 + .105 * aspect) * np.sqrt(np.clip(edge_depth * ratio / .135, 0, 1))
    else:
        depth = .072 + np.clip(edge_depth * ratio * .35, 0, .055)
    solid = silhouette & (np.abs(y) <= depth)
    rgb = rgba.transpose(1, 0, 2)[np.ix_(px, pz)][:, None, :, :3]
    return solid, np.broadcast_to(rgb, (*solid.shape, 3))


def character_surface(kind, x, y, z, brief):
    shape = (len(x), y.shape[1], z.shape[2])
    solid = np.zeros(shape, dtype=bool)
    color = np.zeros((*shape, 3), dtype=np.uint8)

    def paint(mask, rgb):
        mask = np.broadcast_to(mask, shape)
        solid[mask] = True
        color[mask] = rgb

    def oval(center, radius, rgb, tilt=0):
        cx, cy, cz = center
        rx, ry, rz = radius
        a, b = x - cx, z - cz
        u = a * math.cos(tilt) - b * math.sin(tilt)
        v = a * math.sin(tilt) + b * math.cos(tilt)
        paint((u / rx)**2 + ((y - cy) / ry)**2 + (v / rz)**2 <= 1, rgb)

    if kind == "avatar":
        skin, hair = (218, 159, 118), (38, 38, 55)
        suit = (58, 117, 206) if "蓝色" in brief else (38, 155, 155)
        oval((0, -.012, .226), (.325, .175, .234), suit)
        oval((0, .087, .244), (.106, .105, .203), (229, 238, 237))
        oval((0, 0, .035), (.088, .094, .129), skin)
        oval((0, -.04, -.211), (.183, .145, .195), hair)
        oval((0, .032, -.168), (.157, .133, .184), skin)
        oval((-.064, .053, -.293), (.128, .132, .083), hair, -.40)
        oval((.092, .057, -.297), (.079, .114, .063), hair, .38)
        for side in (-1, 1):
            oval((side*.155, .018, -.171), (.041, .053, .061), skin)
            oval((side*.169, -.006, -.193), (.049, .08, .074), (21, 74, 95))
            oval((side*.064, .152, -.183), (.027, .019, .02), (46, 34, 42))
        oval((0, .157, -.132), (.035, .035, .044), (231, 170, 125))
        oval((0, .143, -.079), (.05, .023, .013), (142, 69, 59))
        oval((-.166, .122, .211), (.035, .027, .04), (231, 194, 102))
    else:
        amber = (215, 74, 41) if "红色" in brief else (231, 112, 36)
        white, brown = (251, 228, 188), (105, 55, 43)
        oval((.235, -.053, .128), (.113, .113, .258), amber, .58)
        oval((.319, -.053, -.025), (.095, .105, .121), white, .58)
        oval((0, -.014, .239), (.166, .122, .187), amber)
        oval((0, .077, .251), (.108, .071, .131), white)
        for side in (-1, 1):
            a = (z + .449) / .252
            center = side * (.191 - .043*a)
            outer = (a > 0) & (a < 1) & (np.abs(x - center) < .017 + .104*a)
            paint(outer & (np.abs(y) < .072 + .025*a), amber)
            inner = (a > .21) & (a < .89) & (np.abs(x - center) < .004 + .065*(a-.18))
            paint(inner & (y > .063) & (y < .095), (240, 159, 153))
            oval((side*.078, .071, .382), (.061, .102, .05), brown)
        oval((0, .011, -.142), (.24, .149, .169), amber)
        for side in (-1, 1):
            oval((side*.115, .105, -.086), (.118, .083, .071), white, side*.33)
            oval((side*.098, .141, -.153), (.035, .032, .036), (43, 32, 39))
            oval((side*.100, .166, -.165), (.014, .015, .015), (255, 249, 221))
        oval((0, .167, -.078), (.072, .056, .050), white)
        oval((0, .211, -.089), (.042, .04, .031), (60, 39, 44))
        oval((0, .046, .044), (.167, .116, .05), (47, 139, 135))
        oval((.085, .127, .095), (.056, .044, .097), (47, 139, 135), -.52)
    return solid, color


@lru_cache(maxsize=1)
def minifigure_mesh():
    path = Path(__file__).resolve().parent / "inputs" / "gallery" / "minifigure-mesh.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def minifigure_samples():
    vertices, triangles, palette = minifigure_mesh()
    points = np.asarray(vertices)
    clouds, colors = [], []
    for a, b, c, color, _ in triangles:
        start, corner, end = points[[a, b, c]]
        length = max(np.linalg.norm(start - corner), np.linalg.norm(start - end),
                     np.linalg.norm(corner - end))
        divisions = max(2, math.ceil(length * 165))
        u, v = np.indices((divisions + 1, divisions + 1))
        keep = u + v <= divisions
        samples = start + (u[keep, None] * (corner - start)
                           + v[keep, None] * (end - start)) / divisions
        clouds.append(samples)
        colors.append(np.full(len(samples), color, dtype=np.uint8))
    return np.concatenate(clouds), np.concatenate(colors), np.asarray(palette)


def minifigure_surface(grid):
    samples, colors, palette = minifigure_samples()
    voxels = np.floor((samples + .5) * grid).astype(int)
    indexes = tuple(voxels.T)
    shape = (grid,) * 3
    solid = np.zeros(shape, dtype=bool)
    color = np.zeros((*shape, 3), dtype=np.uint8)
    solid[indexes] = True
    color[indexes] = palette[colors]
    # Preserve the printed grin and eyes when their thin surface shares a cell.
    printed = tuple(voxels[colors == 0].T)
    color[printed] = palette[0]
    return solid, color


def sculpture(kind, n, cutout, brief):
    budget = n*n
    candidate = None
    for grid in range(14, 85):
        coords = (np.arange(grid) - (grid - 1)/2) / grid
        x, y, z = np.ix_(coords, coords, coords)
        if kind in IMAGE_PRESETS:
            solid, color = image_surface(kind, cutout, x, y, z)
        elif kind == "minifig":
            solid, color = minifigure_surface(grid)
        else:
            solid, color = character_surface(kind, x, y, z, brief)
        interior = solid.copy()
        for axis in range(3):
            interior &= np.roll(solid, 1, axis) & np.roll(solid, -1, axis)
        exterior = np.argwhere(solid & ~interior)
        if len(exterior) > budget:
            break
        if len(exterior):
            candidate = grid, coords, solid, color, exterior, np.argwhere(interior)
    if candidate is None:
        raise ValueError("这张图在当前二维码格数下无法形成清晰体积，请换个轮廓或更长的扫码内容。")

    grid, coords, solid, color, exterior, interior = candidate
    indexes = np.concatenate((exterior, interior))[:budget]
    spare = budget - len(indexes)
    neighbors = ((0,-1,0), (0,1,0), (0,0,-1), (1,0,0), (0,0,1), (-1,0,0))
    occupied = np.zeros(solid.shape, dtype=bool)
    occupied[tuple(indexes.T)] = True
    padded = np.pad(occupied, 1)
    pieces = []
    for index, (i,j,k) in enumerate(indexes):
        x, y, z = (float(coords[t]) for t in (i,j,k))
        light = .91 + .09 * math.tanh((-x*.35 + y*.30 - z*.62) * 6)
        base = [round(channel*light) for channel in color[i,j,k]]
        layers = 1 + spare // len(indexes) + (index < spare % len(indexes))
        depth = 1/grid/layers
        hidden = sum(1 << side for side, (dx,dy,dz) in enumerate(neighbors)
                     if padded[i+dx+1,j+dy+1,k+dz+1])
        for layer in range(layers):
            faces = hidden | (1 if layer else 0) | (2 if layer < layers - 1 else 0)
            pieces.append(dict(id=len(pieces), x=x, z=z, h=y+(layer-(layers-1)/2)*depth,
                               w=1/grid, d=depth, hiddenFaces=faces, color=base,
                               group=f"{i//4}:{j//4}:{k//4}"))
    return pieces, grid
