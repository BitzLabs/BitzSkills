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
TASK_ID2 = "TSK-" + "002"
GHOST_TASK_ID = "TSK-" + "999"


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


def test_task_to_task_depends_on_is_not_ghost(tmp_path: Path):
    """タスクが depends_on で他の実在タスクを参照しても幽霊参照にならない（SI-CORE-003）"""
    tasks_dir = make_spec(tmp_path)
    (tasks_dir / f"{TASK_ID}.md").write_text(
        f"---\nid: {TASK_ID}\nimplements: {REQ_ID}\ndepends_on: []\n---\n\n### {TASK_ID} 先行タスク\n",
        encoding="utf-8",
    )
    (tasks_dir / f"{TASK_ID2}.md").write_text(
        f"---\nid: {TASK_ID2}\nimplements: {REQ_ID}\ndepends_on: [{TASK_ID}]\n---\n\n### {TASK_ID2} 後続タスク\n",
        encoding="utf-8",
    )
    res = run_inspect(tmp_path)
    assert res.returncode == 0
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")
    assert "PASS" in report
    assert f"{TASK_ID} ←" not in report  # タスク間参照が幽霊参照として列挙されないこと


def test_spec_doc_referencing_task_id_is_not_ghost(tmp_path: Path):
    """.spec/specs/ の文書が実在タスク ID に言及しても幽霊参照にならない（SI-CORE-003）"""
    tasks_dir = make_spec(tmp_path)
    (tasks_dir / f"{TASK_ID}.md").write_text(
        f"---\nid: {TASK_ID}\nimplements: {REQ_ID}\ndepends_on: []\n---\n\n### {TASK_ID} タスク\n",
        encoding="utf-8",
    )
    specs_dir = tmp_path / ".spec" / "specs" / "feature"
    specs_dir.mkdir(parents=True)
    (specs_dir / "test-spec.md").write_text(
        f"# テスト仕様\n\n{REQ_ID} の検証。実装は {TASK_ID} を参照。\n",
        encoding="utf-8",
    )
    res = run_inspect(tmp_path)
    assert res.returncode == 0
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")
    assert "PASS" in report


def test_missing_task_reference_still_detected(tmp_path: Path):
    """存在しないタスク ID への参照は引き続き幽霊参照として FAIL になる"""
    tasks_dir = make_spec(tmp_path)
    (tasks_dir / f"{TASK_ID}.md").write_text(
        f"---\nid: {TASK_ID}\nimplements: {REQ_ID}\ndepends_on: [{GHOST_TASK_ID}]\n---\n\n### {TASK_ID} タスク\n",
        encoding="utf-8",
    )
    res = run_inspect(tmp_path)
    assert res.returncode == 1
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")
    assert GHOST_TASK_ID in report
    assert "FAIL" in report


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


# ---- SDD-FR-132: ワークスペース間 spec-issue 委託の横断検証 ----

SI_ID = "SI-T-" + "001"
DELEGATED_REQ_ID = "FR-" + "101"
GHOST_DELEGATED_ID = "FR-" + "888"


def make_delegation_workspaces(tmp_path: Path, delegated_to: str, sub_origin: str):
    """ルート ws（spec-issue 1件）+ サブ ws（要件1件）の委託 fixture を構築する"""
    root = tmp_path / "root"
    make_spec(root)
    si_dir = root / ".spec" / "spec-issues"
    si_dir.mkdir(parents=True)
    (si_dir / f"{SI_ID}.md").write_text(
        f"---\nid: {SI_ID}\nraised_by: test\ntarget: sub\n"
        f"proposed_change_type: bump\nstatus: accepted\norigin: root\n"
        f"delegated_to: {delegated_to}\n---\n- **目的**: テスト\n",
        encoding="utf-8",
    )
    sub = tmp_path / "sub"
    sub_req_dir = sub / ".spec" / "requirements"
    sub_req_dir.mkdir(parents=True)
    (sub_req_dir / f"{DELEGATED_REQ_ID}.md").write_text(
        f"---\nid: {DELEGATED_REQ_ID}\nversion: 1.0\nstatus: draft\n"
        f"origin: {sub_origin}\n---\n\n### {DELEGATED_REQ_ID} 委任先要件\n",
        encoding="utf-8",
    )
    (sub / ".spec" / "tasks").mkdir(parents=True)
    return root, sub


def run_inspect_multi(*roots: Path):
    return subprocess.run(
        [sys.executable, str(INSPECT_SCRIPT), "--workspace", *[str(r) for r in roots]],
        capture_output=True,
        text=True,
    )


def test_spec_issue_without_delegation_fields_passes(tmp_path: Path):
    """origin / delegated_to を持たない既存書式の spec-issue は委託チェック対象外で PASS（後方互換）"""
    make_spec(tmp_path)
    si_dir = tmp_path / ".spec" / "spec-issues"
    si_dir.mkdir(parents=True)
    (si_dir / f"{SI_ID}.md").write_text(
        f"---\nid: {SI_ID}\nraised_by: test\ntarget: t\n"
        f"proposed_change_type: bump\nstatus: open\n---\n- **目的**: テスト\n",
        encoding="utf-8",
    )
    res = run_inspect(tmp_path)
    assert res.returncode == 0, res.stdout
    assert "[委託]" not in res.stdout


def test_delegation_valid_bidirectional_passes(tmp_path: Path):
    """delegated_to の先が実在し origin: が委託元へ言及していれば PASS"""
    root, sub = make_delegation_workspaces(
        tmp_path, f"sub:{DELEGATED_REQ_ID}", SI_ID
    )
    res = run_inspect_multi(root, sub)
    assert res.returncode == 0, res.stdout
    assert "[委託]" not in res.stdout


def test_delegation_broken_link_fails(tmp_path: Path):
    """delegated_to の先の ID がどこにも実在しなければ FAIL"""
    root, sub = make_delegation_workspaces(
        tmp_path, f"sub:{GHOST_DELEGATED_ID}", SI_ID
    )
    res = run_inspect_multi(root, sub)
    assert res.returncode == 1
    assert "[委託]" in res.stdout
    assert GHOST_DELEGATED_ID in res.stdout


def test_delegation_missing_backlink_fails(tmp_path: Path):
    """委託先は実在するが origin: に委託元 spec-issue への言及が無ければ FAIL（双方向リンク欠如）"""
    root, sub = make_delegation_workspaces(
        tmp_path, f"sub:{DELEGATED_REQ_ID}", "別の由来"
    )
    res = run_inspect_multi(root, sub)
    assert res.returncode == 1
    assert "[委託]" in res.stdout
    assert "双方向" in res.stdout


def test_delegation_backlink_with_annotation_passes(tmp_path: Path):
    """origin: が注記付き（例: root（SI-... の実装振り返り）相当）でも言及ベースで PASS"""
    root, sub = make_delegation_workspaces(
        tmp_path, f"sub:{DELEGATED_REQ_ID}", f"root ws（{SI_ID} の委任）"
    )
    res = run_inspect_multi(root, sub)
    assert res.returncode == 0, res.stdout
    assert "[委託]" not in res.stdout


def test_delegation_multiple_targets(tmp_path: Path):
    """delegated_to のカンマ区切り複数エントリを個別に検証する（1件でもリンク切れなら FAIL）"""
    root, sub = make_delegation_workspaces(
        tmp_path,
        f"sub:{DELEGATED_REQ_ID}, sub:{GHOST_DELEGATED_ID}",
        SI_ID,
    )
    res = run_inspect_multi(root, sub)
    assert res.returncode == 1
    assert GHOST_DELEGATED_ID in res.stdout


def test_delegation_to_sub_spec_issue_passes(tmp_path: Path):
    """委託先が spec-issue（サブ ws の SI）でも実在 + 双方向言及で PASS する"""
    sub_si_id = "SI-S-" + "001"
    root, sub = make_delegation_workspaces(tmp_path, f"sub:{sub_si_id}", SI_ID)
    sub_si_dir = sub / ".spec" / "spec-issues"
    sub_si_dir.mkdir(parents=True)
    (sub_si_dir / f"{sub_si_id}.md").write_text(
        f"---\nid: {sub_si_id}\nraised_by: 委任\ntarget: t\n"
        f"proposed_change_type: bump\nstatus: open\norigin: root（{SI_ID} の委任）\n"
        f"---\n- **目的**: テスト\n",
        encoding="utf-8",
    )
    res = run_inspect_multi(root, sub)
    assert res.returncode == 0, res.stdout
    assert "[委託]" not in res.stdout


def test_SDD_FR_124_active_requirement_accepts_unit_test(tmp_path: Path):
    """SDD-FR-124: active 要件の unit-test を語彙外として報告しない。"""
    req_id = "SDD-FR-" + "124"
    req_dir = tmp_path / ".spec" / "requirements"
    req_dir.mkdir(parents=True)
    (req_dir / f"{req_id}.md").write_text(
        f"---\nid: {req_id}\nversion: 1.0\nstatus: approved\n"
        f"domain: verification\nverification_method: unit-test\n---\n\n"
        f"### {req_id} unit-test 語彙\n",
        encoding="utf-8",
    )
    tasks_dir = tmp_path / ".spec" / "tasks"
    tasks_dir.mkdir(parents=True)
    task_id = "SDD-TSK-" + "010"
    (tasks_dir / f"{task_id}.md").write_text(
        f"---\nimplements: {req_id}\ndepends_on: []\nstatus: done\n---\n",
        encoding="utf-8",
    )

    res = run_inspect(tmp_path)
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")
    assert res.returncode == 0, report
    assert "verification_method が未記入/語彙外" not in report
