"""Check rendered browser frames, supplied QR symbols and exact downloaded bytes."""

import base64
import hashlib
from datetime import datetime, timezone
import re
import subprocess
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from interaction_design import DESIGN_ITEMS, read_intake_prompt, read_workflow, validate_design
from prepare import build_scene, generate_qr, generate_text_qr, decode_zxing, open_image, read_opencv, read_original, read_vision


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha(path.read_bytes())


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verified_payload(image, expected):
    found = decode_zxing(image)
    assert len(found) == 1 and bytes(found[0].bytes) == expected, "ZXing payload mismatch"
    decoder = "OpenCV"
    if read_opencv(image) != expected:
        assert read_vision(image) == expected, "Independent decoder mismatch"
        decoder = "Apple Vision"
    return ["ZXing-C++", decoder]


def verify_chat_prompt(metadata):
    receipt = metadata["agent"]
    if "workflowSha256" not in receipt:
        assert receipt["promptSha256"] == file_sha(ROOT / ".work/scene-motion-parent/对话运行Prompt.md")
        return
    workflow, workflow_sha = read_workflow()
    review = metadata["interactionReview"]
    assert receipt["workflowSha256"] == review["workflowSha256"] == workflow_sha
    assert receipt["promptSha256"] == sha(read_intake_prompt(workflow).encode())
    assert review["status"] == "preview" and review["checks"] == list(DESIGN_ITEMS)
    assert validate_design(review["design"]) == review["design"]


def verify(key, case, batch):
    evidence_batch = os.environ.get("QR_EVIDENCE_BATCH") or batch
    evidence = ROOT / "evidence" / f"{evidence_batch}-{key}"
    browser = load(evidence / "browser.json")
    run = ROOT / "runs" / browser["run"]["id"]
    scene = load(run / "scene.json")
    n = case["n"]
    assert browser["source"] == case
    if batch == "agent-pilot":
        assert browser["run"]["title"] == case["title"]
        assert browser["run"]["placement"] == case["placement"]
        metadata = load(run / "input-output.json")
        assert metadata["id"] == browser["run"]["id"]
        assert metadata["placement"] == case["placement"]
    chat_receipt = {}
    if batch == "agent-chat":
        chat = load(evidence / "chat.json")
        metadata = load(run / "input-output.json")
        assert chat["message"] == case["message"]
        assert chat["uploads"] == [case[name] for name in ("subject", "qr") if name in case]
        assert chat["run"] == browser["run"] == dict(metadata, page=browser["run"]["page"])
        assert metadata["artScene"] == metadata["agent"]["scene"] == scene["artScene"] == case["artScene"]
        assert re.fullmatch(r"[0-9a-f-]{36}", metadata["agent"]["thread"])
        assert metadata["agent"]["messageSha256"] == [sha(case["message"].encode())]
        verify_chat_prompt(metadata)
        assert set(chat["links"]) == {"preview", "component", "backup", "guide"}
        assert set(chat["links"].values()) == {
            f"/runs/{run.name}/{name}" for name in ("site.html", "component.zip", metadata["original"], "README.md")
        }
        assert file_sha(evidence / "chat-backup") == file_sha(run / metadata["original"])
        assert file_sha(evidence / "chat-guide.md") == file_sha(run / "README.md")
        assert len({file_sha(evidence / name) for name in ("front.png", "side.png", "back.png")}) == 3
        if evidence_batch == "scene-motion":
            vertices, faces, palette, fragments = scene["mesh"]
            assert vertices and palette and len(faces) == len(fragments)
            assert len(set(fragments)) > n * n * .40
            assert min(fragments) >= 0 and max(fragments) < n * n
        chat_receipt = {"chat": {"thread": metadata["agent"]["thread"], "links": chat["links"],
                                 "scene": case["artScene"], "placement": metadata["placement"],
                                 "guideSha256": file_sha(evidence / "chat-guide.md")}}
    assert scene["n"] == n == browser["run"]["dimension"]
    assert scene["payload"] == case["payload"] == browser["run"]["payload"]
    payload = base64.b64decode(scene["payloadBase64"], validate=True)
    assert payload == case["payload"].encode("utf-8")
    if case.get("subject"):
        original_subject = ROOT / case["subject"]
        subject_bytes = original_subject.read_bytes()
        subject = open_image(subject_bytes)[0]
        assert file_sha(original_subject) == scene["subjectSha256"] == file_sha(run / browser["run"]["subject"])
    else:
        subject_bytes = subject = None
        assert scene["subjectSha256"] is None and browser["run"]["subject"] is None
    stored_qr = run / browser["run"]["original"]
    qr_bytes = stored_qr.read_bytes()
    assert file_sha(stored_qr) == scene["qrSha256"]
    expected_source = "url" if case.get("urlInput") else "text" if case.get("payloadText") else "image"
    assert browser["run"]["qrSource"] == expected_source
    if expected_source != "image":
        encode = generate_qr if expected_source == "url" else generate_text_qr
        _, regenerated, encoded_payload = encode(case["payload"])
        assert qr_bytes == regenerated and encoded_payload == payload
    else:
        assert file_sha(ROOT / case["qr"]) == scene["qrSha256"]
    source_image = open_image(qr_bytes)[0]
    preset = case.get("preset", "photo")
    assert browser["run"]["preset"] == preset
    assert browser["run"]["brief"] == case.get("brief", "")
    assert browser["run"].get("palette", "") == case.get("palette", "")
    wechat = case.get("purpose") == "wechat-follow"
    assert browser["run"].get("purpose") == case.get("purpose")
    current_scene, _, _ = build_scene(subject, source_image, subject_bytes, qr_bytes, preset=preset,
                                      brief=case.get("brief", ""), palette=case.get("palette", ""),
                                      effect=case.get("effectInput", ""), wechat=wechat,
                                      art_scene=case.get("artScene", ""))
    assert json.dumps(current_scene, sort_keys=True) == json.dumps(scene, sort_keys=True), (
        "generated scene differs from the current implementation")
    _, source_payload, sampled, _, _, source_checker, _ = read_original(source_image, allow_center_overlay=wechat)
    assert source_payload == payload
    white = Image.new("RGBA", source_image.size, "white")
    white.alpha_composite(source_image)
    detected = decode_zxing(np.asarray(white.convert("L")))[0]
    source_symbol = np.asarray(detected.to_image(with_quiet_zones=False)) != 0
    matrix = np.array(scene["matrix"], dtype=bool)
    assert matrix.shape == source_symbol.shape == (n, n)
    assert np.array_equal(source_symbol, sampled) and np.array_equal(sampled, matrix)

    tiles = scene["tiles"]
    assert len(tiles) == n * n
    assert {tile["source"]["id"] for tile in tiles} == set(range(n * n))
    assert {(tile["target"]["r"], tile["target"]["c"]) for tile in tiles} == {
        (r, c) for r in range(n) for c in range(n)
    }
    assert all(tile["target"]["dark"] == matrix[tile["target"]["r"], tile["target"]["c"]]
               for tile in tiles)
    movement = [((p["target"]["x"] - p["source"]["x"]) ** 2 +
                 (p["target"]["z"] - p["source"]["z"]) ** 2) ** .5 for p in tiles]
    assert np.count_nonzero(np.array(movement) > .04) > .25 * n * n
    assert min(p["source"]["d"] for p in tiles) > 0
    assert len({p["source"]["group"] for p in tiles}) > 1
    if preset == "planet":
        assert scene["style"] == "planet" and np.ptp([p["source"]["h"] for p in tiles]) > .80
        assert file_sha(evidence / "back.png") not in {
            file_sha(evidence / "side.png"), file_sha(evidence / "front.png")
        }

    default_ink = [29, 47, 78] if batch == "agent-chat" else [0, 0, 0]
    ink = case.get("inkRGB", default_ink)
    assert scene.get("ink", [0, 0, 0]) == ink
    if preset == "brick":
        assert scene["style"] == "brick" and scene["sampleGrid"] >= 22
        assert np.ptp([p["source"]["h"] for p in tiles]) > .40
        assert file_sha(evidence / "underside.png") not in {
            file_sha(evidence / "front.png"), file_sha(evidence / "side.png"), file_sha(evidence / "back.png")
        }
        verified_payload(cv2.imread(str(evidence / "embedded-flat-screen.png"), cv2.IMREAD_GRAYSCALE), payload)

    if case.get("gallery"):
        assert scene["solid"] and np.ptp([p["source"]["h"] for p in tiles]) > .12
        assert len({file_sha(evidence / name) for name in ("front.png", "side.png", "back.png")}) == 3
        assert browser["run"]["title"] == case["title"]
        verified_payload(cv2.imread(str(evidence / "embedded-flat-screen.png"), cv2.IMREAD_GRAYSCALE), payload)
    expected_cells = np.where(matrix[..., None], ink, 255).astype(np.uint8)
    accent_ink = case.get("accentInkRGB")
    assert scene.get("accentInk") == accent_ink
    assert scene.get("effect") == case.get("effect")
    if batch == "v8":
        assert browser["subjectEffectWithoutOrbit"]
        assert browser["run"].get("effectInput") == case.get("effectInput")
    if batch == "v9":
        parent = next(item for item in load(ROOT / "evidence/verification-v8.json")["cases"]
                      if item["key"] == "dji-logo")
        assert file_sha(stored_qr) == parent["originalQrSha256"]
        assert scene["subjectSha256"] == parent["subjectSha256"]
        assert file_sha(run / "flat.png") == parent["artifactSha256"]["flat.png"]
        assert scene["shape"] == "字标飞行灯阵" and browser["run"]["effectInput"] == case["effectInput"]
        assert file_sha(evidence / "front.png") != file_sha(ROOT / "evidence/v8-dji-logo/front.png")
    if batch == "v10":
        assert browser["run"]["effectInput"] == case["effectInput"]
        assert case["urlInput"] and subject_bytes is not None
        if key == "dji-logo-night-flight-color":
            parent = load(ROOT / "evidence/verification-v9.json")["cases"][0]
            previous = load(ROOT / "runs" / parent["run"] / "scene.json")
            assert file_sha(stored_qr) == parent["originalQrSha256"]
            assert scene["subjectSha256"] == parent["subjectSha256"]
            for attribute in ("matrix", "tiles", "theme", "pose", "flare", "effect", "shape"):
                assert scene[attribute] == previous[attribute], attribute
            assert file_sha(run / "flat.png") != parent["artifactSha256"]["flat.png"]
        else:
            assert browser["authoredEffect"] == case["effect"]
            assert scene["shape"] == {"file-stack": "立体标志与叠层文件台",
                                      "print-development": "拍立得相机"}[case["effect"]]
            if case["effect"] == "print-development":
                assert np.ptp([tile["source"]["h"] for tile in tiles]) > .35
    gradient = case.get("inkGradient", False)
    assert scene.get("inkGradient", False) == gradient
    if gradient:
        rows, columns = np.indices(matrix.shape)
        weight = np.clip((2*columns + rows - n*.60) / (n*1.82), 0, 1)
        cells = np.array(ink) + weight[..., None] * (np.array(accent_ink) - ink)
        expected_cells[matrix] = np.floor(cells[matrix] + .5)
        assert len(np.unique(expected_cells[matrix], axis=0)) > 24
    elif accent_ink:
        row, column = np.ogrid[:n, :n]
        expected_cells[matrix & (2 * column + row >= 2 * n)] = accent_ink
    finder_ink = case.get("finderInkRGB")
    assert scene.get("finderInk") == finder_ink
    if finder_ink:
        for row, column in ((0, 0), (0, n - 7), (n - 7, 0)):
            region = slice(row, row + 7), slice(column, column + 7)
            expected_cells[region][matrix[region]] = finder_ink
    frame = np.asarray(Image.open(evidence / "flat.png").convert("RGB"))
    height, width = frame.shape[:2]
    step = min(height, width) // (n + 8)
    x, y = (width - step * n) // 2, (height - step * n) // 2
    ideal = np.full(frame.shape, 255, np.uint8)
    ideal[y:y + step * n, x:x + step * n] = expected_cells.repeat(step, axis=0).repeat(step, axis=1)
    assert np.array_equal(frame, ideal), "browser canvas differs from source cells or quiet zone"
    margins = min(x, y, width - x - step * n, height - y - step * n) / step
    assert margins >= 4
    decoders = verified_payload(cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY), payload)
    exported_png = np.asarray(Image.open(run / "flat.png").convert("RGB"))
    width_module = exported_png.shape[0] // (n + 8)
    expected_export = np.pad(expected_cells, ((4, 4), (4, 4), (0, 0)), constant_values=255)
    expected_export = expected_export.repeat(width_module, axis=0).repeat(width_module, axis=1)
    assert np.array_equal(exported_png, expected_export)
    flat_decoders = verified_payload(cv2.cvtColor(exported_png, cv2.COLOR_RGB2GRAY), payload)
    wechat_receipt = {}
    if wechat:
        original_frame = evidence / "embedded-flat-screen.png"
        mobile_saved = evidence / f"mobile-saved-{browser['run']['original']}"
        assert browser["install"]["offlineIframeTapAndSaveOriginal"]
        assert file_sha(mobile_saved) == file_sha(stored_qr)
        wechat_receipt = {
            "wechatOriginal": {
                "uploadedOriginalDecoderNames": verified_payload(np.asarray(white.convert("L")), payload),
                "embeddedVisibleDecoderNames": verified_payload(cv2.imread(str(original_frame), cv2.IMREAD_GRAYSCALE), payload),
                "visibleFrameSha256": file_sha(original_frame),
                "mobileSavedOriginalSha256": file_sha(mobile_saved),
            },
        }
    elif batch == "agent-chat":
        embedded = evidence / "embedded-flat-screen.png"
        assert browser["install"]["offlineIframeRoundtrip"]
        chat_receipt["chat"]["embeddedDecoderNames"] = verified_payload(
            cv2.imread(str(embedded), cv2.IMREAD_GRAYSCALE), payload)
    extra_artifacts = ()
    artwork = {}
    if case.get("artwork"):
        from art_studio import ART_NAME, REPORT_NAME
        art = browser["run"]["artwork"]
        extra_artifacts = (ART_NAME, REPORT_NAME)
        report = load(run / REPORT_NAME)
        assert report["input_hashes"]["image"] == scene["subjectSha256"]
        assert scene["payload"] == report["expected"] and art["candidate"] == report["candidate"]
        assert (file_sha(evidence / "downloaded-art.png") == art["sha256"] ==
                file_sha(run / ART_NAME) == report["sha256"][ART_NAME])
        assert report["status"][ART_NAME]["native"] and not report["status"][ART_NAME]["foreign"]
        raster = Image.open(evidence / "downloaded-art.png").convert("RGBA")
        white = Image.new("RGBA", raster.size, "white")
        white.alpha_composite(raster)
        art_decoders = verified_payload(np.asarray(white.convert("L")), payload)
        assert art["decoders"] == art_decoders and file_sha(run / "flat.png") != art["sha256"]
        curl = subprocess.run(
            ["curl", "--noproxy", "*", "-fsSL", "--max-time", "20", "-o",
             str(ROOT / ".work" / "v11-landing.html"), "-w", "%{http_code}\n%{url_effective}", scene["payload"]],
            check=True, capture_output=True, text=True,
        )
        status, final = curl.stdout.splitlines()
        assert status == "200" and final == case.get("websiteFinal", case["payload"])
        source = (ROOT / ".work" / "v11-landing.html").read_text()
        match = re.search(r"<title>([^<]+)</title>", source)
        assert match and case["websiteTitle"] in match.group(1)
        artwork = dict(art, reportSha256=file_sha(run / REPORT_NAME), payload=scene["payload"],
                       themedDecoders=flat_decoders, studioEngines=report["engines"], home={
                           "status": int(status), "final": final, "title": match.group(1).strip(),
                           "checkedAt": datetime.now(timezone.utc).isoformat(), "error": None,
                       })
    if case.get("effect") == "crank-pixels":
        assert browser["authoredEffect"] == "crank-pixels" and scene["shape"] == "手摇像素掌机"
        assert abs(browser["crankAngles"]["held"] - browser["crankAngles"]["idle"]) > .6

    assert file_sha(evidence / "front.png") == file_sha(evidence / "restored.png")
    assert browser["flatHeldOnBlurLeaveAndHover"] and browser["flatDwellMs"] >= 1000
    assert browser["touch"] and browser["tabs"] >= 1
    assert browser["orbitDegrees"] > 360 and browser["singleClickAndHoverStay"]
    assert browser["canvasHashes"]["flat"] == file_sha(evidence / "flat.png")
    assert browser["canvasHashes"]["front"] == file_sha(evidence / "front.png")
    for direction in ("forward", "reverse"):
        proof = browser[direction]
        assert proof["observedIntermediateFrames"] >= 5
        assert len(proof["frames"]) == 3
        for capture in proof["frames"]:
            assert 0 < capture["progress"] < 1
            assert file_sha(evidence / capture["name"]) == capture["sha256"]
    assert sha((ROOT / "web/qr-blocks.js").read_bytes()) == file_sha(run / "qr-blocks.js")
    assert file_sha(ROOT / "web/qr-blocks.css") == file_sha(run / "qr-blocks.css")
    assert file_sha(ROOT / "web/page.css") == file_sha(run / "page.css")
    if case.get("newInputs"):
        assert all(browser["install"].values())
    archive_file = evidence / "component.zip"
    assert file_sha(archive_file) == file_sha(run / "component.zip")
    with ZipFile(archive_file) as archive:
        assert archive.testzip() is None
        assert {"site.html", "embed.html", "DesignQR-LICENSE.txt", "README.md", "qr-blocks.js",
                "qr-blocks.css", "scene.json", "flat.png", browser["run"]["original"]}.issubset(archive.namelist())
        assert all(sha(archive.read(name)) == file_sha(run / name) for name in archive.namelist())
        assert b"Permission is hereby granted" in archive.read("DesignQR-LICENSE.txt")
        assert b"iframe src=" in archive.read("README.md")
    return dict(key=key, run=browser["run"]["id"], page=browser["run"]["page"],
                dimension=n, matchingCells=n*n, cleanCanvasPixels=width*height, inkRGB=ink,
                quietZoneMinimumModules=margins, browserDecoderNames=decoders,
                sourceSecondDecoder=source_checker, payload=scene["payload"],
                payloadBase64=scene["payloadBase64"], appearance=scene["foreground"],
                observations={"frontEqualsRestored": True, "flatDwellMs": browser["flatDwellMs"],
                              "forwardFrames": browser["forward"]["observedIntermediateFrames"],
                              "reverseFrames": browser["reverse"]["observedIntermediateFrames"],
                              "desktopKeyboardAndMouse": True, "mobileTouchEmulation": True,
                              "heldPointerOrbitDegrees": browser["orbitDegrees"],
                              "offlineBundle": browser["install"]},
                subjectSha256=scene["subjectSha256"], originalQrSha256=scene["qrSha256"],
                artifactSha256={name:file_sha(run / name) for name in
                                ("site.html", "embed.html", "component.zip", "scene.json", "flat.png", "qr-blocks.js", *extra_artifacts)},
                inputOrigin=case.get("origin"), **chat_receipt, **wechat_receipt, **({"artwork": artwork,
                                                     "crankAngles": browser["crankAngles"]} if artwork else {}))


def verify_table(batch):
    evidence = ROOT / "evidence" / f"{batch}-case-table"
    table = load(evidence / "browser.json")
    if batch in ("v6", "v7", "v8", "v9", "v10", "v11"):
        cases = {item["key"]: item for item in load(ROOT / "evidence" / "case-catalog.json")}
        assert set(table["standalone"]) == cases.keys() and table["offlineArchive"]
    else:
        cases = {key: case for key, case in load(ROOT / "scripts" / "cases.json").items()
                 if case.get("gallery") and case.get("batch", "v4") <= batch}
    assert {item["key"] for item in table["observations"]} == cases.keys()
    decoded = []
    for item in table["observations"]:
        key = item["key"]
        expected = cases[key]["payload"]
        assert item["payload"] == expected and item["dragDegrees"] >= 360
        assert item["singleClickStays"] and item["doubleClickBothWays"] and item["pngDownloadMatches"]
        path = evidence / f"{key}-in-table.png"
        names = verified_payload(cv2.imread(str(path), cv2.IMREAD_GRAYSCALE), expected.encode("utf-8"))
        result = {"key": key, "run": item["run"], "payload": expected,
                  "decoders": names, "canvasSha256": file_sha(path)}
        if batch in ("v6", "v7", "v8", "v9", "v10", "v11"):
            assert item["run"] == cases[key]["run"]
            single = evidence / f"{key}-single-flat.png"
            result["standaloneDecoders"] = verified_payload(
                cv2.imread(str(single), cv2.IMREAD_GRAYSCALE), expected.encode("utf-8"))
            result["standaloneCanvasSha256"] = file_sha(single)
        decoded.append(result)
    (evidence / "decoded.json").write_text(json.dumps(decoded, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    print(f"Read back {len(decoded)} table previews")


def verify_hero(folder, evidence, sample):
    intake = load(evidence / f"{sample}-intake.json")
    metadata = load(folder / "input-output.json")
    scene = load(folder / "scene.json")
    browser = load(evidence / "browser.json")
    assert intake["http"] == 201 and intake["run"] == dict(metadata, page=intake["links"]["preview"])
    assert set(intake["links"]) == {"preview", "component", "art", "backup", "guide"}
    assert browser["opened"] == (folder / "site.html").resolve().as_uri()
    assert metadata["agent"]["messageSha256"] == [sha(intake["prompt"].encode())]
    verify_chat_prompt(metadata)
    original = metadata["original"]
    for name in ("art-qr.png", original, "README.md"):
        assert file_sha(folder / name) == file_sha(evidence / f"{sample}-{name}")
    with ZipFile(evidence / f"{sample}-qr-blocks-component.zip") as archive:
        for entry in archive.namelist():
            assert sha(archive.read(entry)) == file_sha(folder / entry)
    assert sha((folder / metadata["subject"]).read_bytes()) == file_sha(ROOT / intake["files"][0])
    if metadata["qrSource"] == "image":
        assert file_sha(folder / original) == file_sha(ROOT / intake["files"][1])
    expected = base64.b64decode(scene["payloadBase64"])
    assert expected.decode() == intake["run"]["payload"] == scene["payload"]
    scans = {}
    for file in [folder / name for name in ("art-qr.png", original, "flat.png")] + [
        evidence / name for name in ("desktop-scan.png", "mobile-scan.png")
    ]:
        gray = np.asarray(Image.open(file).convert("L"))
        scans[file.name] = {"decoders": verified_payload(gray, expected), "sha256": file_sha(file)}
    receipt = {"run": metadata["id"], "payload": scene["payload"], "scans": scans,
               "siteSha256": file_sha(folder / "site.html"), "workflowSha256": metadata["agent"]["workflowSha256"]}
    (evidence / "scan-verification.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"{sample} {metadata['id']}: {len(scans)} artifacts decoded")


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "hero":
        verify_hero(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4])
        return
    if len(sys.argv) > 2 and sys.argv[1] == "table":
        batch = sys.argv[2]
        assert batch in ("v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11")
        verify_table(batch)
        return
    batch = sys.argv[1] if len(sys.argv) > 1 else "v4"
    assert batch in ("v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "agent-pilot", "agent-chat")
    definitions = load(ROOT / "scripts" / "cases.json")
    records = [verify(key, case, batch) for key, case in definitions.items()
               if case.get("batch", "v4") == batch]
    if batch == "agent-chat":
        assert {r["key"] for r in records} == {"qidian-chat", "ssv-chat", "playdate-chat"}
        assert len({r["chat"]["thread"] for r in records}) == 3
        save_receipts(batch, records, {"cases": records})
        return
    if batch == "agent-pilot":
        assert {r["key"] for r in records} == {"qidian-wechat", "ssv-wechat", "playdate-setup"}
        rejection = load(ROOT / "evidence/agent-pilot-rejection.json")
        for key in ("strict", "malformed", "unrelated"):
            assert rejection[key]["response"] == 422 and rejection[key]["originalUploadDownloadMatches"]
        assert rejection["directUrlRejected"] == 422
        save_receipts(batch, records, {"cases": records, "rejections": rejection})
        return
    if batch in ("v6", "v7", "v8", "v9", "v10", "v11"):
        expected = {
            "v6": {"planet-colored", "nasa-colored", "sanrio-kitty-colored", "lego-minifig"},
            "v7": {"planet-art", "nasa-art", "hello-kitty-art", "lego-minifig-art", "image-palette-qa"},
            "v8": {"dji-logo", "dji-osmo-pocket-3", "hello-kitty-petals", "lego-minifig-bounce"},
            "v9": {"dji-logo-night-flight"},
            "v10": {"dji-logo-night-flight-color", "dropbox-file-stack", "polaroid-flip-print"},
            "v11": {"playdate-crank-pixels"},
        }
        assert {r["key"] for r in records} == expected[batch]
        save_receipts(batch, records, {"cases": records})
        return
    if batch == "v5":
        assert {r["key"] for r in records} == {"sanrio-retsuko", "sanrio-logo", "sanrio-kitty"}
        assert all(definitions[r["key"]]["preset"] == "volume" for r in records)
        assert len({r["subjectSha256"] for r in records}) == len(records)
        assert len({r["artifactSha256"]["scene.json"] for r in records}) == len(records)
        assert {r["payload"] for r in records} == {"https://corporate.sanrio.co.jp/en/index.html"}
        assert len({r["originalQrSha256"] for r in records}) == 1
        save_receipts(batch, records, {"cases": records})
        return
    new_cases = [record for record in records if definitions[record["key"]].get("newInputs")]
    assert len(new_cases) >= 2 and len({r["dimension"] for r in new_cases}) >= 2
    assert len({r["subjectSha256"] or r["appearance"] for r in new_cases}) == len(new_cases)
    assert len({r["originalQrSha256"] for r in new_cases}) == len(new_cases)
    assert set(record["key"] for record in records) >= {"wiki", "commons", "mask", "raw", "lego"}
    parent = load(ROOT / "evidence" / "v4-raw-parent-keyboard.json")
    assert parent["sourceSha256"] == file_sha(ROOT / "research/二维码双向延展/motion/coffee/preview.html")
    assert parent["Enter"] and parent["Space"] and not parent["historicalKeyboardReachedSameFlat"]
    rejection = load(ROOT / "evidence" / "v4-rejection.json")
    assert rejection["response"] == 422 and rejection["originalUploadDownloadMatches"]
    save_receipts(batch, records, {"cases": records, "legacyRawKeyboard": parent, "invalidInputFallback": rejection})


def save_receipts(batch, records, output):
    evidence_batch = os.environ.get("QR_EVIDENCE_BATCH") or batch
    file = ROOT / "evidence" / f"verification-{evidence_batch}.json"
    file.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for record in records:
        print(record["key"], record["run"], record["matchingCells"], *record["browserDecoderNames"])


if __name__ == "__main__":
    main()
