"""Bounded app-specific workflow with package and fresh-output checks."""
import re
import time
import uuid

from .evidence import Evidence
from .observe import discover, fresh_response, select


def run(device, config, folder, record=False, ocr=False, ocr_language="eng", tesseract=None, ocr_engine="rapidocr"):
    package = device.package_name(config["package"])
    if not config.get("response") or not config.get("input") or not config.get("submit"):
        raise ValueError("Workflow requires input, submit and response selectors")
    prompt_template = config.get("prompt", "")
    if "{nonce}" not in prompt_template or not config.get("expected_output"):
        raise ValueError("Prompt must contain {nonce}; expected_output is required")
    wait = float(config.get("wait_seconds", 20))
    if not 0 < wait <= 120:
        raise ValueError("wait_seconds must be 0..120")
    nonce = uuid.uuid4().hex[:10]
    prompt = prompt_template.replace("{nonce}", nonce)
    evidence = Evidence(folder, package, ocr, ocr_language, tesseract, ocr_engine)
    result = {"package": package, "mode": "live_adb", "fixture": bool(config.get("fixture", False)),
              "nonce": nonce, "status": "incomplete", "input_verified": False,
              "new_output_verified": False, "ai_model_quality": "not_assessed",
              "legal_compliance": "not_assessed"}
    handle = None
    try:
        device.launch(package)
        time.sleep(float(config.get("launch_wait", 2)))
        device.guard(package)
        if record:
            handle = device.record_start()
        first = evidence.capture(device, "entry")
        if config.get("entry", "discover") == "discover":
            candidates = discover(first["nodes"], package, first["size"])
            evidence.event("entry_candidates", candidates=candidates)
            if not candidates or candidates[0]["score"] < 1 or (len(candidates)>1 and candidates[1]["score"] == candidates[0]["score"]):
                raise RuntimeError("No unique explicit AI entry; review or provide an exact entry selector")
            box = candidates[0]["bounds"]
        else:
            box = select(first["nodes"], config["entry"], package, first["size"])["bounds"]
        device.tap(box, package)
        evidence.event("tap_entry", bounds=box)
        time.sleep(0.5)
        entered = evidence.capture(device, "entered")
        field = select(entered["nodes"], config["input"], package, entered["size"])
        if ("EditText" not in field.get("class", "") or field.get("password")
                or field.get("text", "") not in {"", config.get("input_placeholder", "")}):
            raise RuntimeError("Input must be an empty non-password EditText")
        device.tap(field["bounds"], package)
        evidence.event("input_started", prompt=prompt)
        device.text(prompt, package)
        time.sleep(0.3)
        before = evidence.capture(device, "before_submit", [prompt])
        field = select(before["nodes"], config["input"], package, before["size"])
        if field.get("text", "").strip() != prompt:
            raise RuntimeError("Typed input does not match expected prompt")
        result["input_verified"] = True
        button = select(before["nodes"], config["submit"], package, before["size"])
        device.tap(button["bounds"], package)
        evidence.event("submit", bounds=button["bounds"])
        deadline = time.monotonic()+wait
        while time.monotonic() < deadline:
            time.sleep(0.7)
            device.guard(package)
            after = evidence.capture(device, "after_submit", [prompt])
            text = " ".join(n.get("text", "") for n in after["nodes"])
            if re.search(r"sign in or sign up to continue|login required|登录后继续", text, re.I):
                result["status"] = "login_barrier"
                break
            output = fresh_response(before["nodes"], after["nodes"], config["response"], package,
                                    prompt, nonce, config["expected_output"], after["size"])
            if output:
                result.update(status="fixture_workflow_passed" if result["fixture"] else "fresh_output_observed",
                              new_output_verified=True, output=output)
                break
        else:
            result["status"] = "output_not_established"
    except Exception as exc:
        result.update(status="blocked_or_failed", error=str(exc))
        evidence.event("failure", error=str(exc))
    finally:
        if handle:
            try:
                device.record_finish(handle, evidence.folder/"demo.mp4")
                evidence.event("recording_saved", path="demo.mp4")
            except Exception as exc:
                evidence.event("recording_failed", error=str(exc))
                result["recording_error"] = str(exc)
        evidence.finish(result)
    return result
