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


def test_response_ancestor_rejects_user_bubble_and_wrapped_prompt_echo():
    parents=[node("",resource_id="assistant",index=0),node("",resource_id="user",index=1)]
    selector={"class":"android.widget.TextView","ancestor":{"resource_id":"assistant"}}
    prompt="Return 25 code abc123"
    answer=node("25 abc123",index=2,ancestors=[0],**{"class":"android.widget.TextView"})
    user=node("25 abc123",index=3,ancestors=[1],**{"class":"android.widget.TextView"})
    echo=node("You: Return 25 code abc123",index=4,ancestors=[0],**{"class":"android.widget.TextView"})
    check=lambda ns:fresh_response([],parents+ns,selector,PKG,prompt,"abc123","25",SIZE)
    assert check([answer])
    assert not check([user])
    assert not check([echo])


def test_launch_uses_resolved_activity_without_random_monkey_input():
    adb=object.__new__(Adb);calls=[]
    adb.foreground=lambda:"other.app"
    def shell(*args):
        calls.append(args)
        return PKG+"/.MainActivity" if args[0]=="cmd" else "Status: ok"
    adb.shell=shell
    adb.launch(PKG)
    assert calls[-1]==("am","start","-W","-n",PKG+"/.MainActivity")
    assert not any(c[0]=="monkey" for c in calls)
    calls.clear();adb.foreground=lambda:PKG;adb.launch(PKG)
    assert not calls


def test_role_selector_excludes_user_even_under_shared_chat_container():
    nodes=[node("",index=0),node("",index=1,ancestors=[0]),node("",index=2,ancestors=[0]),
           node("AI Bot",index=3,ancestors=[0,1]),node("User",index=4,ancestors=[0,2]),
           node("25 abc123",index=5,ancestors=[0,1],**{"class":"android.widget.TextView"}),
           node("25 abc123",index=6,ancestors=[0,2],**{"class":"android.widget.TextView"})]
    selector={"class":"android.widget.TextView","role":{"text":"AI Bot","exclude_text":"User"}}
    assert fresh_response([],nodes,selector,PKG,"Return code abc123","abc123","25",SIZE)
    assert not fresh_response([],nodes[:5]+[nodes[6]],selector,PKG,"Return code abc123","abc123","25",SIZE)


def test_dump_retries_transient_missing_hierarchy_and_cleans_remote_file(monkeypatch):
    import subprocess
    monkeypatch.setattr("aigui.device.time.sleep",lambda s:None)
    adb=object.__new__(Adb);count=0;commands=[]
    def shell(*args):
        nonlocal count
        commands.append(args)
        if args[0]=="uiautomator":count+=1;return "ERROR: null root node returned" if count==1 else "UI hierarchy dumped"
        if args[0]=="cat":
            if count==1:raise subprocess.CalledProcessError(1,args)
            return '<hierarchy/>'
        return ''
    adb.shell=shell
    assert adb.dump()=='<hierarchy/>' and adb.last_dump_attempts==2
    assert adb.last_dump_errors==["ERROR: null root node returned"]
    assert commands[-1][0:2]==("rm","-f")

