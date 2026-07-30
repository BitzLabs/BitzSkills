"""sdd_report.py の回帰テスト（SI-SDD-001 / SI-SDD-002 / SI-SDD-021）。

- SI-SDD-001: 要件走査が spec_inspect.py の load_requirements と同じ判定基準であること
  （_ 始まり・domains.md を除外し、frontmatter に id が無いファイルは数えない）
- SI-SDD-002: 要件タイトルを本文見出し「### <ID> <タイトル>」から抽出すること
  （frontmatter title があればそちらを優先）
- SI-SDD-021 (SDD-FR-139): タスク集計を正規語彙（pending / implementing / blocked / done）で行い、
  語彙外 status を正規区分へ吸収せず (none) 等で可視化すること。表示は日本語主併記。
"""
import json
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


# ────────────────────────────────────────────────────────────────
# SDD-FR-154: 統合レポートへの検証証跡集計
# ────────────────────────────────────────────────────────────────

EVIDENCE_HEADING = "## 7. 検証証跡"


def write_evidence(tmp_path: Path, name: str, **overrides):
    payload = {
        "schema": "bitzsdd/verification-evidence@1",
        "command_id": name,
        "command": ["pytest", "-q"],
        "cwd": ".",
        "commit": "a" * 40,
        "dirty": False,
        "recorded_at": "2026-07-29T00:00:00Z",
        "tool": {"name": "pytest", "version": "8.0.0"},
        "exit_code": 0,
        "counts": {"passed": 3, "failed": 0, "errors": 0, "skipped": 0},
        "requirements": [REQ_ID1],
        "observed": {"duration_seconds": 1.23},
    }
    payload.update(overrides)
    directory = tmp_path / ".spec" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}--aaaaaaa.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_SDD_FR_154_section_absent_without_evidence_dir(tmp_path: Path):
    """証跡ディレクトリが無ければ節を出さない（既存レポート構成を変えない）"""
    req_dir = make_spec(tmp_path)
    write_req(req_dir, REQ_ID1, "verified", "対象要件")

    report = run_report(tmp_path)

    assert EVIDENCE_HEADING not in report


def test_SDD_FR_154_evidence_rows_are_reported(tmp_path: Path):
    """証跡ごとにファイル名・commit・終了コード・対象要件を表へ出す"""
    req_dir = make_spec(tmp_path)
    write_req(req_dir, REQ_ID1, "verified", "対象要件")
    write_evidence(tmp_path, "pytest")

    report = run_report(tmp_path)

    assert EVIDENCE_HEADING in report
    assert "pytest--aaaaaaa.json" in report
    assert "aaaaaaa" in report
    assert REQ_ID1 in report


def test_SDD_FR_154_counts_covered_requirements_and_failures(tmp_path: Path):
    """証跡が覆う要件数と失敗件数を集計する"""
    req_dir = make_spec(tmp_path)
    write_req(req_dir, REQ_ID1, "verified", "対象要件1")
    write_req(req_dir, REQ_ID2, "verified", "対象要件2")
    write_evidence(tmp_path, "pytest", requirements=[REQ_ID1, REQ_ID2])

    report = run_report(tmp_path)

    assert "**証跡が覆う要件**: 2 件" in report
    assert "**失敗・不正な証跡**: 0 件" in report


def test_SDD_FR_154_failed_evidence_turns_health_red(tmp_path: Path):
    """失敗した証跡があれば総合ヘルスを RED にする"""
    req_dir = make_spec(tmp_path)
    write_req(req_dir, REQ_ID1, "verified", "対象要件")
    write_evidence(tmp_path, "pytest", exit_code=1)

    report = run_report(tmp_path)

    assert "RED (失敗した検証証跡あり)" in report
    assert "**失敗・不正な証跡**: 1 件" in report


def test_SDD_FR_154_unreadable_evidence_is_counted_as_failure(tmp_path: Path):
    """読み取れない証跡も失敗として数え、黙って無視しない"""
    req_dir = make_spec(tmp_path)
    write_req(req_dir, REQ_ID1, "verified", "対象要件")
    directory = tmp_path / ".spec" / "verification"
    directory.mkdir(parents=True)
    (directory / "broken--aaaaaaa.json").write_text("{ not json", encoding="utf-8")

    report = run_report(tmp_path)

    assert "読取不能" in report
    assert "**失敗・不正な証跡**: 1 件" in report


# --- レビュー集計はビューを数えない（SDD-FR-160） -----------------------------

def test_SDD_FR_160_review_view_is_not_counted(tmp_path: Path):
    """`_` 始まりのビュー（_review-synthesis.md）はレビュー件数にも判定にも入らない"""
    make_spec(tmp_path)
    reviews = tmp_path / ".spec" / "reviews"
    reviews.mkdir(parents=True)
    review_id = "XX-" + "REV-" + "001"
    (reviews / f"{review_id}.md").write_text(
        f"---\nid: {review_id}\nstatus: active\ndecision: PASS\n---\n\n# レビュー\n",
        encoding="utf-8")
    (reviews / "_review-synthesis.md").write_text(
        f"---\nview_of: {review_id}\npath: {review_id}.md\n---\n\n# ビュー\n",
        encoding="utf-8")

    report = run_report(tmp_path)

    assert "1 件のレビューが存在" in report
    assert "PENDING" not in report
