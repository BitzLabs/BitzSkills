#!/usr/bin/env python3
"""BitzSDD の .spec/ と docs/ の本文を双方向同期する。"""

import argparse
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# 同期するデフォルトのマッピング定義 (spec_file_path -> docs_file_path)
# 全てリポジトリルートからの相対パス。この対応表が同期元追跡の正となる。
DEFAULT_MAPPING = {
    ".spec/discovery/vision.md": "docs/00_はじめに/ミッション・ビジョン.md",
    ".spec/discovery/scope.md": "docs/00_はじめに/対象外.md",
    ".spec/design/domain-model.md": "docs/03_設計仕様/ドメインモデル.md",
    ".spec/design/api-design.md": "docs/03_設計仕様/公開API.md",
    ".spec/design/architecture.md": "docs/03_設計仕様/アーキテクチャ.md",
    ".spec/design/data-model.md": "docs/03_設計仕様/データモデル.md",
}

SCRIPT_DIR = Path(__file__).resolve().parent
DOCS_TEMPLATE_ROOT = SCRIPT_DIR.parent / "assets" / "docs-templates" / "docs"
PROJECT_TYPES = {"app", "library", "both"}


class SyncError(ValueError):
    """同期契約を満たさない入力を表す。"""


def get_mtime(path: Path) -> float:
    if not path.exists():
        return 0.0
    return path.stat().st_mtime


def format_mtime(mtime: float) -> str:
    if mtime == 0.0:
        return "なし"
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")


def split_frontmatter(text: str, label: str) -> tuple[str, str]:
    """frontmatterブロックと本文を返す。欠如・未閉鎖は拒否する。"""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise SyncError(f"{label} にfrontmatterがありません")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter = "".join(lines[: index + 1])
            body = "".join(lines[index + 1 :]).lstrip("\r\n")
            return frontmatter, body
    raise SyncError(f"{label} のfrontmatterが閉じていません")


def render_document(frontmatter: str, body: str) -> str:
    """同期先frontmatterと同期元本文を決定的に結合する。"""
    return frontmatter.rstrip("\r\n") + "\n\n" + body


def frontmatter_value(frontmatter: str, key: str) -> str | None:
    """stdlibだけで単純なscalar値を取得する。"""
    prefix = f"{key}:"
    for line in frontmatter.splitlines()[1:-1]:
        if line.startswith(prefix):
            return line[len(prefix) :].split("#", 1)[0].strip() or None
    return None


def replace_frontmatter_value(frontmatter: str, key: str, value: str) -> str:
    """生成用frontmatterのscalar値を置換する。"""
    prefix = f"{key}:"
    lines = frontmatter.splitlines(keepends=True)
    for index, line in enumerate(lines[1:-1], start=1):
        if line.startswith(prefix):
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"{key}: {value}{newline}"
            return "".join(lines)
    raise SyncError(f"テンプレートfrontmatterに '{key}' がありません")


def docs_template_path(docs_rel: str) -> Path:
    parts = Path(docs_rel).parts
    if not parts or parts[0] != "docs":
        raise SyncError(f"docs同期先パスが不正です: {docs_rel}")
    return DOCS_TEMPLATE_ROOT.joinpath(*parts[1:])


def generated_docs_frontmatter(root: Path, docs_rel: str) -> str:
    """同梱テンプレートからプロジェクト整合済みfrontmatterを生成する。"""
    template = docs_template_path(docs_rel)
    if not template.is_file():
        raise SyncError(f"docsテンプレートがありません: {template}")
    template_frontmatter, _ = split_frontmatter(
        template.read_text(encoding="utf-8"), f"docsテンプレート {template}"
    )

    master = root / "docs" / "MASTER.md"
    if not master.is_file():
        raise SyncError("docs/MASTER.md がありません")
    master_frontmatter, _ = split_frontmatter(
        master.read_text(encoding="utf-8"), "docs/MASTER.md"
    )
    project_type = frontmatter_value(master_frontmatter, "project_type")
    if project_type not in PROJECT_TYPES:
        raise SyncError(
            "docs/MASTER.md の project_type が不正です "
            f"(許容: {sorted(PROJECT_TYPES)}, actual: {project_type!r})"
        )
    return replace_frontmatter_value(template_frontmatter, "project_type", project_type)


def docs_destination_frontmatter(root: Path, docs_path: Path, docs_rel: str) -> str:
    """既存docsのfrontmatterを保持し、欠如時だけテンプレートから生成する。"""
    if not docs_path.exists():
        return generated_docs_frontmatter(root, docs_rel)
    text = docs_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return generated_docs_frontmatter(root, docs_rel)
    frontmatter, _ = split_frontmatter(text, str(docs_path))
    return frontmatter


def atomic_write_document(dst: Path, content: str, source_mtime_ns: int) -> None:
    """同一ディレクトリの一時ファイルから原子的に置換し、mtimeを同期する。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    mode = (dst.stat().st_mode & 0o777) if dst.exists() else 0o644
    fd, temporary_name = tempfile.mkstemp(prefix=f".{dst.name}.", dir=dst.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, dst)
        current_atime_ns = dst.stat().st_atime_ns
        os.utime(dst, ns=(current_atime_ns, source_mtime_ns))
    except (OSError, UnicodeError):
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def sync_pull_file(root: Path, spec_path: Path, docs_path: Path, docs_rel: str) -> None:
    spec_text = spec_path.read_text(encoding="utf-8")
    _, spec_body = split_frontmatter(spec_text, str(spec_path))
    docs_frontmatter = docs_destination_frontmatter(root, docs_path, docs_rel)
    rendered = render_document(docs_frontmatter, spec_body)
    atomic_write_document(docs_path, rendered, spec_path.stat().st_mtime_ns)


def sync_push_file(spec_path: Path, docs_path: Path) -> None:
    docs_text = docs_path.read_text(encoding="utf-8")
    _, docs_body = split_frontmatter(docs_text, str(docs_path))
    if not spec_path.exists():
        raise SyncError(f"push先の .spec 文書がありません: {spec_path}")
    spec_text = spec_path.read_text(encoding="utf-8")
    spec_frontmatter, _ = split_frontmatter(spec_text, str(spec_path))
    rendered = render_document(spec_frontmatter, docs_body)
    atomic_write_document(spec_path, rendered, docs_path.stat().st_mtime_ns)


def build_stories_summary(spec_stories_dir: Path, target_docs_story: Path):
    """.spec/design/stories/ を docs/03_設計仕様/ドメインストーリー.md へ集約する。"""
    if not spec_stories_dir.exists():
        return False

    stories = sorted(spec_stories_dir.glob("story-*.md"))
    if not stories:
        return False

    content = [
        "---",
        "id: DOC-design-story",
        "title: ドメインストーリー一覧 (自動集計)",
        "status: active",
        "version: 1.0.0",
        "changeImpact: low",
        "project_type: both",
        f"updated: {datetime.now().strftime('%Y-%m-%d')}",
        "owner: agent",
        "---",
        "",
        "# ドメインストーリー一覧",
        "",
        "このドキュメントは `.spec/design/stories/` 内のストーリーを自動集計したものです。",
        "",
    ]

    for story_file in stories:
        content.append(f"## {story_file.stem.replace('story-', '').upper()}")
        story_text = story_file.read_text(encoding="utf-8")
        if story_text.startswith("---"):
            _, story_text = split_frontmatter(story_text, str(story_file))
        content.append(story_text.strip())
        content.append("\n---\n")

    target_docs_story.parent.mkdir(parents=True, exist_ok=True)
    target_docs_story.write_text("\n".join(content), encoding="utf-8")
    print(f"SUCCESS [pull]: {len(stories)} 件のストーリーを {target_docs_story} へ統合しました。")
    return True


def print_summary(label: str, success_count: int, failure_count: int) -> None:
    print(f"--- {label}: 成功: {success_count} / 失敗: {failure_count} ---")
    if failure_count:
        print("ACTION: エラーを修正して同じコマンドを再実行してください。")


def do_pull(root: Path) -> int:
    """.spec -> docs（frontmatterを保持して本文を展開）。"""
    print(">>> 同期実行中: .spec/ (マスター) -> docs/ (ナラティブ)")
    success_count = 0
    failure_count = 0
    for spec_rel, docs_rel in DEFAULT_MAPPING.items():
        spec_path = root / spec_rel
        docs_path = root / docs_rel
        if not spec_path.exists():
            print(f"SKIP: ソース仕様 {spec_rel} が存在しません。")
            continue

        spec_mtime = get_mtime(spec_path)
        docs_mtime = get_mtime(docs_path)
        if spec_mtime <= docs_mtime and docs_mtime != 0.0:
            print(f"UP-TO-DATE: {docs_rel} は最新です。")
            continue

        try:
            sync_pull_file(root, spec_path, docs_path, docs_rel)
            success_count += 1
            print(f"SUCCESS [pull]: {spec_path.name} の本文を {docs_path} へ同期しました。")
        except (OSError, UnicodeError, SyncError) as error:
            failure_count += 1
            print(f"ERROR [pull]: {spec_rel} -> {docs_rel}: {error}", file=sys.stderr)

    try:
        if build_stories_summary(
            root / ".spec/design/stories",
            root / "docs/03_設計仕様/ドメインストーリー.md",
        ):
            success_count += 1
    except (OSError, UnicodeError, SyncError) as error:
        failure_count += 1
        print(f"ERROR [pull]: ドメインストーリー集約: {error}", file=sys.stderr)

    print_summary("同期完了", success_count, failure_count)
    return 1 if failure_count else 0


def do_push(root: Path) -> int:
    """docs -> .spec（frontmatterを保持して本文を逆反映）。"""
    print(">>> 逆同期実行中: docs/ (手動修正) -> .spec/ (マスター)")
    success_count = 0
    failure_count = 0
    for spec_rel, docs_rel in DEFAULT_MAPPING.items():
        spec_path = root / spec_rel
        docs_path = root / docs_rel
        if not docs_path.exists():
            print(f"SKIP: ドキュメント {docs_rel} が存在しません。")
            continue

        spec_mtime = get_mtime(spec_path)
        docs_mtime = get_mtime(docs_path)
        if docs_mtime <= spec_mtime and spec_mtime != 0.0:
            print(f"UP-TO-DATE: {spec_rel} は最新です（docsの変更はありません）。")
            continue

        try:
            sync_push_file(spec_path, docs_path)
            success_count += 1
            print(f"SUCCESS [push]: {docs_path.name} の本文を {spec_path} へ同期しました。")
        except (OSError, UnicodeError, SyncError) as error:
            failure_count += 1
            print(f"ERROR [push]: {docs_rel} -> {spec_rel}: {error}", file=sys.stderr)

    print_summary("逆同期完了", success_count, failure_count)
    return 1 if failure_count else 0


def do_diff(root: Path) -> int:
    """.spec と docs のタイムスタンプ・乖離状況を表示する。"""
    print(">>> 仕様とドキュメントの同期状態:")
    print(f"{'成果物パス':<35} | {'.spec最終更新':<20} | {'docs最終更新':<20} | {'ステータス'}")
    print("-" * 95)
    for spec_rel, docs_rel in DEFAULT_MAPPING.items():
        spec_mtime = get_mtime(root / spec_rel)
        docs_mtime = get_mtime(root / docs_rel)

        status = "同期済み"
        if spec_mtime == 0.0 and docs_mtime == 0.0:
            status = "両方未作成"
        elif spec_mtime == 0.0:
            status = "docs側のみ存在 (push前に.spec作成が必要)"
        elif docs_mtime == 0.0:
            status = "spec側のみ存在 (pullが必要)"
        elif spec_mtime > docs_mtime:
            status = "spec側が新しい (pullが必要)"
        elif docs_mtime > spec_mtime:
            status = "docs側が新しい (pushが必要)"

        print(
            f"{docs_rel:<35} | {format_mtime(spec_mtime):<20} | "
            f"{format_mtime(docs_mtime):<20} | {status}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="BitzSDD: .spec ⇄ docs 本文双方向同期ツール")
    parser.add_argument("action", choices=["pull", "push", "diff"], help="同期アクション")
    parser.add_argument("--root", default=".", help="リポジトリルートのパス")
    args = parser.parse_args()

    root_path = Path(args.root).resolve()
    if args.action == "pull":
        return do_pull(root_path)
    if args.action == "push":
        return do_push(root_path)
    return do_diff(root_path)


if __name__ == "__main__":
    sys.exit(main())
