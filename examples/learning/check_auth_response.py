"""Example property verifier; no real authentication or network access."""

import json
import sys
from pathlib import Path


def main() -> int:
    check = "authenticated-boolean-required"
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        valid = isinstance(data, dict) and data.get("authenticated") is True
    except (IndexError, OSError, ValueError):
        print(json.dumps({"check": check, "error": "Unreadable input or malformed JSON"}))
        return 2
    verdict = {"check": check, "valid": valid}
    if not valid:
        verdict["reason"] = "authenticated must be the boolean true"
    print(json.dumps(verdict))
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
