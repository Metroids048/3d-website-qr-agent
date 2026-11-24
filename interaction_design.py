"""Project-wide design criteria used by intake and the shared builder."""
import hashlib
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parent / "docs" / "通用3D交互规范.md"
DESIGN_ITEMS = {
    "opening": "官网首屏", "loop": "自主循环", "reveal": "双击归码",
    "art": "彩色艺术码", "value": "用途",
}


def read_workflow():
    raw = WORKFLOW.read_bytes()
    return raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()


def read_intake_prompt(workflow):
    return WORKFLOW.with_name("对话运行Prompt.md").read_text(encoding="utf-8") + "\n\n" + workflow


def validate_design(design):
    if (not isinstance(design, dict) or design.keys() != DESIGN_ITEMS.keys()
            or any(not isinstance(value, str) or not 1 <= len(value.strip()) <= 360
                   for value in design.values())):
        raise ValueError("互动设计需要包含官网首屏、自主循环、双击归码、彩色艺术码和用途。")
    return {key: design[key].strip() for key in DESIGN_ITEMS}
