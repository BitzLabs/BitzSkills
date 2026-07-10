import subprocess
import sys
from pathlib import Path

# プロジェクトルートにある元のスクリプト
INSPECT_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "bitz-sdd" / "skills" / "sdd-core" / "scripts" / "spec_inspect.py"
)

# fixture 用 ID は連結で組み立てる（リテラルで書くと、このリポジトリ自身の
# spec_inspect 走査が本ファイルを幽霊参照として誤検知するため）
REQ_ID = "FR-" + "001"
GHOST_ID = "FR-" + "999"
TASK_ID = "TSK-" + "001"


def make_spec(tmp_path: Path):
    """最小構成の .spec ワークスペース（要件1件 + tasks/ ディレクトリ）を構築する"""
    req_dir = tmp_path / ".spec" / "requirements"
    req_dir.mkdir(parents=True)
    (req_dir / f"{REQ_ID}.md").write_text(
        f"---\nid: {REQ_ID}\nversion: 1.0\nstatus: draft\n---\n\n### {REQ_ID} サンプル要件\n",
        encoding="utf-8",
    )
    tasks_dir = tmp_path / ".spec" / "tasks"
    tasks_dir.mkdir(parents=True)
    return tasks_dir


def run_inspect(root: Path):
    return subprocess.run(
        [sys.executable, str(INSPECT_SCRIPT), str(root)],
        capture_output=True,
        text=True,
    )


def test_task_self_id_is_not_ghost(tmp_path: Path):
    """タスクファイルが自身の ID を frontmatter・見出しに書いても幽霊参照にならない（SI-CORE-002）"""
    tasks_dir = make_spec(tmp_path)
    (tasks_dir / f"{TASK_ID}.md").write_text(
        f"---\nid: {TASK_ID}\nimplements: {REQ_ID}\ndepends_on: []\n---\n\n### {TASK_ID} サンプルタスク\n",
        encoding="utf-8",
    )
    res = run_inspect(tmp_path)
    assert res.returncode == 0
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")
    assert "PASS" in report
    assert f"{TASK_ID} ←" not in report  # 自己言及が幽霊参照として列挙されないこと


def test_true_ghost_reference_still_detected(tmp_path: Path):
    """存在しない要件 ID への参照は引き続き幽霊参照として FAIL になる"""
    tasks_dir = make_spec(tmp_path)
    (tasks_dir / f"{TASK_ID}.md").write_text(
        f"---\nid: {TASK_ID}\nimplements: {GHOST_ID}\ndepends_on: []\n---\n\n存在しない {GHOST_ID} を参照する。\n",
        encoding="utf-8",
    )
    res = run_inspect(tmp_path)
    assert res.returncode == 1
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")
    assert GHOST_ID in report
    assert "FAIL" in report
