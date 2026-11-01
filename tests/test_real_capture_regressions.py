"""Regression checks on actual captured UI, without ADB, OCR or model access."""
import json
from pathlib import Path
import pytest
from aigui.observe import fresh_response


@pytest.mark.parametrize('case',['pocketpal-05','chatterui-03','duckduckgo-05'])
def test_actual_assistant_response_passes_and_presubmit_state_does_not(case):
    root=Path(__file__).resolve().parents[1]/'artifacts/real-apps-v0.2.0/runs'/case
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    result=read(root/'result.json');config=read(root/'scenario.json')
    events=[json.loads(l) for l in (root/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    before=next(e for e in events if e.get('stage')=='before_submit')
    after=[e for e in events if e.get('stage')=='after_submit'][-1]
    # UI paths and sibling nodes.json refer to the same native observation.
    before_nodes=read((root/before['ui']).with_name('nodes.json'))
    after_nodes=read((root/after['ui']).with_name('nodes.json'))
    prompt=next(e['prompt'] for e in events if e['kind']=='input_started')
    check=lambda previous,current:fresh_response(previous,current,config['response'],result['package'],
                                               prompt,result['nonce'],config['expected_output'],after['size'])
    output=check(before_nodes,after_nodes)
    assert output and output['text']==result['output']['text']
    assert not check(before_nodes,before_nodes)
    assert not check(after_nodes,after_nodes)
    assert result['stable_polls_required']==2 and not result['fixture']
