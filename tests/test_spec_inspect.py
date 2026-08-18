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


def test_multi_workspace_task_reference_resolves_sibling_task(tmp_path: Path):
    """複数 workspace 検査では、他 workspace の実在タスク ID も既知として扱う。"""
    root = tmp_path / "root"
    make_spec(root)
    plugin = tmp_path / "plugin"
    plugin_tasks = make_spec(plugin)
    (plugin_tasks / f"{TASK_ID2}.md").write_text(
        f"---\nimplements: {REQ_ID}\ndepends_on: []\n---\n\n### sibling task\n",
        encoding="utf-8",
    )
    write_root_test(root, f'"""実装タスクは {TASK_ID2}。"""\n')

    res = run_inspect_multi(root, plugin)

    assert res.returncode == 0, res.stdout
    assert TASK_ID2 not in section_body(report_of(root), GHOST_SECTION)


def test_single_workspace_does_not_resolve_external_task(tmp_path: Path):
    """単一 workspace 検査では、検査対象外のタスク ID を既知化しない。"""
    root = tmp_path / "root"
    make_spec(root)
    write_root_test(root, f'"""検査対象外の実装タスクは {TASK_ID2}。"""\n')

    res = run_inspect(root)

    assert res.returncode == 1
    assert TASK_ID2 in section_body(report_of(root), GHOST_SECTION)


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


# ---- SDD-FR-146 / 147 / 148: 未参照判定の正確化（SI-SDD-014） ----

TRACE_REQ_ID = "TR-FR-" + "001"
TRACE_GHOST_ID = "TR-FR-" + "902"

AUTO_SECTION = "## テスト/実装からの参照がない要件（approved以降）"
MANUAL_SECTION = "## 参照がない manual-check 要件"
EXTERNAL_SECTION = "## 他ワークスペースのテスト/実装から参照されている要件"
GHOST_SECTION = "## 幽霊参照（存在しないIDへの参照）"


def section_body(report: str, heading: str) -> str:
    """レポートから見出し直下のブロックを取り出す（次の見出しまで）"""
    lines = report.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(heading):
            body = []
            for rest in lines[i + 1:]:
                if rest.startswith("## "):
                    break
                body.append(rest)
            return "\n".join(body)
    raise AssertionError(f"見出しが見つかりません: {heading}\n---\n{report}")


def make_plugin_workspace(tmp_path: Path, vmethod: str = "unit-test"):
    """ルート ws（tests/ を持つ）+ プラグイン ws（要件1件）の fixture を構築する"""
    root = tmp_path / "root"
    make_spec(root)
    plugin = tmp_path / "plugin"
    req_dir = plugin / ".spec" / "requirements"
    req_dir.mkdir(parents=True)
    (req_dir / f"{TRACE_REQ_ID}.md").write_text(
        f"---\nid: {TRACE_REQ_ID}\nversion: 1.0\nstatus: approved\n"
        f"domain: verification\nverification_method: {vmethod}\n---\n\n"
        f"### {TRACE_REQ_ID} 参照判定の対象要件\n",
        encoding="utf-8",
    )
    (plugin / ".spec" / "tasks").mkdir(parents=True)
    return root, plugin


def write_root_test(root: Path, body: str):
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_plugin_feature.py").write_text(body, encoding="utf-8")


def report_of(root: Path) -> str:
    return (root / ".spec" / "inspection-report.md").read_text(encoding="utf-8")


def test_SDD_FR_146_root_test_reference_resolves_plugin_requirement(tmp_path: Path):
    """canonical 実行では、ルート tests からの参照でプラグイン要件の未参照が解消する。"""
    root, plugin = make_plugin_workspace(tmp_path)
    write_root_test(root, f'"""{TRACE_REQ_ID}: プラグイン要件の検証。"""\n')

    res = run_inspect_multi(root, plugin)

    assert res.returncode == 0, res.stdout
    report = report_of(plugin)
    assert TRACE_REQ_ID not in section_body(report, AUTO_SECTION)
    external = section_body(report, EXTERNAL_SECTION)
    assert TRACE_REQ_ID in external
    # 参照元のワークスペース名と相対パスを識別できること
    assert "root/tests/test_plugin_feature.py" in external


def test_SDD_FR_146_reports_use_checkout_independent_workspace_ids(tmp_path: Path):
    """Git 配下の参照元は repo 相対で表し、checkout 名が違ってもレポートを同一にする。"""
    source = tmp_path / "source"
    make_spec(source)
    root_req = source / ".spec" / "requirements" / f"{REQ_ID}.md"
    root_req.write_text(
        f"---\nid: {REQ_ID}\nversion: 1.0\nstatus: approved\n"
        "domain: verification\nverification_method: unit-test\n---\n\n"
        f"### {REQ_ID} ルート要件\n",
        encoding="utf-8",
    )

    plugin = source / "plugins" / "demo"
    plugin_req = plugin / ".spec" / "requirements"
    plugin_req.mkdir(parents=True)
    (plugin_req / f"{TRACE_REQ_ID}.md").write_text(
        f"---\nid: {TRACE_REQ_ID}\nversion: 1.0\nstatus: approved\n"
        "domain: verification\nverification_method: unit-test\n---\n\n"
        f"### {TRACE_REQ_ID} プラグイン要件\n",
        encoding="utf-8",
    )
    (plugin / ".spec" / "tasks").mkdir(parents=True)
    write_root_test(source, f'"""{TRACE_REQ_ID}: プラグイン要件の検証。"""\n')
    plugin_tests = plugin / "tests"
    plugin_tests.mkdir()
    (plugin_tests / "test_root_feature.py").write_text(
        f'"""{REQ_ID}: ルート要件の検証。"""\n', encoding="utf-8"
    )
    init_git(source)

    reports = []
    for checkout_name in ("checkout-alpha", "checkout-beta"):
        checkout = tmp_path / checkout_name
        subprocess.run(
            ["git", "clone", "-q", str(source), str(checkout)],
            check=True,
            capture_output=True,
            text=True,
        )
        result = run_inspect_multi(checkout, checkout / "plugins" / "demo")
        assert result.returncode == 0, result.stdout
        reports.append((report_of(checkout), report_of(checkout / "plugins" / "demo")))

    assert reports[0] == reports[1]
    root_external = section_body(reports[0][0], EXTERNAL_SECTION)
    plugin_external = section_body(reports[0][1], EXTERNAL_SECTION)
    assert "plugins/demo/tests/test_root_feature.py" in root_external
    assert "./tests/test_plugin_feature.py" in plugin_external
    assert "checkout-alpha" not in reports[0][0] + reports[0][1]
    assert "checkout-beta" not in reports[1][0] + reports[1][1]


def test_SDD_FR_146_single_workspace_inspection_is_unchanged(tmp_path: Path):
    """同じ配置でも単一ワークスペース検査では集約せず、未参照のまま報告する。"""
    root, plugin = make_plugin_workspace(tmp_path)
    write_root_test(root, f'"""{TRACE_REQ_ID}: プラグイン要件の検証。"""\n')

    res = run_inspect(plugin)

    assert res.returncode == 0, res.stdout
    report = report_of(plugin)
    assert TRACE_REQ_ID in section_body(report, AUTO_SECTION)
    assert section_body(report, EXTERNAL_SECTION).strip() == "- なし ✅"


def test_SDD_FR_146_unreferenced_requirement_still_reported(tmp_path: Path):
    """どのワークスペースからも参照されない要件は、集約後も未参照として残る。"""
    root, plugin = make_plugin_workspace(tmp_path)
    write_root_test(root, '"""無関係なテスト。"""\n')

    res = run_inspect_multi(root, plugin)

    assert res.returncode == 0, res.stdout
    assert TRACE_REQ_ID in section_body(report_of(plugin), AUTO_SECTION)


def test_SDD_FR_146_aggregation_keeps_ghost_detection_and_exit_code(tmp_path: Path):
    """集約は幽霊参照の検出と終了コードを変えない。"""
    root, plugin = make_plugin_workspace(tmp_path)
    write_root_test(root, f'"""{TRACE_REQ_ID}: 検証。"""\n')
    (plugin / ".spec" / "tasks" / f"{TASK_ID}.md").write_text(
        f"---\nimplements: {TRACE_GHOST_ID}\ndepends_on: []\n---\n\n### 幽霊を参照するタスク\n",
        encoding="utf-8",
    )

    res = run_inspect_multi(root, plugin)

    assert res.returncode == 1, res.stdout
    report = report_of(plugin)
    assert TRACE_GHOST_ID in section_body(report, GHOST_SECTION)
    assert "FAIL" in report


def test_SDD_FR_147_implementation_script_reference_resolves(tmp_path: Path):
    """skills/<name>/scripts/ のコードによる参照で未参照が解消する。"""
    root, plugin = make_plugin_workspace(tmp_path)
    scripts = plugin / "skills" / "demo" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "demo_tool.py").write_text(
        f'"""{TRACE_REQ_ID} を実装するツール。"""\n', encoding="utf-8"
    )

    res = run_inspect(plugin)

    assert res.returncode == 0, res.stdout
    assert TRACE_REQ_ID not in section_body(report_of(plugin), AUTO_SECTION)


def test_SDD_FR_147_markdown_in_scripts_dir_is_not_implementation_reference(tmp_path: Path):
    """追加走査対象の Markdown による言及は実装参照として数えない。"""
    root, plugin = make_plugin_workspace(tmp_path)
    scripts = plugin / "skills" / "demo" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "README.md").write_text(f"{TRACE_REQ_ID} の解説。\n", encoding="utf-8")

    res = run_inspect(plugin)

    assert res.returncode == 0, res.stdout
    assert TRACE_REQ_ID in section_body(report_of(plugin), AUTO_SECTION)


def test_SDD_FR_147_example_id_in_implementation_code_is_not_ghost(tmp_path: Path):
    """実装コードの docstring に書かれた使用例の ID を幽霊参照にしない。"""
    root, plugin = make_plugin_workspace(tmp_path)
    scripts = plugin / "skills" / "demo" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "demo_tool.py").write_text(
        f'"""使用例: demo_tool.py --impact {TRACE_GHOST_ID}"""\n', encoding="utf-8"
    )

    res = run_inspect(plugin)

    assert res.returncode == 0, res.stdout
    report = report_of(plugin)
    assert TRACE_GHOST_ID not in section_body(report, GHOST_SECTION)
    assert "PASS" in report


def test_SDD_FR_147_ghost_detection_in_existing_subdirs_unchanged(tmp_path: Path):
    """従来の走査対象での幽霊参照の検出は変わらない。"""
    root, plugin = make_plugin_workspace(tmp_path)
    (plugin / ".spec" / "tasks" / f"{TASK_ID}.md").write_text(
        f"---\nimplements: {TRACE_GHOST_ID}\ndepends_on: []\n---\n\n### 幽霊を参照するタスク\n",
        encoding="utf-8",
    )

    res = run_inspect(plugin)

    assert res.returncode == 1, res.stdout
    assert TRACE_GHOST_ID in section_body(report_of(plugin), GHOST_SECTION)


def test_SDD_FR_147_workspace_without_extra_dirs_is_unchanged(tmp_path: Path):
    """追加走査対象を持たないワークスペースの結果は従来どおり。"""
    root, plugin = make_plugin_workspace(tmp_path)

    res = run_inspect(plugin)

    assert res.returncode == 0, res.stdout
    report = report_of(plugin)
    assert TRACE_REQ_ID in section_body(report, AUTO_SECTION)
    assert "PASS" in report


def test_SDD_FR_148_manual_check_requirement_is_listed_separately(tmp_path: Path):
    """manual-check 要件は自動検証要件の未参照リストへ入れず、専用見出しへ分離する。"""
    root, plugin = make_plugin_workspace(tmp_path, vmethod="manual-check")

    res = run_inspect(plugin)

    assert res.returncode == 0, res.stdout
    report = report_of(plugin)
    assert TRACE_REQ_ID not in section_body(report, AUTO_SECTION)
    assert TRACE_REQ_ID in section_body(report, MANUAL_SECTION)
    assert "検証記録で担保" in report


def test_SDD_FR_148_automated_requirement_stays_in_original_section(tmp_path: Path):
    """自動検証要件は従来どおりの見出しへ列挙され、manual-check 側へ移らない。"""
    root, plugin = make_plugin_workspace(tmp_path, vmethod="unit-test")

    res = run_inspect(plugin)

    assert res.returncode == 0, res.stdout
    report = report_of(plugin)
    assert TRACE_REQ_ID in section_body(report, AUTO_SECTION)
    assert TRACE_REQ_ID not in section_body(report, MANUAL_SECTION)


def test_SDD_FR_148_separation_does_not_change_exit_code(tmp_path: Path):
    """未参照の分離報告は PASS / FAIL 判定を変えない。"""
    root, manual_ws = make_plugin_workspace(tmp_path, vmethod="manual-check")
    auto_ws = tmp_path / "auto"
    auto_req = auto_ws / ".spec" / "requirements"
    auto_req.mkdir(parents=True)
    (auto_req / f"{REQ_ID}.md").write_text(
        f"---\nid: {REQ_ID}\nversion: 1.0\nstatus: approved\n"
        "domain: verification\nverification_method: unit-test\n---\n\n"
        f"### {REQ_ID} 自動検証要件\n",
        encoding="utf-8",
    )
    (auto_ws / ".spec" / "tasks").mkdir(parents=True)

    assert run_inspect(manual_ws).returncode == 0
    assert run_inspect(auto_ws).returncode == 0


# ────────────────────────────────────────────────────────────────
# SDD-FR-153: 検証証跡の構造検証と参照切れ検出
# ────────────────────────────────────────────────────────────────

EVIDENCE_SECTION = "## 検証証跡（.spec/verification/"
EVIDENCE_WARN_SECTION = "## 検証証跡の WARN"
EVIDENCE_SCHEMA = "bitzsdd/verification-evidence@1"
VERIFIED_REQ_ID = "FR-" + "010"


def init_git(root: Path) -> str:
    """fixture を git リポジトリにして HEAD の SHA を返す"""
    def git(*args: str):
        return subprocess.run(["git", *args], cwd=str(root),
                              capture_output=True, text=True, check=True)
    git("init", "-q", ".")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "test")
    git("add", "-A")
    git("commit", "-qm", "init")
    return git("rev-parse", "HEAD").stdout.strip()


def make_evidence_workspace(tmp_path: Path, *, vmethod: str = "unit-test",
                            status: str = "verified"):
    """verified 要件 + 完了タスクを持つ、証跡検査用のワークスペース"""
    make_spec(tmp_path)
    req_dir = tmp_path / ".spec" / "requirements"
    (req_dir / f"{VERIFIED_REQ_ID}.md").write_text(
        f"---\nid: {VERIFIED_REQ_ID}\nversion: 1.0\nstatus: {status}\n"
        f"domain: verification\nverification_method: {vmethod}\n---\n\n"
        f"### {VERIFIED_REQ_ID} 証跡検査の対象要件\n",
        encoding="utf-8",
    )
    (tmp_path / ".spec" / "tasks" / f"{TASK_ID2}.md").write_text(
        f"---\nimplements: {VERIFIED_REQ_ID}\ndepends_on: []\nstatus: done\n---\n\n"
        "### 証跡検査の対象タスク\n",
        encoding="utf-8",
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_evidence_target.py").write_text(
        f'"""{VERIFIED_REQ_ID}: 対象要件の検証。"""\n', encoding="utf-8"
    )
    return init_git(tmp_path)


def write_evidence(root: Path, name: str = "pytest", **overrides):
    payload = {
        "schema": EVIDENCE_SCHEMA,
        "command_id": name,
        "command": ["pytest", "-q"],
        "cwd": ".",
        "commit": overrides.pop("commit", "0" * 40),
        "dirty": False,
        "recorded_at": "2026-07-29T00:00:00Z",
        "tool": {"name": "pytest", "version": "8.0.0"},
        "exit_code": 0,
        "counts": {"passed": 1, "failed": 0, "errors": 0, "skipped": 0},
        "requirements": [VERIFIED_REQ_ID],
        "observed": {"duration_seconds": 1.23},
    }
    payload.update(overrides)
    for key in [k for k, v in payload.items() if v is _DROP]:
        del payload[key]
    directory = root / ".spec" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}--abcdef1.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class _Drop:
    pass


_DROP = _Drop()


def test_SDD_FR_153_workspace_without_evidence_dir_is_unchanged(tmp_path: Path):
    """証跡ディレクトリが無いワークスペースは従来どおり無検査で PASS する"""
    make_evidence_workspace(tmp_path)

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    report = report_of(tmp_path)
    assert "PASS ✅" in report
    assert EVIDENCE_SECTION not in report


def test_SDD_FR_153_valid_evidence_is_listed_and_passes(tmp_path: Path):
    """正しい証跡は FAIL にならず、専用セクションへ一覧される"""
    head = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit=head)

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    report = report_of(tmp_path)
    assert "PASS ✅" in report
    assert VERIFIED_REQ_ID in section_body(report, EVIDENCE_SECTION)
    assert "検証証跡: 1" in report


def test_SDD_FR_153_unreadable_evidence_fails(tmp_path: Path):
    """JSON として読めない証跡は FAIL"""
    make_evidence_workspace(tmp_path)
    directory = tmp_path / ".spec" / "verification"
    directory.mkdir(parents=True)
    (directory / "broken--abcdef1.json").write_text("{ not json", encoding="utf-8")

    res = run_inspect(tmp_path)

    assert res.returncode == 1
    assert "読み取れません" in report_of(tmp_path)


def test_SDD_FR_153_unknown_schema_fails(tmp_path: Path):
    """想定外の schema 識別子は FAIL"""
    head = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit=head, schema="something/else@9")

    res = run_inspect(tmp_path)

    assert res.returncode == 1
    assert "schema" in report_of(tmp_path)


def test_SDD_FR_153_missing_required_key_fails(tmp_path: Path):
    """必須キーの欠落は欠落名つきで FAIL"""
    head = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit=head, recorded_at=_DROP)

    res = run_inspect(tmp_path)

    assert res.returncode == 1
    report = report_of(tmp_path)
    assert "必須キー" in report
    assert "recorded_at" in report


def test_SDD_FR_153_nonzero_exit_code_fails(tmp_path: Path):
    """失敗した実行の証跡は FAIL（記録しただけで通してはいけない）"""
    head = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit=head, exit_code=1)

    res = run_inspect(tmp_path)

    assert res.returncode == 1
    assert "exit_code=1" in report_of(tmp_path)


def test_SDD_FR_153_failed_counts_fail(tmp_path: Path):
    """終了コードが 0 でも failed 件数があれば FAIL"""
    head = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit=head,
                   counts={"passed": 1, "failed": 2, "errors": 0, "skipped": 0})

    res = run_inspect(tmp_path)

    assert res.returncode == 1
    assert "失敗・エラーが 2 件" in report_of(tmp_path)


def test_SDD_FR_153_dangling_requirement_reference_fails(tmp_path: Path):
    """存在しない要件を指す証跡は参照切れとして FAIL"""
    head = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit=head, requirements=[GHOST_ID])

    res = run_inspect(tmp_path)

    assert res.returncode == 1
    report = report_of(tmp_path)
    assert "参照切れ" in report
    assert GHOST_ID in report


def test_SDD_FR_153_empty_requirements_fails(tmp_path: Path):
    """検証対象が空の証跡は FAIL（何を担保したのか不明なため）"""
    head = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit=head, requirements=[])

    res = run_inspect(tmp_path)

    assert res.returncode == 1
    assert "requirements が空" in report_of(tmp_path)


def test_SDD_FR_153_unresolvable_commit_is_warn_not_fail(tmp_path: Path):
    """解決できない commit の証跡は安全側で WARN に留める（FAIL にはしない）"""
    make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit="1" * 40)

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    report = report_of(tmp_path)
    assert "PASS ✅" in report
    assert "以降にソースが変更されています" in section_body(report, EVIDENCE_WARN_SECTION)


def test_SDD_FR_153_evidence_from_earlier_commit_is_current_when_only_evidence_changed(
    tmp_path: Path,
):
    """証跡ファイルをコミットしただけで古い扱いにしない（HEAD 一致は原理的に不可能なため）"""
    previous = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit=previous)
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), check=True,
                   capture_output=True, text=True)
    subprocess.run(["git", "commit", "-qm", "record evidence"], cwd=str(tmp_path),
                   check=True, capture_output=True, text=True)

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    report = report_of(tmp_path)
    assert "PASS ✅" in report
    assert "以降にソースが変更" not in section_body(report, EVIDENCE_WARN_SECTION)


def test_SDD_FR_153_evidence_is_stale_when_source_changed_after_recording(tmp_path: Path):
    """証跡の commit 以降にソースが変わったら WARN（再記録が必要）"""
    previous = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit=previous)
    (tmp_path / "tests" / "test_evidence_target.py").write_text(
        f'"""{VERIFIED_REQ_ID}: 変更後の検証。"""\n', encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), check=True,
                   capture_output=True, text=True)
    subprocess.run(["git", "commit", "-qm", "change source"], cwd=str(tmp_path),
                   check=True, capture_output=True, text=True)

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    assert "以降にソースが変更されています" in section_body(
        report_of(tmp_path), EVIDENCE_WARN_SECTION
    )


def test_SDD_FR_153_dirty_evidence_is_warn_not_fail(tmp_path: Path):
    """未コミット状態で記録された暫定証跡は WARN に留める"""
    head = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, commit=head, dirty=True)

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    assert "暫定証跡" in section_body(report_of(tmp_path), EVIDENCE_WARN_SECTION)


def test_SDD_FR_153_verified_without_evidence_is_warn_not_fail(tmp_path: Path):
    """証跡ディレクトリがあるのに証跡が無い verified 要件は WARN（加法的導入）"""
    head = make_evidence_workspace(tmp_path)
    write_evidence(tmp_path, name="other", commit=head, requirements=[REQ_ID])

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    report = report_of(tmp_path)
    assert "PASS ✅" in report
    warn_body = section_body(report, EVIDENCE_WARN_SECTION)
    assert VERIFIED_REQ_ID in warn_body
    assert "検証証跡がありません" in warn_body


def test_SDD_FR_153_manual_check_requirement_needs_no_evidence(tmp_path: Path):
    """manual-check 要件は証跡が無くても WARN を出さない"""
    head = make_evidence_workspace(tmp_path, vmethod="manual-check")
    write_evidence(tmp_path, commit=head, requirements=[REQ_ID])

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    assert VERIFIED_REQ_ID not in section_body(report_of(tmp_path), EVIDENCE_WARN_SECTION)


# --- GatePassage（SDD-FR-155） -----------------------------------------------

GATE_ID = "X-" + "GATE-" + "001"
GATE_SECTION = "## Gate 通過記録"


def make_gate_workspace(tmp_path: Path, *, gate="promotion", scope=None,
                        decision_refs=(".spec/reports/decision-sample.md",),
                        omit=(), gate_id=GATE_ID):
    """要件1件と裁定記録1件を持つ WS に GatePassage を1件置く"""
    make_spec(tmp_path)
    (tmp_path / ".spec" / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".spec" / "reports" / "decision-sample.md").write_text(
        "# 裁定記録\n", encoding="utf-8")
    scope = [REQ_ID] if scope is None else scope
    fields = {
        "id": gate_id,
        "gate": gate,
        "date": "2026-07-30",
        "arbiter": "hide",
        "scope": "[" + ", ".join(scope) + "]",
        "checklist_ref": "skills/sdd-core/references/gates.md#3-promotion-gate",
    }
    lines = [f"{key}: {value}" for key, value in fields.items() if key not in omit]
    if "confirmed_decision_refs" not in omit:
        lines.append("confirmed_decision_refs:")
        lines += [f"  - {ref}" for ref in decision_refs]
    path = tmp_path / ".spec" / "gates" / f"{gate_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + "\n".join(lines) + "\n---\n\n# 通過記録\n", encoding="utf-8")
    return path


def test_SDD_FR_155_absent_gates_dir_is_silent(tmp_path: Path):
    """.spec/gates/ が無いワークスペースでは何も報告しない（既存 WS を遡及的に FAIL させない）"""
    make_spec(tmp_path)

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    report = report_of(tmp_path)
    assert "PASS ✅" in report
    assert GATE_SECTION not in report


def test_SDD_FR_155_valid_gate_passage_passes_and_is_listed(tmp_path: Path):
    """必須項目の揃った GatePassage は PASS し、レポートの専用節に現れる"""
    make_gate_workspace(tmp_path)

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    report = report_of(tmp_path)
    assert "PASS ✅" in report
    assert GATE_ID in section_body(report, GATE_SECTION)


def test_SDD_FR_155_missing_required_key_fails(tmp_path: Path):
    """必須 frontmatter（arbiter）の欠落を検出して FAIL する"""
    make_gate_workspace(tmp_path, omit=("arbiter",))

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert f"[gate] {GATE_ID}: arbiter が未記入" in report_of(tmp_path)


def test_SDD_FR_155_unknown_gate_kind_fails(tmp_path: Path):
    """gate の値が統制語彙（discovery / design / promotion）の外なら FAIL する"""
    make_gate_workspace(tmp_path, gate="release")

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "gate 'release' は語彙外" in report_of(tmp_path)


def test_SDD_FR_155_scope_ghost_reference_fails(tmp_path: Path):
    """scope が存在しない ID を指していれば幽霊参照として FAIL する"""
    make_gate_workspace(tmp_path, scope=[GHOST_ID])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert f"scope の {GHOST_ID} が存在しない" in report_of(tmp_path)


def test_SDD_FR_155_missing_decision_ref_target_fails(tmp_path: Path):
    """confirmed_decision_refs の参照先が実在しなければ FAIL する"""
    make_gate_workspace(tmp_path, decision_refs=[".spec/reports/decision-missing.md"])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "confirmed_decision_refs の参照先が存在しない" in report_of(tmp_path)


def test_SDD_FR_155_decision_ref_outside_workspace_fails(tmp_path: Path):
    """confirmed_decision_refs がワークスペース外を指していれば FAIL する"""
    make_gate_workspace(tmp_path, decision_refs=["/etc/hosts"])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "confirmed_decision_refs は" in report_of(tmp_path)


def test_SDD_FR_155_filename_id_mismatch_fails(tmp_path: Path):
    """ファイル名と id の不一致を検出する"""
    path = make_gate_workspace(tmp_path)
    path.rename(path.parent / "other-name.md")

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "ファイル名と id" in report_of(tmp_path)


def test_SDD_FR_155_checklist_ref_anchor_is_not_truncated(tmp_path: Path):
    """checklist_ref の `#アンカー` をコメントとして切り落とさない"""
    sys.path.insert(0, str(INSPECT_SCRIPT.parent))
    import spec_inspect

    fm = spec_inspect.parse_frontmatter_full(
        "---\nchecklist_ref: refs/gates.md#3-promotion-gate\nnote: value # 注記\n---\n"
    )

    assert fm["checklist_ref"] == "refs/gates.md#3-promotion-gate"
    assert fm["note"] == "value"


# --- ReviewFinding（SDD-FR-158 / 159 / 160 / 161） ----------------------------

REV_ID = "XX-" + "REV-" + "001"
SYN = "SYN-" + "001"


def base_finding(**overrides):
    finding = {
        "id": f"{REV_ID}:{SYN}",
        "priority": "P1",
        "severity": "major",
        "source": ["OPS-601"],
        "title": "サンプル指摘",
        "recommendation": "サンプルの是正内容",
        "tracked_by": ISSUE_ID,
        "status": "tracked",
    }
    finding.update(overrides)
    return finding


def base_precondition(**overrides):
    precondition = {
        "id": "GP-001",
        "from": f"{REV_ID}:{SYN}",
        "condition": "サンプル前提条件",
        "kind": "blocking",
        "basis": "verified",
        "evidence": ".spec/reviews/individual/operations.json",
    }
    precondition.update(overrides)
    return precondition


def gp_response(original, status="accepted", **overrides):
    response = {
        "status": status,
        "original": original,
        "normalized": "実装向け表現",
        "target": ".spec/design/sample.md#section",
    }
    response.update(overrides)
    return response


def make_review_workspace(tmp_path: Path, *, findings=None, preconditions=None,
                          verdict="CONDITIONAL_PASS", carried_over=None,
                          schema_version=2, archived=True, view_id=REV_ID):
    """spec-issue 1件を持つ WS に番号付きレビューと review-synthesis ビューを置く"""
    make_spec(tmp_path)
    (tmp_path / ".spec" / "spec-issues").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".spec" / "spec-issues" / f"{ISSUE_ID}.md").write_text(
        f"---\nid: {ISSUE_ID}\nstatus: open\n---\n- 目的: サンプル\n", encoding="utf-8")
    reviews = tmp_path / ".spec" / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    payload = {
        "review_id": REV_ID,
        "verdict": verdict,
        "findings": [base_finding()] if findings is None else findings,
        "gate_preconditions": ([base_precondition()] if preconditions is None
                               else preconditions),
    }
    if schema_version is not None:
        payload["schema_version"] = schema_version
    if carried_over is not None:
        payload["carried_over"] = carried_over
    if archived:
        (reviews / f"{REV_ID}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        (reviews / f"{REV_ID}.md").write_text(
            f"---\nid: {REV_ID}\nstatus: active\ndecision: {verdict}\n---\n\n# レビュー\n",
            encoding="utf-8")
    (reviews / "review-synthesis.json").write_text(
        json.dumps({"view_of": view_id, "review_id": view_id,
                    "path": f"{view_id}.json"}, ensure_ascii=False), encoding="utf-8")
    (reviews / "review-synthesis.md").write_text(
        f"---\nview_of: {view_id}\npath: {view_id}.md\n---\n\n# ビュー\n", encoding="utf-8")
    return reviews


def test_SDD_FR_160_missing_archive_fails(tmp_path: Path):
    """ビューが指す番号付きファイルが無ければアーカイブ漏れとして FAIL する"""
    make_review_workspace(tmp_path, archived=False)

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert f"アーカイブ漏れ: .spec/reviews/review-synthesis.json が指す {REV_ID}.json" \
        in report_of(tmp_path)


def test_SDD_FR_160_view_without_review_id_fails(tmp_path: Path):
    """ビューが review_id を持たなければ FAIL する"""
    reviews = make_review_workspace(tmp_path)
    (reviews / "review-synthesis.json").write_text("{}", encoding="utf-8")

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "review_id がない" in report_of(tmp_path)


def test_SDD_FR_160_view_and_archive_coexist_without_duplicate_id(tmp_path: Path):
    """ビューと番号付きファイルが併存しても ID 重複にならない"""
    make_review_workspace(tmp_path)

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    report = report_of(tmp_path)
    assert "PASS ✅" in report
    assert "[重複]" not in report


def test_SDD_FR_160_carried_over_ghost_reference_fails(tmp_path: Path):
    """carried_over の取り込み元 finding が実在しなければ幽霊参照として FAIL する"""
    make_review_workspace(tmp_path, carried_over=[f"{REV_ID}:SYN-" + "099"])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "取り込み元に" in report_of(tmp_path)


def test_SDD_FR_160_carried_over_existing_finding_passes(tmp_path: Path):
    """実在する finding を指す carried_over は通る"""
    make_review_workspace(tmp_path, carried_over=[f"{REV_ID}:{SYN}"])

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout


def test_SDD_FR_158_missing_required_finding_key_fails(tmp_path: Path):
    """findings の必須キー欠落を finding ID 付きで報告する"""
    finding = base_finding()
    del finding["recommendation"]
    make_review_workspace(tmp_path, findings=[finding])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "必須キー 'recommendation' が無い" in report_of(tmp_path)


def test_SDD_FR_158_unqualified_finding_id_fails(tmp_path: Path):
    """レビュー内連番のままの finding ID は形式違反として報告する"""
    make_review_workspace(tmp_path, findings=[base_finding(id=SYN)])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "<REV-ID>:SYN-NNN 形式" in report_of(tmp_path)


def test_SDD_FR_158_controlled_vocabulary_is_enforced(tmp_path: Path):
    """priority / severity / status の語彙外を検出する"""
    make_review_workspace(tmp_path, findings=[base_finding(status="wip")])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "status 'wip' は語彙外" in report_of(tmp_path)


def test_SDD_FR_158_legacy_review_without_schema_version_is_skipped(tmp_path: Path):
    """schema_version を持たないレビューは遡及的に不整合としない"""
    make_review_workspace(tmp_path, schema_version=None,
                          findings=[{"id": SYN, "priority": "P0", "title": "旧書式"}])

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    assert "PASS ✅" in report_of(tmp_path)


def test_SDD_FR_159_untracked_p0_fails(tmp_path: Path):
    """tracked_by が空の P0 は未紐づけとして FAIL する"""
    make_review_workspace(tmp_path, findings=[base_finding(priority="P0", tracked_by="")])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "未紐づけの P0/P1 finding がある" in report_of(tmp_path)


def test_SDD_FR_159_untracked_p3_is_allowed(tmp_path: Path):
    """P2/P3 は tracked_by が空でもよい（キーは置く）"""
    make_review_workspace(tmp_path,
                          findings=[base_finding(priority="P3", severity="info",
                                                 tracked_by="", status="open")])

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout


def test_SDD_FR_159_pass_verdict_with_untracked_p1_fails(tmp_path: Path):
    """未紐づけの P0/P1 がある状態で verdict: PASS を出せない"""
    make_review_workspace(tmp_path, verdict="PASS",
                          findings=[base_finding(tracked_by="")])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "verdict: PASS を出せない" in report_of(tmp_path)


def test_SDD_FR_159_tracked_by_ghost_spec_issue_fails(tmp_path: Path):
    """tracked_by が実在しない spec-issue を指せば幽霊参照として FAIL する"""
    make_review_workspace(tmp_path,
                          findings=[base_finding(tracked_by="SI-" + "TEST-" + "999")])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "が存在しない（幽霊参照）" in report_of(tmp_path)


def test_SDD_FR_159_tracked_by_gate_precondition_resolves(tmp_path: Path):
    """tracked_by が <REV-ID>:GP-NNN 形式なら同一レビューの gate_preconditions で解決する"""
    make_review_workspace(tmp_path,
                          findings=[base_finding(tracked_by=f"{REV_ID}:GP-001")])

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout


def test_SDD_FR_159_tracked_by_unknown_gate_precondition_fails(tmp_path: Path):
    """存在しない GP を指す tracked_by は幽霊参照として FAIL する"""
    make_review_workspace(tmp_path,
                          findings=[base_finding(tracked_by=f"{REV_ID}:GP-" + "099")])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "gate_preconditions に無い" in report_of(tmp_path)


def test_SDD_FR_161_missing_kind_or_basis_fails(tmp_path: Path):
    """gate_preconditions の kind / basis 欠落を検出する"""
    precondition = base_precondition()
    del precondition["kind"]
    make_review_workspace(tmp_path, preconditions=[precondition])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "kind は blocking / agenda のいずれか" in report_of(tmp_path)


def test_SDD_FR_161_assumed_blocking_violates_invariant(tmp_path: Path):
    """basis: assumed を根拠に kind: blocking は立てられない（不変条件）"""
    make_review_workspace(tmp_path,
                          preconditions=[base_precondition(basis="assumed",
                                                           kind="blocking")])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "不変条件違反" in report_of(tmp_path)


def test_SDD_FR_161_assumed_agenda_is_allowed(tmp_path: Path):
    """未検証の想定は agenda（Gate で決める論点）としてなら置ける"""
    make_review_workspace(tmp_path,
                          findings=[base_finding(tracked_by=f"{REV_ID}:GP-001")],
                          preconditions=[base_precondition(basis="assumed",
                                                           kind="agenda",
                                                           evidence=None)])

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout


def test_SDD_FR_161_verified_basis_requires_evidence(tmp_path: Path):
    """basis: verified には実測の所在が必要"""
    precondition = base_precondition()
    del precondition["evidence"]
    make_review_workspace(tmp_path, preconditions=[precondition])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "実測の所在（evidence）が必要" in report_of(tmp_path)


def test_SI_SDD_042_unknown_gp_kind_fails(tmp_path: Path):
    make_review_workspace(tmp_path, preconditions=[base_precondition(gp_kind="unknown")])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "gp_kind は behavioral / artifact / process のいずれか" in report_of(tmp_path)


def test_SI_SDD_042_behavioral_gp_requires_ears(tmp_path: Path):
    make_review_workspace(tmp_path, preconditions=[base_precondition(gp_kind="behavioral")])

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "gp_kind: behavioral には ears が必要" in report_of(tmp_path)


def test_SI_SDD_042_behavioral_gp_requires_when_and_shall(tmp_path: Path):
    make_review_workspace(
        tmp_path,
        preconditions=[base_precondition(gp_kind="behavioral", ears="SHALL だけ")],
    )

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "WHEN 節と SHALL を含める" in report_of(tmp_path)


def test_SI_SDD_042_behavioral_gp_with_ears_passes(tmp_path: Path):
    ears = "WHEN 操作を適用する THEN system SHALL 現在値を照合する"
    make_review_workspace(
        tmp_path,
        preconditions=[base_precondition(
            gp_kind="behavioral",
            ears=ears,
            response=gp_response(ears),
        )],
    )

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout


def test_SI_SDD_042_non_behavioral_gp_does_not_require_ears(tmp_path: Path):
    for gp_kind in ("artifact", "process"):
        workspace = tmp_path / gp_kind
        make_review_workspace(
            workspace,
            preconditions=[base_precondition(
                gp_kind=gp_kind,
                response=gp_response("サンプル前提条件"),
            )],
        )

        res = run_inspect(workspace)

        assert res.returncode == 0, res.stdout


def test_SI_SDD_042_classified_blocking_gp_requires_response(tmp_path: Path):
    make_review_workspace(
        tmp_path,
        preconditions=[base_precondition(gp_kind="artifact")],
    )

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "分類済み blocking GP には response が必要" in report_of(tmp_path)


def test_SI_SDD_042_response_original_must_match_gp_verbatim(tmp_path: Path):
    make_review_workspace(
        tmp_path,
        preconditions=[base_precondition(
            gp_kind="artifact",
            response=gp_response("意味を変えた文"),
        )],
    )

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    assert "GP 原文と逐語一致" in report_of(tmp_path)


def test_SI_SDD_042_rejected_requires_reason_and_rereview(tmp_path: Path):
    response = gp_response("サンプル前提条件", status="rejected")
    response.pop("normalized")
    response.pop("target")
    make_review_workspace(
        tmp_path,
        preconditions=[base_precondition(gp_kind="process", response=response)],
    )

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    report = report_of(tmp_path)
    assert "rejected response には reason が必要" in report
    assert "rejected response には rereview が必要" in report


def test_SI_SDD_042_rejected_with_evidence_passes(tmp_path: Path):
    response = gp_response(
        "サンプル前提条件",
        status="rejected",
        reason="前提が実測と矛盾する",
        rereview="independent-review-record",
    )
    response.pop("normalized")
    response.pop("target")
    make_review_workspace(
        tmp_path,
        preconditions=[base_precondition(gp_kind="process", response=response)],
    )

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout


def test_SI_SDD_042_deferred_requires_valid_tracking_contract(tmp_path: Path):
    response = gp_response(
        "サンプル前提条件",
        status="deferred",
        tracking_target="tracking-record",
        deadline="later",
        gate="unknown",
    )
    response.pop("normalized")
    response.pop("target")
    make_review_workspace(
        tmp_path,
        preconditions=[base_precondition(gp_kind="artifact", response=response)],
    )

    res = run_inspect(tmp_path)

    assert res.returncode != 0
    report = report_of(tmp_path)
    assert "deadline は YYYY-MM-DD 形式" in report
    assert "gate は discovery / design / promotion のいずれか" in report


def test_SI_SDD_042_deferred_with_tracking_contract_passes(tmp_path: Path):
    response = gp_response(
        "サンプル前提条件",
        status="deferred",
        tracking_target="tracking-record",
        deadline="2026-09-01",
        gate="promotion",
    )
    response.pop("normalized")
    response.pop("target")
    make_review_workspace(
        tmp_path,
        preconditions=[base_precondition(gp_kind="artifact", response=response)],
    )

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout


# --- 設計成果物の走査範囲と ID 一意性（SDD-FR-162） ---------------------------

# fixture 用の設計 ID は連結で組み立てる（このリポジトリ自身の走査が
# 本ファイルを幽霊参照として誤検知しないように。ファイル冒頭の流儀に合わせる）
DSN = "DSN-"


def write_design(root: Path, relpath: str, did: str, status: str = "draft"):
    path = root / ".spec" / "design" / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: {did}\ntitle: \"設計\"\nstatus: {status}\n---\n\n# {did} 設計\n",
        encoding="utf-8",
    )
    return path


def test_SDD_FR_162_design_subdirectory_artifact_is_scanned(tmp_path: Path):
    """design のサブディレクトリ（stories/ 等）の成果物が Traceability Matrix に現れる。

    非再帰 glob では `design/stories/` の成果物が機械検証の対象外だった（SI-SDD-036）。
    """
    make_spec(tmp_path)
    did = DSN + "006"
    write_design(tmp_path, "stories/story-p1-sample.md", did)

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    assert did in report_of(tmp_path), \
        "design のサブディレクトリの成果物が Matrix に現れなければならない"


def test_SDD_FR_162_duplicate_id_across_subdirectory_fails(tmp_path: Path):
    """design 直下とサブディレクトリで ID が重複したら FAIL する。"""
    make_spec(tmp_path)
    did = DSN + "006"
    write_design(tmp_path, f"{did}.md", did)
    write_design(tmp_path, "stories/story-p1-sample.md", did)

    res = run_inspect(tmp_path)

    assert res.returncode != 0, "重複 ID は無検出のままにしてはならない"
    assert "IDが重複している" in report_of(tmp_path)


def test_SDD_FR_162_duplicate_id_report_shows_both_paths(tmp_path: Path):
    """重複 ID の報告に衝突した両方のパスが含まれる（どちらを改番するか判断できる）。"""
    make_spec(tmp_path)
    did = DSN + "006"
    write_design(tmp_path, f"{did}.md", did)
    write_design(tmp_path, "stories/story-p1-sample.md", did)

    run_inspect(tmp_path)
    report = report_of(tmp_path)

    duplicate_lines = [ln for ln in report.splitlines() if "IDが重複している" in ln]
    assert duplicate_lines, report
    line = duplicate_lines[0]
    assert f"design/{did}.md" in line, line
    assert "design/stories/story-p1-sample.md" in line, line


def test_SDD_FR_162_underscore_prefixed_design_file_is_ignored(tmp_path: Path):
    """`_` 始まりのファイルは走査範囲の拡大後も検査対象外（作業メモ用の逃げ道）。"""
    make_spec(tmp_path)
    path = tmp_path / ".spec" / "design" / "stories" / "_wip.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("本文だけで frontmatter を持たない作業メモ\n", encoding="utf-8")

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    assert "_wip.md" not in report_of(tmp_path)


def test_SDD_FR_162_requirements_scan_stays_non_recursive(tmp_path: Path):
    """requirements は再帰しない（design 以外の走査範囲は変えない）。"""
    make_spec(tmp_path)
    nested = tmp_path / ".spec" / "requirements" / "archive"
    nested.mkdir(parents=True)
    (nested / "old.md").write_text("frontmatter を持たない旧稿\n", encoding="utf-8")

    res = run_inspect(tmp_path)

    assert res.returncode == 0, res.stdout
    assert "archive/old.md" not in report_of(tmp_path)


# ---- SDD-FR-168: ガバナンス主張の機械検証 ----


def make_governance_workspace(root: Path, *, status: str = "verified") -> dict:
    tasks = make_spec(root)
    write_active_requirement(root, status)
    if status in {"verified", "promoted"}:
        (tasks / f"{TASK_ID}.md").write_text(
            f"---\nimplements: {REQ_ID}\ndepends_on: []\nstatus: done\n---\n",
            encoding="utf-8",
        )
    design = root / ".spec" / "design" / "sample.md"
    design.parent.mkdir(parents=True)
    design.write_text("---\nid: DSN-001\nstatus: active\n---\n", encoding="utf-8")
    reports = root / ".spec" / "reports"
    reports.mkdir(parents=True)
    (reports / "decision-sample.md").write_text("# 裁定記録\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "decision_claims": [{
            "subject": "sample-decision",
            "decision_ref": ".spec/reports/decision-sample.md",
            "claim_sources": [".spec/design/sample.md"],
        }],
        "authorities": [{
            "topic": "sample-contract",
            "source": ".spec/design/sample.md",
            "claim_sources": [".spec/design/sample.md"],
        }],
        "design_constraints": [{
            "design": ".spec/design/sample.md",
            "requirement": REQ_ID,
            "alignment": "compliant",
        }],
    }


def write_governance_claims(root: Path, payload: dict) -> None:
    (root / ".spec" / "governance-claims.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_SDD_FR_168_valid_governance_claims_pass(tmp_path: Path):
    payload = make_governance_workspace(tmp_path)
    write_governance_claims(tmp_path, payload)
    result = run_inspect(tmp_path)
    assert result.returncode == 0, report_of(tmp_path)


def test_SDD_FR_168_missing_decision_record_fails(tmp_path: Path):
    payload = make_governance_workspace(tmp_path)
    payload["decision_claims"][0]["decision_ref"] = ".spec/reports/decision-missing.md"
    write_governance_claims(tmp_path, payload)
    result = run_inspect(tmp_path)
    assert result.returncode != 0
    assert "decision_ref: 参照先が存在しない" in report_of(tmp_path)


def test_SDD_FR_168_duplicate_authority_topic_fails(tmp_path: Path):
    payload = make_governance_workspace(tmp_path)
    payload["authorities"].append(dict(payload["authorities"][0]))
    write_governance_claims(tmp_path, payload)
    result = run_inspect(tmp_path)
    assert result.returncode != 0
    assert "同一topicの正が複数ある" in report_of(tmp_path)


def test_SDD_FR_168_non_verified_constraint_fails(tmp_path: Path):
    payload = make_governance_workspace(tmp_path, status="approved")
    write_governance_claims(tmp_path, payload)
    result = run_inspect(tmp_path)
    assert result.returncode != 0
    assert "requirement は verified/promoted ではない" in report_of(tmp_path)


def test_SDD_FR_168_verified_constraint_conflict_fails(tmp_path: Path):
    payload = make_governance_workspace(tmp_path)
    payload["design_constraints"][0]["alignment"] = "conflict"
    write_governance_claims(tmp_path, payload)
    result = run_inspect(tmp_path)
    assert result.returncode != 0
    assert "verified制約との競合が宣言されている" in report_of(tmp_path)


def test_SDD_FR_168_manifest_is_optional_for_existing_workspace(tmp_path: Path):
    make_spec(tmp_path)
    result = run_inspect(tmp_path)
    assert result.returncode == 0, report_of(tmp_path)
