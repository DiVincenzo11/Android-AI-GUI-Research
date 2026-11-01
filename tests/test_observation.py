import json
from pathlib import Path
import pytest
from aigui.observe import discover, markers, parse_xml, select, fresh_response
from aigui.device import Adb

PKG = "org.example.app"
SIZE = (1080, 2400)


def node(text="", **kwargs):
    return {"text": text, "package": PKG, "class": "android.widget.TextView", "enabled": True,
            "clickable": True, "bounds": [10, 10, 500, 100], "source": "native", **kwargs}


def test_xml_preserves_sources_and_password():
    n = parse_xml('<hierarchy><node text="AI Assistant" content-desc="Open" package="org.example.app" bounds="[1,2][30,40]" enabled="true" clickable="true" password="true"/></hierarchy>')[0]
    assert n["bounds"] == [1, 2, 30, 40] and n["password"] and n["source"] == "native"


def test_xml_rejects_entities():
    with pytest.raises(ValueError):
        parse_xml('<!DOCTYPE foo [<!ENTITY test "bad">]><hierarchy/>')


def test_discover_ignores_foreign_noninteractive_and_offscreen():
    n = [node("AI Assistant"), node("AI Assistant", package="foreign.app"),
         node("AI Assistant", clickable=False), node("AI Assistant", bounds=[-1, 0, 20, 20])]
    assert len(discover(n, PKG, SIZE)) == 1


def test_marker_categories_do_not_turn_warning_into_identity():
    n = [node("AI Meeting Assistant"), node("May make mistakes"), node("AI powered"),
         node("AI Assistant", **{"class": "android.widget.EditText"}), node("AI Assistant", password=True)]
    assert [x["category"] for x in markers(n, PKG, SIZE)] == [
        "explicit_ai_identity_text", "contextual_limitation_warning", "ai_keyword_only"]
    assert not markers(n, PKG, SIZE)[0]["pixel_confirmed"]


def test_selector_refuses_ambiguity_and_foreign_target():
    with pytest.raises(ValueError):
        select([node("Send"), node("Send")], {"text": "Send"}, PKG, SIZE)
    with pytest.raises(ValueError):
        select([node("Send", package="other.app")], {"text": "Send"}, PKG, SIZE)


def test_response_requires_new_non_prompt_selected_nonce():
    selector = {"resource_id": "answer"}
    prompt = "Return 25 code abc123"
    response = node("25 abc123", resource_id="answer")
    f = lambda before, after: fresh_response(before, after, selector, PKG, prompt, "abc123", "25", SIZE)
    assert f([], [response])
    assert not f([response], [response])
    assert not f([], [node(prompt, resource_id="answer")])
    assert not f([], [node("25 abc123", resource_id="answer", **{"class": "android.widget.EditText"})])
    assert not f([], [node("25", resource_id="answer")])
    assert not f([], [node("25 abc123", resource_id="wrong")])


def test_adb_shell_quotes_remote_metacharacters():
    adb = object.__new__(Adb)
    commands = []
    adb.run = lambda *args, **kw: commands.append(args)
    adb.shell("input", "text", "a;b")
    assert commands[0] == ("shell", "input text 'a;b'")


def test_text_input_rejects_shell_and_unicode():
    adb = object.__new__(Adb)
    adb.guard = lambda p: None
    adb.shell = lambda *args: None
    for bad in ["hello; rm", "$(echo bad)", "中文", "100%"]:
        with pytest.raises(ValueError):
            adb.text(bad, PKG)


def test_foreground_uses_full_window_dump():
    adb = object.__new__(Adb)
    def shell(*args):
        assert args == ("dumpsys", "window")
        return "mCurrentFocus=Window{123 u0 org.example.app/.MainActivity}"
    adb.shell = shell
    assert adb.foreground() == PKG


def test_discovery_does_not_promote_clickable_screen_container():
    xml = '<hierarchy><node package="org.example.app" clickable="true" enabled="true" bounds="[0,0][1080,2400]"><node text="AI models" package="org.example.app" clickable="false" enabled="true" bounds="[50,500][1000,560]"/></node></hierarchy>'
    assert discover(parse_xml(xml), PKG, SIZE) == []


def test_historical_cases_keep_failed_output_status():
    folder = Path(__file__).resolve().parents[1]/"examples"/"historical"
    assert len(list(folder.glob("*/case.json"))) == 3
    for file in folder.glob("*/case.json"):
        case = json.loads(file.read_text(encoding="utf-8"))
        assert case["historical_outcome"]["new_output_verified"] is False
        assert case["benchmark"] is False
        for capture in case["captures"]:
            assert (file.parent/capture["screenshot"]).is_file()

