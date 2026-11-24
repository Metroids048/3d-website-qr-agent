"""Turn an image-derived description into a bounded, offline character mesh."""
import math

import numpy as np

from brand_scene import angles


IMAGE_FORM = "image-character"
STAGES = ("gallery", "companion", "sky", "dawn", "download", "lightbox")
PROFILE_ROWS = np.array([.12, .30, .50, .70, .88, .95])


def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def vector_schema(size, limit, minimum=None):
    return {"type": "array", "minItems": size, "maxItems": size,
            "items": {"type": "number", "minimum": -limit if minimum is None else minimum, "maximum": limit}}


PART_SCHEMA = object_schema({
    "name": {"type": "string"},
    "shape": {"enum": ["oval", "box", "sweep"]},
    "color": vector_schema(3, 255, 0),
    "center": vector_schema(3, 1),
    "size": vector_schema(3, 1, .003),
    "angle": vector_schema(3, 180),
    "path": {"type": "array", "maxItems": 10, "items": vector_schema(4, 1)},
    "motion": vector_schema(3, .18),
    "anchor": {"anyOf": [vector_schema(3, 1), {"type": "null"}]},
})
EYE_SCHEMA = object_schema({
    "support": {"type": "integer", "minimum": 0, "maximum": 47},
    "center": vector_schema(2, 1),
    "radius": vector_schema(2, .24, .008),
    "white": vector_schema(3, 255, 0),
    "pupil": vector_schema(3, 255, 0),
    "rim": {"anyOf": [vector_schema(3, 255, 0), {"type": "null"}]},
    "gaze": vector_schema(2, .58),
    "pupilRatio": {"type": "number", "minimum": .15, "maximum": .45},
})
CHARACTER_SCHEMA = {"anyOf": [object_schema({
    "stage": {"enum": list(STAGES)},
    "stance": {"enum": ["grounded", "floating"]},
    "mainColor": vector_schema(3, 255, 0),
    "accentColor": vector_schema(3, 255, 0),
    "parts": {"type": "array", "minItems": 5, "maxItems": 48, "items": PART_SCHEMA},
    "eyes": {"type": "array", "maxItems": 8, "items": EYE_SCHEMA},
    "view": vector_schema(2, .25),
}), {"type": "null"}]}


def rotation(angle):
    sx, sy, sz = np.sin(np.radians(angle))
    cx, cy, cz = np.cos(np.radians(angle))
    return (np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
            @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
            @ np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]))


def silhouette_profile(subject):
    alpha = np.asarray(subject.getchannel("A"))
    if np.mean(alpha < 24) < .08:
        return None
    rows, cols = np.nonzero(alpha >= 150)
    if rows.size < 64 or rows.max() - rows.min() < 24:
        return None
    height = rows.max() - rows.min() + 1
    middle = (int(cols.max()) + int(cols.min())) / 2
    profile = []
    for t in PROFILE_ROWS:
        xs = cols[np.abs((rows - rows.min()) / height - t) < .035]
        if len(xs) < 12:
            profile.append(None)
            continue
        profile.append((np.percentile(xs - middle, [2, 98]) / height).round(4).tolist())
    return profile


def fit_silhouette(points, profile):
    """Match the reference's width and center by height without flattening its depth."""
    height = np.ptp(points[:, 2])
    position = (points[:, 2] - points[:, 2].min()) / height
    middle = (points[:, 0].min() + points[:, 0].max()) / 2
    shifts, scales = [], []
    for row, bounds in zip(PROFILE_ROWS, profile):
        xs = points[np.abs(position - row) < .04, 0]
        if bounds is None or len(xs) < 12 or np.ptp(xs) < .03 * height:
            shifts.append(0.)
            scales.append(1.)
            continue
        left, right = bounds
        width = np.ptp(xs)
        scale = np.clip(height * (right - left) / width, .82, 1.2)
        shifts.append(np.clip(height * (left + right) / 2 - (xs.min() + width / 2 - middle) * scale,
                              -.085 * height, .085 * height))
        scales.append(scale)
    scale = np.interp(position, PROFILE_ROWS, scales)
    shift = np.interp(position, PROFILE_ROWS, shifts)
    points[:, 0] = middle + (points[:, 0] - middle) * scale + shift
    return scale


def eye_depth(part, x, z):
    origin = np.asarray(part["center"])
    axes = rotation(part["angle"]) / np.asarray(part["size"])
    ray = axes[1]
    delta = (np.array([x, origin[1], z]) - origin) @ axes
    a, b, c = ray @ ray, delta @ ray, delta @ delta - 1
    # Eyes may extend beyond the outline. Seat those at the nearby curved edge.
    return origin[1] + (-b + math.sqrt(max(.04 * a, b*b - a*c))) / a


def build_eye(mesh, parts, eye):
    source = eye["support"]
    if not 0 <= source < len(parts) or parts[source]["shape"] != "oval":
        raise ValueError("眼睛须附着在有效的椭球头部或身体上。")
    support = parts[source]
    x, z = eye["center"]
    rx, rz = eye["radius"]
    depth = min(rx, rz) * .37
    y = eye_depth(support, x, z)
    rim = eye["rim"]
    if rim is not None:
        mesh.oval((x, y - .25 * depth, z), (rx, depth, rz), rim)
    inset = .86 if rim is not None else 1.
    white_y = y + (.68 if rim is not None else -.10) * depth
    mesh.oval((x, white_y, z), (rx * inset, depth, rz * inset), eye["white"])
    gx, gz = eye["gaze"]
    pupil = eye["pupilRatio"]
    stretch = max(1., math.hypot(gx, gz) / (.88 - pupil))
    gx, gz = gx / stretch, gz / stretch
    pupil_y = white_y + depth * math.sqrt(1 - gx*gx - gz*gz)
    mesh.oval((x + gx * rx * inset, pupil_y, z + gz * rz * inset),
              (rx * inset * pupil, .30 * depth, rz * inset * pupil), eye["pupil"])
    return support


def sweep(mesh, path, color):
    if not 2 <= len(path) <= 10 or not np.isfinite(path).all():
        raise ValueError("弯曲部件需要 2 至 10 个有效截面。")
    points, radii = path[:, :3], path[:, 3]
    if (np.linalg.norm(np.diff(points, axis=0), axis=1).min() < .004
            or (radii < 0).any() or radii.max() <= .003):
        raise ValueError("弯曲部件的相邻截面必须分开，半径须为正或在端点收尖。")
    neighbors = np.vstack([2 * path[0] - path[1], path, 2 * path[-1] - path[-2]])
    sections = []
    for a, b, c, d in zip(neighbors, neighbors[1:], neighbors[2:], neighbors[3:]):
        for t in (0, .25, .5, .75):
            sections.append(.5 * (2 * b + (-a + c) * t + (2*a - 5*b + 4*c - d) * t**2
                                  + (-a + 3*b - 3*c + d) * t**3))
    sections = np.array([*sections, path[-1]])
    tangents = np.gradient(sections[:, :3], axis=0)
    rings = []
    for section, tangent in zip(sections, tangents):
        norm = np.linalg.norm(tangent)
        if norm < 1e-6:
            raise ValueError("弯曲部件的路径出现重叠截面。")
        tangent /= norm
        reference = [0, 1, 0] if abs(tangent[1]) < .89 else [0, 0, 1]
        u = np.cross(tangent, reference)
        u /= np.linalg.norm(u)
        v = np.cross(tangent, u)
        rings.append([section[:3] + max(0, section[3]) * (math.cos(t)*u + math.sin(t)*v)
                      for t in angles(16)])
    mesh.surface([np.repeat([points[0]], 16, axis=0), *rings,
                  np.repeat([points[-1]], 16, axis=0)], color)


def build_character(mesh, actions, recipe, subject):
    if not isinstance(recipe, dict) or recipe.get("stage") not in STAGES:
        raise ValueError("缺少根据本轮参考图生成的全身模型描述。")
    parts = recipe.get("parts", [])
    if not 5 <= len(parts) <= 48:
        raise ValueError("全身模型须包含 5 至 48 个结构部件。")
    moving = []
    for part in parts:
        start = len(mesh.vertices)
        center = np.array(part["center"], dtype=float)
        size = np.array(part["size"], dtype=float)
        color = np.rint(part["color"]).astype(int).tolist()
        angle = part["angle"]
        shape = part["shape"]
        if shape == "sweep":
            sweep(mesh, np.array(part["path"], dtype=float), color)
        elif shape == "box":
            mesh.shell(center, size, min(size[0], size[2]) * .07, color)
        elif shape == "oval":
            mesh.oval(center, size, color, steps=28, bands=18)
        else:
            raise ValueError("模型包含遇到未知形状的部件。")
        end = len(mesh.vertices)
        if shape != "sweep" and any(angle):
            mesh.vertices[start:end] = (center + (mesh.vertices[start:end] - center)
                                        @ rotation(angle).T).round(5).tolist()
        if any(part["motion"]):
            moving.append((start, end, np.array(part["motion"], dtype=float), part["anchor"]))
    for eye in recipe.get("eyes", []):
        start = len(mesh.vertices)
        support = build_eye(mesh, parts, eye)
        if any(support["motion"]):
            moving.append((start, len(mesh.vertices), np.array(support["motion"], dtype=float), None))
    points = np.array(mesh.vertices)
    low, high = points.min(axis=0), points.max(axis=0)
    extent = high - low
    if not np.isfinite(points).all() or extent.min() < .12 * extent.max() or not moving:
        raise ValueError("本轮生成没有形成有体积且可动的全身角色。")
    profile = silhouette_profile(subject) if "view" in recipe else None
    original = points.copy()
    local_scale = fit_silhouette(points, profile) if profile is not None else np.ones(len(points))
    low, high = points.min(axis=0), points.max(axis=0)
    extent = high - low
    scale = .89 / extent.max()
    mesh.vertices[:] = ((points - (low + high) / 2) * scale).round(5).tolist()
    for start, end, motion, anchor in moving:
        motion[0] *= np.mean(local_scale[start:end])
        if anchor is None:
            actions.append([start, end, *(motion * scale), 1])
            continue
        distances = np.linalg.norm(original[start:end] - anchor, axis=1)
        extent = distances.max()
        # Quantize the deformation so adjacent rings move together from the anchor.
        weights = np.round(distances / max(extent, .001) * 12) / 12
        ranges = np.flatnonzero(np.diff(weights, prepend=-1, append=-1))
        for first, last in zip(ranges, ranges[1:]):
            if weights[first]:
                actions.append([start + int(first), start + int(last), *(motion * scale * weights[first]), 1])
