"""Record an exact real-app entry tap without claiming a model response."""
import argparse,json,time
from pathlib import Path
from aigui.device import Adb
from aigui.evidence import Evidence,write_json
from aigui.observe import select


def main():
    p=argparse.ArgumentParser();p.add_argument('--adb');p.add_argument('--serial',required=True)
    p.add_argument('--ui-backend',choices=['shell','uiautomator2'],default='shell')
    p.add_argument('--package',required=True);p.add_argument('--entry',required=True,help='Exact selector JSON')
    p.add_argument('--out',required=True,type=Path);p.add_argument('--wait',type=float,default=8)
    p.add_argument('--ocr',action='store_true');p.add_argument('--record',action='store_true')
    a=p.parse_args()
    if not 0<=a.wait<=30:raise ValueError('wait must be 0..30 seconds')
    device=Adb(a.serial,a.adb,a.ui_backend);package=device.package_name(a.package);device.launch(package)
    evidence=Evidence(a.out,package,a.ocr);handle=None
    result={'package':package,'mode':'live_entry_probe','entry_mode':'explicit_selector','fixture':False,
            'input_verified':False,'new_output_verified':False,'status':'incomplete','benchmark':False}
    write_json(evidence.folder/'scenario.json',{'package':package,'entry':json.loads(a.entry),'wait_seconds':a.wait})
    try:
        if a.record:handle=device.record_start()
        capture=evidence.capture(device,'entry')
        target=select(capture['nodes'],json.loads(a.entry),package,capture['size'])
        device.tap(target['bounds'],package);evidence.event('tap_entry',bounds=target['bounds'])
        time.sleep(a.wait);device.guard(package)
        evidence.capture(device,'entered')
        result['status']='entry_opened_output_not_tested'
    except Exception as exc:
        result.update(status='blocked_or_failed',error=str(exc));evidence.event('failure',error=str(exc))
    finally:
        if handle:
            try:device.record_finish(handle,evidence.folder/'demo.mp4')
            except Exception as exc:result['recording_error']=str(exc)
        evidence.finish(result)
    print(json.dumps(result,ensure_ascii=True,indent=2))
    if result['status']=='blocked_or_failed':raise SystemExit(2)


if __name__=='__main__':main()
