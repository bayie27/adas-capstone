"""Pull the document text out of a saved Drive tool-result file.

The paper is ~271k characters and `ADAS_Paper_Audit` ~90k, so reading either
through the Drive connector overflows the tool's output cap. The harness then
saves the whole response to a file and hands back the path instead. That file is
JSON, so it is not greppable as-is.

    uv run python paper_sync/extract_doc.py <saved-path> <output.txt>

Do this once per document per session, then grep and read the plain text.

Deliberately stdlib-only, and tolerant about shape: the point is to never lose a
turn re-deriving an extraction one-liner, so it accepts the wrappers seen in
practice and says plainly what it found when it cannot.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ordered by how likely each is to hold the document body.
TEXT_KEYS = ("fileContent", "content", "text", "body")


def extract(raw: str) -> str:
    """The document text inside a saved tool result, JSON-wrapped or not."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Already plain text — the harness saved a non-JSON response, or someone
        # has extracted this file once already. Passing it through is correct.
        return raw

    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in TEXT_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
        raise SystemExit(
            f"No document text found. Top-level keys were: {sorted(data)}\n"
            f"Add the right key to TEXT_KEYS in {Path(__file__).name}."
        )
    raise SystemExit(f"Unexpected JSON root: {type(data).__name__}")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print(
            "usage: extract_doc.py <saved-tool-result-path> <output.txt>",
            file=sys.stderr,
        )
        return 2

    source, target = Path(argv[1]), Path(argv[2])
    if not source.is_file():
        print(f"No such file: {source}", file=sys.stderr)
        return 1

    text = extract(source.read_text(encoding="utf-8", errors="replace"))
    target.write_text(text, encoding="utf-8")
    print(f"Wrote {target} ({len(text):,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
