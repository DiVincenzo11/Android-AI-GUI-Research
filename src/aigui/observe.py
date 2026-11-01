"""UI-tree / optional OCR observations, with source and spatial provenance."""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import re
import xml.etree.ElementTree as ET

from PIL import Image


def parse_xml(xml: str) -> list[dict]:
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ValueError("DTD/entity input is not supported")
    start = xml.find("<?xml")
    if start < 0:
        start = xml.find("<hierarchy")
    if start < 0:
        raise ValueError("Missing UIAutomator hierarchy")
    root = ET.fromstring(xml[start:])
    out = []
    ancestors = {}
    def walk(element, parents):
        if element.tag == "node":
            ancestors[id(element)] = list(parents)
            parents = parents + [len(ancestors)-1]
        for child in element:
            walk(child, parents)
    walk(root, [])
    for i, node in enumerate(root.iter("node")):
        a = node.attrib
        bounds = [int(x) for x in re.findall(r"-?\d+", a.get("bounds", ""))]
        out.append({"index": i, "text": a.get("text", ""),
                    "description": a.get("content-desc", ""),
                    "resource_id": a.get("resource-id", ""), "class": a.get("class", ""),
                    "package": a.get("package", ""), "bounds": bounds,
                    "enabled": a.get("enabled") == "true", "clickable": a.get("clickable") == "true",
                    "password": a.get("password") == "true", "source": "native",
                    "ancestors": ancestors[id(node)]})
    return out


@lru_cache(maxsize=1)
def rapid_engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR(intra_op_num_threads=2, inter_op_num_threads=2)


def ocr_nodes(image_path, language="eng", executable=None, engine="rapidocr"):
    """Optional OCR line boxes; unavailable engines fail explicitly."""
    if engine == "rapidocr":
        result, _ = rapid_engine()(str(image_path))
        return [{"text": text, "bounds": [int(min(p[0] for p in points)), int(min(p[1] for p in points)),
                                          int(max(p[0] for p in points)), int(max(p[1] for p in points))],
                 "source": "ocr", "backend": "rapidocr_onnxruntime_1.4.4", "confidence": float(confidence), "package": ""}
                for points, text, confidence in (result or []) if confidence >= .5]
    if engine != "tesseract":
        raise ValueError("Unknown OCR engine")
    import pytesseract
    if executable:
        pytesseract.pytesseract.tesseract_cmd = str(executable)
    with Image.open(image_path) as im:
        data = pytesseract.image_to_data(im, lang=language, output_type=pytesseract.Output.DICT)
    lines = defaultdict(list)
    for i, t in enumerate(data["text"]):
        if t.strip() and float(data["conf"][i]) >= 40:
            lines[(data["block_num"][i], data["par_num"][i], data["line_num"][i])].append(i)
    out = []
    for indices in lines.values():
        x = min(data["left"][i] for i in indices)
        y = min(data["top"][i] for i in indices)
        x2 = max(data["left"][i] + data["width"][i] for i in indices)
        y2 = max(data["top"][i] + data["height"][i] for i in indices)
        out.append({"text": " ".join(data["text"][i] for i in indices),
                    "bounds": [x, y, x2, y2], "source": "ocr", "package": ""})
    return out


EXPLICIT = re.compile(r"\bAI\s+(?:(?:meeting|powered|chat|personal|virtual)\s+){0,2}(?:assistant|chatbot)|\bAI\s+models?\b|artificial intelligence|人工智能|AI助手", re.I)
AI_WORD = re.compile(r"\bAI\b|chatgpt|copilot|人工智能|智能助手", re.I)
WARNING = re.compile(r"(?:can|may) make mistakes|可能.*(?:错误|不准确)", re.I)
ENTRY = re.compile(r"\bAI\b|assistant|chatgpt|copilot|智能助手|问问AI", re.I)


def valid_box(bounds, size):
    return (len(bounds) == 4 and 0 <= bounds[0] < bounds[2] <= size[0]
            and 0 <= bounds[1] < bounds[3] <= size[1])


def contains(outer, inner):
    return (len(outer) == len(inner) == 4 and outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3])


def discover(nodes, package, size):
    """Conservative lexical candidate ranking. Not a semantic / icon classifier."""
    out = []
    for n in nodes:
        t = (n.get("text", "") + " " + n.get("description", "")).strip()
        if (n.get("source") == "ocr" or n.get("package") != package or not n.get("enabled")
                or not ENTRY.search(t) or not valid_box(n.get("bounds", []), size)):
            continue
        target = n if n.get("clickable") else next((p for p in reversed(nodes[:n.get("index", 0)])
            if p.get("clickable") and p.get("enabled") and p.get("package") == package
            and p.get("index") in n.get("ancestors", [])
            and contains(p.get("bounds", []), n["bounds"])
            and (p["bounds"][2]-p["bounds"][0])*(p["bounds"][3]-p["bounds"][1])
                <= 3*(n["bounds"][2]-n["bounds"][0])*(n["bounds"][3]-n["bounds"][1])), None)
        if target:
            out.append({"text": t, "bounds": target["bounds"], "resource_id": target.get("resource_id", ""),
                        "source": "native", "score": 1.0 if EXPLICIT.search(t) else 0.7,
                        "reason": "explicit_ai_phrase" if EXPLICIT.search(t) else "lexical_candidate",
                        "review_required": True})
    return sorted(out, key=lambda x: -x["score"])


def markers(nodes, package, size, excluded_texts=()):
    out = []
    excluded = {x.strip().casefold() for x in excluded_texts}
    for n in nodes:
        if n.get("source") != "ocr" and n.get("package") != package:
            continue
        t = (n.get("text", "") + " " + n.get("description", "")).strip()
        if (not t or t.casefold() in excluded or n.get("password")
                or "EditText" in n.get("class", "") or not valid_box(n.get("bounds", []), size)):
            continue
        category = ("explicit_ai_identity_text" if EXPLICIT.search(t) else
                    "contextual_limitation_warning" if WARNING.search(t) else
                    "ai_keyword_only" if AI_WORD.search(t) else None)
        if category:
            out.append({"text": t, "bounds": n["bounds"], "category": category,
                        "source": n.get("source", "native"), "review_required": True,
                        "pixel_confirmed": n.get("source") == "ocr"})
    return out


def select(nodes, selector, package, size, optional=False):
    if not selector or not set(selector).issubset({"resource_id", "text", "description", "class"}):
        raise ValueError("Selector must specify exact resource_id, text, description or class")
    hits = [n for n in nodes if n.get("package") == package and n.get("enabled")
            and valid_box(n.get("bounds", []), size)
            and all(n.get(k) == v for k, v in selector.items())]
    if not hits and optional:
        return None
    if len(hits) != 1:
        raise ValueError(f"Selector requires exactly one target; observed {len(hits)}")
    return hits[0]


def fresh_response(before, after, selector, package, prompt, nonce, expected, size):
    """Requires selected non-editable text absent before submit and carrying a fresh nonce."""
    if (not selector or not set(selector).issubset({"resource_id", "text", "description", "class", "ancestor", "role"})
            or not (set(selector)-{"ancestor", "role"})):
        raise ValueError("Response selector requires exact native fields; ancestor is optional")
    ancestor = selector.get("ancestor")
    if ancestor is not None and (not ancestor or not set(ancestor).issubset({"resource_id", "text", "description", "class"})):
        raise ValueError("Invalid response ancestor selector")
    role=selector.get("role")
    if role is not None and (not isinstance(role,dict) or set(role)!={"text","exclude_text"}
                             or not role["text"] or not role["exclude_text"] or role["text"]==role["exclude_text"]):
        raise ValueError("Role requires distinct exact text and exclude_text labels")
    fields = {k:v for k,v in selector.items() if k not in {"ancestor", "role"}}
    def matches(n, nodes):
        parent_matches = ancestor is None or any(
            p.get("index") in n.get("ancestors", []) and p.get("package")==package
            and all(p.get(k)==v for k,v in ancestor.items()) for p in nodes)
        role_matches = role is None or any(
            any(x.get("text")==role["text"] for x in nodes if i in x.get("ancestors",[]) and x.get("package")==package)
            and not any(x.get("text")==role["exclude_text"] for x in nodes if i in x.get("ancestors",[]) and x.get("package")==package)
            for i in n.get("ancestors",[]))
        return (parent_matches and role_matches and n.get("package") == package and all(n.get(k) == v for k, v in fields.items())
                and "EditText" not in n.get("class", "") and not n.get("password")
                and valid_box(n.get("bounds", []), size))
    prior = {n.get("text", "").strip() for n in before if matches(n, before)}
    normalized_prompt = " ".join(prompt.split()).casefold()
    for n in after:
        t = n.get("text", "").strip()
        if (matches(n, after) and t not in prior and normalized_prompt not in " ".join(t.split()).casefold()
                and nonce in t and expected in t):
            return {"text": t, "bounds": n["bounds"], "status": "fresh_selected_output_observed",
                    "semantic_correctness": "not_assessed", "review_required": True}
    return None
