"""Deterministic tests for metadata CLI and agent skill parity."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import asyncio
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
from urllib.parse import urlsplit

import pytest

from modeldesk_mcp import __version__, server
from modeldesk_mcp.tools import EXPECTED_TOOL_NAMES, TOOL_DOMAIN_BY_NAME, TOOL_DOMAINS


SKILL_PATH = Path(__file__).resolve().parents[1] / ".github" / "skills" / "modeldesk-mcp-tools" / "SKILL.md"
BEGIN_MARKER = "<!-- BEGIN TOOL INDEX -->"
END_MARKER = "<!-- END TOOL INDEX -->"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch launcher.")
@pytest.mark.parametrize(("tool_name", "expected_prefix"), (("uv", "--directory "), ("py", "-3.14 -m uv --directory ")))
@pytest.mark.parametrize("exit_code", (0, 7))
def test_windows_launcher_resolves_uv_and_preserves_exit_code(
    tmp_path: Path, tool_name: str, expected_prefix: str, exit_code: int
) -> None:
    launcher = SKILL_PATH.parents[3] / "ModelDeskMCP.cmd"
    (tmp_path / f"{tool_name}.cmd").write_text(f"@echo %*\n@exit /b {exit_code}\n", encoding="ascii")
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join((str(tmp_path), str(Path(environment["SYSTEMROOT"]) / "System32")))

    result = subprocess.run(
        [environment["COMSPEC"], "/d", "/c", str(launcher), "--list-tools"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == exit_code
    assert result.stderr == ""
    assert result.stdout.startswith(expected_prefix)
    assert f'"{launcher.parent}\\."' in result.stdout
    assert result.stdout.rstrip().endswith("run python -m modeldesk_mcp.server --list-tools")


@pytest.mark.parametrize(
    ("arguments", "expected"),
    (
        (("--version",), f"modeldesk-mcp {__version__}"),
        (("--list-resources",), "modeldesk://workflow-catalog"),
        (("--list-prompts",), "No MCP prompts are registered."),
    ),
)
def test_metadata_cli_writes_exact_output(arguments: tuple[str, ...], expected: str) -> None:
    stdout = StringIO()

    with redirect_stdout(stdout):
        result = server.main(list(arguments))

    assert result == 0
    assert stdout.getvalue() == f"{expected}\n"


def test_create_app_initialize_version_matches_package_version(monkeypatch: pytest.MonkeyPatch) -> None:
    from mcp import ClientSession
    from mcp.client._memory import InMemoryTransport
    import modeldesk_mcp.com_bridge as com_bridge

    monkeypatch.setattr(com_bridge, "ComStaDispatcher", object)
    app = server.create_app()

    async def initialize() -> str:
        async with InMemoryTransport(app) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                result = await session.initialize()
                return result.server_info.version

    assert asyncio.run(initialize()) == __version__


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


def test_documented_tool_inventory_matches_registry() -> None:
    reference_path = SKILL_PATH.parents[3] / "docs" / "tools.md"
    reference = reference_path.read_text(encoding="utf-8")
    names = re.findall(r"^\| `(modeldesk_[a-z0-9_]+)` \|", reference, re.MULTILINE)

    assert len(names) == len(set(names)) == len(EXPECTED_TOOL_NAMES)
    assert set(names) == set(EXPECTED_TOOL_NAMES)


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


def test_public_checkout_excludes_personal_configuration_and_local_state() -> None:
    """Keep private checkout state excluded without hiding the public product skill."""
    root = SKILL_PATH.parents[3]
    assert SKILL_PATH.is_file()
    if not (root / ".git").exists() or shutil.which("git") is None:
        pytest.skip("Publication validation requires a Git checkout and Git.")
    tracked_config = subprocess.run(
        ["git", "ls-files", "--cached", "--", ".vscode/mcp.json"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert not tracked_config.stdout, "Keep the local MCP config out of Git tracking."
    private_paths = (
        ".vscode/mcp.json",
        ".agent-runtime/example/state.json",
        ".github/agents/example.agent.md",
        ".github/tools/example.mjs",
        ".github/skills/worker-handover/SKILL.md",
        ".github/.preference.ini",
        ".github/.learnings.json",
        ".github/decisions.md",
        ".github/graph.json",
        ".github/graph.html",
        "docs/live-modeldesk-qa.md",
        "problems.md",
        ".env.local",
        "credentials.json",
        "secrets.json",
    )
    result = subprocess.run(
        ["git", "-c", "core.excludesFile=NUL", "check-ignore", "--no-index", "-v", "-z", "--stdin"],
        cwd=root,
        input="\0".join(private_paths) + "\0",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    matches = result.stdout.rstrip("\0").split("\0")
    assert len(matches) == 4 * len(private_paths)
    assert all(source == ".gitignore" for source in matches[::4])
    public_skill = subprocess.run(
        ["git", "-c", "core.excludesFile=NUL", "check-ignore", "--no-index", "--",
         ".github/skills/modeldesk-mcp-tools/SKILL.md"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert public_skill.returncode == 1
    assert public_skill.stdout == ""


def test_public_setup_docs_use_local_configuration_without_private_config_links() -> None:
    """Retain usable product examples after removing the personal config file."""
    root = SKILL_PATH.parents[3]
    for relative in ("README.md", "docs/clients.md"):
        document = (root / relative).read_text(encoding="utf-8")
        assert not re.search(r"\]\((?:\.\./)?\.vscode/mcp\.json\)", document)
        assert "organization-local mirror" not in document
        assert '"modeldesk-mcp"' in document
        assert '"${workspaceFolder}\\\\ModelDeskMCP.cmd"' in document
        assert "modeldesk://workflow-catalog" in document


def test_public_lock_uses_pypi_and_hashed_public_artifacts() -> None:
    """Reject private package sources without starting uv or installing dependencies."""
    with (SKILL_PATH.parents[3] / "uv.lock").open("rb") as lock_file:
        lock = tomllib.load(lock_file)
    root_package = next(package for package in lock["package"] if package["name"] == "modeldesk-mcp")
    assert root_package["version"] == __version__
    assert root_package["source"] == {"editable": "."}
    for package in lock["package"]:
        if package is root_package:
            continue
        assert package["source"] == {"registry": "https://pypi.org/simple"}
        artifacts = package.get("wheels", []) + ([package["sdist"]] if "sdist" in package else [])
        assert artifacts
        for artifact in artifacts:
            address = urlsplit(artifact["url"])
            assert address.scheme == "https"
            assert address.hostname == "files.pythonhosted.org"
            assert address.username is None and address.password is None
            assert address.path.startswith("/packages/")
            assert re.fullmatch(r"sha256:[a-f0-9]{64}", artifact["hash"])
            assert isinstance(artifact["size"], int) and artifact["size"] > 0
