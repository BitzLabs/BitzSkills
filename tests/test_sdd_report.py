"""sdd_report.py の回帰テスト（SI-SDD-001 / SI-SDD-002 / SI-SDD-021）。

- SI-SDD-001: 要件走査が spec_inspect.py の load_requirements と同じ判定基準であること
  （_ 始まり・domains.md を除外し、frontmatter に id が無いファイルは数えない）
- SI-SDD-002: 要件タイトルを本文見出し「### <ID> <タイトル>」から抽出すること
  （frontmatter title があればそちらを優先）
- SI-SDD-021 (SDD-FR-139): タスク集計を正規語彙（pending / implementing / blocked / done）で行い、
  語彙外 status を正規区分へ吸収せず (none) 等で可視化すること。表示は日本語主併記。
"""
import subprocess
import sys
from pathlib import Path

REPORT_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "bitz-sdd" / "skills" / "sdd-report" / "scripts" / "sdd_report.py"
)

# fixture 用 ID は連結で組み立てる（リテラルで書くと、このリポジトリ自身の
# spec_inspect 走査が本ファイルを幽霊参照として誤検知するため）
REQ_ID1 = "FR-" + "001"
REQ_ID2 = "FR-" + "002"


def write_req(req_dir: Path, req_id: str, status: str, title: str, extra_fm: str = ""):
    (req_dir / f"{req_id}.md").write_text(
        f"---\nid: {req_id}\nversion: 1.0\nstatus: {status}\n{extra_fm}---\n"
        f"\n### {req_id} {title}\n\n- 説明: テスト用要件\n",
        encoding="utf-8",
    )


def run_report(root: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(REPORT_SCRIPT), str(root)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return (root / ".spec" / "reports" / "status-report.md").read_text(encoding="utf-8")


def make_spec(tmp_path: Path) -> Path:
    req_dir = tmp_path / ".spec" / "requirements"
    req_dir.mkdir(parents=True)
    return req_dir


def write_task(tmp_path: Path, task_id: str, status: str):
    tasks_dir = tmp_path / ".spec" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    body = f"---\nid: {task_id}\nstatus: {status}\n---\n" if status is not None \
        else f"---\nid: {task_id}\n---\n"
    (tasks_dir / f"{task_id}.md").write_text(body + f"\n### {task_id}\n", encoding="utf-8")


def test_domains_md_is_not_counted_as_requirement(tmp_path: Path):
    """SI-SDD-001: domains.md（統制語彙）を要件として数えず、ヘルスも誤判定しない"""
    req_dir = make_spec(tmp_path)
    write_req(req_dir, REQ_ID1, "approved", "サンプル要件")
    (req_dir / "domains.md").write_text(
        "# domains 統制語彙\n\n- reporting\n- core\n", encoding="utf-8"
    )
    report = run_report(tmp_path)
    assert "(1 件)" in report          # 実要件1件のみ
    assert "**起草中（draft）**: 0 件" in report  # domains.md が draft 扱いされない
    assert "YELLOW" not in report       # ヘルスが誤って YELLOW にならない
    assert "domains" not in report.split("### 要件一覧")[1].split("---")[0]


def test_underscore_and_no_id_files_are_skipped(tmp_path: Path):
    """SI-SDD-001: _ 始まりのファイルと frontmatter に id が無いファイルは数えない"""
    req_dir = make_spec(tmp_path)
    write_req(req_dir, REQ_ID1, "approved", "サンプル要件")
    (req_dir / "_counter.md").write_text("last: 1\n", encoding="utf-8")
    (req_dir / "notes.md").write_text(
        "---\nstatus: draft\n---\n\n# id を持たないメモ\n", encoding="utf-8"
    )
    report = run_report(tmp_path)
    assert "(1 件)" in report
    assert "**起草中（draft）**: 0 件" in report


def test_title_extracted_from_heading(tmp_path: Path):
    """SI-SDD-002: タイトルを本文見出し「### <ID> <タイトル>」から抽出する"""
    req_dir = make_spec(tmp_path)
    write_req(req_dir, REQ_ID1, "approved", "レポートの自動生成")
    report = run_report(tmp_path)
    assert f"| {REQ_ID1} | レポートの自動生成 | 承認済み（approved） |" in report
    assert "No Title" not in report


def test_frontmatter_title_takes_precedence(tmp_path: Path):
    """SI-SDD-002: frontmatter に title があればそちらを優先する"""
    req_dir = make_spec(tmp_path)
    write_req(req_dir, REQ_ID1, "approved", "見出し側タイトル",
              extra_fm="title: FM側タイトル\n")
    report = run_report(tmp_path)
    assert f"| {REQ_ID1} | FM側タイトル | 承認済み（approved） |" in report


def test_status_counting_still_works(tmp_path: Path):
    """既存挙動の回帰確認: status 別カウントと進捗率"""
    req_dir = make_spec(tmp_path)
    write_req(req_dir, REQ_ID1, "approved", "要件その1")
    write_req(req_dir, REQ_ID2, "verified", "要件その2")
    report = run_report(tmp_path)
    assert "(2 件)" in report
    assert "**承認済み（approved）**: 1 件" in report
    assert "**検証済み（verified）**: 1 件" in report
    assert "**50%** (1 / 2 要件)" in report


# --- SI-SDD-021 (SDD-FR-139): タスク集計の正規語彙化 ---

def _task_section(report: str) -> str:
    """レポートから「## 5. タスク実行状況」節だけを取り出す。"""
    return report.split("## 5. タスク実行状況")[1].split("##")[0]


def test_blocked_and_implementing_are_counted_independently(tmp_path: Path):
    """SDD-FR-139: blocked / implementing が独立区分で計上され Todo に吸収されない"""
    make_spec(tmp_path)
    write_task(tmp_path, "TSK-" + "001", "blocked")
    write_task(tmp_path, "TSK-" + "002", "implementing")
    write_task(tmp_path, "TSK-" + "003", "done")
    report = run_report(tmp_path)
    section = _task_section(report)
    # 旧語彙は消えている
    assert "Todo" not in section
    assert "Doing" not in section
    # 正規語彙が日本語主併記で独立計上される
    assert "**介入待ち（blocked）**: 1 件" in section
    assert "**実装中（implementing）**: 1 件" in section
    assert "**完了（done）**: 1 件" in section
    assert "**着手待ち（pending）**: 0 件" in section
    assert "(.spec/tasks/ - 3 件)" in report


def test_unknown_and_missing_status_not_absorbed_into_pending(tmp_path: Path):
    """SDD-FR-139: 語彙外・欠落 status は正規区分へ吸収せず独立可視化する"""
    make_spec(tmp_path)
    write_task(tmp_path, "TSK-" + "004", "pending")
    write_task(tmp_path, "TSK-" + "005", "wip")   # 語彙外の未知値
    write_task(tmp_path, "TSK-" + "006", None)     # status 欠落
    report = run_report(tmp_path)
    section = _task_section(report)
    # 正規区分の pending は 1 件のみ（wip / 欠落を吸収しない）
    assert "**着手待ち（pending）**: 1 件" in section
    # 語彙外は独立区分として現れる（未知語は機械値のまま）
    assert "**wip**: 1 件" in section
    assert "**(none)**: 1 件" in section
    assert "(.spec/tasks/ - 3 件)" in report
