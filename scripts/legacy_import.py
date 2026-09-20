#!/usr/bin/env python3
"""Read-only historical JSONL importer. Records are never activated or reverified."""
import argparse
import json
from pathlib import Path


def read_history(path):
    records = []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip(): continue
        try: record = json.loads(line)
        except ValueError:
            records.append({'line': number, 'status': 'unavailable', 'error': 'invalid historical JSON'}); continue
        records.append({'line': number, 'status': 'historical_unverified', 'record': record})
    return {'schema': 'sips.historical-import.v1', 'source': str(Path(path).resolve()), 'records': records, 'writes': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('path')
    print(json.dumps(read_history(parser.parse_args().path), indent=2))
