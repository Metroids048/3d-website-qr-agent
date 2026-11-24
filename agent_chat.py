"""Conversational intake for the existing local QR component builder."""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from image_character import silhouette_profile
from prepare import decode_zxing
from rotate_align import ROOT

WECHAT = re.compile(r"https?://weixin\.qq\.com/[qr]/[A-Za-z0-9_-]+")
URL = re.compile(r"""https?://[^\s，。；、）】〉“”"'<>]+""")
FIELDS = {"status": {"enum": ["build", "clarify"]}, **{
    key: {"type": "string"} for key in ("title", "placement", "destination", "reply")
}}
SCHEMA = {"type": "object", "properties": FIELDS, "required": list(FIELDS),
          "additionalProperties": False}


class ModelUnavailable(RuntimeError):
    pass


def interpret(turns, subject, has_qr, choices, workflow):
    runner = shutil.which("codex")
    if not runner:
        raise ModelUnavailable("本机缺少 Codex CLI，对话暂时无法处理。")
    prompt = (ROOT / "docs/旋转对齐对话Prompt.md").read_text(encoding="utf-8") + "\n\n" + workflow
    context = {"user_turns": turns, "user_provided_urls": choices,
               "original_qr_attached": has_qr, "subject_image_attached": subject is not None}
    with tempfile.TemporaryDirectory(prefix="website-qr-agent-") as scratch:
        work = Path(scratch)
        schema = work / "output-schema.json"
        schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
        last = work / "reply.json"
        args = [
            runner, "-a", "never", "exec", "--ephemeral", "--ignore-user-config",
            "--disable", "plugins", "--disable", "shell_tool", "--sandbox", "read-only",
            "--skip-git-repo-check", "-C", scratch, "-c", 'web_search="disabled"',
            "-c", 'model_reasoning_effort="low"', "-c", "project_doc_max_bytes=0",
            "--json", "--color", "never", "--output-schema", str(schema),
            "--output-last-message", str(last),
        ]
        if subject is not None:
            context["subject_silhouette"] = silhouette_profile(subject)
            scale = min(640 / max(subject.size), max(1., 352 / min(subject.size)))
            preview = subject.resize(tuple(max(1, round(side * scale)) for side in subject.size),
                                     Image.Resampling.LANCZOS)
            white = Image.new("RGBA", preview.size, "white")
            white.alpha_composite(preview)
            reference = work / "subject-preview.png"
            white.convert("RGB").save(reference)
            args.extend(["--image", str(reference)])
        try:
            completed = subprocess.run([*args, "-"], input=prompt + "\n\nCustomer material JSON:\n" + json.dumps(context, ensure_ascii=False),
                                       capture_output=True, text=True, timeout=240, check=True)
            events = [json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")]
            thread = next(event["thread_id"] for event in events if event.get("type") == "thread.started")
            result = json.loads(last.read_text(encoding="utf-8"))
        except (OSError, subprocess.SubprocessError, ValueError, StopIteration, KeyError) as error:
            print(f"QR Agent model turn failed: {type(error).__name__}", flush=True)
            raise ModelUnavailable("本轮未收到 Codex 的完整回复。附件和需求还在输入区，可稍后重发。") from error
    if (not isinstance(result, dict) or set(result) != set(FIELDS)
            or any(not isinstance(value, str) for value in result.values())
            or result["status"] not in FIELDS["status"]["enum"]):
        raise ModelUnavailable("本轮对话结果缺少必要字段。")
    return result, thread, hashlib.sha256(prompt.encode()).hexdigest()


def reply_to(data, read_upload, save_run):
    turns, uploads = data.get("messages"), data.get("uploads", [])
    if (not isinstance(turns, list) or not 1 <= len(turns) <= 8
            or any(not isinstance(text, str) or not text.strip() or len(text) > 2000 for text in turns)
            or not isinstance(uploads, list) or len(uploads) > 2):
        raise ValueError("每轮请写一条 2000 字以内的需求，并提交至多两张图片。二维码使用 PNG 或 JPEG。")
    subject = qr = reference = None
    for upload in uploads:
        _, _, picture, extension = read_upload({"subject": upload}, "subject")
        if extension == "svg":
            if subject is not None:
                return {"reply": "请提供一张主体参考图，以及一张单独的、可扫的备用二维码。"}
            subject, reference = upload, picture
            continue
        white = Image.new("RGBA", picture.size, "white")
        white.alpha_composite(picture)
        codes = decode_zxing(np.asarray(white.convert("L")))
        if len(codes) > 1 or (codes and qr) or (not codes and subject):
            return {"reply": "请提供一张主体参考图，以及一张单独的、可扫的备用二维码。"}
        if codes:
            qr = (upload, codes[0].text)
        else:
            subject, reference = upload, picture
    all_text = "\n".join(turns)
    choices = list(dict.fromkeys(URL.findall(all_text)))
    wechat = bool((qr and WECHAT.fullmatch(qr[1])) or re.search(r"公众号|微信扫码关注", all_text))
    if wechat and (not qr or not WECHAT.fullmatch(qr[1])):
        return {"reply": "请补发现用公众号原二维码的清晰图片。收到后会原样保留为备用码。"}
    if not qr and not choices:
        return {"reply": "请补发备用二维码，或把扫码后要打开的完整网址贴进对话。"}
    if subject is None:
        return {"reply": "请补发一张希望做成立体二维码的主体图。"}
    workflow, workflow_sha = rotation_workflow()
    result, thread, prompt_sha = interpret(turns, reference, bool(qr), choices, workflow)
    if result["status"] == "clarify" or not result["placement"].strip():
        return {"reply": result["reply"][:480] or "请补充组件放在官网的哪个位置。"}
    if not qr and result["destination"] not in choices:
        return {"reply": "请明确说明哪一个网址需要写进二维码。"}
    request = {
        "title": result["title"], "placement": result["placement"], "preset": "volume",
        "subject": subject, "purpose": "wechat-follow" if wechat else "general",
        **({"qr": qr[0]} if qr else {"url": result["destination"]}),
    }
    receipt = {
        "runtime": "Codex CLI", "thread": thread, "promptSha256": prompt_sha,
        "messageSha256": [hashlib.sha256(turn.encode()).hexdigest() for turn in turns],
        "scene": "rotate-align-v1", "workflowSha256": workflow_sha,
    }
    run = save_run(request, agent=receipt)
    base = f"/runs/{run['id']}/"
    return {
        "reply": f"「{run['title']}」已生成。向上拖动立体造型到 90° 可扫码，中途可停或回拖。"
                 + ("备用码保留你上传的原图。" if qr else "备用码使用你提供的目标网址。"),
        "run": run, "links": {"preview": run["page"], "component": base + "component.zip",
                              "backup": base + run["original"], "guide": base + "README.md"},
    }


def rotation_workflow():
    raw = (ROOT / "docs/旋转对齐二维码交付规范.md").read_bytes()
    return raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()
