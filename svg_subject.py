"""Rasterize simple vector subjects while retaining the submitted SVG bytes."""
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

SVG = "{http://www.w3.org/2000/svg}"
GRAPHICS = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
            "defs", "linearGradient", "radialGradient", "stop", "clipPath", "mask", "title", "desc"}
RASTER = """
const sharp = require('sharp');
(async () => {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  process.stdout.write(await sharp(Buffer.concat(chunks), {limitInputPixels: 640 * 640}).png().toBuffer());
})().catch(error => { process.stderr.write(error.message); process.exitCode = 1; });
"""


def rasterize(raw):
    error = "请提供带 viewBox 的静态轮廓 SVG，或上传透明 PNG。"
    if len(raw) > 524288:
        raise ValueError(error)
    try:
        source = raw.decode("utf-8").lstrip("\ufeff")
        if re.search(r"<\s*!\s*(DOCTYPE|ENTITY)|<\?(?!xml\s)", source, re.I):
            raise ValueError(error)
        root = ET.fromstring(source)
        if root.tag not in (SVG + "svg", "svg"):
            raise ValueError(error)
        for element in root.iter():
            if element.tag.removeprefix(SVG) not in GRAPHICS:
                raise ValueError(error)
            for name, value in element.attrib.items():
                attr = name.rsplit("}", 1)[-1].lower()
                if attr.startswith("on") or attr in ("href", "style", "src", "base"):
                    raise ValueError(error)
                # Paint servers and masks may refer to local SVG IDs.
                if re.search(r"url\s*\(", re.sub(r"url\(#[\w.-]+\)", "", value, flags=re.I), re.I):
                    raise ValueError(error)
        _, _, width, height = map(float, re.split(r"[ ,]+", root.get("viewBox", "").strip()))
        if any(not math.isfinite(size) or size <= 0 for size in (width, height)):
            raise ValueError(error)
    except (UnicodeError, ET.ParseError, ValueError) as issue:
        raise ValueError(error) from issue

    for dimension, size in (("width", width), ("height", height)):
        root.set(dimension, str(max(1, round(640 * (size / max(width, height))))))
    ET.register_namespace("", SVG[1:-1])
    runner = os.environ.get("QR_SVG_NODE") or shutil.which("node")
    if not runner:
        raise ValueError("本机暂不能读取 SVG，请改用透明 PNG。")
    try:
        result = subprocess.run([runner, "-e", RASTER], cwd=Path(__file__).resolve().parent,
                                input=ET.tostring(root), capture_output=True, check=True, timeout=8)
    except (OSError, subprocess.SubprocessError) as issue:
        raise ValueError("SVG 无法渲染，请改用透明 PNG。") from issue
    return result.stdout
