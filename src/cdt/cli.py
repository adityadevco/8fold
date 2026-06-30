"""CLI entrypoint.

Usage:
    python -m cdt.cli --inputs sample_inputs/*.csv sample_inputs/*.json \
        --config configs/default.json --out output.json
"""
from __future__ import annotations

import argparse
import json
import sys

from cdt.pipeline import run_pipeline


def main(argv=None):
    parser = argparse.ArgumentParser(description="Multi-Source Candidate Data Transformer")
    parser.add_argument("--inputs", nargs="+", required=True, help="Paths to source files")
    parser.add_argument("--config", default=None, help="Path to a runtime output config JSON")
    parser.add_argument("--out", default=None, help="Write JSON output here (default: stdout)")
    args = parser.parse_args(argv)

    config = None
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            config = json.load(f)

    outputs = run_pipeline(args.inputs, config)
    text = json.dumps(outputs, indent=2)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Wrote {len(outputs)} candidate profile(s) to {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
