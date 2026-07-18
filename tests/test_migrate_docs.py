import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/bitz-sdd/skills/sdd-docs/scripts/migrate_docs.py"
INSPECT = ROOT / "plugins/bitz-sdd/skills/sdd-docs/scripts/docs_inspect.py"


def run_migration(root: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
    )


def doc(doc_id: str, title: str, area: str, body: str) -> str:
    return f"""---
id: {doc_id}
title: {title}
status: active
version: 0.1.0
changeImpact: low
project_type: app
updated: 2026-07-18
owner: human
---

# {title}

{body}
"""


def make_legacy(root: Path, *, with_reference: bool = False):
    docs = root / "docs"
    files = {
        "01-context/mission-vision.md": doc("DOC-context-mission", "Mission", "context", "vision"),
        "02-design/ARCHITECTURE.md": doc("DOC-design-architecture", "Architecture", "design", "architecture"),
        "08-knowledge/LESSONS_LEARNED.md": doc("DOC-knowledge-lessons", "Lessons", "knowledge", "lessons"),
    }
    if with_reference:
        files["06-reference/EXTERNAL-APIS.md"] = doc(
            "DOC-reference-external-apis", "External APIs", "reference", "external"
        )
    for rel, content in files.items():
        path = docs / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    reference_row = ""
    if with_reference:
        reference_row = "| DOC-reference-external-apis | [External APIs](06-reference/EXTERNAL-APIS.md) | reference | active | 0.1.0 | refs |\n"
    master = f"""---
id: DOC-master
title: Legacy docs
status: active
version: 0.1.0
changeImpact: low
project_type: app
updated: 2026-07-18
owner: human
---

# Legacy docs

| id | 文書 | area | status | version | 概要 |
|---|---|---|---|---|---|
| DOC-context-mission | [Mission](01-context/mission-vision.md) | context | active | 0.1.0 | vision |
| DOC-design-architecture | [Architecture](02-design/ARCHITECTURE.md) | design | active | 0.1.0 | design |
| DOC-knowledge-lessons | [Lessons](08-knowledge/LESSONS_LEARNED.md) | knowledge | active | 0.1.0 | lessons |
{reference_row}<!-- DOCUMENT_REGISTRY_END -->
"""
    (docs / "MASTER.md").write_text(master, encoding="utf-8")


def snapshot(root: Path):
    result = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def test_default_is_readonly_dry_run(tmp_path: Path):
    make_legacy(tmp_path)
    before = snapshot(tmp_path)

    res = run_migration(tmp_path)

    assert res.returncode == 0
    assert "DRY-RUN" in res.stdout
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "docs" / ".sdd-docs-migration.json").exists()


def test_apply_migrates_and_strict_inspection_passes(tmp_path: Path):
    make_legacy(tmp_path)

    res = run_migration(tmp_path, "--apply")

    assert res.returncode == 0, res.stderr
    assert (tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md").exists()
    assert (tmp_path / "docs" / "01_システム仕様" / "システム仕様.md").exists()
    assert (tmp_path / "docs" / "02_ユースケース" / "ユースケース一覧.md").exists()
    assert (tmp_path / "docs" / "03_設計仕様" / "アーキテクチャ.md").exists()
    assert (tmp_path / "docs" / "05_リリース・運用" / "教訓.md").exists()
    assert not (tmp_path / "docs" / "01-context" / "mission-vision.md").exists()
    master = (tmp_path / "docs" / "MASTER.md").read_text(encoding="utf-8")
    assert "00_はじめに/ミッション・ビジョン.md" in master
    assert "01_システム仕様/システム仕様.md" in master

    inspected = subprocess.run(
        [sys.executable, str(INSPECT), str(tmp_path), "--strict", "--out", str(tmp_path / "report.md")],
        capture_output=True,
        text=True,
    )
    assert inspected.returncode == 0, inspected.stdout + inspected.stderr


def test_conflict_stops_before_any_change(tmp_path: Path):
    make_legacy(tmp_path)
    conflict = tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("different", encoding="utf-8")
    before = snapshot(tmp_path)

    res = run_migration(tmp_path, "--apply")

    assert res.returncode != 0
    assert "CONFLICT" in res.stderr
    assert snapshot(tmp_path) == before


def test_rollback_restores_legacy_tree(tmp_path: Path):
    make_legacy(tmp_path)
    before = snapshot(tmp_path)
    assert run_migration(tmp_path, "--apply").returncode == 0

    res = run_migration(tmp_path, "--rollback")

    assert res.returncode == 0, res.stderr
    after = snapshot(tmp_path)
    manifest = "docs/.sdd-docs-migration.json"
    backup = "docs/.sdd-docs-migration-master.backup"
    after.pop(manifest)
    after.pop(backup)
    assert after == before


def test_second_apply_is_idempotent(tmp_path: Path):
    make_legacy(tmp_path)
    assert run_migration(tmp_path, "--apply").returncode == 0
    before = snapshot(tmp_path)

    res = run_migration(tmp_path, "--apply")

    assert res.returncode == 0
    assert "ALREADY-APPLIED" in res.stdout
    assert snapshot(tmp_path) == before


def test_reference_migration_declares_optional_chapter(tmp_path: Path):
    make_legacy(tmp_path, with_reference=True)

    res = run_migration(tmp_path, "--apply")

    assert res.returncode == 0, res.stderr
    assert (tmp_path / "docs" / "06_リファレンス" / "外部API.md").exists()
    master = (tmp_path / "docs" / "MASTER.md").read_text(encoding="utf-8")
    assert "optional_chapters: reference" in master
    assert "06_リファレンス/外部API.md" in master
