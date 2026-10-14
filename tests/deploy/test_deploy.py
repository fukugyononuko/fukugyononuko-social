"""TC-N05・N06：承認の hook と、launchd の雛形（DD-16、DD-17）。"""

import importlib.util
import json
import plistlib
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "deploy" / "claude" / "block_approve.py"


def load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load(HOOK)
install = load(ROOT / "scripts" / "install_launchd.py")


@pytest.mark.parametrize(
    "command",
    [
        "nukosns approve 3 3fa2c1d8",
        "uv run nukosns approve 3 3fa2c1d8",
        "uv run --project ~/fukugyononuko/projects/fukugyononuko-social nukosns approve 3 3fa2c1d8",
        "cd /tmp && nukosns approve 3 3fa2c1d8",
        "bash -c 'nukosns approve 3 3fa2c1d8'",
        ".venv/bin/nukosns approve 3 3fa2c1d8",
        "~/.local/bin/nukosns  approve 3 3fa2c1d8",
        "python -m fukugyononuko_social.composition approve 3 3fa2c1d8",
        "echo ok\nnukosns approve 3 3fa2c1d8",
        "x=$(nukosns approve 3 3fa2c1d8)",
    ],
)
def test_n05_hook_blocks_approval(command: str) -> None:
    assert hook.blocked(command)


@pytest.mark.parametrize(
    "command",
    [
        "nukosns draft list --status approved",
        "nukosns draft show 3",
        "nukosns publish 3",
        "nukosns measure",
        "git log --oneline | grep approve",
        "uv run pytest -q tests/integration/test_publishing.py",
        "echo nukosns; echo approve",
    ],
)
def test_n05_hook_allows_other_commands(command: str) -> None:
    assert not hook.blocked(command)


def run_hook(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, check=False)


def test_n05_hook_exit_codes() -> None:
    denied = run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": "nukosns approve 3 3fa2c1d8"}}))
    assert denied.returncode == 2 and "運営者" in denied.stderr
    assert run_hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": "nukosns measure"}})).returncode == 0
    assert run_hook("not json").returncode == 0


def test_n06_launchd_template_is_generic_and_renders_valid_plist() -> None:
    template = install.TEMPLATE.read_text(encoding="utf-8")
    assert "/Users/" not in template and "{NUKOSNS}" in template and "{LOGS}" in template
    rendered = install.render(template, Path("/opt/x/bin/nukosns"), Path("/opt/x/logs"))
    plist = plistlib.loads(rendered.encode())
    assert plist["Label"] == install.LABEL
    assert plist["ProgramArguments"] == ["/opt/x/bin/nukosns", "measure"]
    assert plist["StartCalendarInterval"] == {"Weekday": 1, "Hour": 9, "Minute": 0}
    assert plist["StandardErrorPath"] == "/opt/x/logs/launchd.err.log"
