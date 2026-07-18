import importlib.util
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/bitz-sdd/skills/sdd-docs/scripts/docs_inspect.py"
TEMPLATES = ROOT / "plugins/bitz-sdd/skills/sdd-docs/assets/docs-templates"


def load_module():
    spec = importlib.util.spec_from_file_location("docs_inspect", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def copy_template(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    shutil.copytree(TEMPLATES / "docs", root / "docs")
    return root


def codes(findings):
    return {finding.code for finding in findings}


def test_japanese_six_chapter_template_passes_strict(tmp_path: Path):
    module = load_module()
    root = copy_template(tmp_path)

    assert module.run_docs_checks(str(root)) == []


def test_missing_mandatory_chapter_is_error(tmp_path: Path):
    module = load_module()
    root = copy_template(tmp_path)
    shutil.move(root / "docs" / "02_ユースケース", root / "missing-use-cases")

    assert "LAYOUT_MISSING" in codes(module.run_docs_checks(str(root)))


def test_legacy_chapter_mixed_with_japanese_layout_is_error(tmp_path: Path):
    module = load_module()
    root = copy_template(tmp_path)
    legacy = root / "docs" / "01-context"
    legacy.mkdir()
    (legacy / "legacy.md").write_text("legacy", encoding="utf-8")

    assert "LAYOUT_LEGACY" in codes(module.run_docs_checks(str(root)))


def test_optional_reference_requires_master_declaration(tmp_path: Path):
    module = load_module()
    root = copy_template(tmp_path)
    shutil.copytree(TEMPLATES / "optional" / "06_リファレンス", root / "docs" / "06_リファレンス")

    assert "OPTIONAL_UNDECLARED" in codes(module.run_docs_checks(str(root)))


def test_declared_optional_reference_passes(tmp_path: Path):
    module = load_module()
    root = copy_template(tmp_path)
    shutil.copytree(TEMPLATES / "optional" / "06_リファレンス", root / "docs" / "06_リファレンス")
    master = root / "docs" / "MASTER.md"
    text = master.read_text(encoding="utf-8").replace("optional_chapters:", "optional_chapters: reference")
    text = text.replace(
        "<!-- OPTIONAL_DOCUMENTS -->",
        "| DOC-reference-external-apis | [外部APIとリファレンス](06_リファレンス/外部API.md) | reference | active | 0.1.0 | 外部依存・移行ガイド |",
    )
    master.write_text(text, encoding="utf-8")

    assert module.run_docs_checks(str(root)) == []


def test_excluded_path_skips_unmanaged_research_docs(tmp_path: Path):
    module = load_module()
    root = copy_template(tmp_path)
    research = root / "docs" / "調査報告"
    research.mkdir()
    (research / "メモ.md").write_text("frontmatterなし", encoding="utf-8")
    master = root / "docs" / "MASTER.md"
    master.write_text(
        master.read_text(encoding="utf-8").replace("excluded_paths:", "excluded_paths: 調査報告"),
        encoding="utf-8",
    )

    assert module.run_docs_checks(str(root)) == []


def test_excluded_path_cannot_hide_managed_chapter(tmp_path: Path):
    module = load_module()
    root = copy_template(tmp_path)
    master = root / "docs" / "MASTER.md"
    master.write_text(
        master.read_text(encoding="utf-8").replace("excluded_paths:", "excluded_paths: 03_設計仕様"),
        encoding="utf-8",
    )

    assert "EXCLUDED_INVALID" in codes(module.run_docs_checks(str(root)))
