"""CORE-FR-003 spec_status.py の回帰テスト（テスト先行）。

読み取り専用の軽量状況照会スクリプトの
status 集計・フェーズ判定・JSON 構造・読み取り専用性・空状態・複数 workspace を検証する。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

STATUS_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "bitz-sdd" / "skills" / "sdd-core" / "scripts" / "spec_status.py"
)

# fixture 用 ID は連結で組み立てる（このリポジトリ自身の spec_inspect 走査が
# 本ファイルを幽霊参照として誤検知しないように。test_spec_inspect.py と同じ流儀）
FR = "FR-"
TSK = "TSK-"
DSC = "DSC-"
DSN = "DSN-"


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_spec(root: Path, *, reqs=None, issues=None, tasks=None, discovery=False,
              design=False, design_in_stories=False,
              req_origins=None, issue_implemented=None, issue_delegated=None):
    """指定した status を持つ要件/spec-issue/タスクで最小 .spec ツリーを構築する。

    reqs/issues/tasks は (連番, status) のタプルのリスト。
    design: .spec/design/ 直下に設計成果物 (DSN-*.md) を置く。
    design_in_stories: .spec/design/stories/ サブディレクトリのみに成果物を置く。
    req_origins: {連番: "origin文字列"} — 要件の origin: フィールドを差し込む。
    issue_implemented: 本文に `**実施**:` マーカーを付与する spec-issue 連番の集合。
    issue_delegated: {連番: "delegated_to文字列"} — spec-issue の delegated_to: を差し込む。
    """
    spec = root / ".spec"
    (spec / "requirements").mkdir(parents=True, exist_ok=True)
    req_origins = req_origins or {}
    issue_implemented = issue_implemented or set()
    issue_delegated = issue_delegated or {}
    for i, status in (reqs or []):
        rid = f"{FR}{i:03d}"
        origin_line = f"\norigin: {req_origins[i]}" if i in req_origins else ""
        _write(spec / "requirements" / f"{rid}.md",
                f"---\nid: {rid}\nversion: 1.0\nstatus: {status}{origin_line}\n---\n\n### {rid} サンプル要件\n")
    for i, status in (issues or []):
        iid = f"SI-CORE-{i:03d}"
        delegated_line = f"\ndelegated_to: {issue_delegated[i]}" if i in issue_delegated else ""
        body = "- 目的: サンプル\n"
        if i in issue_implemented:
            body += "- **実施**: 2026-07-18 対象 SKILL.md へ反映済み。\n"
        _write(spec / "spec-issues" / f"{iid}.md",
                f"---\nid: {iid}\nstatus: {status}{delegated_line}\n---\n{body}")
    for i, status in (tasks or []):
        tid = f"{TSK}{i:03d}"
        _write(spec / "tasks" / f"{tid}.md",
                f"---\nimplements: {FR}001\ndepends_on: []\nstatus: {status}\n---\n\n### {tid} サンプルタスク\n")
    if discovery:
        did = f"{DSC}001"
        _write(spec / "discovery" / f"{did}.md",
               f"---\nid: {did}\nstatus: draft\n---\n\n### {did} 探索\n")
    if design:
        did = f"{DSN}001"
        _write(spec / "design" / f"{did}.md",
               f"---\nid: {did}\nstatus: draft\n---\n\n### {did} 設計\n")
    if design_in_stories:
        _write(spec / "design" / "stories" / "story-001.md",
               "---\nid: story-001\nstatus: draft\n---\n\n### ドメインストーリー\n")
    return root


def run_status(*roots, json_out=False, workspace=None):
    cmd = [sys.executable, str(STATUS_SCRIPT)]
    if workspace:
        cmd += ["--workspace", *[str(w) for w in workspace]]
    else:
        cmd += [str(r) for r in roots]
    if json_out:
        cmd.append("--json")
    return subprocess.run(cmd, capture_output=True, text=True)


def snapshot(root: Path):
    """root 配下の全ファイルの相対パスと内容ハッシュのマップを返す（読み取り専用性の検査用）。"""
    snap = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            snap[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


# --- status 集計 -------------------------------------------------------------

def test_counts_by_status_text(tmp_path):
    """テキスト出力に要件・spec-issue・タスクの status 別件数が現れる。"""
    make_spec(tmp_path,
              reqs=[(1, "draft"), (2, "approved"), (3, "approved")],
              issues=[(11, "open"), (12, "accepted")],
              tasks=[(1, "done"), (2, "todo")])
    res = run_status(tmp_path)
    assert res.returncode == 0, res.stderr
    out = res.stdout
    assert "draft" in out and "approved" in out
    assert "open" in out and "accepted" in out
    assert "done" in out and "todo" in out


def test_json_structure_and_counts(tmp_path):
    """--json は集計・フェーズ・次アクションを含む機械可読な構造を返す。"""
    make_spec(tmp_path,
              reqs=[(1, "draft"), (2, "approved"), (3, "verified")],
              issues=[(11, "open")],
              tasks=[(1, "done"), (2, "todo")])
    res = run_status(tmp_path, json_out=True)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    ws = data["workspaces"][0]
    assert ws["requirements"]["total"] == 3
    assert ws["requirements"]["by_status"]["draft"] == 1
    assert ws["requirements"]["by_status"]["approved"] == 1
    assert ws["requirements"]["by_status"]["verified"] == 1
    assert ws["spec_issues"]["by_status"]["open"] == 1
    assert ws["tasks"]["by_status"]["done"] == 1
    assert ws["tasks"]["by_status"]["todo"] == 1
    assert "phase" in ws and "phase_code" in ws
    assert isinstance(ws["next_actions"], list)


# --- accepted 未着手検知 (CORE-FR-012) ---------------------------------------

def test_accepted_unaddressed_detected_when_no_origin_reference(tmp_path):
    """accepted だが origin: にも実施マーカーにも言及が無ければ未着手として検出する。"""
    make_spec(tmp_path, issues=[(11, "accepted")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["accepted_unaddressed"] == ["SI-CORE-011"]
    joined = "".join(ws["next_actions"])
    assert "accepted" in joined and "1" in joined


def test_accepted_unaddressed_excluded_when_origin_references(tmp_path):
    """要件の origin: に spec-issue ID への言及があれば未着手に含めない。"""
    make_spec(tmp_path,
              reqs=[(1, "draft")],
              issues=[(11, "accepted")],
              req_origins={1: "SI-CORE-011"})
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["accepted_unaddressed"] == []


def test_accepted_unaddressed_excluded_when_implemented_marker(tmp_path):
    """spec-issue 本文に **実施**: マーカーがあれば origin: 未参照でも未着手に含めない（軽量レーン）。"""
    make_spec(tmp_path, issues=[(11, "accepted")], issue_implemented={11})
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["accepted_unaddressed"] == []


def test_accepted_unaddressed_ignores_open_issues(tmp_path):
    """open な spec-issue は accepted ではないため未着手集計の対象外。"""
    make_spec(tmp_path, issues=[(11, "open")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["accepted_unaddressed"] == []


def test_accepted_unaddressed_cross_workspace_origin(tmp_path):
    """--workspace 複数指定時、別 workspace の requirement の origin: 参照でも解消と認める。"""
    a = make_spec(tmp_path / "a", issues=[(11, "accepted")])
    b = make_spec(tmp_path / "b", reqs=[(1, "draft")], req_origins={1: "SI-CORE-011"})
    data = json.loads(run_status(json_out=True, workspace=[a, b]).stdout)
    ws_a = next(w for w in data["workspaces"] if Path(w["root"]).name == "a")
    assert ws_a["accepted_unaddressed"] == []


def test_accepted_unaddressed_absent_from_existing_fixture(tmp_path):
    """既存フィクスチャ（accepted issue が origin 未参照）でも既存アサーションは崩れず新フィールドのみ追加される。"""
    make_spec(tmp_path,
              reqs=[(1, "draft"), (2, "approved"), (3, "approved")],
              issues=[(11, "open"), (12, "accepted")],
              tasks=[(1, "done"), (2, "todo")])
    res = run_status(tmp_path, json_out=True)
    ws = json.loads(res.stdout)["workspaces"][0]
    assert ws["accepted_unaddressed"] == ["SI-CORE-012"]


# --- 委譲済み accepted の分離集計 (SDD-FR-141) --------------------------------

def test_SDD_FR_141_delegated_unresolved_separated_from_unaddressed(tmp_path):
    """delegated_to を持ち origin 参照が無い accepted は、未着手ではなく委譲済み・未解決に計上する。"""
    make_spec(tmp_path, issues=[(11, "accepted")],
              issue_delegated={11: "bitz-sdd:SDD-FR-999"})
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["accepted_unaddressed"] == []
    assert ws["accepted_delegated_unresolved"] == ["SI-CORE-011"]
    joined = "".join(ws["next_actions"])
    assert "委譲" in joined and "SI-CORE-011" in joined


def test_SDD_FR_141_delegated_but_addressed_by_origin_not_flagged(tmp_path):
    """delegated_to があってもスコープ内 origin 参照で対応済みなら、どの未解決リストにも入れない。"""
    make_spec(tmp_path,
              reqs=[(1, "approved")],
              issues=[(11, "accepted")],
              req_origins={1: "SI-CORE-011"},
              issue_delegated={11: "bitz-sdd:SDD-FR-999"})
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["accepted_unaddressed"] == []
    assert ws["accepted_delegated_unresolved"] == []


def test_SDD_FR_141_non_delegated_still_unaddressed(tmp_path):
    """delegated_to を持たず origin 参照も実施マーカーも無いものは従来どおり未着手に計上する。"""
    make_spec(tmp_path, issues=[(11, "accepted")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["accepted_unaddressed"] == ["SI-CORE-011"]
    assert ws["accepted_delegated_unresolved"] == []


def test_SDD_FR_141_delegated_unresolved_across_scopes(tmp_path):
    """一括実行でも委譲先 origin が無ければ委譲済み・未解決として計上する（単一/一括で意味は同じ）。"""
    a = make_spec(tmp_path / "a", issues=[(11, "accepted")],
                  issue_delegated={11: "bitz-sdd:SDD-FR-999"})
    b = make_spec(tmp_path / "b", reqs=[(1, "draft")])  # SI-CORE-011 を参照しない
    data = json.loads(run_status(json_out=True, workspace=[a, b]).stdout)
    ws_a = next(w for w in data["workspaces"] if Path(w["root"]).name == "a")
    assert ws_a["accepted_delegated_unresolved"] == ["SI-CORE-011"]
    assert ws_a["accepted_unaddressed"] == []


# --- 実施記録欠落の機械警告 (SDD-FR-142) -------------------------------------

def test_SDD_FR_142_completion_record_missing_when_verified_origin_no_marker(tmp_path):
    """origin 参照元要件が verified かつ実施マーカーが無い accepted を記録欠落として警告する。"""
    make_spec(tmp_path,
              reqs=[(1, "verified")],
              issues=[(11, "accepted")],
              req_origins={1: "SI-CORE-011"})
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["completion_record_missing"] == ["SI-CORE-011"]
    assert ws["accepted_unaddressed"] == []  # 別フィールド・別警告（accepted_unaddressed は不変）
    joined = "".join(ws["next_actions"])
    assert "実施" in joined and "SI-CORE-011" in joined


def test_SDD_FR_142_no_warning_when_origin_requirement_not_verified(tmp_path):
    """origin 参照元要件が verified/promoted 未満なら記録欠落として警告しない（実装未完了）。"""
    make_spec(tmp_path,
              reqs=[(1, "approved")],
              issues=[(11, "accepted")],
              req_origins={1: "SI-CORE-011"})
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["completion_record_missing"] == []


def test_SDD_FR_142_no_warning_when_marker_present(tmp_path):
    """実施マーカーがあれば origin 要件が verified でも記録欠落に含めない。"""
    make_spec(tmp_path,
              reqs=[(1, "verified")],
              issues=[(11, "accepted")],
              req_origins={1: "SI-CORE-011"},
              issue_implemented={11})
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["completion_record_missing"] == []


def test_SDD_FR_141_142_ignore_open_and_terminal_issues(tmp_path):
    """open / deprecated / superseded の spec-issue は新フィールドいずれにも計上しない。"""
    make_spec(tmp_path,
              reqs=[(1, "verified")],
              issues=[(11, "open"), (12, "deprecated"), (13, "superseded")],
              req_origins={1: "SI-CORE-011"},
              issue_delegated={12: "bitz-sdd:SDD-FR-999"})
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["accepted_delegated_unresolved"] == []
    assert ws["completion_record_missing"] == []
    assert ws["accepted_unaddressed"] == []


def test_SDD_FR_141_142_json_keys_additive(tmp_path):
    """新フィールドは加算のみ。既存 JSON フィールドのキー・型は不変（公開契約の回帰）。"""
    make_spec(tmp_path, reqs=[(1, "draft")], issues=[(11, "accepted")], tasks=[(1, "done")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    # 既存キー（型）
    assert isinstance(ws["accepted_unaddressed"], list)
    assert isinstance(ws["next_actions"], list)
    assert isinstance(ws["requirements"]["by_status"], dict)
    # 新規キー（型）
    assert isinstance(ws["accepted_delegated_unresolved"], list)
    assert isinstance(ws["completion_record_missing"], list)


# --- 読み取り専用性 ----------------------------------------------------------

def test_read_only_no_writes(tmp_path):
    """.spec/ を含む対象ツリーへ一切書き込まない。"""
    make_spec(tmp_path,
              reqs=[(1, "approved")],
              issues=[(11, "open")],
              tasks=[(1, "todo")])
    before = snapshot(tmp_path)
    run_status(tmp_path)
    run_status(tmp_path, json_out=True)
    after = snapshot(tmp_path)
    assert before == after, "spec_status は読み取り専用でなければならない（ファイルの追加・変更を検出）"


# --- 空状態 ------------------------------------------------------------------

def test_empty_spec_no_error(tmp_path):
    """要件が0件でもエラーにならず空集計を返す。"""
    (tmp_path / ".spec" / "requirements").mkdir(parents=True)
    res = run_status(tmp_path, json_out=True)
    assert res.returncode == 0, res.stderr
    ws = json.loads(res.stdout)["workspaces"][0]
    assert ws["requirements"]["total"] == 0
    assert ws["tasks"]["total"] == 0


def test_no_valid_workspace_errors(tmp_path):
    """.spec を持たないディレクトリはエラー（非0終了）。"""
    res = run_status(tmp_path)
    assert res.returncode != 0


# --- 複数ワークスペース ------------------------------------------------------

def test_multiple_workspaces(tmp_path):
    """--workspace は複数ルートをワークスペースごとに集計する。"""
    a = make_spec(tmp_path / "a", reqs=[(1, "approved")])
    b = make_spec(tmp_path / "b", reqs=[(1, "draft"), (2, "draft")])
    res = run_status(json_out=True, workspace=[a, b])
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert len(data["workspaces"]) == 2
    totals = {Path(w["root"]).name: w["requirements"]["total"] for w in data["workspaces"]}
    assert totals["a"] == 1 and totals["b"] == 2


# --- フェーズ判定 ------------------------------------------------------------

def test_phase_map_when_untouched(tmp_path):
    """要件もタスクも discovery も無ければ Map。"""
    (tmp_path / ".spec" / "requirements").mkdir(parents=True)
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "map"


def test_phase_discovery(tmp_path):
    """discovery のみ存在すれば Discovery。"""
    make_spec(tmp_path, discovery=True)
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "discovery"


def test_phase_plan_when_only_draft(tmp_path):
    """draft 要件のみ（承認済みなし）は Plan。"""
    make_spec(tmp_path, reqs=[(1, "draft")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "plan"


def test_phase_plan_when_approved_no_tasks(tmp_path):
    """承認済み要件はあるがタスク未分解は Plan。"""
    make_spec(tmp_path, reqs=[(1, "approved")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "plan"


def test_phase_execute_when_tasks_pending(tmp_path):
    """承認済み要件＋未完了タスクがあれば Execute。"""
    make_spec(tmp_path, reqs=[(1, "approved")], tasks=[(1, "todo")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "execute"


def test_phase_verify_when_tasks_done_not_verified(tmp_path):
    """タスク完了だが要件未 verified は Verify。"""
    make_spec(tmp_path, reqs=[(1, "approved")], tasks=[(1, "done")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "verify"


def test_phase_done_when_all_verified(tmp_path):
    """全要件 verified かつタスク完了なら Done。"""
    make_spec(tmp_path, reqs=[(1, "verified")], tasks=[(1, "done")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "done"


# --- フェーズ判定: design フェーズ (SDD-FR-136) --------------------------------

def _load_status_module():
    """spec_status.py をモジュールとして読み込む（PHASE_CODES 定数の検査用）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("spec_status", STATUS_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_phase_design_when_design_artifacts_only(tmp_path):
    """設計成果物のみ（要件・タスク0件）は Design。"""
    make_spec(tmp_path, design=True)
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "design"


def test_phase_design_wins_over_discovery(tmp_path):
    """discovery と design の両方に成果物があれば Design（優先順位 design > discovery）。"""
    make_spec(tmp_path, discovery=True, design=True)
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "design"


def test_phase_design_detects_stories_subdir(tmp_path):
    """design/stories/ サブディレクトリのみの成果物でも Design と判定する（再帰検出）。"""
    make_spec(tmp_path, design_in_stories=True)
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "design"


def test_phase_plan_when_design_and_draft_req(tmp_path):
    """設計成果物があっても要件が1件でもあれば Plan 以降の判定（既存挙動の維持）。"""
    make_spec(tmp_path, design=True, reqs=[(1, "draft")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "plan"


def test_phase_code_vocabulary_is_seven_words():
    """phase_code の値集合は7語で固定（公開契約。既存値の削除・改名は後方互換違反）。"""
    mod = _load_status_module()
    assert tuple(mod.PHASE_CODES) == (
        "map", "discovery", "design", "plan", "execute", "verify", "done")


def test_design_next_action_mentions_design_gate(tmp_path):
    """Design フェーズでは next_actions が Design Gate 通過準備（sdd-review）を提示する。"""
    make_spec(tmp_path, design=True)
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    joined = "".join(ws["next_actions"])
    assert "Design Gate" in joined and "sdd-review" in joined


def test_done_label_indicates_promotion_gate(tmp_path):
    """Done の表示ラベルは Promotion Gate 待ちであることを示す。"""
    make_spec(tmp_path, reqs=[(1, "verified")], tasks=[(1, "done")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    assert ws["phase_code"] == "done"
    assert "Promotion Gate" in ws["phase"]


def test_next_action_flags_open_issues(tmp_path):
    """open な spec-issue があれば次アクションで裁定を促す。"""
    make_spec(tmp_path, reqs=[(1, "approved")], issues=[(11, "open")], tasks=[(1, "todo")])
    ws = json.loads(run_status(tmp_path, json_out=True).stdout)["workspaces"][0]
    joined = "".join(ws["next_actions"])
    assert "spec-issue" in joined or "裁定" in joined
