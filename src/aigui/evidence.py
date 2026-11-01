from __future__ import annotations
import hashlib
import html
import json
from pathlib import Path
import time

from PIL import Image
from .observe import markers, ocr_nodes, parse_xml


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Evidence:
    def __init__(self, folder, package, ocr=False, ocr_language="eng", tesseract=None, ocr_engine="rapidocr"):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=False)
        self.package, self.ocr = package, ocr
        self.ocr_language, self.tesseract = ocr_language, tesseract
        self.ocr_engine = ocr_engine
        self.events = []

    def event(self, kind, **data):
        item = {"time_epoch": time.time(), "kind": kind, **data}
        self.events.append(item)
        with (self.folder/"events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False)+"\n")
        return item

    def capture(self, device, stage, excluded_texts=()):
        folder = self.folder/f"{len(self.events):03d}_{stage}"
        folder.mkdir()
        started = time.time()
        device.screenshot(folder/"screen.png")
        screenshot_time = time.time()
        xml = device.dump()
        xml_time = time.time()
        (folder/"ui.xml").write_text(xml, encoding="utf-8")
        nodes = parse_xml(xml)
        with Image.open(folder/"screen.png") as im:
            size = im.size
        ocr = ocr_nodes(folder/"screen.png", self.ocr_language, self.tesseract, self.ocr_engine) if self.ocr else []
        write_json(folder/"nodes.json", nodes)
        write_json(folder/"ocr.json", ocr)
        item = self.event("observation", stage=stage, capture_started=started,
                          screenshot_epoch=screenshot_time, ui_epoch=xml_time,
                          atomic_capture=False, screenshot=str((folder/"screen.png").relative_to(self.folder)).replace("\\", "/"),
                          ui_backend=getattr(device,"dump_backend","shell"),
                          ui_dump_attempts=getattr(device,"last_dump_attempts",1),
                          ui_dump_errors=getattr(device,"last_dump_errors",[]),
                          ui=str((folder/"ui.xml").relative_to(self.folder)).replace("\\", "/"),
                          size=list(size), ocr_status="completed" if self.ocr else "disabled",
                          ocr_engine=self.ocr_engine if self.ocr else None,
                          markers=markers(nodes+ocr, self.package, size, excluded_texts))
        return {"nodes": nodes, "size": size, "event": item}

    def finish(self, result):
        write_json(self.folder/"result.json", result)
        observations = [e for e in self.events if e["kind"] == "observation"]
        blocks = []
        for e in observations:
            blocks.append(f'<section><h2>{html.escape(e["stage"])}</h2><img width="270" src="{html.escape(e["screenshot"], quote=True)}">'
                          f'<pre>{html.escape(json.dumps(e["markers"], ensure_ascii=False, indent=2))}</pre></section>')
        (self.folder/"report.html").write_text('<!doctype html><meta charset="utf-8"><title>Android GUI evidence</title>'
            '<style>body{font:16px system-ui;max-width:1000px;margin:32px auto}pre{white-space:pre-wrap}section{border-top:1px solid #aaa;padding:16px}</style>'
            '<h1>Android GUI evidence</h1><p>Native text is not automatically pixel-confirmed. Captures are sequential; review screenshots. No legal compliance verdict.</p>'
            + '<pre>'+html.escape(json.dumps(result, ensure_ascii=False, indent=2))+'</pre>'+''.join(blocks), encoding="utf-8")
        hashes = {str(p.relative_to(self.folder)).replace("\\", "/"): digest(p)
                  for p in sorted(self.folder.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.json"}
        write_json(self.folder/"SHA256SUMS.json", hashes)
