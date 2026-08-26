"""Deterministic tests for metadata CLI and agent skill parity."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import re

import pytest

from modeldesk_mcp import __version__, server
from modeldesk_mcp.tools import EXPECTED_TOOL_NAMES, TOOL_DOMAIN_BY_NAME, TOOL_DOMAINS


SKILL_PATH = Path(__file__).resolve().parents[1] / ".github" / "skills" / "modeldesk-mcp-tools" / "SKILL.md"
BEGIN_MARKER = "<!-- BEGIN TOOL INDEX -->"
END_MARKER = "<!-- END TOOL INDEX -->"


@pytest.mark.parametrize(
    ("arguments", "expected"),
    (
        (("--version",), f"modeldesk-mcp {__version__}"),
        (("--list-resources",), "No MCP resources are registered."),
        (("--list-prompts",), "No MCP prompts are registered."),
    ),
)
def test_metadata_cli_writes_exact_output(arguments: tuple[str, ...], expected: str) -> None:
    stdout = StringIO()

    with redirect_stdout(stdout):
        result = server.main(list(arguments))

    assert result == 0
    assert stdout.getvalue() == f"{expected}\n"


def test_list_tools_cli_matches_expected_order() -> None:
    stdout = StringIO()

    with redirect_stdout(stdout):
        result = server.main(["--list-tools"])

    assert result == 0
    assert stdout.getvalue().splitlines() == list(EXPECTED_TOOL_NAMES)


def test_metadata_cli_does_not_create_app_or_initialize_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_create_app() -> object:
        raise AssertionError("metadata commands must not create the MCP app")

    monkeypatch.setattr(server, "create_app", fail_create_app)
    for arguments in (("--version",), ("--list-tools",), ("--list-resources",), ("--list-prompts",)):
        with redirect_stdout(StringIO()):
            assert server.main(list(arguments)) == 0


def test_no_argument_cli_preserves_synchronous_stdio_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class FakeApp:
        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr(server, "create_app", lambda: FakeApp())

    assert server.main([]) is None
    assert calls == ["run"]


def test_cli_rejects_multiple_metadata_flags_with_argparse_error() -> None:
    stderr = StringIO()

    with redirect_stderr(stderr), pytest.raises(SystemExit) as exception:
        server.main(["--version", "--list-tools"])

    assert exception.value.code == 2
    assert "not allowed with argument" in stderr.getvalue()


def test_expected_tool_names_have_expected_count_and_are_unique() -> None:
    assert len(EXPECTED_TOOL_NAMES) == 83
    assert len(set(EXPECTED_TOOL_NAMES)) == 83


def test_skill_markers_and_index_parity() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    begin = skill.index(BEGIN_MARKER)
    end = skill.index(END_MARKER)
    tool_index = skill[begin : end + len(END_MARKER)]

    names = tuple(re.findall(r"^\| `(modeldesk_[a-z0-9_]+)` \|", tool_index, re.MULTILINE))
    expected_grouped_names = tuple(
        name for domain in TOOL_DOMAINS for name in EXPECTED_TOOL_NAMES if TOOL_DOMAIN_BY_NAME[name] == domain
    )
    assert names == expected_grouped_names
    assert len(names) == 83
    assert len(names) == len(set(names))


def test_skill_index_preserves_registry_order_within_each_domain() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    tool_index = skill[skill.index(BEGIN_MARKER) : skill.index(END_MARKER) + len(END_MARKER)]

    for domain in TOOL_DOMAINS:
        section_start = tool_index.index(f"### {domain}")
        section_end = tool_index.find("### ", section_start + len(domain) + 4)
        section = tool_index[section_start:] if section_end < 0 else tool_index[section_start:section_end]
        actual = tuple(re.findall(r"^\| `(modeldesk_[a-z0-9_]+)` \|", section, re.MULTILINE))
        expected = tuple(name for name in EXPECTED_TOOL_NAMES if TOOL_DOMAIN_BY_NAME[name] == domain)
        assert actual == expected

    assert set(TOOL_DOMAIN_BY_NAME.values()) == set(TOOL_DOMAINS)
