"""Compare the registry with an explicitly selected tool reference document."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Compare registry names with a caller-provided public-safe reference."""

    parser = argparse.ArgumentParser(description="Compare ModelDesk MCP tool names with a reference document.")
    parser.add_argument(
        "--reference",
        type=Path,
        default=os.environ.get("MODELDESK_MCP_TOOL_REFERENCE"),
        help="Markdown reference containing backtick-quoted modeldesk_ tool names.",
    )
    args = parser.parse_args(argv)
    reference = Path(args.reference).expanduser() if args.reference else None
    if reference is None:
        print("ERROR: provide --reference or MODELDESK_MCP_TOOL_REFERENCE.")
        return 2
    if not reference.is_file():
        print("ERROR: the selected reference document does not exist.")
        return 2

    root = Path(__file__).resolve().parent
    registry = root / "src" / "modeldesk_mcp" / "tools" / "registry.py"
    reg_text = registry.read_text(encoding="utf-8")
    doc_text = reference.read_text(encoding="utf-8")

    match = re.search(r"EXPECTED_TOOL_NAMES\s*=\s*\((.*?)\)\s*\n", reg_text, re.S)
    if not match:
        print("ERROR: could not find EXPECTED_TOOL_NAMES in registry.py")
        return 2

    reg_tools = re.findall(r'"(modeldesk_[a-z0-9_]+)"', match.group(1))
    doc_tools = sorted(set(re.findall(r"`(modeldesk_[a-z0-9_]+)`", doc_text)))
    set_reg = set(reg_tools)
    set_doc = set(doc_tools)

    print("Registered tools count:", len(reg_tools))
    print("Documented tools count:", len(doc_tools))
    print("\nTools only in registry (not in doc):")
    for tool_name in sorted(set_reg - set_doc):
        print("-", tool_name)
    print("\nTools only in doc (not in registry):")
    for tool_name in sorted(set_doc - set_reg):
        print("-", tool_name)
    print("\nCommon tools count:", len(set_reg & set_doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
