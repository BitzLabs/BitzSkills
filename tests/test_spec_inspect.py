import subprocess
import sys
import base64
import hashlib
import json
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
ISSUE_ID = "SI-" + "TEST-" + "001"


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


def run_inspect(root: Path, *extra_args: str):
    return subprocess.run(
        [sys.executable, str(INSPECT_SCRIPT), str(root), *extra_args],
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


def test_wrapped_ears_clause_accepts_shall_on_continuation_line(tmp_path: Path):
    """EARS 節は物理行ではなく箇条書き全体で SHALL の有無を検査する。"""
    make_spec(tmp_path)
    req_path = tmp_path / ".spec" / "requirements" / f"{REQ_ID}.md"
    req_path.write_text(
        f"---\nid: {REQ_ID}\nversion: 1.0\nstatus: draft\n---\n\n"
        f"### {REQ_ID} 折り返し EARS\n\n"
        "- **受入基準 (EARS)**:\n"
        "  - WHEN 入力が複数行に折り返される\n"
        "    THEN 箇条書き全体を一つの節として検査すること SHALL\n",
        encoding="utf-8",
    )

    result = run_inspect(tmp_path, "--check-only")

    assert result.returncode == 0, result.stdout
    assert "EARS不完全" not in result.stdout


def test_ears_clause_without_shall_still_fails(tmp_path: Path):
    """論理的な WHEN 節全体に SHALL が無ければ引き続き FAIL にする。"""
    make_spec(tmp_path)
    req_path = tmp_path / ".spec" / "requirements" / f"{REQ_ID}.md"
    req_path.write_text(
        f"---\nid: {REQ_ID}\nversion: 1.0\nstatus: draft\n---\n\n"
        f"### {REQ_ID} 不完全 EARS\n\n"
        "- **受入基準 (EARS)**:\n"
        "  - WHEN 入力を受け取る\n"
        "    THEN 処理する\n",
        encoding="utf-8",
    )

    result = run_inspect(tmp_path, "--check-only")

    assert result.returncode == 1
    assert "EARS不完全" in result.stdout


# ---- SDD-FR-133: check-only 読み取り専用検査 ----


def test_SDD_FR_133_check_only_preserves_existing_report_and_matches_output(tmp_path: Path):
    """check-only は通常検査と同じ出力・終了コードを返し、既存レポートを変更しない。"""
    make_spec(tmp_path)
    normal = run_inspect(tmp_path)
    assert normal.returncode == 0

    report_path = tmp_path / ".spec" / "inspection-report.md"
    sentinel = b"existing report\n"
    report_path.write_bytes(sentinel)

    check_only = run_inspect(tmp_path, "--check-only")
    assert check_only.returncode == normal.returncode
    assert check_only.stdout == normal.stdout
    assert report_path.read_bytes() == sentinel


def test_SDD_FR_133_check_only_does_not_create_missing_report(tmp_path: Path):
    """check-only 実行前にレポートが無ければ、検査後も生成しない。"""
    make_spec(tmp_path)
    report_path = tmp_path / ".spec" / "inspection-report.md"

    result = run_inspect(tmp_path, "--check-only")

    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert not report_path.exists()


def test_SDD_FR_133_check_only_failure_does_not_write_report(tmp_path: Path):
    """check-only がFAILを返す場合もレポートを生成しない。"""
    make_spec(tmp_path)
    req_path = tmp_path / ".spec" / "requirements" / f"{REQ_ID}.md"
    req_path.write_text(
        f"---\nid: {REQ_ID}\nversion: 1.0\nstatus: implementing\n"
        "domain: verification\nverification_method: unit-test\n---\n\n"
        f"### {REQ_ID} 実装中要件\n",
        encoding="utf-8",
    )

    result = run_inspect(tmp_path, "--check-only")

    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert not (tmp_path / ".spec" / "inspection-report.md").exists()


def test_SDD_FR_133_check_only_preserves_all_workspace_reports(tmp_path: Path):
    """複数workspaceのcheck-onlyでも全レポートを不変に保ち、通常検査と同じ出力を返す。"""
    roots = [tmp_path / "one", tmp_path / "two"]
    for root in roots:
        make_spec(root)
    command = [
        sys.executable,
        str(INSPECT_SCRIPT),
        "--workspace",
        *[str(root) for root in roots],
    ]
    normal = subprocess.run(command, capture_output=True, text=True)
    assert normal.returncode == 0

    sentinels = {}
    for index, root in enumerate(roots):
        report_path = root / ".spec" / "inspection-report.md"
        sentinels[report_path] = f"existing report {index}\n".encode()
        report_path.write_bytes(sentinels[report_path])

    check_only = subprocess.run(
        [*command, "--check-only"], capture_output=True, text=True
    )

    assert check_only.returncode == normal.returncode
    assert check_only.stdout == normal.stdout
    for report_path, sentinel in sentinels.items():
        assert report_path.read_bytes() == sentinel


# ---- SDD-FR-134: approved 実装待ちと孤児FAILの分離 ----


def write_active_requirement(root: Path, status: str):
    req_path = root / ".spec" / "requirements" / f"{REQ_ID}.md"
    req_path.write_text(
        f"---\nid: {REQ_ID}\nversion: 1.0\nstatus: {status}\n"
        "domain: verification\nverification_method: unit-test\n---\n\n"
        f"### {REQ_ID} {status} 要件\n",
        encoding="utf-8",
    )


def test_SDD_FR_134_approved_without_task_is_warning_and_passes(tmp_path: Path):
    """approved のタスク未紐付けは実装待ち警告であり、単独ではFAILにしない。"""
    make_spec(tmp_path)
    write_active_requirement(tmp_path, "approved")

    result = run_inspect(tmp_path)
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")

    assert result.returncode == 0, report
    assert "実装待ち要件（approved" in report
    assert f"- {REQ_ID}" in report
    assert "孤児要件: 0" in report
    assert "PASS" in report


def test_SDD_FR_134_post_approval_without_task_is_orphan_and_fails(tmp_path: Path):
    """implementing 以降のタスク未紐付けは孤児要件としてFAILを維持する。"""
    for status in ("implementing", "verified", "promoted"):
        root = tmp_path / status
        make_spec(root)
        write_active_requirement(root, status)

        result = run_inspect(root)
        report = (root / ".spec" / "inspection-report.md").read_text(encoding="utf-8")

        assert result.returncode == 1
        assert "孤児要件（implementing以降" in report
        assert f"- {REQ_ID}" in report
        assert "FAIL" in report


def test_SDD_FR_134_approved_with_task_is_not_waiting(tmp_path: Path):
    """approved でも実装タスクがあれば実装待ち警告へ列挙しない。"""
    tasks_dir = make_spec(tmp_path)
    write_active_requirement(tmp_path, "approved")
    (tasks_dir / f"{TASK_ID}.md").write_text(
        f"---\nimplements: {REQ_ID}\ndepends_on: []\nstatus: pending\n---\n",
        encoding="utf-8",
    )

    result = run_inspect(tmp_path)
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")

    assert result.returncode == 0, report
    waiting_section = report.split("## 実装待ち要件", 1)[1].split("##", 1)[0]
    assert REQ_ID not in waiting_section
    assert "PASS" in report


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


# ---- SDD-FR-143: local task completion / audit integrity --------------------


def test_SDD_FR_143_verified_with_incomplete_local_task_fails(tmp_path: Path):
    tasks_dir = make_spec(tmp_path)
    write_active_requirement(tmp_path, "verified")
    (tasks_dir / f"{TASK_ID}.md").write_text(
        f"---\nimplements: {REQ_ID}\ndepends_on: []\nstatus: implementing\n---\n",
        encoding="utf-8",
    )

    result = run_inspect(tmp_path)
    assert result.returncode == 1
    assert "[trace]" in result.stdout
    assert "未完了local task" in result.stdout


def test_SDD_FR_143_corrupt_structured_state_event_fails(tmp_path: Path):
    make_spec(tmp_path)
    (tmp_path / ".spec" / "STATE.md").write_text(
        "- 2026-07-27 sample\n<!-- sdd-event:not-base64! -->\n",
        encoding="utf-8",
    )

    result = run_inspect(tmp_path)
    assert result.returncode == 1
    assert "audit-corruption" in result.stdout


def test_SDD_FR_143_incomplete_journal_fails_inspect(tmp_path: Path):
    make_spec(tmp_path)
    transactions = tmp_path / ".spec" / ".transactions"
    transactions.mkdir()
    (transactions / "event.json").write_text("{}", encoding="utf-8")

    result = run_inspect(tmp_path)
    assert result.returncode == 1
    assert "incomplete-transaction" in result.stdout


def _state_event(
    artifact_id: str,
    path: str,
    old: str,
    new: str,
    event_id: str,
) -> str:
    event = {
        "schema_version": 1,
        "event_id": event_id,
        "timestamp": "2026-07-27T00:00:00Z",
        "path": path,
        "artifact_id": artifact_id,
        "old": old,
        "new": new,
        "provenance": {"kind": "agent", "actor": "test"},
        "artifact_before_hash": hashlib.sha256(old.encode()).hexdigest(),
        "artifact_after_hash": hashlib.sha256(new.encode()).hexdigest(),
    }
    payload = json.dumps(
        event, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    encoded = base64.b64encode(payload).decode()
    return (
        f"- 2026-07-27 {artifact_id}: {old} → {new} (test)\n"
        f"<!-- sdd-event:{encoded} -->\n"
    )


def test_SDD_FR_143_transition_chain_mismatch_fails_inspect(tmp_path: Path):
    make_spec(tmp_path)
    req_path = tmp_path / ".spec" / "requirements" / f"{REQ_ID}.md"
    req_path.write_text(
        f"---\nid: {REQ_ID}\nversion: 1.0\nstatus: verified\n"
        "domain: verification\nverification_method: unit-test\n---\n",
        encoding="utf-8",
    )
    task = tmp_path / ".spec" / "tasks" / f"{TASK_ID}.md"
    task.write_text(
        f"---\nimplements: {REQ_ID}\nstatus: done\n---\n",
        encoding="utf-8",
    )
    relative = f".spec/requirements/{REQ_ID}.md"
    state = tmp_path / ".spec" / "STATE.md"
    state.write_text(
        "# STATE\n\n"
        + _state_event(REQ_ID, relative, "draft", "approved", "event-1")
        + _state_event(REQ_ID, relative, "implementing", "verified", "event-2"),
        encoding="utf-8",
    )

    result = run_inspect(tmp_path, "--check-only")

    assert result.returncode == 1
    assert "遷移連鎖が不正" in result.stdout


def test_SDD_FR_143_current_status_must_match_last_event(tmp_path: Path):
    make_spec(tmp_path)
    state = tmp_path / ".spec" / "STATE.md"
    state.write_text(
        "# STATE\n\n"
        + _state_event(
            REQ_ID,
            f".spec/requirements/{REQ_ID}.md",
            "draft",
            "approved",
            "event-1",
        ),
        encoding="utf-8",
    )

    result = run_inspect(tmp_path, "--check-only")

    assert result.returncode == 1
    assert "現status" in result.stdout


# ---- SDD-FR-144: target SHA bound integration preflight ---------------------


def _git(root: Path, *args: str):
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_git_workspace(root: Path):
    make_spec(root)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "test")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "baseline")
    branch = _git(root, "branch", "--show-current").stdout.strip()
    return branch


def test_SDD_FR_144_target_ref_preflight_reports_exact_sha(tmp_path: Path):
    branch = _init_git_workspace(tmp_path)
    _git(tmp_path, "switch", "-qc", "feature")
    second_id = "FR-" + "002"
    (tmp_path / ".spec" / "requirements" / f"{second_id}.md").write_text(
        f"---\nid: {second_id}\nversion: 1.0\nstatus: draft\n---\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "feature")
    target_sha = _git(tmp_path, "rev-parse", branch).stdout.strip()

    result = run_inspect(tmp_path, "--check-only", "--target-ref", branch)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"target_sha={target_sha}" in result.stdout


def test_SDD_FR_144_target_ref_collision_fails(tmp_path: Path):
    make_spec(tmp_path)
    collision_id = "FR-" + "002"
    legacy = tmp_path / ".spec" / "requirements" / "legacy.md"
    legacy.write_text(
        f"---\nid: {collision_id}\nversion: 1.0\nstatus: draft\n---\n",
        encoding="utf-8",
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "baseline")
    branch = _git(tmp_path, "branch", "--show-current").stdout.strip()
    _git(tmp_path, "switch", "-qc", "feature")
    (tmp_path / ".spec" / "requirements" / f"{collision_id}.md").write_text(
        f"---\nid: {collision_id}\nversion: 1.0\nstatus: draft\n---\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "renumbered")

    result = run_inspect(tmp_path, "--check-only", "--target-ref", branch)
    assert result.returncode == 1
    assert "ID衝突" in result.stdout
    assert collision_id in result.stdout


def test_SDD_FR_144_target_ref_allows_id_preserving_relocation(tmp_path: Path):
    """target上の旧pathからIDを除去して新pathへ移すだけなら再採番衝突ではない。"""
    make_spec(tmp_path)
    relocated_id = "FR-" + "002"
    legacy = tmp_path / ".spec" / "requirements" / "legacy.md"
    legacy.write_text(
        f"---\nid: {relocated_id}\nversion: 1.0\nstatus: draft\n---\n",
        encoding="utf-8",
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "baseline")
    branch = _git(tmp_path, "branch", "--show-current").stdout.strip()
    _git(tmp_path, "switch", "-qc", "feature")
    legacy.unlink()
    (tmp_path / ".spec" / "requirements" / f"{relocated_id}.md").write_text(
        f"---\nid: {relocated_id}\nversion: 1.0\nstatus: draft\n---\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "relocated")

    result = run_inspect(tmp_path, "--check-only", "--target-ref", branch)

    assert result.returncode == 0, result.stdout + result.stderr


def test_SDD_FR_144_target_ref_detects_accepted_origin_disappearance(tmp_path: Path):
    make_spec(tmp_path)
    req_path = tmp_path / ".spec" / "requirements" / f"{REQ_ID}.md"
    req_path.write_text(
        f"---\nid: {REQ_ID}\nversion: 1.0\nstatus: draft\n"
        f"origin: {ISSUE_ID}\n---\n",
        encoding="utf-8",
    )
    issues = tmp_path / ".spec" / "spec-issues"
    issues.mkdir()
    (issues / f"{ISSUE_ID}.md").write_text(
        f"---\nid: {ISSUE_ID}\nstatus: accepted\n---\n",
        encoding="utf-8",
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "baseline")
    branch = _git(tmp_path, "branch", "--show-current").stdout.strip()
    _git(tmp_path, "switch", "-qc", "feature")
    req_path.unlink()
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "lost origin")

    result = run_inspect(tmp_path, "--check-only", "--target-ref", branch)

    assert result.returncode == 1
    assert "origin成果物消失" in result.stdout
    assert ISSUE_ID in result.stdout


# ---- SDD-FR-145: schema v2 proxy event audit --------------------------------


def _proxy_event(
    artifact_id: str,
    path: str,
    old: str,
    new: str,
    event_id: str,
    decision_ref: str,
    schema_version: int = 2,
    kind: str = "agent-proxy-unverified",
    drop: tuple = (),
) -> str:
    provenance = {
        "kind": kind,
        "actor": "claude",
        "on_behalf_of": "hide",
        "decision_ref": decision_ref,
    }
    for key in drop:
        provenance.pop(key, None)
    event = {
        "schema_version": schema_version,
        "event_id": event_id,
        "timestamp": "2026-07-27T00:00:00Z",
        "path": path,
        "artifact_id": artifact_id,
        "old": old,
        "new": new,
        "provenance": provenance,
        "artifact_before_hash": hashlib.sha256(old.encode()).hexdigest(),
        "artifact_after_hash": hashlib.sha256(new.encode()).hexdigest(),
    }
    payload = json.dumps(
        event, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    encoded = base64.b64encode(payload).decode()
    return (
        f"- 2026-07-27 {artifact_id}: {old} → {new} (claude on behalf of hide)\n"
        f"<!-- sdd-event:{encoded} -->\n"
    )


def _approved_requirement(tmp_path: Path) -> str:
    req_path = tmp_path / ".spec" / "requirements" / f"{REQ_ID}.md"
    req_path.write_text(
        f"---\nid: {REQ_ID}\nversion: 1.0\nstatus: approved\n"
        "domain: verification\nverification_method: unit-test\n---\n\n"
        f"### {REQ_ID} サンプル要件\n- WHEN x THEN y SHALL\n",
        encoding="utf-8",
    )
    return f".spec/requirements/{REQ_ID}.md"


def test_SDD_FR_145_valid_proxy_event_passes_inspect(tmp_path: Path):
    make_spec(tmp_path)
    relative = _approved_requirement(tmp_path)
    ref = f".spec/spec-issues/{ISSUE_ID}.md"
    issue = tmp_path / ref
    issue.parent.mkdir(parents=True, exist_ok=True)
    issue.write_text(f"---\nid: {ISSUE_ID}\nstatus: accepted\n---\n- 裁定\n", encoding="utf-8")
    (tmp_path / ".spec" / "STATE.md").write_text(
        "# STATE\n\n" + _proxy_event(REQ_ID, relative, "draft", "approved", "event-1", ref),
        encoding="utf-8",
    )
    result = run_inspect(tmp_path)
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")
    assert result.returncode == 0, report
    assert "audit-corruption" not in report
    assert "decision-ref参照先が見つかりません" not in report


def test_SDD_FR_145_proxy_event_missing_reference_field_fails(tmp_path: Path):
    make_spec(tmp_path)
    relative = _approved_requirement(tmp_path)
    (tmp_path / ".spec" / "STATE.md").write_text(
        "# STATE\n\n"
        + _proxy_event(REQ_ID, relative, "draft", "approved", "event-1",
                       "unused", drop=("decision_ref",)),
        encoding="utf-8",
    )
    result = run_inspect(tmp_path)
    assert result.returncode == 1
    assert "audit-corruption" in result.stdout


def test_SDD_FR_145_proxy_event_requires_schema_v2(tmp_path: Path):
    make_spec(tmp_path)
    relative = _approved_requirement(tmp_path)
    (tmp_path / ".spec" / "STATE.md").write_text(
        "# STATE\n\n"
        + _proxy_event(REQ_ID, relative, "draft", "approved", "event-1",
                       ".spec/STATE.md", schema_version=1),
        encoding="utf-8",
    )
    result = run_inspect(tmp_path)
    assert result.returncode == 1
    assert "audit-corruption" in result.stdout


def test_SDD_FR_145_schema_v2_requires_proxy_kind(tmp_path: Path):
    make_spec(tmp_path)
    relative = _approved_requirement(tmp_path)
    (tmp_path / ".spec" / "STATE.md").write_text(
        "# STATE\n\n"
        + _proxy_event(REQ_ID, relative, "draft", "approved", "event-1",
                       ".spec/STATE.md", kind="agent"),
        encoding="utf-8",
    )
    result = run_inspect(tmp_path)
    assert result.returncode == 1
    assert "audit-corruption" in result.stdout


def test_SDD_FR_145_missing_decision_ref_file_warns_but_passes(tmp_path: Path):
    make_spec(tmp_path)
    relative = _approved_requirement(tmp_path)
    (tmp_path / ".spec" / "STATE.md").write_text(
        "# STATE\n\n"
        + _proxy_event(REQ_ID, relative, "draft", "approved", "event-1",
                       ".spec/spec-issues/GONE.md"),
        encoding="utf-8",
    )
    result = run_inspect(tmp_path)
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")
    assert result.returncode == 0, report
    assert "decision-ref参照先が見つかりません" in report
    assert "PASS" in report


# ---- SDD-FR-143 / SI-SDD-026: baseline 監査（CLI迂回の事後検出） ---------------


def _audit_workspace(tmp_path: Path, baseline_status: str) -> str:
    """git 管理下の workspace を作り、baseline コミットの SHA を返す。"""
    make_spec(tmp_path)
    write_active_requirement(tmp_path, baseline_status)
    (tmp_path / ".spec" / "tasks" / f"{TASK_ID}.md").write_text(
        f"---\nimplements: {REQ_ID}\ndepends_on: []\nstatus: done\n---\n",
        encoding="utf-8",
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "baseline")
    return _git(tmp_path, "rev-parse", "HEAD").stdout.strip()


def _declare_baseline(tmp_path: Path, baseline: str):
    (tmp_path / ".spec" / "PROJECT.md").write_text(
        f"---\naudit_baseline: {baseline}\n---\n\n# テスト用ワークスペース\n",
        encoding="utf-8",
    )


def test_SDD_FR_143_audit_baseline_undeclared_skips_audit(tmp_path: Path):
    """audit_baseline 未宣言なら、無記録の promotion があっても従来どおり PASS する。"""
    _audit_workspace(tmp_path, "verified")
    write_active_requirement(tmp_path, "promoted")  # spec update を通さない手編集

    result = run_inspect(tmp_path)
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")

    assert result.returncode == 0, report
    assert "audit-corruption" not in report
    assert "PASS" in report


def test_SDD_FR_143_audit_baseline_detects_unrecorded_promotion(tmp_path: Path):
    """宣言済み workspace では、event を伴わない verified→promoted を検出して FAIL する。"""
    baseline = _audit_workspace(tmp_path, "verified")
    write_active_requirement(tmp_path, "promoted")
    _declare_baseline(tmp_path, baseline)

    result = run_inspect(tmp_path, "--check-only")

    assert result.returncode == 1
    assert "audit-corruption" in result.stdout
    assert REQ_ID in result.stdout
    assert "spec update を迂回した手編集の疑い" in result.stdout


def test_SDD_FR_143_audit_baseline_detects_unrecorded_chain_start(tmp_path: Path):
    """記録済み event より前に未記録の approved 到達があれば検出する。"""
    baseline = _audit_workspace(tmp_path, "draft")
    write_active_requirement(tmp_path, "verified")
    relative = f".spec/requirements/{REQ_ID}.md"
    (tmp_path / ".spec" / "STATE.md").write_text(
        "# STATE\n\n"
        + _state_event(REQ_ID, relative, "approved", "implementing", "event-1")
        + _state_event(REQ_ID, relative, "implementing", "verified", "event-2"),
        encoding="utf-8",
    )
    _declare_baseline(tmp_path, baseline)

    result = run_inspect(tmp_path, "--check-only")

    assert result.returncode == 1
    assert "audit-corruption" in result.stdout
    assert "'draft' から 'approved' へ" in result.stdout


def test_SDD_FR_143_audit_baseline_accepts_recorded_transition(tmp_path: Path):
    """正規CLI経由で記録された遷移は baseline 監査を通過する。"""
    baseline = _audit_workspace(tmp_path, "verified")
    write_active_requirement(tmp_path, "promoted")
    ref = f".spec/spec-issues/{ISSUE_ID}.md"
    issue = tmp_path / ref
    issue.parent.mkdir(parents=True, exist_ok=True)
    issue.write_text(f"---\nid: {ISSUE_ID}\nstatus: accepted\n---\n- 裁定\n", encoding="utf-8")
    (tmp_path / ".spec" / "STATE.md").write_text(
        "# STATE\n\n"
        + _proxy_event(
            REQ_ID, f".spec/requirements/{REQ_ID}.md", "verified", "promoted", "event-1", ref
        ),
        encoding="utf-8",
    )
    _declare_baseline(tmp_path, baseline)

    result = run_inspect(tmp_path)
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")

    assert result.returncode == 0, report
    assert "audit-corruption" not in report
    assert "PASS" in report


def test_SDD_FR_143_audit_baseline_unresolvable_is_warning_not_failure(tmp_path: Path):
    """baseline commit を解決できない環境では FAIL させず WARN に落とす。"""
    _audit_workspace(tmp_path, "verified")
    write_active_requirement(tmp_path, "promoted")
    _declare_baseline(tmp_path, "0" * 40)

    result = run_inspect(tmp_path)
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")

    assert result.returncode == 0, report
    assert "baseline監査を実行できません" in report
    assert "PASS" in report
