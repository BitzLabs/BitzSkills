import json
import os
import subprocess
import sys
from pathlib import Path

# プロジェクトルートにある元のスクリプト
CHECK_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release_check.py"


def run_check(script_path: Path):
    """CLIの検出を避けるため最小限の PATH でスクリプトを実行する"""
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent)
    return subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        env=env
    )


def test_release_check_pass(make_repo, copy_script):
    """正常な fixture の場合、exit 0 になり PASS が出力されること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    res = run_check(script)
    assert res.returncode == 0
    assert "PASS" in res.stdout


def test_release_check_mismatched_versions(make_repo, copy_script):
    """3マニフェストの version 不一致の場合、exit 1 になり該当 FAIL 行が出ること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    agy_file = repo / "plugins/demo/plugin.json"
    agy_file.write_text('{"name":"demo","version":"0.2.0"}', encoding="utf-8")
    
    res = run_check(script)
    assert res.returncode == 1
    assert "FAIL" in res.stdout
    assert "version 一致" in res.stdout


def test_release_check_missing_codex_manifest(make_repo, copy_script):
    """Codex マニフェストが欠落している場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    (repo / "plugins/demo/.codex-plugin/plugin.json").unlink()

    res = run_check(script)
    assert res.returncode == 1
    assert "マニフェスト3つの存在" in res.stdout


def test_release_check_invalid_codex_skills_path(make_repo, copy_script):
    """Codex マニフェストが skills/ を公開しない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    codex_file = repo / "plugins/demo/.codex-plugin/plugin.json"
    codex_file.write_text(
        '{"name":"demo","version":"0.1.0","skills":"skills"}',
        encoding="utf-8",
    )

    res = run_check(script)
    assert res.returncode == 1
    assert "Codex skills パス" in res.stdout


def test_release_check_ghost_plugin(make_repo, copy_script):
    """marketplace.json に実体のないプラグイン参照がある場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    marketplace = repo / ".claude-plugin/marketplace.json"
    mp_data = json.loads(marketplace.read_text(encoding="utf-8"))
    mp_data["plugins"].append({"name": "ghost", "source": "./plugins/ghost"})
    marketplace.write_text(json.dumps(mp_data), encoding="utf-8")
    
    res = run_check(script)
    assert res.returncode == 1
    assert "実体なし" in res.stdout


def test_release_check_unlisted_plugin(make_repo, copy_script):
    """marketplace.json に未列挙のプラグイン実体がある場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    # marketplace.json に記載されていない実体ディレクトリを作る
    ghost_dir = repo / "plugins/ghost/.claude-plugin"
    ghost_dir.mkdir(parents=True)
    
    res = run_check(script)
    assert res.returncode == 1
    assert "未列挙" in res.stdout


def test_release_check_missing_metadata(make_repo, copy_script):
    """SKILL.md の metadata 欠落（updated を消す等）で exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    skill_md = repo / "plugins/demo/skills/demo-skill/SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    # updated を消去
    content = content.replace("  updated: 2026-01-01\n", "")
    skill_md.write_text(content, encoding="utf-8")
    
    res = run_check(script)
    assert res.returncode == 1
    assert "updated" in res.stdout


def add_plugin(repo: Path, name: str, version: str = "0.1.0", dependencies=None,
               dependencies_by_runtime=None):
    """fixture リポジトリへプラグインを追加し marketplace に登録する。

    dependencies は3マニフェスト共通の metadata.dependencies。
    dependencies_by_runtime={"claude": [...], "agy": [...], "codex": [...]} を渡すと
    ランタイムごとに異なる宣言を書ける（不一致テスト用）。
    """
    plugin_dir = repo / "plugins" / name
    (plugin_dir / "skills").mkdir(parents=True)
    manifests = {
        "claude": plugin_dir / ".claude-plugin" / "plugin.json",
        "agy": plugin_dir / "plugin.json",
        "codex": plugin_dir / ".codex-plugin" / "plugin.json",
    }
    for runtime, path in manifests.items():
        data = {"name": name, "version": version}
        if runtime == "codex":
            data["skills"] = "./skills/"
        deps = dependencies
        if dependencies_by_runtime is not None:
            deps = dependencies_by_runtime.get(runtime)
        if deps is not None:
            data["metadata"] = {"dependencies": deps}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    marketplace = repo / ".claude-plugin/marketplace.json"
    mp_data = json.loads(marketplace.read_text(encoding="utf-8"))
    mp_data["plugins"].append({"name": name, "source": f"./plugins/{name}"})
    marketplace.write_text(json.dumps(mp_data), encoding="utf-8")


def set_demo_dependencies(repo: Path, dependencies):
    """既存 demo プラグインの3マニフェストへ metadata.dependencies を書き込む"""
    for path in (
        repo / "plugins/demo/.claude-plugin/plugin.json",
        repo / "plugins/demo/plugin.json",
        repo / "plugins/demo/.codex-plugin/plugin.json",
    ):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["metadata"] = {"dependencies": dependencies}
        path.write_text(json.dumps(data), encoding="utf-8")


def test_release_check_dependency_satisfied(make_repo, copy_script):
    """実在する依存先 + 満たされる semver 制約の宣言は PASS になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    add_plugin(repo, "base", version="1.5.0")
    set_demo_dependencies(repo, ["base>=1.4"])

    res = run_check(script)
    assert res.returncode == 0
    assert "PASS" in res.stdout


def test_release_check_dependency_missing_target(make_repo, copy_script):
    """依存先プラグインが実体に存在しない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    set_demo_dependencies(repo, ["ghost>=1.0"])

    res = run_check(script)
    assert res.returncode == 1
    assert "依存先" in res.stdout


def test_release_check_dependency_version_unsatisfied(make_repo, copy_script):
    """依存先の現行 version が semver 制約を満たさない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    add_plugin(repo, "base", version="0.9.0")
    set_demo_dependencies(repo, ["base>=1.4"])

    res = run_check(script)
    assert res.returncode == 1
    assert "制約" in res.stdout


def test_release_check_dependency_cycle(make_repo, copy_script):
    """依存グラフに循環がある場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    add_plugin(repo, "base", dependencies=["demo"])
    set_demo_dependencies(repo, ["base"])

    res = run_check(script)
    assert res.returncode == 1
    assert "循環" in res.stdout


def test_release_check_dependency_manifest_mismatch(make_repo, copy_script):
    """3マニフェストで metadata.dependencies が同値でない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    add_plugin(
        repo,
        "mixed",
        dependencies_by_runtime={
            "claude": ["demo>=0.1"],
            "agy": ["demo>=0.1"],
            "codex": ["demo>=0.2"],
        },
    )

    res = run_check(script)
    assert res.returncode == 1
    assert "dependencies 一致" in res.stdout


def test_release_check_no_dependency_declaration_stays_silent(make_repo, copy_script):
    """依存宣言を持たないプラグインは依存検証の報告対象にならず PASS のままであること（後方互換）"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)

    res = run_check(script)
    assert res.returncode == 0
    assert "依存" not in res.stdout


def test_release_check_missing_frontmatter(make_repo, copy_script):
    """SKILL.md に frontmatter 自体がない場合、exit 1 になること"""
    repo = make_repo()
    script = copy_script(repo, CHECK_SCRIPT)
    
    skill_md = repo / "plugins/demo/skills/demo-skill/SKILL.md"
    skill_md.write_text("# Demo Skill\nNo frontmatter here.", encoding="utf-8")
    
    res = run_check(script)
    assert res.returncode == 1
    assert "欠落" in res.stdout


# --- 対訳辞書 SSOT と複製の一致 (SDD-FR-137) -----------------------------------

def _make_label_repo(make_repo, body_ssot: str, body_copy=None):
    """bitz-sdd の spec_labels.py（SSOT と複製）を持つ fixture を組み立てる。"""
    repo = make_repo()
    core = repo / "plugins" / "bitz-sdd" / "skills" / "sdd-core" / "scripts"
    report = repo / "plugins" / "bitz-sdd" / "skills" / "sdd-report" / "scripts"
    core.mkdir(parents=True)
    report.mkdir(parents=True)
    (core / "spec_labels.py").write_text(body_ssot, encoding="utf-8")
    if body_copy is not None:
        (report / "spec_labels.py").write_text(body_copy, encoding="utf-8")
    return repo


def test_label_dictionary_copy_identical_passes(make_repo, copy_script):
    """SSOT と複製が完全一致していれば当該チェックは PASS。

    fixture の bitz-sdd はマニフェストを持たない最小構成のため他チェックは FAIL する。
    ここでは対訳辞書チェックの判定行だけを検査する。
    """
    repo = _make_label_repo(make_repo, "LABELS = {'a': 'あ'}\n", "LABELS = {'a': 'あ'}\n")
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert "[PASS] 対訳辞書の複製" in res.stdout


def test_label_dictionary_drift_fails(make_repo, copy_script):
    """SSOT と複製が乖離していたら FAIL（訳語が種別ごとに食い違うのを防ぐ）。"""
    repo = _make_label_repo(make_repo, "LABELS = {'a': 'あ'}\n", "LABELS = {'a': 'い'}\n")
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.returncode != 0
    assert "一致しない" in res.stdout


def test_label_dictionary_missing_copy_fails(make_repo, copy_script):
    """複製が存在しなければ FAIL。"""
    repo = _make_label_repo(make_repo, "LABELS = {'a': 'あ'}\n", None)
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.returncode != 0
    assert "複製が存在しない" in res.stdout


def test_label_dictionary_skipped_without_bitz_sdd(make_repo, copy_script):
    """bitz-sdd を含まないリポジトリでは SKIP し、既存の検査結果に影響しない。"""
    repo = make_repo()
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.returncode == 0, res.stdout
    assert "[SKIP] 対訳辞書の複製一致" in res.stdout


# ────────────────────────────────────────────────────────────────
# フェーズ正規語彙 PHASE_CODES ⇔ 文書マーカーの一致検査（SDD-FR-140）
# ────────────────────────────────────────────────────────────────

CANON = ["map", "discovery", "design", "plan", "execute", "verify", "done"]
_PHASE_STATUS_PY = (
    'PHASE_CODES = ("map", "discovery", "design", "plan", '
    '"execute", "verify", "done")\n'
)


def _phase_doc(prefix: str, marker_words, prose_words) -> str:
    """散文リスト（`w / w / ...`）とマーカーを持つ文書本文を組み立てる。

    marker_words が None のときはマーカーを省く（マーカー欠落ケース用）。
    """
    prose = "`" + " / ".join(prose_words) + "`"
    body = f"{prefix}\n\nフェーズ語彙は {prose} が正（PHASE_CODES）。\n"
    if marker_words is not None:
        body += "<!-- phase-vocabulary: " + ", ".join(marker_words) + " -->\n"
    return body


def _skill_md(marker_words, prose_words) -> str:
    fm = (
        "---\nname: sdd-core\ndescription: demo\nmetadata:\n  version: 1.0.0\n"
        "  author: test\n  created: 2026-01-01\n  updated: 2026-01-01\n---\n"
    )
    return fm + _phase_doc("# sdd-core", marker_words, prose_words)


def _make_phase_repo(make_repo, *, status_py=_PHASE_STATUS_PY,
                     skill_marker=CANON, skill_prose=CANON,
                     gates_marker=CANON, gates_prose=CANON):
    """フェーズ語彙検査に必要な bitz-sdd 相当（spec_status.py + SKILL.md + gates.md）を組む。

    対訳辞書検査（SDD-FR-137）の巻き添え FAIL を避けるため、spec_labels.py の
    SSOT と複製（同一）も用意する。
    """
    repo = make_repo()
    core = repo / "plugins" / "bitz-sdd" / "skills" / "sdd-core"
    (core / "scripts").mkdir(parents=True)
    (core / "references").mkdir(parents=True)
    (core / "scripts" / "spec_status.py").write_text(status_py, encoding="utf-8")
    (core / "SKILL.md").write_text(_skill_md(skill_marker, skill_prose), encoding="utf-8")
    (core / "references" / "gates.md").write_text(
        _phase_doc("# gates", gates_marker, gates_prose), encoding="utf-8")
    report = repo / "plugins" / "bitz-sdd" / "skills" / "sdd-report" / "scripts"
    report.mkdir(parents=True)
    (core / "scripts" / "spec_labels.py").write_text("LABELS = {}\n", encoding="utf-8")
    (report / "spec_labels.py").write_text("LABELS = {}\n", encoding="utf-8")
    return repo


def test_phase_vocab_pass(make_repo, copy_script):
    """正しいマーカー・散文リストなら両文書とも PASS 行が出る。"""
    repo = _make_phase_repo(make_repo)
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.stdout.count("[PASS] フェーズ語彙マーカー") == 2, res.stdout


def test_phase_vocab_marker_word_tampered(make_repo, copy_script):
    """マーカー内の語を1つ改竄すると FAIL（PHASE_CODES と不一致）。"""
    tampered = ["map", "discovery", "designX", "plan", "execute", "verify", "done"]
    repo = _make_phase_repo(make_repo, skill_marker=tampered)
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.returncode != 0
    assert "[FAIL] フェーズ語彙マーカー" in res.stdout
    assert "不一致" in res.stdout


def test_phase_vocab_marker_missing_word(make_repo, copy_script):
    """マーカーから語が欠落すると FAIL し、欠落語が示される。"""
    repo = _make_phase_repo(make_repo, gates_marker=CANON[:-1])  # done 欠落
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.returncode != 0
    assert "[FAIL] フェーズ語彙マーカー" in res.stdout
    assert "done" in res.stdout


def test_phase_vocab_marker_extra_word(make_repo, copy_script):
    """マーカーに余剰語があると FAIL（加算は PHASE_CODES 側と同時でなければ通さない）。"""
    repo = _make_phase_repo(make_repo, skill_marker=CANON + ["review"])
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.returncode != 0
    assert "余剰" in res.stdout
    assert "review" in res.stdout


def test_phase_vocab_prose_drift(make_repo, copy_script):
    """マーカーは正しいが可視の散文リストがドリフトしたら FAIL。"""
    drifted = ["map", "discovery", "design", "plan", "execute", "verify", "gone"]
    repo = _make_phase_repo(make_repo, skill_marker=CANON, skill_prose=drifted)
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.returncode != 0
    assert "散文リストがマーカーと不一致" in res.stdout


def test_phase_vocab_marker_absent(make_repo, copy_script):
    """マーカーが無い文書は FAIL。"""
    repo = _make_phase_repo(make_repo, skill_marker=None)
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.returncode != 0
    assert "マーカーが無い" in res.stdout


def test_phase_vocab_additive_change_passes(make_repo, copy_script):
    """PHASE_CODES への加算とマーカー・散文の同時更新は FAIL しない（加算的変更を妨げない）。"""
    extended = CANON + ["archive"]
    status_py = (
        'PHASE_CODES = ("map", "discovery", "design", "plan", '
        '"execute", "verify", "done", "archive")\n'
    )
    repo = _make_phase_repo(
        make_repo, status_py=status_py,
        skill_marker=extended, skill_prose=extended,
        gates_marker=extended, gates_prose=extended,
    )
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.stdout.count("[PASS] フェーズ語彙マーカー") == 2, res.stdout


def test_phase_vocab_skipped_without_bitz_sdd(make_repo, copy_script):
    """bitz-sdd を含まないリポジトリでは SKIP し、既存の検査結果に影響しない。"""
    repo = make_repo()
    res = run_check(copy_script(repo, CHECK_SCRIPT))
    assert res.returncode == 0, res.stdout
    assert "[SKIP] フェーズ語彙の一致" in res.stdout
