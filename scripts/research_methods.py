#!/usr/bin/env python3
"""Read-only, bounded SIPS research methods. See references/research-methods.md."""
import argparse
import json
from pathlib import Path
from sips_runtime.methods import METHODS,analyze


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('method',choices=METHODS)
    p.add_argument('--request-file',required=True);args=p.parse_args()
    try: result=analyze(args.method,json.loads(Path(args.request_file).read_text()))
    except (ValueError,KeyError,TypeError,OSError) as exc: p.exit(2,str(exc)+'\n')
    print(json.dumps(result,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
