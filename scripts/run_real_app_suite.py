"""Run prepared real-app adapters sequentially; retain failed attempts too.

Models/onboarding must be prepared manually using docs/REAL_APPS.md. This
script does not clear app data, log in, download models, or accept permissions.
"""
import argparse,json,re,time
from pathlib import Path
from aigui.device import Adb
from aigui.evidence import write_json
from aigui.runner import run


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--adb');p.add_argument('--serial',required=True)
    p.add_argument('--ui-backend',choices=['shell','uiautomator2'],default='shell')
    p.add_argument('--configs',nargs='+',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--ocr',action='store_true');p.add_argument('--record',action='store_true')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    device=Adb(a.serial,a.adb,a.ui_backend)
    metadata={'started_epoch':time.time(),'serial':a.serial,'android_api':device.shell('getprop','ro.build.version.sdk').strip(),
              'abi':device.shell('getprop','ro.product.cpu.abilist').strip(),'benchmark':False,'cases':[]}
    write_json(a.out/'suite.json',metadata)
    for number,path in enumerate(a.configs):
        config=json.loads(path.read_text(encoding='utf-8'));package=device.package_name(config['package'])
        if config.get('fixture',False):raise ValueError('Real-app suite does not accept fixture scenarios')
        version=device.shell('dumpsys','package',package)
        versions=[line.strip() for line in version.splitlines() if re.search(r'\bversion(?:Code|Name)=',line)]
        name=f'{number+1:02d}-{path.stem}'
        result=run(device,config,a.out/name,a.record,a.ocr)
        metadata['cases'].append({'case':name,'package':package,'versions':versions,'result':result})
        write_json(a.out/'suite.json',metadata)
    metadata['finished_epoch']=time.time();write_json(a.out/'suite.json',metadata)
    print(json.dumps(metadata,ensure_ascii=True,indent=2))
    if any(not c['result']['new_output_verified'] for c in metadata['cases']):raise SystemExit(2)


if __name__=='__main__':main()
