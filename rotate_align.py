"""Build and verify the fixed terrain used by the shared component exporter."""
import base64
import hashlib
import html
import io
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image

from prepare import decode_zxing, foreground, read_original, read_vision

ROOT = Path(__file__).resolve().parent
ASSETS = ("rotate-align.js", "rotate-align.css", "Every-QR-Code-LICENSE.txt")
SSV_SOURCE = "75e9fbfc306ce491c8fcf1c557e1496f4094382ffccdb56800c07a18f101fd08"


def png_url(image):
    with io.BytesIO() as output:
        image.save(output, format="PNG")
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def ssv_terrain(x, z, matrix):
    # The three folds and mineral palette approved against this particular mark.
    ridges = (
        (.15, .30, .45, -.12, .16, .92),
        (.80, .22, -.09, .47, .15, 1.02),
        (.66, .83, -.42, -.27, .17, .86),
    )
    colors = np.array([[.14,.39,.78], [.83,.29,.22], [.23,.54,.34]])
    x, z = x + .5, z + .5
    edge = np.minimum.reduce((x, z, 1-x, 1-z))
    floor = (.045 + .075 * np.minimum(1, edge * 12) - .057 * np.exp(-22*((x-.5)**2+(z-.52)**2))
             + .018 * np.sin(18*x+7*z)*np.cos(18*z-4*x))
    peaks = []
    for ox, oz, dx, dz, width, height in ridges:
        u, v = x-ox, z-oz
        t = np.clip((u*dx + v*dz)/(dx*dx + dz*dz), 0, 1)
        taper = np.sin(np.pi*t)
        distance = np.hypot(u-t*dx, v-t*dz)
        peaks.append(height * np.maximum(0, 1-distance/(width*(.66+.34*taper)))**1.38 * (.42+.58*taper))
    which = np.argmax(peaks, axis=0)
    peak = np.max(peaks, axis=0)
    value = np.clip(np.round((floor + peak * np.where(matrix, 1, .65))*30)/30, 0, 1)
    blend = np.clip((value-.065)/.095, 0, 1)[...,None]
    neutral = np.array([.30,.53,.54])*(1-blend) + np.array([.74,.69,.57])*blend
    rock = np.where((peak < .11)[...,None], neutral, colors[which] * (.72 + .28 * value[...,None]))
    return (0.1+12.6*value**.72)*1.4/len(matrix), rock


def portrait_terrain(x, z, cutout):
    # A colored front relief uses the actual alpha silhouette; its crest and
    # stepped supports are the same full-footprint columns that carry QR cells.
    width, height = cutout.size
    view_width = min(.79, .64 * width / height)
    view_height = min(.67, view_width * height / width)
    alpha = np.asarray(cutout.getchannel("A"))
    source_x = np.clip(((x[0] / view_width + .5)*width).astype(int), 0, width-1)
    crest = np.zeros(x.shape[1])
    colors = np.ones((len(crest), 3)) * np.array([.57,.69,.72])
    rgb = np.asarray(cutout)[...,:3]
    half = max(1, int(width / (2*view_width*len(crest))))
    for column, px in enumerate(source_x):
        if abs(x[0,column]) > view_width/2 + .5/len(crest):
            continue
        region = slice(max(0, px-half), min(width, px+half+1))
        ys = np.where(np.any(alpha[:,region] > 180, axis=1))[0]
        if len(ys):
            crest[column] = .018 + view_height * (1 - ys[0] / height)
            colors[column] = np.median(rgb[:,region][alpha[:,region]>180],axis=0)/255
    ridge = round(len(crest)*.43)
    steps = np.clip(1 - (ridge - np.arange(len(crest))) / max(3, len(crest)*.19), 0, 1)
    steps[ridge+1:] = 0
    body = steps[:,None] * crest[None,:]
    painted = (np.arange(len(crest))[:,None] == ridge) * (body > .025)
    rock = np.where((body>.025)[...,None], colors[None,...]*.82, np.array([.48,.59,.61]))
    field = np.maximum(body, .010 + .006*(1-np.minimum(1,np.hypot(x,z)*1.8)))
    return field, rock, painted, view_width, view_height


def build(subject, qr, source_raw, qr_raw):
    text, payload, matrix, flat, _, source_check, matrix_check = read_original(qr, allow_center_overlay=True)
    n = len(matrix)
    source_sha = hashlib.sha256(source_raw).hexdigest()
    cutout, method = foreground(subject)
    z, x = np.mgrid[:n,:n] / n + .5/n - .5
    ssv = source_sha == SSV_SOURCE
    if ssv:
        height, rock = ssv_terrain(x, z, matrix)
        painted = np.zeros_like(matrix)
        cutout = Image.new("RGBA", (1, 1))
        width = portrait_height = 1
        method = "按经用户验收的红蓝绿折叶构建三条固定山脊"
    else:
        height, rock, painted, width, portrait_height = portrait_terrain(x, z, cutout)
        cutout.thumbnail((400, 400), Image.Resampling.LANCZOS)
        method += "，沿原画全轮廓构建固定台阶，颜色贴在构件朝前的侧壁"
    dark = np.array([.06,.075,.072])*.40 + rock*.60
    light = np.array([.99,.98,.95])*.8 + rock*.2
    top = np.where(matrix[...,None], dark, light)
    columns = np.column_stack((rock.reshape(-1,3), height.ravel(), top.reshape(-1,3), painted.ravel()))
    if (columns.shape != (n*n,8) or not np.all(np.isfinite(columns)) or height.min() <= 0
            or not np.array_equal(top @ np.array([.2126,.7152,.0722]) < .58, matrix)):
        raise ValueError("立体构件和码格未能一一对应。")
    scene = {
        "version": "rotate-align-v1", "n": n, "yaw": .7 if ssv else .10,
        "center": .10 if ssv else .23, "portraitWidth": width, "portraitHeight": portrait_height,
        "columns": np.round(columns, 5).ravel().tolist(), "texture": png_url(cutout),
        "subjectSha256": source_sha, "originalSha256": hashlib.sha256(qr_raw).hexdigest(),
        "payload": text, "payloadBase64": base64.b64encode(payload).decode("ascii"),
        "shape": "三色折叶山脊" if ssv else "原图侧壁浮雕", "foreground": method,
        "sourceDecoder": source_check, "matrixDecoder": matrix_check,
    }
    return scene, flat


def pages(title, placement, scene_json, original, source, destination):
    packed = scene_json.replace("<", "\\u003c")
    widget = f"""<section data-rotate-terrain data-state="loading" aria-label="可旋转立体二维码">
<canvas tabindex="0" aria-label="拖拽或用方向键旋转的立体二维码"></canvas>
<div class="terrain-controls">
<label>视角 <input type="range" min="15" max="90" value="32"><output>32°</output></label>
<button type="button" data-pan aria-pressed="false">平移</button><button type="button" data-reset>复位</button>
</div>
<p class="terrain-note">向上拖到 90° 扫码，横拖环看。触屏用单指拖动。</p>
<p role="status"></p>
<div class="terrain-fallback"><a href="{original}" download><img src="{original}" alt="下载备用二维码"></a></div>
<script type="application/json">{packed}</script></section>"""
    heading = f"""<header><h1>{html.escape(title)}</h1></header><p>{html.escape(placement)}</p>"""
    links = f"""<nav class="links" aria-label="下载与接入"><a href="component.zip" download>组件 ZIP</a>
<a href="embed.html">独立组件</a><a href="{source}" download>原始主体图</a>
<a href="{original}" download>备用码</a><a href="README.md" download>接入说明</a>
{destination}</nav>"""
    head = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><link href="rotate-align.css" rel="stylesheet"><script defer src="rotate-align.js"></script>"""
    return head + f"<body><main>{heading}{widget}{links}</main></body></html>", head + f'<body class="embed"><main>{widget}</main></body></html>'


def verify_delivery(staging, scene):
    dependency_root = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
    node = shutil.which("node") or dependency_root / "bin/node"
    environment = dict(os.environ)
    environment.setdefault("NODE_PATH", str(dependency_root / "node_modules"))
    screenshot = staging / "verified-90.png"
    try:
        output = subprocess.run(
            [str(node), str(ROOT / "scripts/rotate-align-browser.cjs"), "--save", str(staging / "site.html"), str(screenshot)],
            capture_output=True, text=True, timeout=35, check=True, env=environment,
        )
        proof = json.loads(output.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Rotate-align preview verification failed: {getattr(error, 'stderr', None) or error}", flush=True)
        raise ValueError("未能验证该组件的 90° 立体画布，本次未出件。") from error
    gray = np.asarray(Image.open(screenshot).convert("L"))
    expected = base64.b64decode(scene["payloadBase64"])
    if [bytes(code.bytes) for code in decode_zxing(gray)] != [expected] or read_vision(gray) != expected:
        raise ValueError("拖至 90° 的同版立体画布未通过两个解码器，本次未出件。")
    proof.update({
        "decoders": ["ZXing-C++", "Apple Vision"], "payloadBase64": scene["payloadBase64"],
        "screenshotSha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
        "pageSha256": hashlib.sha256((staging / "site.html").read_bytes()).hexdigest(),
        "rendererSha256": hashlib.sha256((staging / "rotate-align.js").read_bytes()).hexdigest(),
    })
    (staging / "rotate-scan.json").write_text(json.dumps(proof, ensure_ascii=False), encoding="utf-8")
    return proof
