import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# プロジェクトルートからの相対パスで元のスクリプトを特定
SDD_SYNC_SCRIPT = Path(__file__).resolve().parent.parent / "plugins" / "bitz-sdd" / "skills" / "sdd-docs" / "scripts" / "sdd_sync.py"


def run_sync(tmp_path: Path, action: str):
    """subprocess.run を用いて対象スクリプトを実行する"""
    return subprocess.run(
        [sys.executable, str(SDD_SYNC_SCRIPT), action, "--root", str(tmp_path)],
        capture_output=True,
        text=True
    )


def test_pull_new_file(tmp_path: Path):
    """pull: .spec 側にのみファイルがある -> docs 側へコピーされ内容一致"""
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("vision content", encoding="utf-8")
    
    res = run_sync(tmp_path, "pull")
    assert res.returncode == 0
    docs = tmp_path / "docs" / "01-context" / "mission-vision.md"
    assert docs.exists()
    assert docs.read_text(encoding="utf-8") == "vision content"


def test_pull_docs_newer_no_overwrite(tmp_path: Path):
    """pull: docs 側の mtime が新しい -> 上書きされない（docs の内容が保持される）"""
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "01-context" / "mission-vision.md"
    
    spec.parent.mkdir(parents=True)
    spec.write_text("spec content", encoding="utf-8")
    docs.parent.mkdir(parents=True)
    docs.write_text("docs content", encoding="utf-8")
    
    now = time.time()
    os.utime(spec, (now - 10, now - 10))
    os.utime(docs, (now, now))
    
    res = run_sync(tmp_path, "pull")
    assert res.returncode == 0
    assert docs.read_text(encoding="utf-8") == "docs content"


def test_pull_spec_newer_overwrites(tmp_path: Path):
    """pull: spec 側が新しい -> docs が更新される"""
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "01-context" / "mission-vision.md"
    
    spec.parent.mkdir(parents=True)
    spec.write_text("spec content new", encoding="utf-8")
    docs.parent.mkdir(parents=True)
    docs.write_text("docs content old", encoding="utf-8")
    
    now = time.time()
    os.utime(docs, (now - 10, now - 10))
    os.utime(spec, (now, now))
    
    res = run_sync(tmp_path, "pull")
    assert res.returncode == 0
    assert docs.read_text(encoding="utf-8") == "spec content new"


def test_pull_stories_aggregation(tmp_path: Path):
    """pull: stories 集約"""
    stories_dir = tmp_path / ".spec" / "design" / "stories"
    stories_dir.mkdir(parents=True)
    
    (stories_dir / "story-a.md").write_text("---\ntitle: a\n---\nbody a", encoding="utf-8")
    (stories_dir / "story-b.md").write_text("body b", encoding="utf-8")
    
    res = run_sync(tmp_path, "pull")
    assert res.returncode == 0
    
    docs_story = tmp_path / "docs" / "02-design" / "domain-story.md"
    assert docs_story.exists()
    content = docs_story.read_text(encoding="utf-8")
    
    # ソート順（a -> b）と内容の検証
    assert "## A" in content
    assert "body a" in content
    assert "title: a" not in content  # frontmatter は除去されていること
    assert "## B" in content
    assert "body b" in content


def test_push_docs_newer_reverses_sync(tmp_path: Path):
    """push: docs 側が新しい -> .spec へ逆反映される"""
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "01-context" / "mission-vision.md"
    
    spec.parent.mkdir(parents=True)
    spec.write_text("spec content old", encoding="utf-8")
    docs.parent.mkdir(parents=True)
    docs.write_text("docs content new", encoding="utf-8")
    
    now = time.time()
    os.utime(spec, (now - 10, now - 10))
    os.utime(docs, (now, now))
    
    res = run_sync(tmp_path, "push")
    assert res.returncode == 0
    assert spec.read_text(encoding="utf-8") == "docs content new"


def test_push_spec_newer_no_reverse_sync(tmp_path: Path):
    """push: spec 側が新しい -> 逆反映されない"""
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    docs = tmp_path / "docs" / "01-context" / "mission-vision.md"
    
    spec.parent.mkdir(parents=True)
    spec.write_text("spec content new", encoding="utf-8")
    docs.parent.mkdir(parents=True)
    docs.write_text("docs content old", encoding="utf-8")
    
    now = time.time()
    os.utime(docs, (now - 10, now - 10))
    os.utime(spec, (now, now))
    
    res = run_sync(tmp_path, "push")
    assert res.returncode == 0
    assert spec.read_text(encoding="utf-8") == "spec content new"


def test_diff_is_readonly(tmp_path: Path):
    """diff: 実行してもどのファイルの内容・mtime も変化しない"""
    spec = tmp_path / ".spec" / "discovery" / "vision.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("vision content", encoding="utf-8")
    
    now = time.time()
    os.utime(spec, (now, now))
    
    res = run_sync(tmp_path, "diff")
    assert res.returncode == 0
    
    assert spec.exists()
    assert spec.stat().st_mtime == pytest.approx(now, abs=1)
    
    docs = tmp_path / "docs" / "01-context" / "mission-vision.md"
    assert not docs.exists()


def test_pull_does_not_modify_unrelated_docs(tmp_path: Path):
    """pull: マッピング外の既存ファイルを変更しない"""
    docs = tmp_path / "docs" / "unrelated.md"
    docs.parent.mkdir(parents=True)
    docs.write_text("unrelated content", encoding="utf-8")
    
    now = time.time()
    os.utime(docs, (now, now))
    
    res = run_sync(tmp_path, "pull")
    assert res.returncode == 0
    
    assert docs.read_text(encoding="utf-8") == "unrelated content"
    assert docs.stat().st_mtime == pytest.approx(now, abs=1)
