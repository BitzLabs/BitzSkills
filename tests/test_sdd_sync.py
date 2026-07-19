import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
SDD_SYNC_SCRIPT = ROOT / "plugins/bitz-sdd/skills/sdd-docs/scripts/sdd_sync.py"
DOCS_INSPECT_SCRIPT = ROOT / "plugins/bitz-sdd/skills/sdd-docs/scripts/docs_inspect.py"
DOCS_TEMPLATES = ROOT / "plugins/bitz-sdd/skills/sdd-docs/assets/docs-templates/docs"


def run_sync(tmp_path: Path, action: str):
    return subprocess.run(
        [sys.executable, str(SDD_SYNC_SCRIPT), action, "--root", str(tmp_path)],
        capture_output=True,
        text=True,
    )


def spec_document(body: str, ident: str = "fixture-spec-001") -> str:
    return (
        "---\n"
        f"id: {ident}\n"
        "title: テスト仕様\n"
        "status: draft\n"
        "version: 1.0\n"
        "updated: 2026-07-19\n"
        "owner: test\n"
        "---\n\n"
        f"{body}"
    )


def docs_document(
    body: str,
    ident: str = "DOC-context-test",
    project_type: str = "both",
) -> str:
    return (
        "---\n"
        f"id: {ident}\n"
        "title: テスト文書\n"
        "status: active\n"
        "version: 1.2.3\n"
        "changeImpact: low\n"
        f"project_type: {project_type}\n"
        "updated: 2026-07-19\n"
        "owner: test\n"
        "---\n\n"
        f"{body}"
    )


def split_document(text: str) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    assert lines and lines[0].strip() == "---"
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter = "".join(lines[: index + 1])
            body = "".join(lines[index + 1 :]).lstrip("\r\n")
            return frontmatter, body
    raise AssertionError("frontmatterが閉じていません")


def init_docs(tmp_path: Path) -> Path:
    docs_root = tmp_path / "docs"
    shutil.copytree(DOCS_TEMPLATES, docs_root)
    return docs_root


def set_master_project_type(docs_root: Path, project_type: str) -> None:
    master = docs_root / "MASTER.md"
    text = master.read_text(encoding="utf-8")
    text = text.replace("project_type: both", f"project_type: {project_type}", 1)
    master.write_text(text, encoding="utf-8")


def set_newer(newer: Path, older: Path) -> None:
    now_ns = time.time_ns()
    os.utime(older, ns=(now_ns - 10_000_000_000, now_ns - 10_000_000_000))
    os.utime(newer, ns=(now_ns, now_ns))


def test_SDD_FR_135_pull_missing_target_uses_template_frontmatter_and_master_type(tmp_path: Path):
    docs_root = init_docs(tmp_path)
    set_master_project_type(docs_root, "library")
    docs = docs_root / "00_はじめに" / "ミッション・ビジョン.md"
    docs.unlink()
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(spec_document("# 新しいビジョン\n"), encoding="utf-8")

    res = run_sync(tmp_path, "pull")

    assert res.returncode == 0, res.stderr
    frontmatter, body = split_document(docs.read_text(encoding="utf-8"))
    assert "id: DOC-context-mission\n" in frontmatter
    assert "project_type: library" in frontmatter
    assert "fixture-spec-001" not in frontmatter
    assert body == "# 新しいビジョン\n"


def test_SDD_FR_135_pull_preserves_docs_frontmatter_and_syncs_only_spec_body(tmp_path: Path):
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md"
    spec.parent.mkdir(parents=True)
    docs.parent.mkdir(parents=True)
    spec.write_text(spec_document("spec body new\n"), encoding="utf-8")
    original_docs = docs_document("docs body old\n", ident="DOC-context-kept")
    docs.write_text(original_docs, encoding="utf-8")
    original_frontmatter, _ = split_document(original_docs)
    set_newer(spec, docs)

    res = run_sync(tmp_path, "pull")

    assert res.returncode == 0, res.stderr
    actual_frontmatter, actual_body = split_document(docs.read_text(encoding="utf-8"))
    assert actual_frontmatter == original_frontmatter
    assert actual_body == "spec body new\n"
    assert docs.stat().st_mtime_ns == spec.stat().st_mtime_ns


def test_SDD_FR_135_pull_existing_doc_without_frontmatter_uses_template(tmp_path: Path):
    docs_root = init_docs(tmp_path)
    docs = docs_root / "00_はじめに" / "ミッション・ビジョン.md"
    docs.write_text("legacy docs body", encoding="utf-8")
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(spec_document("rendered body\n"), encoding="utf-8")
    set_newer(spec, docs)

    res = run_sync(tmp_path, "pull")

    assert res.returncode == 0, res.stderr
    frontmatter, body = split_document(docs.read_text(encoding="utf-8"))
    assert "id: DOC-context-mission\n" in frontmatter
    assert body == "rendered body\n"


def test_SDD_FR_135_pull_rejects_source_without_frontmatter_without_modifying_docs(tmp_path: Path):
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md"
    spec.parent.mkdir(parents=True)
    docs.parent.mkdir(parents=True)
    spec.write_text("spec body without frontmatter", encoding="utf-8")
    original = docs_document("preserved docs body\n")
    docs.write_text(original, encoding="utf-8")
    set_newer(spec, docs)

    res = run_sync(tmp_path, "pull")

    assert res.returncode != 0
    assert docs.read_text(encoding="utf-8") == original


def test_SDD_FR_135_pull_rejects_unclosed_docs_frontmatter_without_modification(tmp_path: Path):
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md"
    spec.parent.mkdir(parents=True)
    docs.parent.mkdir(parents=True)
    spec.write_text(spec_document("new body\n"), encoding="utf-8")
    original = "---\nid: DOC-context-broken\n# closing delimiter missing\n"
    docs.write_text(original, encoding="utf-8")
    set_newer(spec, docs)

    res = run_sync(tmp_path, "pull")

    assert res.returncode != 0
    assert docs.read_text(encoding="utf-8") == original
    assert "失敗: 1" in res.stdout
    assert "再実行" in res.stdout


def test_SDD_FR_135_pull_rejects_invalid_master_type_before_generating_target(tmp_path: Path):
    docs_root = init_docs(tmp_path)
    set_master_project_type(docs_root, "invalid")
    docs = docs_root / "00_はじめに" / "ミッション・ビジョン.md"
    docs.unlink()
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(spec_document("body\n"), encoding="utf-8")

    res = run_sync(tmp_path, "pull")

    assert res.returncode != 0
    assert not docs.exists()


def test_SDD_FR_135_pull_then_docs_inspect_strict_passes(tmp_path: Path):
    docs_root = init_docs(tmp_path)
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = docs_root / "00_はじめに" / "ミッション・ビジョン.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(spec_document("# strict compatible body\n"), encoding="utf-8")
    set_newer(spec, docs)

    pull = run_sync(tmp_path, "pull")
    inspect = subprocess.run(
        [
            sys.executable,
            str(DOCS_INSPECT_SCRIPT),
            str(tmp_path),
            "--strict",
            "--out",
            str(tmp_path / "docs-inspection-report.md"),
        ],
        capture_output=True,
        text=True,
    )

    assert pull.returncode == 0, pull.stderr
    assert inspect.returncode == 0, inspect.stdout + inspect.stderr
    assert "ERROR: 0 / WARN: 0" in inspect.stdout


def test_SDD_FR_135_push_preserves_spec_frontmatter_and_syncs_only_docs_body(tmp_path: Path):
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md"
    spec.parent.mkdir(parents=True)
    docs.parent.mkdir(parents=True)
    original_spec = spec_document("spec body old\n", ident="fixture-spec-kept")
    spec.write_text(original_spec, encoding="utf-8")
    docs.write_text(docs_document("docs body new\n"), encoding="utf-8")
    original_frontmatter, _ = split_document(original_spec)
    set_newer(docs, spec)

    res = run_sync(tmp_path, "push")

    assert res.returncode == 0, res.stderr
    actual_frontmatter, actual_body = split_document(spec.read_text(encoding="utf-8"))
    assert actual_frontmatter == original_frontmatter
    assert actual_body == "docs body new\n"
    assert "DOC-context-test" not in actual_frontmatter
    assert spec.stat().st_mtime_ns == docs.stat().st_mtime_ns


def test_SDD_FR_135_push_rejects_docs_source_without_frontmatter(tmp_path: Path):
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md"
    spec.parent.mkdir(parents=True)
    docs.parent.mkdir(parents=True)
    original = spec_document("preserved spec body\n")
    spec.write_text(original, encoding="utf-8")
    docs.write_text("docs body without frontmatter", encoding="utf-8")
    set_newer(docs, spec)

    res = run_sync(tmp_path, "push")

    assert res.returncode != 0
    assert spec.read_text(encoding="utf-8") == original


def test_SDD_FR_135_push_rejects_missing_spec_target(tmp_path: Path):
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md"
    docs.parent.mkdir(parents=True)
    docs.write_text(docs_document("docs body\n"), encoding="utf-8")

    res = run_sync(tmp_path, "push")

    assert res.returncode != 0
    assert not spec.exists()


@pytest.mark.parametrize(
    "invalid_spec",
    [
        "spec body without frontmatter",
        "---\nid: fixture-spec-broken\nbody without closing delimiter\n",
    ],
)
def test_SDD_FR_135_push_rejects_invalid_spec_target_without_modification(
    tmp_path: Path, invalid_spec: str
):
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md"
    spec.parent.mkdir(parents=True)
    docs.parent.mkdir(parents=True)
    spec.write_text(invalid_spec, encoding="utf-8")
    docs.write_text(docs_document("docs body\n"), encoding="utf-8")
    set_newer(docs, spec)

    res = run_sync(tmp_path, "push")

    assert res.returncode != 0
    assert spec.read_text(encoding="utf-8") == invalid_spec


def test_pull_docs_newer_no_overwrite(tmp_path: Path):
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md"
    spec.parent.mkdir(parents=True)
    docs.parent.mkdir(parents=True)
    spec.write_text(spec_document("spec content\n"), encoding="utf-8")
    original = docs_document("docs content\n")
    docs.write_text(original, encoding="utf-8")
    set_newer(docs, spec)

    res = run_sync(tmp_path, "pull")

    assert res.returncode == 0
    assert docs.read_text(encoding="utf-8") == original


def test_pull_stories_aggregation(tmp_path: Path):
    stories_dir = tmp_path / ".spec" / "design" / "stories"
    stories_dir.mkdir(parents=True)
    (stories_dir / "story-a.md").write_text("---\ntitle: a\n---\nbody a", encoding="utf-8")
    (stories_dir / "story-b.md").write_text("body b", encoding="utf-8")

    res = run_sync(tmp_path, "pull")

    assert res.returncode == 0
    content = (tmp_path / "docs" / "03_設計仕様" / "ドメインストーリー.md").read_text(
        encoding="utf-8"
    )
    assert "## A" in content
    assert "body a" in content
    assert "title: a" not in content
    assert "## B" in content
    assert "body b" in content


def test_push_spec_newer_no_reverse_sync(tmp_path: Path):
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md"
    spec.parent.mkdir(parents=True)
    docs.parent.mkdir(parents=True)
    original = spec_document("spec content new\n")
    spec.write_text(original, encoding="utf-8")
    docs.write_text(docs_document("docs content old\n"), encoding="utf-8")
    set_newer(spec, docs)

    res = run_sync(tmp_path, "push")

    assert res.returncode == 0
    assert spec.read_text(encoding="utf-8") == original


def test_diff_is_readonly(tmp_path: Path):
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(spec_document("vision content\n"), encoding="utf-8")
    now_ns = time.time_ns()
    os.utime(spec, ns=(now_ns, now_ns))

    res = run_sync(tmp_path, "diff")

    assert res.returncode == 0
    assert spec.stat().st_mtime_ns == now_ns
    assert not (tmp_path / "docs" / "00_はじめに" / "ミッション・ビジョン.md").exists()


@pytest.mark.parametrize(
    ("spec_rel", "docs_rel"),
    [
        (".spec/discovery/vision.md", "docs/00_はじめに/ミッション・ビジョン.md"),
        (".spec/discovery/scope.md", "docs/00_はじめに/対象外.md"),
        (".spec/design/domain-model.md", "docs/03_設計仕様/ドメインモデル.md"),
        (".spec/design/api-design.md", "docs/03_設計仕様/公開API.md"),
        (".spec/design/architecture.md", "docs/03_設計仕様/アーキテクチャ.md"),
        (".spec/design/data-model.md", "docs/03_設計仕様/データモデル.md"),
    ],
)
def test_pull_uses_japanese_mapping(tmp_path: Path, spec_rel: str, docs_rel: str):
    init_docs(tmp_path)
    spec = tmp_path / spec_rel
    docs = tmp_path / docs_rel
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(spec_document(f"{spec_rel}\n", ident="fixture-design-001"), encoding="utf-8")
    original_frontmatter, _ = split_document(docs.read_text(encoding="utf-8"))
    set_newer(spec, docs)

    res = run_sync(tmp_path, "pull")

    assert res.returncode == 0, res.stderr
    actual_frontmatter, actual_body = split_document(docs.read_text(encoding="utf-8"))
    assert actual_frontmatter == original_frontmatter
    assert actual_body == f"{spec_rel}\n"


def test_push_design_doc_uses_japanese_mapping(tmp_path: Path):
    spec = tmp_path / ".spec" / "design" / "architecture.md"
    docs = tmp_path / "docs" / "03_設計仕様" / "アーキテクチャ.md"
    spec.parent.mkdir(parents=True)
    docs.parent.mkdir(parents=True)
    spec.write_text(spec_document("old\n", ident="fixture-design-001"), encoding="utf-8")
    docs.write_text(docs_document("new\n", ident="DOC-design-architecture"), encoding="utf-8")
    set_newer(docs, spec)

    res = run_sync(tmp_path, "push")

    assert res.returncode == 0, res.stderr
    _, body = split_document(spec.read_text(encoding="utf-8"))
    assert body == "new\n"


def test_pull_does_not_modify_unrelated_docs(tmp_path: Path):
    docs = tmp_path / "docs" / "unrelated.md"
    docs.parent.mkdir(parents=True)
    docs.write_text("unrelated content", encoding="utf-8")
    now_ns = time.time_ns()
    os.utime(docs, ns=(now_ns, now_ns))

    res = run_sync(tmp_path, "pull")

    assert res.returncode == 0
    assert docs.read_text(encoding="utf-8") == "unrelated content"
    assert docs.stat().st_mtime_ns == now_ns
