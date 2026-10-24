"""Self-contained interactive 3-D viewer (three.js) with live route finding."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("viewer_template.html")


def write_viewer(model: dict, out_path: str | Path):
    slim = {k: model[k] for k in ("meta", "timing", "floors", "connectors", "legs")}
    data = json.dumps(slim, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__MODEL__*/null", data)
    Path(out_path).write_text(html, encoding="utf-8")
