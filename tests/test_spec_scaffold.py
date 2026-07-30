"""CORE-FR-004 / CORE-FR-010 spec_scaffold.py の回帰テスト（テスト先行）。

CORE-FR-004: 採番の一意性・連番・001 起番、生成物の spec_inspect PASS（書式互換）、
既存ファイル非上書き、副作用の限定（.spec/ 配下のみ）を検証する。
CORE-FR-010: 生成時の統制語彙検証（verification_method / domain / status）と
DSN（design）種別の追加。語彙外は exit≠0・雛形非生成、語彙は spec_inspect と単一定義。
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "bitz-sdd" / "skills" / "sdd-core" / "scripts"
)
SCAFFOLD = SCRIPTS_DIR / "spec_scaffold.py"
INSPECT = SCRIPTS_DIR / "spec_inspect.py"

# fixture 用 ID は連結で組み立てる（このリポジトリ自身の spec_inspect 走査が
# 本ファイルを幽霊参照として誤検知しないように。test_spec_status.py と同じ流儀）
FR = "FR-"
NFR = "NFR-"
TSK = "TSK-"


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_req(root: Path, num: int, status: str = "approved", prefix: str = "CORE-" + FR[:-1]):
    rid = f"{prefix}-{num:03d}"
    _write(root / ".spec" / "requirements" / f"{rid}.md",
           f"---\nid: {rid}\nversion: 1.0\nstatus: {status}\ndomain: tooling\n"
           f"verification_method: example-test\n---\n\n### {rid} サンプル\n"
           f"- **受入基準 (EARS)**:\n  - WHEN x する THEN y すること SHALL\n")
    return rid


def run(*args, **kw):
    return subprocess.run([sys.executable, str(SCAFFOLD), *map(str, args)],
                          capture_output=True, text=True, **kw)


def snapshot(root: Path):
    snap = set()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            snap.add(str(p.relative_to(root)))
    return snap


# --- 採番 -------------------------------------------------------------------

def test_first_number_is_001(tmp_path):
    """同一プレフィックスの既存 ID が無ければ 001 を採番する。"""
    (tmp_path / ".spec" / "requirements").mkdir(parents=True)
    res = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1])
    assert res.returncode == 0, res.stderr
    assert (tmp_path / ".spec" / "requirements" / f"CORE-{FR}001.md").exists()


def test_next_number_is_max_plus_one(tmp_path):
    """既存 ID の最大番号 + 1 を採番する（連番の欠けは詰めない）。"""
    make_req(tmp_path, 1)
    make_req(tmp_path, 7)
    res = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1])
    assert res.returncode == 0, res.stderr
    assert (tmp_path / ".spec" / "requirements" / f"CORE-{FR}008.md").exists()
    # 出力に採番した ID が現れる
    assert f"CORE-{FR}008" in res.stdout


def test_prefix_isolation(tmp_path):
    """採番はプレフィックス単位。別プレフィックスの番号に影響されない。"""
    nfr_prefix = "CORE-" + NFR[:-1]             # 連結で組み立て（自リポジトリの幽霊検知回避）
    make_req(tmp_path, 5)                        # FR 側
    make_req(tmp_path, 9, prefix=nfr_prefix)     # NFR 側
    res = run(tmp_path, "requirement", "--prefix", nfr_prefix)
    assert res.returncode == 0, res.stderr
    assert (tmp_path / ".spec" / "requirements" / f"CORE-{NFR}010.md").exists()


# --- 書式互換（spec_inspect PASS）-------------------------------------------

def test_generated_requirement_passes_inspect(tmp_path):
    """生成された要件雛形は spec_inspect の検証を PASS する。"""
    (tmp_path / ".spec" / "requirements").mkdir(parents=True)
    res = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1],
              "--domain", "tooling", "--title", "サンプル要件")
    assert res.returncode == 0, res.stderr
    insp = subprocess.run([sys.executable, str(INSPECT), str(tmp_path)],
                          capture_output=True, text=True)
    rid = f"CORE-{FR}001"
    # 生成した要件に対する lint/frontmatter 問題が無いこと
    problem_lines = [ln for ln in insp.stdout.splitlines()
                     if rid in ln and ("[lint]" in ln or "[frontmatter]" in ln or "[domain]" in ln)]
    assert not problem_lines, f"生成物が spec_inspect で問題検出: {problem_lines}"


def test_generated_task_references_requirement(tmp_path):
    """生成されたタスク雛形は implements 先の要件を参照でき、幽霊参照にならない。"""
    rid = make_req(tmp_path, 1)
    (tmp_path / ".spec" / "tasks").mkdir(parents=True)
    res = run(tmp_path, "task", "--implements", rid, "--prefix", "CORE-" + TSK[:-1])
    assert res.returncode == 0, res.stderr
    task_file = tmp_path / ".spec" / "tasks" / f"CORE-{TSK}001.md"
    assert task_file.exists()
    assert rid in task_file.read_text(encoding="utf-8")


def test_generated_spec_issue_has_open_status(tmp_path):
    """生成された spec-issue は status: open で作られる。"""
    (tmp_path / ".spec" / "spec-issues").mkdir(parents=True)
    res = run(tmp_path, "spec-issue", "--prefix", "SI-CORE")
    assert res.returncode == 0, res.stderr
    f = tmp_path / ".spec" / "spec-issues" / "SI-CORE-001.md"
    assert f.exists()
    assert "status: open" in f.read_text(encoding="utf-8")


def test_spec_issue_with_delegation_fields(tmp_path):
    """SDD-FR-132: --origin / --delegated-to 指定時は spec-issue の frontmatter に反映される。"""
    delegated = "sub:" + FR + "101"
    res = run(tmp_path, "spec-issue", "--prefix", "SI-CORE",
              "--origin", "root", "--delegated-to", delegated)
    assert res.returncode == 0, res.stderr
    text = (tmp_path / ".spec" / "spec-issues" / "SI-CORE-001.md").read_text(encoding="utf-8")
    assert "origin: root" in text
    assert f"delegated_to: {delegated}" in text


def test_spec_issue_without_delegation_fields_omits_them(tmp_path):
    """SDD-FR-132: 委託フィールド未指定なら frontmatter に出力しない（既存書式の後方互換）。"""
    res = run(tmp_path, "spec-issue", "--prefix", "SI-CORE")
    assert res.returncode == 0, res.stderr
    text = (tmp_path / ".spec" / "spec-issues" / "SI-CORE-001.md").read_text(encoding="utf-8")
    assert "delegated_to" not in text
    assert "origin" not in text.split("---")[1]  # frontmatter 部に origin 行が無い


# --- 非上書き・副作用の限定 --------------------------------------------------

def test_refuses_overwrite(tmp_path):
    """指定番号のファイルが既に存在する場合は上書きせず非ゼロで失敗する。"""
    make_req(tmp_path, 3)
    res = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1], "--number", "3")
    assert res.returncode != 0, "既存ファイルを上書きしてはならない"
    # 既存ファイルが変わっていない（雛形で潰されていない）
    assert "サンプル" in (tmp_path / ".spec" / "requirements" / f"CORE-{FR}003.md").read_text(encoding="utf-8")


def test_side_effect_only_under_spec(tmp_path):
    """副作用は .spec/ 配下への新規ファイル生成のみ。他ディレクトリを変更しない。"""
    (tmp_path / ".spec" / "requirements").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "keep.md").write_text("keep", encoding="utf-8")
    before_outside = snapshot(tmp_path / "docs")
    run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1])
    after_outside = snapshot(tmp_path / "docs")
    assert before_outside == after_outside


# --- 生成時語彙検証（CORE-FR-010）------------------------------------------

def test_invalid_verification_method_fails(tmp_path):
    """語彙外の --verification-method は非ゼロで失敗し雛形を生成しない。"""
    (tmp_path / ".spec" / "requirements").mkdir(parents=True)
    before = snapshot(tmp_path)
    res = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1],
              "--verification-method", "inspection")  # 語彙外（正は example-test）
    assert res.returncode != 0, "語彙外の verification_method を弾くべき"
    assert snapshot(tmp_path) == before, "失敗時は雛形を生成しない"


def test_valid_verification_method_succeeds(tmp_path):
    """語彙内の --verification-method は従来どおり生成できる（後方互換）。"""
    (tmp_path / ".spec" / "requirements").mkdir(parents=True)
    res = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1],
              "--verification-method", "manual-check")
    assert res.returncode == 0, res.stderr


def test_SDD_FR_124_unit_test_verification_method_succeeds(tmp_path):
    """SDD-FR-124: unit-test は統制語彙として要件雛形へ指定できる。"""
    (tmp_path / ".spec" / "requirements").mkdir(parents=True)
    res = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1],
              "--verification-method", "unit-test")
    assert res.returncode == 0, res.stderr
    generated = tmp_path / ".spec" / "requirements" / f"CORE-{FR}001.md"
    assert "verification_method: unit-test" in generated.read_text(encoding="utf-8")


def test_invalid_domain_fails_when_domains_present(tmp_path):
    """domains.md がある時、語彙外の --domain は非ゼロで失敗し雛形を生成しない。"""
    req_dir = tmp_path / ".spec" / "requirements"
    req_dir.mkdir(parents=True)
    (req_dir / "domains.md").write_text(
        "| code | 意味 |\n|---|---|\n| tooling | ツール |\n", encoding="utf-8")
    before = snapshot(tmp_path)
    res = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1],
              "--domain", "nonexistent")
    assert res.returncode != 0, "domains.md 語彙外の domain を弾くべき"
    assert snapshot(tmp_path) == before, "失敗時は雛形を生成しない"


def test_domain_skipped_when_no_domains_file(tmp_path):
    """domains.md が無ければ domain 検証はスキップして生成する（縮退挙動）。"""
    (tmp_path / ".spec" / "requirements").mkdir(parents=True)
    res = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1],
              "--domain", "anything")
    assert res.returncode == 0, res.stderr


def test_vocab_single_source_with_inspect(tmp_path):
    """語彙は spec_inspect と単一定義を共有する（scaffold 側で二重定義しない）。"""
    src = SCAFFOLD.read_text(encoding="utf-8")
    assert "from spec_inspect import" in src or "import spec_inspect" in src, \
        "spec_inspect から語彙を import すべき"
    assert "VMETHODS =" not in src and "STATUSES =" not in src, \
        "scaffold 側に語彙をリテラル再定義してはならない（単一の正）"


# --- DSN（design）種別（CORE-FR-010）---------------------------------------

def test_design_scaffold_passes_inspect(tmp_path):
    """design 種別は id と既定 status:draft を持ち spec_inspect を PASS する。"""
    (tmp_path / ".spec" / "design").mkdir(parents=True)
    res = run(tmp_path, "design", "--prefix", "DSN", "--title", "サンプル設計")
    assert res.returncode == 0, res.stderr
    f = tmp_path / ".spec" / "design" / "DSN-001.md"
    assert f.exists()
    text = f.read_text(encoding="utf-8")
    assert "id: DSN-001" in text
    assert "status: draft" in text
    insp = subprocess.run([sys.executable, str(INSPECT), str(tmp_path)],
                          capture_output=True, text=True)
    problem = [ln for ln in insp.stdout.splitlines()
               if "DSN-001" in ln and ("[構造]" in ln or "[frontmatter]" in ln)]
    assert not problem, f"DSN 生成物が spec_inspect で問題検出: {problem}"


def test_design_invalid_status_fails(tmp_path):
    """design の --status が STATUSES 語彙外なら非ゼロで失敗し雛形を生成しない。"""
    (tmp_path / ".spec" / "design").mkdir(parents=True)
    before = snapshot(tmp_path)
    res = run(tmp_path, "design", "--prefix", "DSN", "--status", "bogus")
    assert res.returncode != 0, "語彙外の status を弾くべき"
    assert snapshot(tmp_path) == before, "失敗時は雛形を生成しない"


def test_design_number_skips_suffixed_existing_file(tmp_path):
    """既存の DSN ファイルが説明的サフィックス付き（例: DSN-001-delegation-registry.md）でも、
    採番はそれを走査対象に含め番号が重複しない（SI-SDD-006 の回帰）。"""
    design_dir = tmp_path / ".spec" / "design"
    design_dir.mkdir(parents=True)
    (design_dir / "DSN-001-delegation-registry.md").write_text(
        "---\nid: DSN-001\ntitle: \"既存\"\nstatus: active\n---\n", encoding="utf-8")
    res = run(tmp_path, "design", "--prefix", "DSN", "--title", "新規設計")
    assert res.returncode == 0, res.stderr
    # 期待ファイル名を直書きすると spec_inspect がリポジトリに実在しない設計 ID への
    # 幽霊参照として検出するため、番号から組み立てる
    expected = design_dir / f"DSN-{2:03d}.md"
    assert expected.exists(), "サフィックス付き既存ファイルの番号を見逃してはならない"
    assert not (design_dir / "DSN-001.md").exists(), "既存の DSN-001 と ID が重複してはならない"


# --- SDD-FR-144: 排他的・回復可能な公開 -------------------------------------


def test_SDD_FR_144_existing_workspace_lock_fails_without_output(tmp_path):
    req_dir = tmp_path / ".spec" / "requirements"
    req_dir.mkdir(parents=True)
    (tmp_path / ".spec" / ".mutation-lock").write_text("{}", encoding="utf-8")

    result = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1])

    assert result.returncode != 0
    assert "mutation-conflict" in result.stderr
    assert not list(req_dir.glob("CORE-*.md"))


def test_SDD_FR_144_success_cleans_lock_and_journal(tmp_path):
    req_dir = tmp_path / ".spec" / "requirements"
    req_dir.mkdir(parents=True)

    result = run(tmp_path, "requirement", "--prefix", "CORE-" + FR[:-1])

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / ".spec" / ".mutation-lock").exists()
    transactions = tmp_path / ".spec" / ".transactions"
    assert not list(transactions.glob("*.json"))
    assert (req_dir / f"CORE-{FR}001.md").read_text(encoding="utf-8").endswith("\n")


# --- GatePassage 種別（SDD-FR-155） -------------------------------------------

GATE = "GATE-"


def make_decision_record(root: Path, name="decision-sample.md") -> str:
    rel = f".spec/reports/{name}"
    _write(root / rel, "# 裁定記録\n")
    return rel


def run_gate(root, *extra):
    return run(root, "gate", "--prefix", "CORE-" + GATE[:-1], *extra)


def test_SDD_FR_155_gate_scaffold_produces_inspect_pass(tmp_path):
    """gate 種別の雛形は spec_inspect を PASS する（CORE-FR-004 の雛形契約）"""
    rid = make_req(tmp_path, 1)
    ref = make_decision_record(tmp_path)

    res = run_gate(tmp_path, "--gate", "promotion", "--arbiter", "hide",
                   "--scope", rid, "--decision-ref", ref)

    assert res.returncode == 0, res.stderr
    generated = tmp_path / ".spec" / "gates" / f"CORE-{GATE}001.md"
    assert generated.exists()
    inspect = subprocess.run([sys.executable, str(INSPECT), str(tmp_path)],
                             capture_output=True, text=True)
    assert inspect.returncode == 0, inspect.stdout
    report = (tmp_path / ".spec" / "inspection-report.md").read_text(encoding="utf-8")
    assert "PASS ✅" in report
    assert f"CORE-{GATE}001" in report


def test_SDD_FR_155_gate_scaffold_writes_expected_frontmatter(tmp_path):
    """scope / confirmed_decision_refs / checklist_ref が雛形に載る"""
    rid = make_req(tmp_path, 1)
    rid2 = make_req(tmp_path, 2)
    ref = make_decision_record(tmp_path)

    res = run_gate(tmp_path, "--gate", "promotion", "--arbiter", "hide",
                   "--scope", f"{rid},{rid2}", "--decision-ref", ref)

    assert res.returncode == 0, res.stderr
    text = (tmp_path / ".spec" / "gates" / f"CORE-{GATE}001.md").read_text(encoding="utf-8")
    assert f"scope: [{rid}, {rid2}]" in text
    assert f"  - {ref}" in text
    assert "checklist_ref: skills/sdd-core/references/gates.md#3-promotion-gate" in text


def test_SDD_FR_155_gate_scaffold_accepts_multiple_decision_refs(tmp_path):
    """--decision-ref は複数回指定できる（1回の Gate が複数の裁定記録を確認する）"""
    rid = make_req(tmp_path, 1)
    first = make_decision_record(tmp_path, "decision-a.md")
    second = make_decision_record(tmp_path, "decision-b.md")

    res = run_gate(tmp_path, "--gate", "design", "--arbiter", "hide", "--scope", rid,
                   "--decision-ref", first, "--decision-ref", second)

    assert res.returncode == 0, res.stderr
    text = (tmp_path / ".spec" / "gates" / f"CORE-{GATE}001.md").read_text(encoding="utf-8")
    assert f"  - {first}" in text and f"  - {second}" in text


def test_SDD_FR_155_gate_scaffold_requires_mandatory_flags(tmp_path):
    """必須フラグが欠けたら生成前に非ゼロで失敗する（空の雛形を作らない）"""
    make_req(tmp_path, 1)

    res = run_gate(tmp_path, "--gate", "promotion", "--arbiter", "hide")

    assert res.returncode != 0
    assert "--scope" in res.stderr and "--decision-ref" in res.stderr
    assert not (tmp_path / ".spec" / "gates").exists()


def test_SDD_FR_155_gate_scaffold_rejects_unknown_gate_kind(tmp_path):
    """gate 種別が統制語彙の外なら argparse が拒否する"""
    make_req(tmp_path, 1)

    res = run_gate(tmp_path, "--gate", "release", "--arbiter", "hide", "--scope", "X")

    assert res.returncode != 0
    assert not (tmp_path / ".spec" / "gates").exists()


def test_SDD_FR_155_gate_scaffold_numbers_sequentially(tmp_path):
    """同一プレフィックスの GatePassage は連番で採番される"""
    rid = make_req(tmp_path, 1)
    ref = make_decision_record(tmp_path)
    args = ("--gate", "promotion", "--arbiter", "hide", "--scope", rid, "--decision-ref", ref)

    assert run_gate(tmp_path, *args).returncode == 0
    assert run_gate(tmp_path, *args).returncode == 0

    gates = sorted(p.name for p in (tmp_path / ".spec" / "gates").glob("*.md"))
    assert gates == [f"CORE-{GATE}001.md", f"CORE-{GATE}002.md"]
