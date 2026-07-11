"""bitz-env env_guard.py のフック契約テスト。

対応要件: ENV-FR-001（破壊的操作の deny）/ ENV-FR-002（プラットフォーム自動判別と
fail-open）/ ENV-CON-001（pass ケース = 普遍的最小集合の維持）
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "plugins" / "bitz-env" / "scripts" / "env_guard.py"

DESTRUCTIVE_COMMANDS = [
    "rm -rf /tmp/x",
    "rm -fr build",
    "git push --force origin main",
    "git push -f origin main",
    "git reset --hard HEAD~1",
    "git clean -fd",
    "sudo apt install pkg",
    "echo hi && sudo rm x",
]

SAFE_COMMANDS = [
    "rm -r build/",
    "git push origin feature",
    "git reset --soft HEAD~1",
    "python3 sudoku.py",
    "cat pseudo.txt",
    "git status",
]


def run_guard(stdin_text: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, f"ガードは常に正常終了する契約: {proc.stderr}"
    return json.loads(proc.stdout)


def claude_payload(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def agy_payload(command: str) -> str:
    return json.dumps({"toolCall": {"args": {"CommandLine": command}}})


# --- ENV-FR-001: 破壊的操作の deny（両プラットフォーム契約） ---

@pytest.mark.parametrize("command", DESTRUCTIVE_COMMANDS)
def test_claude_denies_destructive(command):
    out = run_guard(claude_payload(command))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "systemMessage" in out


@pytest.mark.parametrize("command", DESTRUCTIVE_COMMANDS)
def test_antigravity_denies_destructive(command):
    out = run_guard(agy_payload(command))
    assert out["decision"] == "deny"
    assert "reason" in out


# --- ENV-FR-001 / ENV-CON-001: 非該当は介入しない（誤検知なし） ---

@pytest.mark.parametrize("command", SAFE_COMMANDS)
def test_claude_passes_safe(command):
    assert run_guard(claude_payload(command)) == {}


@pytest.mark.parametrize("command", SAFE_COMMANDS)
def test_antigravity_passes_safe(command):
    assert run_guard(agy_payload(command)) == {}


# --- ENV-FR-002: プラットフォーム自動判別 ---

def test_platform_detection_claude_contract():
    out = run_guard(claude_payload("sudo x"))
    assert "hookSpecificOutput" in out and "decision" not in out


def test_platform_detection_antigravity_contract():
    out = run_guard(agy_payload("sudo x"))
    assert "decision" in out and "hookSpecificOutput" not in out


# --- ENV-FR-002: 不正入力・unknown 形状の fail-open ---

@pytest.mark.parametrize("stdin_text", [
    "not-json",
    "",
    "{}",
    json.dumps({"unexpected": {"shape": "rm -r x"}}),
])
def test_fail_open_on_invalid_or_unknown(stdin_text):
    assert run_guard(stdin_text) == {}


def test_unknown_shape_still_denies_destructive():
    # 形状不明でも破壊的パターンは全文走査で deny される（保守的側に倒す）
    out = run_guard(json.dumps({"unexpected": {"cmd": "git reset --hard"}}))
    assert out != {}


# --- ENV-FR-008: rules/*.md の SessionStart 注入（Claude Code 経路） ---

PLUGIN_ROOT = GUARD.parents[1]


def test_hooks_json_defines_sessionstart_rules_injection():
    hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())
    session_start = hooks["hooks"]["SessionStart"]
    commands = [h["command"] for entry in session_start for h in entry["hooks"]]
    assert any("rules" in c and "${CLAUDE_PLUGIN_ROOT}" in c for c in commands)


def test_sessionstart_command_outputs_rules_content():
    # ${CLAUDE_PLUGIN_ROOT} をプラグイン実体に解決して注入コマンドを実行し、
    # rules/*.md の内容が stdout（= コンテキスト注入内容）に含まれることを確認する
    proc = subprocess.run(
        ["bash", "-c", f'cat "{PLUGIN_ROOT}"/rules/*.md'],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "ガードレール" in proc.stdout
    assert "rm -rf" in proc.stdout
