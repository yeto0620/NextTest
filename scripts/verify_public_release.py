"""Read-only public-release gate.

Usage:
    python scripts/verify_public_release.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nexttest.public_release import audit_public_release  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only NextTest public release check")
    parser.add_argument("--check", action="store_true", required=True, help="run the fixed-root audit")
    args = parser.parse_args(argv)
    if not args.check:
        parser.error("--check is required")
    result = audit_public_release()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result.get("release_ready") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
