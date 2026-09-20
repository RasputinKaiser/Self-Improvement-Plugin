#!/usr/bin/env python3
"""Foreground runtime pilot and honest trial accounting; never launches a model.

Task definitions are public implementation fixtures. New hidden instances and
foreground authoring receipts are required for any transfer claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def run(protocol,source,output):
    protocol=Path(protocol);raw=protocol.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if protocol.with_suffix('.sha256').read_text().strip()!=digest: raise ValueError('sealed protocol drift')
    data=json.loads(raw);source=Path(source).resolve();results=[]
    tests=Path(__file__).resolve().parents[1]/'tests/test_pilot_runtime.py'
    environment={**os.environ,'SIPS_PILOT_SOURCE':str(source),'PYTHONDONTWRITEBYTECODE':'1'}
    for task in data['tasks']:
        argv=[sys.executable,'-m','pytest',str(tests),'-q','-k',task['root_cause'].replace('-','_')]
        start=time.monotonic();p=subprocess.run(argv,capture_output=True,text=True,env=environment,timeout=120)
        results.append({**task,'command':argv,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,
                        'duration_seconds':time.monotonic()-start,'runtime_status':'passed' if p.returncode==0 else 'unavailable' if p.returncode in (2,5) else 'failed'})
    report={'schema':'sips.pilot-runtime.v1','protocol':digest,'source':str(source),
            'results':results,'agent_effectiveness':'unmeasured','transfer':'unmeasured',
            'claim':'Public synthetic runtime checks; not independent adaptation trials',
            'model':None,'token_usage':None,'activation':'none'}
    Path(output).parent.mkdir(parents=True,exist_ok=True);Path(output).write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',required=True);p.add_argument('--source',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();r=run(a.protocol,a.source,a.out);print(json.dumps({'tasks':len(r['results']),'passed':sum(x['runtime_status']=='passed' for x in r['results']),'agent_effectiveness':'unmeasured'}))
