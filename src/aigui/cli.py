import argparse
import json
from pathlib import Path
from .device import Adb
from .evidence import Evidence, digest, write_json
from .observe import discover, markers
from .runner import run


def main():
    p = argparse.ArgumentParser(description="Android AI GUI research tools")
    p.add_argument("--adb", help="ADB executable; otherwise ADB/PATH/ANDROID_HOME")
    sub = p.add_subparsers(dest="command", required=True)
    for cmd in ["observe", "run"]:
        s = sub.add_parser(cmd)
        s.add_argument("--serial", required=True)
        s.add_argument("--out", type=Path, required=True, help="New output folder; never overwrite")
        s.add_argument("--ocr", action="store_true")
        s.add_argument("--ocr-engine", choices=["rapidocr", "tesseract"], default="rapidocr")
        s.add_argument("--ocr-language", default="eng")
        s.add_argument("--tesseract")
        if cmd == "observe":
            s.add_argument("--package", required=True)
        else:
            s.add_argument("--config", required=True, type=Path)
            s.add_argument("--record", action="store_true")
    s = sub.add_parser("replay", help="Offline analysis of selected historical captures; no ADB")
    s.add_argument("--case", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("verify", help="Verify file hashes of an evidence directory")
    s.add_argument("folder", type=Path)
    a = p.parse_args()
    if a.command == "verify":
        hashes = json.loads((a.folder/"SHA256SUMS.json").read_text(encoding="utf-8"))
        for name, value in hashes.items():
            path = (a.folder/name).resolve()
            if not path.is_relative_to(a.folder.resolve()) or digest(path) != value:
                raise SystemExit(f"Evidence hash mismatch: {name}")
        print(json.dumps({"verified_files": len(hashes)}))
        return
    if a.command == "replay":
        case = json.loads(a.case.read_text(encoding="utf-8"))
        a.out.mkdir(parents=True, exist_ok=False)
        results = []
        for capture in case["captures"]:
            nodes = json.loads((a.case.parent/capture["nodes"]).read_text(encoding="utf-8"))
            results.append({"stage": capture["stage"], "markers": markers(nodes, case["package"], capture["size"]),
                            "candidates": discover(nodes, case["package"], capture["size"])})
        result = {"mode": "offline_historical_capture_analysis", "case": case["name"],
                  "historical_outcome": case["historical_outcome"], "captures": results,
                  "new_live_run": False, "benchmark": False}
        write_json(a.out/"result.json", result)
    else:
        device = Adb(a.serial, a.adb)
        if a.command == "run":
            result = run(device, json.loads(a.config.read_text(encoding="utf-8")), a.out,
                         a.record, a.ocr, a.ocr_language, a.tesseract, a.ocr_engine)
        else:
            device.package_name(a.package)
            device.guard(a.package)
            evidence = Evidence(a.out, a.package, a.ocr, a.ocr_language, a.tesseract, a.ocr_engine)
            capture = evidence.capture(device, "observe")
            result = {"mode": "live_observation", "candidates": discover(capture["nodes"], a.package, capture["size"])}
            evidence.finish(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if a.command == "run" and not result["new_output_verified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
