"""Loopback workbench for preparing and downloading a standalone QR component."""
import argparse
import base64
import binascii
import hashlib
import html
import json
import mimetypes
import re
import shutil
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image
from prepare import build_scene, generate_qr, generate_text_qr, open_image, MAX_FILE, PALETTES, EFFECT_OPTIONS

from showcase import IMAGE_PRESETS, PYTHON_SITE
from art_studio import ART_NAME, REPORT_NAME, studio_art
from hero_art import make_hero_art
from brand_scene import SCENES
from studio_scene import FORMS, LAYER_SLIDE
from image_character import IMAGE_FORM
from agent_chat import ModelUnavailable, reply_to, rotation_workflow
import rotate_align
from interaction_design import DESIGN_ITEMS, read_workflow, validate_design
from svg_subject import rasterize

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
RUNS = ROOT / "runs"
GALLERY_INPUTS = ROOT / "inputs" / "gallery"
ANDROID_CREDIT = (
    "The Android robot is reproduced or modified from work created and shared by Google "
    "and used according to terms described in the Creative Commons 3.0 Attribution License."
)
EVIDENCE = ROOT / "evidence"
ASSETS = ("qr-blocks.js", "qr-blocks.css", "DesignQR-LICENSE.txt", "page.css")
MAX_REQUEST = 2 * ((MAX_FILE + 2) // 3) * 4 + 32768
UPLOAD_PRESETS = ("photo", "nasa", "volume", "mascot", "bottle")


def check_approved_runtime():
    baseline = ROOT / "docs" / "官网交付基线.json"
    try:
        approved = json.loads(baseline.read_bytes())
        if not isinstance(approved, dict) or not approved:
            raise ValueError("Empty runtime baseline")
        for name, digest in approved.items():
            source = ROOT / name
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise ModelUnavailable(f"官网交付基线发生变化（{name}），请先核对项目版本。")
    except (OSError, ValueError) as error:
        raise ModelUnavailable("官网交付基线无法读取，请先核对项目版本。") from error


def as_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def read_upload(data, key):
    try:
        upload = data[key]
        encoded = upload["data"]
        if not isinstance(encoded, str) or len(encoded) > ((MAX_FILE + 2) // 3) * 4:
            raise ValueError()
        raw = base64.b64decode(encoded, validate=True)
    except (KeyError, TypeError, ValueError, binascii.Error) as error:
        label = "主体图" if key == "subject" else "二维码图"
        raise ValueError(f"请上传{label}，每张须小于 8 MiB。") from error
    name = str(upload.get("name", ""))[:180]
    if key == "subject" and name.lower().endswith(".svg"):
        image, _ = open_image(rasterize(raw))
        return name, raw, image, "svg"
    image, extension = open_image(raw)
    return name, raw, image, extension


def local_text(data, key, default, limit):
    return str(data.get(key, default)).strip()[:limit] or default


def page(title, prefix, body, scripts=""):
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{prefix}page.css"><link rel="stylesheet" href="{prefix}qr-blocks.css">
{scripts}</head><body>{body}</body></html>
"""


def link_to_payload(payload):
    try:
        address = urlsplit(payload)
        href = address.scheme.lower() in ("http", "https") and bool(address.netloc)
    except ValueError:
        href = False
    return f'<a class="secondary" href="{html.escape(payload)}" rel="noopener noreferrer">打开原码链接</a>' if href else ""


def component(scene, original, *, original_data_url=""):
    # Prevent user-controlled text inside the scene from closing the JSON script.
    packed = as_json(scene).replace("<", "\\u003c")
    context = " data-qr-wechat" if original_data_url else ""
    reception = scene.get("artScene") == "reception-desk"
    studio = scene.get("studio")
    composition = studio and studio.get("composition")
    orbit_attr = " data-qr-orbit" if composition else ""
    studio_controls = '<button type="button" hidden class="qr-desk-action" data-qr-pause>暂停动效</button>' if composition else ""
    stage_label = (
        "企点接待台。拖动或用方向键旋转，双击、Enter 或空格播放转场。"
        if reception else "拖动或用方向键旋转。双击、双点或按 Enter 或空格查看二维码。"
        if composition else "展开彩色艺术码。双击、Enter 或空格切换。"
        if studio else "展开二维码。双击、Enter 或空格切换。方向键查看立体。"
    )
    desk_controls = (
        '<button type="button" hidden class="qr-desk-action" data-qr-answer aria-pressed="false">按下接听</button>'
        '<button type="button" hidden class="qr-desk-action" data-qr-transition>看完整转场</button>'
        if reception else ""
    )
    original_view = (
        f'<span class="qr-blocks-original"><img src="{original}" alt="公众号原二维码"></span>'
        if original_data_url and not studio else ""
    )
    action = "微信扫码关注" if original_data_url else "显示二维码"
    # file:// iframe documents can navigate to a sibling image instead of downloading it.
    save = (
        f'<a class="qr-blocks-save" href="{original_data_url}" download="{original}">保存原二维码</a>'
        if original_data_url else ""
    )
    reception_attr = " data-qr-reception" if reception else " data-qr-studio" if studio else ""
    art_image = (f'<img class="qr-blocks-art" src="{ART_NAME}" alt="彩色艺术二维码" aria-hidden="true">'
                 if studio else "")
    resolution = 640 if studio else 832
    return f"""<div data-qr-blocks{context}{reception_attr}{orbit_attr} data-style="{scene.get("style", "relief")}">
<button type="button" hidden class="qr-blocks-stage" aria-label="{stage_label}">
  <canvas width="{resolution}" height="{resolution}" aria-hidden="true"></canvas>{art_image}{original_view}
</button>
<div class="qr-blocks-controls">
  <p class="qr-blocks-status" aria-live="polite">请使用下方原二维码。</p>
  {desk_controls}{studio_controls}
  <button type="button" hidden class="qr-blocks-switch" data-qr-switch>{action}</button>
  {save}
</div>
<div class="qr-blocks-backup"><img src="{original}" alt="备用原二维码"></div>
<script type="application/json">{packed}</script>
</div>"""


def save_run(data, *, agent=None, design=None, character=None):
    if agent is not None:
        check_approved_runtime()
    rotation = agent is not None and agent["scene"] == "rotate-align-v1"
    _, workflow_sha = rotation_workflow() if rotation else read_workflow()
    if agent is not None and agent["workflowSha256"] != workflow_sha:
        raise ValueError("互动规范已更新，请按当前规范重新生成设计。")
    review = {"workflowSha256": workflow_sha, "status": "preview",
              "checks": ["fixedGeometry", "drag90", "twoDecoders"] if rotation else list(DESIGN_ITEMS)}
    if design is not None:
        review["design"] = validate_design(design)
    preset = data.get("preset", "photo")
    if preset not in ("photo", "nasa", "planet", "brick", "minifig", "character", *IMAGE_PRESETS):
        raise ValueError("请选择工作台提供的主体造型。")
    purpose = data.get("purpose", "general")
    if purpose not in ("general", "wechat-follow"):
        raise ValueError("请选择工作台提供的用途。")
    wechat = purpose == "wechat-follow"
    if sum(key in data for key in ("url", "qr", "payloadText")) != 1:
        raise ValueError("请选择一种二维码来源。")
    if wechat:
        if "qr" not in data or preset not in UPLOAD_PRESETS:
            raise ValueError("公众号场景需要同时上传品牌图片和现用公众号原二维码。")
        if not isinstance(data.get("placement"), str) or not data["placement"].strip():
            raise ValueError("请填写官网页面地址或组件放置位置。")
    palette = data.get("palette", "")
    if not isinstance(palette, str) or (palette and palette not in PALETTES):
        raise ValueError("请选择工作台提供的二维码配色。")
    effect = data.get("effect", "")
    if not isinstance(effect, str) or (effect and effect not in EFFECT_OPTIONS):
        raise ValueError("请选择工作台提供的展示动效。")
    art_scene = data.get("artScene", "")
    if not isinstance(art_scene, str) or (art_scene and (art_scene not in SCENES or preset not in UPLOAD_PRESETS or effect)):
        raise ValueError("三维场景需要上传参考图，不能同时选择旧展示动效。")
    studio_form = data.get("studioForm", "")
    if (not isinstance(studio_form, str) or (studio_form and
            (studio_form not in FORMS or preset not in UPLOAD_PRESETS or art_scene or effect or palette))):
        raise ValueError("通用立体场景需要选择受支持的造型和一张参考图。")
    if studio_form == IMAGE_FORM and (agent is None or not isinstance(character, dict)):
        raise ValueError("请在对话入口上传全身参考图，由 Agent 生成模型。")
    reception = art_scene == "reception-desk"
    if reception and not wechat:
        raise ValueError("企点接待台需要上传公众号原二维码。")
    source = subject_name = subject_raw = subject = None
    brief = ""
    if preset == "logo-site":
        if data.get("url") != PYTHON_SITE:
            raise ValueError(f"当前官网标志样例请使用 {PYTHON_SITE}")
        subject_name = "python-logo-only.png"
        subject_raw = (GALLERY_INPUTS / subject_name).read_bytes()
        subject, subject_ext = open_image(subject_raw)
        source = "subject." + subject_ext
    elif preset in UPLOAD_PRESETS:
        subject_name, subject_raw, subject, subject_ext = read_upload(data, "subject")
        source = "subject." + subject_ext
    elif preset == "character":
        brief = local_text(data, "brief", "", 240)
    generated_payload = None
    if "url" in data:
        qr, qr_raw, generated_payload = generate_qr(data["url"])
        qr_name, qr_ext, qr_source = "generated-qr.png", "png", "url"
    elif "payloadText" in data:
        qr, qr_raw, generated_payload = generate_text_qr(data["payloadText"])
        qr_name, qr_ext, qr_source = "generated-qr.png", "png", "text"
    else:
        qr_name, qr_raw, qr, qr_ext = read_upload(data, "qr")
        qr_source = "image"
    title = local_text(data, "title", "官网扫码位", 70)
    placement = local_text(data, "placement", "原官网扫码入口", 180)
    if rotation:
        scene, flat = rotate_align.build(subject, qr, subject_raw, qr_raw)
        cutout = None
    else:
        scene, flat, cutout = build_scene(subject, qr, subject_raw, qr_raw, preset=preset,
                                          brief=brief, palette=palette, effect=effect, wechat=wechat, art_scene=art_scene,
                                          studio_form=studio_form, character=character)
    if wechat and not re.fullmatch(r"https?://weixin\.qq\.com/[qr]/[A-Za-z0-9_-]+", scene["payload"]):
        raise ValueError("请使用微信公众平台给出的公众号原二维码。")
    if generated_payload is not None and base64.b64decode(scene["payloadBase64"]) != generated_payload:
        raise ValueError("生成的二维码未能读回完整载荷，请检查输入。")
    artwork = data.get("artwork", False)
    if not isinstance(artwork, bool):
        raise ValueError("请选择是否同时生成 2D 艺术码。")
    if artwork and not source:
        raise ValueError("生成 2D 艺术码需要主体图，请选择支持图片的造型。")
    credits = ""
    if preset == "mascot" or studio_form in ("antenna", "ears"):
        sample = GALLERY_INPUTS / "android-head.png"
        if sample.is_file() and subject_raw == sample.read_bytes():
            credits = ANDROID_CREDIT
    elif preset == "logo-site":
        credits = "Python Logo © Python Software Foundation. 本地立体演示。"
    elif preset == "minifig":
        credits = "零件模型：LDraw.org Parts Library。作者及授权见组件内 minifigure-credit.txt。"
    key = uuid.uuid4().hex[:16]
    staging = RUNS / ("." + key)
    staging.mkdir()
    original = "original-qr." + qr_ext
    metadata = {
        "id": key, "title": title, "placement": placement, "subjectName": subject_name,
        "qrName": qr_name, "subject": source, "original": original, "dimension": scene["n"],
        "payload": scene["payload"], "shape": scene["shape"], "foreground": scene["foreground"],
        "qrSource": qr_source, "preset": preset, "brief": brief, "credits": credits,
        "interactionReview": review,
    }
    if studio_form:
        metadata["studio"] = scene["studio"]
    if character is not None:
        character_bytes = as_json(character).encode("utf-8")
        metadata["character"] = {
            "file": "character.json", "sha256": hashlib.sha256(character_bytes).hexdigest(),
            "subjectSha256": scene["subjectSha256"], "parts": len(character["parts"]),
        }
    if agent is not None:
        metadata["agent"] = agent
    if palette:
        metadata["palette"] = palette
    if wechat:
        metadata["purpose"] = purpose
    if art_scene:
        metadata["artScene"] = art_scene
    if effect:
        metadata["effectInput"] = effect
    try:
        if source:
            (staging / source).write_bytes(subject_raw)
        (staging / original).write_bytes(qr_raw)
        Image.fromarray(flat).save(staging / "flat.png")
        if studio_form:
            art, art_meta = make_hero_art(scene, subject)
            (staging / ART_NAME).write_bytes(art)
            (staging / REPORT_NAME).write_text(as_json(art_meta), encoding="utf-8")
            metadata["artwork"] = art_meta
            scene["heroArt"] = {"matrixFraction": art_meta["matrixFraction"]}
        elif artwork:
            art, report, art_meta = studio_art(subject_raw, subject_ext, qr_raw, qr_ext,
                                                scene["payload"], qr_source, title, placement)
            (staging / ART_NAME).write_bytes(art)
            (staging / REPORT_NAME).write_bytes(report)
            metadata["artwork"] = art_meta
        if character is not None:
            (staging / "character.json").write_bytes(character_bytes)
        if cutout is not None:
            cutout.save(staging / "foreground.png")
        (staging / "scene.json").write_text(as_json(scene), encoding="utf-8")
        if rotation:
            for name in rotate_align.ASSETS:
                shutil.copy2(WEB / name, staging / name)
            site, embed = rotate_align.pages(title, placement, as_json(scene), original, source,
                                             link_to_payload(scene["payload"]))
            (staging / "site.html").write_text(site, encoding="utf-8")
            (staging / "embed.html").write_text(embed, encoding="utf-8")
            (staging / "README.md").write_text(f"""# 拖拽对齐二维码组件

打开 site.html 试玩，向上拖至 90° 扫码，横拖环看。触屏可用单指。
相机到 90° 后，同一套固定方柱的顶面构成原码格位。页面需要支持 WebGPU 的浏览器。

将整个目录放在同一静态目录，再嵌入组件。建议给交互区域保留至少 340 像素宽度。

<iframe src="/qr/{key}/embed.html" title="可旋转二维码" width="420" height="520" style="border:0;max-width:100%"></iframe>

{original} 为独立备用码，浏览器无法运行立体预览时会显示它。
保存前实际拖到 90° 的画布截图为 verified-90.png，双软件结果和网页指纹见 rotate-scan.json。
scene.json 保留固定列位置顺序、高度、表面材质及载荷，input-output.json 对应本次收件。
渲染和拖拽机制沿用 Every QR Code 已验收路线。许可见 Every-QR-Code-LICENSE.txt。
""", encoding="utf-8")
            proof = rotate_align.verify_delivery(staging, scene)
            review["status"] = "verified-canvas"
            metadata["rotateAlign"] = {
                "version": scene["version"], "proof": "rotate-scan.json",
                "subjectSha256": scene["subjectSha256"], "originalSha256": scene["originalSha256"],
                "canvasSha256": proof["screenshotSha256"],
            }
        else:
            for name in ASSETS:
                shutil.copy2(WEB / name, staging / name)
            if preset == "minifig":
                shutil.copy2(GALLERY_INPUTS / "minifigure-credit.txt", staging / "minifigure-credit.txt")
            original_data_url = ""
            if wechat:
                mime = "image/png" if qr_ext == "png" else "image/jpeg"
                original_data_url = f"data:{mime};base64,{base64.b64encode(qr_raw).decode('ascii')}"
            widget = component(scene, original, original_data_url=original_data_url)
            script = '<script defer src="qr-blocks.js"></script>'
            theme = {"planet": " space-result", "brick": " brick-result"}.get(preset, "")
            source_label = {"url": "由输入网址生成", "text": "由输入文字生成", "image": "上传的原二维码"}[qr_source]
            flat_label = "归码网格 PNG" if wechat else "主题彩码 PNG"
            source_link = f'<a class="secondary" href="{source}" download>原始主体图</a>' if source else ""
            credit_note = f'<p class="caption">{html.escape(credits)}</p>' if credits else ""
            art_links = (
                f'<a class="secondary" href="{ART_NAME}" data-art-download download>2D 艺术码 PNG</a>'
                f'<a class="secondary" href="{REPORT_NAME}" download>艺术码读码记录</a>' if artwork or studio_form else ""
            )
            preview_note = ('<p class="caption" data-interaction-review>组件预览。首屏、静置、拖物件、环视、'
                            '单击和双击的实件验收状态见接入说明。</p>')
            normal = f'''<header class="site-bar"><a href="/" class="home">二维码工作台</a>
<span class="local-tag">本地接入示例</span></header>
<main class="shell result{theme}">
<section class="intro"><h1>{html.escape(title)}</h1>
<p class="lede">{html.escape(placement)}</p>{preview_note}</section>
<div class="comparison">
<section class="card scene-card" aria-label="互动预览">{widget}
<button type="button" class="secondary" data-qr-download-states>保存六态预览图</button></section>
<section class="card original-card"><h2>静态二维码</h2><p class="caption">{source_label}</p>
<div class="original-box"><img src="{original}" alt="原二维码"></div>
<p class="caption payload">{scene["n"]} × {scene["n"]} · {html.escape(scene["payload"])}</p>
{link_to_payload(scene["payload"])}</section></div>
<section class="downloads">
<h2>下载与接入</h2><p class="caption">{scene["shape"]} · {html.escape(scene["foreground"])}</p>
<div class="button-row"><a class="primary" href="component.zip" download>下载组件 ZIP</a>
<a class="secondary" href="embed.html">独立组件</a><a class="secondary" href="{original}" download>备用原码</a>
<a class="secondary" href="flat.png" download>{flat_label}</a>{art_links}{source_link}</div>{credit_note}
</section></main>'''
            if reception:
                normal = f'''<main class="reception-preview">
<div class="reception-gallery">
  <header class="reception-intro">
    <p class="reception-brand">腾讯企点</p>
    <h1>企点接待台</h1>
    <p class="reception-lede">拖动看侧面的导轨，按下铜色接听键，打开接待窗口。</p>
    {preview_note}
    <div class="reception-links"><a href="component.zip" download>嵌入组件</a>
    <a href="{original}" download>备用原码</a><a href="README.md">接入说明</a></div>
  </header>
  <section class="reception-stage" aria-label="接待台互动预览">{widget}</section>
</div></main>'''
            if studio_form:
                accent = ", ".join(map(str, scene["studio"]["composition"]["hue"]))
                safe_title = html.escape(title)
                destination = link_to_payload(scene["payload"]).replace("打开原码链接", "浏览品牌")
                portrait = f'<img src="{source}" alt="" width="36" height="36">' if source else ""
                site_copy = ("从立体形象探索品牌，扫码在手机上继续浏览。"
                             if not wechat else "扫描彩色二维码，把品牌带到微信。")
                normal = f"""<div class="brand-site" style="--brand-accent: {accent}">
<header class="brand-header">
<a class="brand-wordmark" href="#top">{portrait}<span>{safe_title}</span></a>
<nav aria-label="站点导航">{destination}<a href="#integration">组件接入</a></nav>
</header>
<main id="top">
<section class="brand-hero" aria-labelledby="brand-title">
  <div class="brand-intro"><h1 id="brand-title">{safe_title}</h1>
  <p>{site_copy}</p>
  <small>拖动查看立体细节，双击或双点打开艺术二维码</small></div>
  <div class="brand-scene" aria-label="{safe_title} 品牌场景">{widget}</div>
</section>
<section class="brand-resources" id="integration" aria-labelledby="integration-title">
  <h2 id="integration-title">组件接入</h2>
  <p>{html.escape(placement)}</p>
  <nav class="studio-links" aria-label="下载与接入">
    <a href="component.zip" download>嵌入组件</a><a href="embed.html">独立组件</a>
    <a href="{ART_NAME}" download>彩色艺术码</a><a href="{original}" download>备用码</a>
    <a href="README.md" download>接入说明</a>
  </nav>{credit_note}
</section></main></div>"""
            embed = f'<main class="embed-panel">{widget}{credit_note}</main>'
            (staging / "site.html").write_text(page(title, "", normal, script), encoding="utf-8")
            (staging / "embed.html").write_text(page(title, "", embed, script), encoding="utf-8")
            frame_title = "微信扫码关注" if wechat else "扫码打开链接"
            frame_height = 590 if reception or studio_form else (520 if wechat else 475)
            flat_note = (
                f"公众号模式在方块归位后显示 {original}，扫码、保存和降级均使用该上传原图。"
                "flat.png 是供方块动画使用的归码网格，中心徽标可能仅保留在上传原图中。"
                "手机点「微信扫码关注」查看原图，再点「保存原二维码」，或按浏览器提示打开图片保存。"
                "正式上线前请在实际页面用 iOS 和 Android 微信验证相机扫码、相册识别和账号名称。"
                if wechat else f"flat.png 是带四模块白边的原始 {scene['n']} × {scene['n']} 网格。"
            )
            opening_note = ("直接打开 site.html 可试玩接待台。拖动看侧面，点铜色键开启窗口。"
                            "「微信扫码关注」立即打开原码，「看完整转场」和双击播放归码。"
                            if reception else "直接打开 site.html 可在同页比较原扫码位与动画。")
            interaction_note = ("按住图案可旋转，双击切换立体和可扫二维码。"
                                "触屏可双点，键盘可用 Enter 或空格，也可用单独的切换按钮。")
            if studio_form:
                opening_note = "打开 site.html 即可查看嵌入官网首屏的自主循环表演。可暂停，系统减少动态效果模式以静帧开场。"
                interaction_note = ("用鼠标或单指拖动查看各个角度，松手后从所选角度继续播放。双击从当前视角归码，再双击回到该角度。"
                                    "触屏可双点或使用展开按钮。键盘用方向键旋转，用 Enter 或空格切换。"
                                    "art-qr.png 与组件的彩色终态一致，art-scan.json 记录读码。")
                flat_note = (f"备用文件 {original} 原样保存。flat.png 是动画网格。"
                             + ("公众号仍需在正式页面用 iOS 和 Android 微信验证相机扫码、相册识别与账号名称。"
                                if wechat else ""))
            if studio_form == LAYER_SLIDE:
                interaction_note = (
                    "进入视口时自动转侧，随原图结构露出厚薄有别的侧壁，再连贯回正。"
                    "拖动查看角度，双击从当前姿态用粒子聚成彩色艺术二维码。"
                    "再次双击，粒子回到触发时的姿态。触屏支持双点，方向键可旋转。")
            criteria = "、".join(DESIGN_ITEMS.values())
            planned = ""
            if "design" in review:
                planned = "\n本次设计方案\n\n" + "\n".join(
                    f"- {label}　{review['design'][key]}" for key, label in DESIGN_ITEMS.items()) + "\n"
            readme = f"""# 官网二维码组件

{opening_note}所有资源在当前目录，本地解压后可离线打开。
把当前目录放到官网的静态资源目录，将下面这一行放进原扫码位。也可以从 embed.html 复用组件标记并引用 qr-blocks.js 和 qr-blocks.css。

<iframe src="/qr/{key}/embed.html" title="{frame_title}" width="380" height="{frame_height}" style="border:0;width:100%;max-width:380px"></iframe>

若官网禁用 iframe，可在原位置继续使用 {original}。脚本或 Canvas 不可用时 embed.html 会显示该文件。
{flat_note}
scene.json 保留归码网格、载荷字节和每个方块的编号、起点与落点。
{interaction_note}
主体为基于输入参考图的立体创作。input-output.json 记录本次输入。作品及原图的使用权限由素材来源决定。
部分方块匹配思路源自 DesignQR City，见 DesignQR-LICENSE.txt。

## 互动设计验收

此版本为组件预览。交付前在同版实际嵌入件核对{criteria}。
{planned}
{credits}
"""
            (staging / "README.md").write_text(readme, encoding="utf-8")
        (staging / "input-output.json").write_text(as_json(metadata), encoding="utf-8")
        with ZipFile(staging / "component.zip", "w", compression=ZIP_DEFLATED) as archive:
            for file in sorted(staging.iterdir()):
                if file.name != "component.zip":
                    archive.write(file, file.name)
        staging.replace(RUNS / key)
    except BaseException:
        shutil.rmtree(staging)
        raise
    return {**metadata, "page": f"/runs/{key}/site.html"}


class WorkbenchServer(ThreadingHTTPServer):
    # Several gallery iframes can request assets at the same time.
    request_queue_size = 32


class Handler(BaseHTTPRequestHandler):
    def send_body(self, code, body, content_type, disposition=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, code, value):
        self.send_body(code, as_json(value).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = urlsplit(self.path).path
        file = None
        if path == "/":
            file = WEB / "index.html"
        elif path == "/agent":
            file = WEB / "agent.html"
        elif path == "/cases":
            file = EVIDENCE / "case-table.html"
        elif path in ("/demo", "/demo/lego"):
            demo = EVIDENCE / ("lego-demo.txt" if path == "/demo/lego" else "v2-demo.txt")
            if demo.is_file():
                key = demo.read_text(encoding="utf-8").strip()
                if re.fullmatch(r"[a-f0-9]{16}", key) and (RUNS / key / "site.html").is_file():
                    self.send_response(302)
                    self.send_header("Location", f"/runs/{key}/site.html")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
        elif path[1:] in (*ASSETS, "workbench.js", "gallery.css", "agent.js", "agent.css"):
            file = WEB / path[1:]
        elif re.fullmatch(r"/(?:cases/)?runs/[a-f0-9]{16}/[A-Za-z0-9.-]+", path):
            folder, basename = path.rsplit("/", 2)[-2:]
            if basename not in (".", ".."):
                file = RUNS / folder / basename
                if path.startswith("/cases/") and (RUNS / folder / "scene.json").is_file():
                    if basename == "qr-blocks.js":
                        file = WEB / basename
                    elif basename == "component.zip":
                        file = EVIDENCE / "case-components" / f"{folder}.zip"
        elif re.fullmatch(r"/evidence/(?:[a-z0-9-]+/)?[A-Za-z0-9.-]+", path):
            if all(part not in (".", "..") for part in path.split("/")):
                file = ROOT / path[1:]
        if file is None or not file.is_file():
            self.send_error(404)
            return
        kind = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if kind.startswith("text") or kind == "application/javascript":
            kind += "; charset=utf-8"
        disposition = None
        if file.suffix == ".zip":
            name = file.name if file.name != "component.zip" else "qr-blocks-component.zip"
            disposition = f'attachment; filename="{name}"'
        elif file.suffix == ".svg":
            disposition = f'attachment; filename="{file.name}"'
        self.send_body(200, file.read_bytes(), kind, disposition)

    def do_POST(self):
        if self.path not in ("/api/build", "/api/agent"):
            self.send_error(404)
            return
        # This is a loopback app. Reject webpage cross-origin submissions and non-JSON requests.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if (host != f"127.0.0.1:{self.server.server_port}" or
            (origin and origin != f"http://{host}")):
            self.send_json(403, {"error": "请从本地工作台生成组件。"})
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(415, {"error": "请在工作台提交。"})
            return
        try:
            count = int(self.headers.get("Content-Length", "0"))
            if not 0 < count <= MAX_REQUEST:
                raise ValueError("上传体积超限，每张图请使用 8 MiB 以内的文件。")
            data = json.loads(self.rfile.read(count))
            if not isinstance(data, dict):
                raise ValueError("请在工作台提交主体和二维码来源。")
            if self.path == "/api/agent":
                check_approved_runtime()
                result = reply_to(data, read_upload, save_run)
            else:
                result = save_run(data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "上传内容损坏，请重新选择图片。"})
        except ModelUnavailable as error:
            self.send_json(503, {"error": str(error)})
        except ValueError as error:
            self.send_json(422, {"error": str(error)})
        except Exception:
            import traceback
            traceback.print_exc()
            self.send_json(500, {"error": "本地处理异常，可先使用原二维码。"})
        else:
            self.send_json(200 if self.path == "/api/agent" and "run" not in result else 201, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    RUNS.mkdir(exist_ok=True)
    with WorkbenchServer(("127.0.0.1", args.port), Handler) as server:
        print(f"二维码工作台 http://127.0.0.1:{server.server_port}/", flush=True)
        server.serve_forever()
