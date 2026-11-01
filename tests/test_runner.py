import json
from PIL import Image
from aigui.runner import run


class Device:
    package_name = staticmethod(lambda p: p)
    launch = guard = tap = lambda *args: None
    def __init__(self, foreign=False, stale=False):
        self.phase, self.prompt, self.stale = 0, "", stale
    def text(self, text, package):
        self.prompt = text
    def screenshot(self, path):
        Image.new("RGB", (100, 300), "white").save(path)
    def dump(self):
        def n(text, rid, cls="TextView"):
            import html
            return f'<node text="{html.escape(text, quote=True)}" package="org.example.app" resource-id="{rid}" class="android.widget.{cls}" bounds="[1,1][90,40]" enabled="true" clickable="true"/>'
        self.phase += 1
        if self.phase == 1:
            return '<hierarchy>'+n("AI Assistant", "entry")+'</hierarchy>'
        answer = ""
        if self.phase > 3 and not self.stale:
            answer = "25 code " + self.prompt.split()[-1].rstrip(".")
        return '<hierarchy>'+n(self.prompt, "prompt", "EditText")+n("Send", "send", "Button")+n(answer, "answer")+'</hierarchy>'


CONFIG = {"package": "org.example.app", "fixture": True, "entry": "discover", "launch_wait": 0,
          "input": {"resource_id": "prompt"}, "submit": {"resource_id": "send"},
          "response": {"resource_id": "answer"}, "prompt": "Return 25 code {nonce}.",
          "expected_output": "25", "wait_seconds": 0.01}


def test_full_workflow_records_three_stages_and_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr("aigui.runner.time.sleep", lambda s: None)
    result = run(Device(), CONFIG, tmp_path/"run")
    assert result["new_output_verified"] and result["status"] == "fixture_workflow_passed"
    events = [json.loads(l) for l in (tmp_path/"run/events.jsonl").read_text().splitlines()]
    stages = {e.get("stage") for e in events}
    assert {"entry", "before_submit", "after_submit"} <= stages
    assert (tmp_path/"run/SHA256SUMS.json").is_file()


def test_stale_or_empty_output_is_failure_with_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("aigui.runner.time.sleep", lambda s: None)
    result = run(Device(stale=True), CONFIG, tmp_path/"fail")
    assert not result["new_output_verified"] and result["status"] == "output_not_established"
    assert (tmp_path/"fail/result.json").is_file()

