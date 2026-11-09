"""D242 administration entrypoint; measured operations retain the v18 runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import stage17_state_journal_v53 as recovery
import stage17_operational_cli_v18 as predecessor


def main():
    recovery.activate()
    if len(sys.argv) < 2 or not sys.argv[1].startswith('d242-'):
        return predecessor.main()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('d242-check', 'd242-author', 'd242-commit'))
    parser.add_argument('--pilot-archive', type=Path, required=True)
    parser.add_argument('--pilot-sidecar', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'd242-check':
        result = recovery.original_validation(args.pilot_archive, args.pilot_sidecar)
        recovery.template(result.resolutions)
        output = dict(status='PASS', current_state=result.current_state,
                      resolutions=result.resolution_count, execution_authority=False)
    else:
        operation = recovery.author if args.command == 'd242-author' else recovery.commit
        output = operation(args.pilot_archive, args.pilot_sidecar)
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
