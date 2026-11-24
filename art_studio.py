"""Bridge the workbench's optional second output to the local 2D Art QR workbench."""
import hashlib
from http.client import HTTPConnection, HTTPException
import json
import re
from uuid import uuid4

import numpy as np
from PIL import Image
from prepare import decode_zxing, open_image, read_opencv, read_vision

ART_NAME = "art-qr.png"
REPORT_NAME = "art-scan.json"


def studio_art(subject, subject_ext, qr, qr_ext, payload, qr_source, title, placement):
    if any(char in payload for char in "\r\n\0") or len(payload.encode("utf-8")) > 512:
        raise ValueError("2D 艺术码支持单行扫码内容，最多 512 字节。")
    fields = {"title": title[:60], "caption": placement[:85], "layout": "label",
              "frame": "full", "graphic": "mosaic", "width": "95", "height": "115"}
    uploads = {"image": (subject_ext, subject)}
    if qr_source == "url":
        fields["url"] = payload
    else:
        uploads["source_qr"] = (qr_ext, qr)
    boundary = uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8")
        for name, value in fields.items()
    ]
    for name, (ext, raw) in uploads.items():
        mime = "jpeg" if ext == "jpg" else "png"
        parts.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{name}.{ext}"\r\n'
                      f'Content-Type: image/{mime}\r\n\r\n'.encode(), raw, b"\r\n"))
    parts.append(f"--{boundary}--\r\n".encode())
    connection = HTTPConnection("127.0.0.1", 8788, timeout=120)

    def request(method, path, body=None, headers=None):
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.getheader("Location", ""), response.read()

    job = None
    try:
        status, location, _ = request("POST", "/jobs", b"".join(parts),
                                      {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        if status == 422:
            raise ValueError("2D 艺术码工作台未能接受该主体或原码，请检查主体图和扫码内容。")
        if status != 303 or not re.fullmatch(r"/jobs/[a-f0-9]{12}", location):
            raise ValueError("2D 艺术码工作台没有返回有效的任务。")
        job = location
        for candidate in ("rich", "clear"):
            status, _, _ = request("POST", f"{job}/select/{candidate}", b"")
            if status == 409:
                continue
            if status != 303:
                raise ValueError(f"2D 艺术码任务 {job.rsplit('/', 1)[-1]} 选稿失败。")
            base = f"{job}/asset/{candidate}"
            png_status, _, png = request("GET", f"{base}/{ART_NAME}?download=1")
            report_status, _, raw_report = request("GET", f"{base}/scan.json?download=1")
            if (png_status, report_status) != (200, 200):
                raise ValueError("2D 艺术码工作台未能返回已选文件与读码记录。")
            report = json.loads(raw_report)
            digest = hashlib.sha256(png).hexdigest()
            native = report["status"][ART_NAME]
            if (report["expected"] != payload or report["sha256"][ART_NAME] != digest
                    or report["candidate"] != candidate or not native["native"] or native["foreign"]
                    or report["input_hashes"]["image"] != hashlib.sha256(subject).hexdigest()
                    or ("source_qr" in uploads and
                        report["input_hashes"]["source_qr"] != hashlib.sha256(qr).hexdigest())):
                raise ValueError("2D 艺术码工作台回执与本次主体、载荷或导出文件不一致。")
            image = open_image(png)[0]
            paper = Image.new("RGBA", image.size, "white")
            paper.alpha_composite(image)
            gray = np.asarray(paper.convert("L"))
            reads = decode_zxing(gray)
            expected = payload.encode("utf-8")
            second = ("OpenCV" if read_opencv(gray) == expected else
                      "Apple Vision" if read_vision(gray) == expected else None)
            if len(reads) != 1 or bytes(reads[0].bytes) != expected or not second:
                continue
            return png, raw_report, {"job": job.rsplit("/", 1)[-1], "candidate": candidate,
                                      "png": ART_NAME, "report": REPORT_NAME, "sha256": digest,
                                      "decoders": ["ZXing-C++", second]}
        raise ValueError(f"2D 艺术码任务 {job.rsplit('/', 1)[-1]} 的候选未通过双码同载荷验证。")
    except (OSError, HTTPException, KeyError, TypeError, json.JSONDecodeError) as error:
        source = f"（2D 任务 {job.rsplit('/', 1)[-1]}）" if job else ""
        raise ValueError(f"2D 艺术码工作台暂时无法返回成品{source}。请确认本地 8788 服务可用。") from error
    finally:
        connection.close()
