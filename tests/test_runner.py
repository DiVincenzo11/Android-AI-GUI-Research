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


def test_already_open_and_optional_steps_still_require_verified_input(tmp_path, monkeypatch):
    monkeypatch.setattr("aigui.runner.time.sleep", lambda s: None)
    config=dict(CONFIG,entry="already_open",wait_seconds=1,
                entry_steps=[{"selector":{"resource_id":"not-on-this-screen"},"if_present":True}],stable_polls=2)
    class SubmittedDevice(Device):
        taps=0
        def tap(self,*args):self.taps+=1
        def dump(self):
            self.phase=2 if self.taps<2 else 10
            return super().dump()
    result=run(SubmittedDevice(),config,tmp_path/"open")
    assert result["input_verified"] and result["new_output_verified"]
    assert result["entry_mode"]=="already_open"
    events=[json.loads(x) for x in (tmp_path/"open/events.jsonl").read_text().splitlines()]
    assert any(e["kind"]=="entry_step_skipped" for e in events)


def test_optional_steps_do_not_hide_ambiguous_controls(tmp_path, monkeypatch):
    monkeypatch.setattr("aigui.runner.time.sleep",lambda s:None)
    from aigui.observe import select
    nodes=[{"package":"org.example.app","resource_id":"same","enabled":True,"bounds":[1,1,5,5]}]*2
    import pytest
    with pytest.raises(ValueError,match="observed 2"):
        select(nodes,{"resource_id":"same"},"org.example.app",(100,300),optional=True)

