"""sdd_report.py の回帰テスト（SI-SDD-001 / SI-SDD-002）。

- SI-SDD-001: 要件走査が spec_inspect.py の load_requirements と同じ判定基準であること
  （_ 始まり・domains.md を除外し、frontmatter に id が無いファイルは数えない）
- SI-SDD-002: 要件タイトルを本文見出し「### <ID> <タイトル>」から抽出すること
  （frontmatter title があればそちらを優先）
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
