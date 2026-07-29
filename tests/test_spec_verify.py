"""SDD-FR-151 / SDD-FR-152: 検証コマンド実出力からの機械可読証跡。

`spec_verify.py record` がコマンドを実行し、安定項目と観測値を分離した証跡を書くこと、
および秘密値・環境固有パスを証跡へ持ち込まないことを検証する。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VERIFY_SCRIPT = ROOT / "plugins/bitz-sdd/skills/sdd-test/scripts/spec_verify.py"

# 証跡へ保存してよいトップレベルキー（許可リスト。SDD-FR-152）
ALLOWED_KEYS = {
    "schema", "command_id", "command", "commit", "dirty", "recorded_at",
    "tool", "exit_code", "counts", "requirements", "observed",
}

REQ_ID = "TT-FR-" + "001"
OTHER_REQ_ID = "TT-FR-" + "002"


def git(workspace: Path, *args: str):
    return subprocess.run(
        ["git", *args], cwd=str(workspace), capture_output=True, text=True, check=True
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """`.spec/` と 1 コミットを持つ最小の git ワークスペース"""
    (tmp_path / ".spec" / "requirements").mkdir(parents=True)
    (tmp_path / ".spec" / "requirements" / "seed.md").write_text("seed\n", encoding="utf-8")
    git(tmp_path, "init", "-q", ".")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "test")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def run_record(workspace: Path, *args: str, command: list[str] | None = None):
    argv = [sys.executable, str(VERIFY_SCRIPT), "record", str(workspace), *args]
    if command is not None:
        argv += ["--", *command]
    return subprocess.run(argv, capture_output=True, text=True, cwd=str(workspace))


def evidence_files(workspace: Path) -> list[Path]:
    return sorted((workspace / ".spec" / "verification").glob("*.json"))


def only_evidence(workspace: Path) -> dict:
    files = evidence_files(workspace)
    assert len(files) == 1, files
    return json.loads(files[0].read_text(encoding="utf-8"))


def head_sha(workspace: Path) -> str:
    return git(workspace, "rev-parse", "HEAD").stdout.strip()


def test_SDD_FR_151_records_stable_fields_from_real_execution(workspace: Path):
    """実行した終了コードと安定項目が証跡へ記録される"""
    res = run_record(
        workspace, "--command-id", "echo-check", "--implements", REQ_ID,
        command=["/bin/echo", "hello"],
    )

    assert res.returncode == 0, res.stderr
    payload = only_evidence(workspace)
    assert payload["schema"] == "bitzsdd/verification-evidence@1"
    assert payload["command_id"] == "echo-check"
    assert payload["command"] == ["/bin/echo", "hello"]
    assert payload["commit"] == head_sha(workspace)
    assert payload["exit_code"] == 0
    assert payload["requirements"] == [REQ_ID]
    assert payload["recorded_at"].endswith("Z")
    assert set(payload["tool"]) == {"name", "version"}


def test_SDD_FR_151_duration_is_isolated_in_observed(workspace: Path):
    """実行時間は observed 配下にだけ現れ、安定項目には混ざらない"""
    run_record(workspace, "--command-id", "echo-check", "--implements", REQ_ID,
               command=["/bin/echo", "hello"])

    payload = only_evidence(workspace)
    assert "duration_seconds" in payload["observed"]
    stable = {k: v for k, v in payload.items() if k != "observed"}
    assert "duration" not in json.dumps(stable)


def test_SDD_FR_151_rerun_at_same_commit_overwrites_same_file(workspace: Path):
    """同一 commit・同一 command-id の再実行はファイルを増やさない（冪等）"""
    for _ in range(3):
        res = run_record(workspace, "--command-id", "echo-check", "--implements", REQ_ID,
                         command=["/bin/echo", "hello"])
        assert res.returncode == 0, res.stderr

    assert len(evidence_files(workspace)) == 1


def test_SDD_FR_151_records_nonzero_exit_code(workspace: Path):
    """失敗した実行も証跡として残す（隠さない）"""
    res = run_record(workspace, "--command-id", "false-check", "--implements", REQ_ID,
                     command=["/bin/sh", "-c", "exit 3"])

    assert res.returncode == 0, res.stderr
    assert only_evidence(workspace)["exit_code"] == 3
    assert "注意" in res.stdout


def test_SDD_FR_151_parses_pytest_summary_counts(workspace: Path):
    """pytest 形式の要約行から件数を解析する"""
    summary = "12 failed, 9 passed, 3 skipped, 18 deselected in 1.19s"
    res = run_record(workspace, "--command-id", "pytest", "--implements", REQ_ID,
                     command=["/bin/echo", summary])

    assert res.returncode == 0, res.stderr
    payload = only_evidence(workspace)
    assert payload["counts"]["passed"] == 9
    assert payload["counts"]["failed"] == 12
    assert payload["counts"]["skipped"] == 3
    assert payload["observed"]["duration_seconds"] == 1.19


def test_SDD_FR_151_counts_are_null_without_a_recognized_summary(workspace: Path):
    """要約を解析できないコマンドでは件数を捏造せず null にする"""
    run_record(workspace, "--command-id", "echo-check", "--implements", REQ_ID,
               command=["/bin/echo", "no summary here"])

    assert only_evidence(workspace)["counts"] is None


def test_SDD_FR_151_multiple_requirements_are_deduplicated_and_sorted(workspace: Path):
    """複数要件は重複を除いて安定順で記録する"""
    run_record(
        workspace, "--command-id", "echo-check",
        "--implements", OTHER_REQ_ID, "--implements", REQ_ID, "--implements", OTHER_REQ_ID,
        command=["/bin/echo", "hello"],
    )

    assert only_evidence(workspace)["requirements"] == [REQ_ID, OTHER_REQ_ID]


def test_SDD_FR_151_dirty_tree_is_rejected_without_opt_in(workspace: Path):
    """未コミットの変更がある状態では記録せず非ゼロ終了する"""
    (workspace / "dirty.txt").write_text("x", encoding="utf-8")

    res = run_record(workspace, "--command-id", "echo-check", "--implements", REQ_ID,
                     command=["/bin/echo", "hello"])

    assert res.returncode != 0
    assert "未コミット" in res.stderr
    assert not (workspace / ".spec" / "verification").exists()


def test_SDD_FR_151_dirty_tree_is_allowed_with_explicit_flag(workspace: Path):
    """--allow-dirty を明示したときだけ暫定証跡として記録し、dirty を立てる"""
    (workspace / "dirty.txt").write_text("x", encoding="utf-8")

    res = run_record(workspace, "--command-id", "echo-check", "--implements", REQ_ID,
                     "--allow-dirty", command=["/bin/echo", "hello"])

    assert res.returncode == 0, res.stderr
    assert only_evidence(workspace)["dirty"] is True


def test_SDD_FR_151_rejects_workspace_without_git(tmp_path: Path):
    """git の HEAD を解決できない場所では記録しない"""
    (tmp_path / ".spec").mkdir()

    res = run_record(tmp_path, "--command-id", "echo-check", "--implements", REQ_ID,
                     command=["/bin/echo", "hello"])

    assert res.returncode != 0
    assert "HEAD" in res.stderr


def test_SDD_FR_151_rejects_malformed_requirement_id(workspace: Path):
    """要件 ID の書式が不正ならコマンドを実行せず拒否する"""
    res = run_record(workspace, "--command-id", "echo-check", "--implements", "not-an-id",
                     command=["/bin/echo", "hello"])

    assert res.returncode != 0
    assert "要件 ID" in res.stderr
    assert not (workspace / ".spec" / "verification").exists()


def test_SDD_FR_151_rejects_malformed_command_id(workspace: Path):
    """command-id はファイル名になるため書式を強制する"""
    res = run_record(workspace, "--command-id", "../escape", "--implements", REQ_ID,
                     command=["/bin/echo", "hello"])

    assert res.returncode != 0
    assert "command-id" in res.stderr


def test_SDD_FR_152_evidence_keys_are_limited_to_the_allow_list(workspace: Path):
    """証跡のトップレベルキーは許可リストを超えない"""
    run_record(workspace, "--command-id", "echo-check", "--implements", REQ_ID,
               command=["/bin/echo", "hello"])

    assert set(only_evidence(workspace)) <= ALLOWED_KEYS


def test_SDD_FR_152_raw_output_is_not_persisted(workspace: Path):
    """検証コマンドの出力本文は証跡へ保存しない（引数ではなく出力だけに現れる値で確認する）"""
    marker = "SENSITIVE-OUTPUT-MARKER"
    script = workspace / "leak.sh"
    script.write_text(f"#!/bin/sh\necho {marker}\n", encoding="utf-8")
    script.chmod(0o755)
    git(workspace, "add", "-A")
    git(workspace, "commit", "-qm", "add leak script")

    res = run_record(workspace, "--command-id", "leak-check", "--implements", REQ_ID,
                     command=["./leak.sh"])

    assert res.returncode == 0, res.stderr
    assert marker in res.stdout
    text = evidence_files(workspace)[0].read_text(encoding="utf-8")
    assert marker not in text


def test_SDD_FR_152_real_output_is_passed_through_to_the_caller(workspace: Path):
    """実出力は呼び出し元へそのまま流す（証跡に残さない代わりに端末では見える）"""
    marker = "VISIBLE-OUTPUT-MARKER"
    res = run_record(workspace, "--command-id", "echo-check", "--implements", REQ_ID,
                     command=["/bin/echo", marker])

    assert marker in res.stdout


@pytest.mark.parametrize(
    "secret_argument",
    ["--token=abc123", "--api-key=zzz", "--password=hunter2", "--credential=x"],
)
def test_SDD_FR_152_rejects_secret_looking_arguments(workspace: Path, secret_argument: str):
    """秘密値らしき引数はコマンドを実行せずに拒否する"""
    res = run_record(workspace, "--command-id", "echo-check", "--implements", REQ_ID,
                     command=["/bin/echo", secret_argument])

    assert res.returncode != 0
    assert "秘密値" in res.stderr
    assert not (workspace / ".spec" / "verification").exists()


def test_SDD_FR_152_rejects_home_absolute_paths(workspace: Path):
    """実行者のホームを含む絶対パスは環境固有情報として拒否する"""
    res = run_record(workspace, "--command-id", "echo-check", "--implements", REQ_ID,
                     command=["/bin/echo", "/home/someone/project/run.sh"])

    assert res.returncode != 0
    assert "絶対パス" in res.stderr


def test_SDD_FR_152_workspace_absolute_paths_are_relativized(workspace: Path):
    """ワークスペース配下の絶対パスは相対パスへ正規化して記録する"""
    script = workspace / "run.sh"
    script.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    script.chmod(0o755)
    git(workspace, "add", "-A")
    git(workspace, "commit", "-qm", "add script")

    res = run_record(workspace, "--command-id", "script-check", "--implements", REQ_ID,
                     command=[str(script)])

    assert res.returncode == 0, res.stderr
    assert only_evidence(workspace)["command"] == ["./run.sh"]
