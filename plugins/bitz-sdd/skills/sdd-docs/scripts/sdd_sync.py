#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

# 同期するデフォルトのマッピング定義 (spec_file_path -> docs_file_path)
# 全てリポジトリルートからの相対パス
DEFAULT_MAPPING = {
    ".spec/discovery/vision.md": "docs/01-context/mission-vision.md",
    ".spec/discovery/scope.md": "docs/01-context/non-goals.md",
    ".spec/design/domain-model.md": "docs/02-design/domain-model.md",
    ".spec/design/api-design.md": "docs/02-design/public-api.md",
    ".spec/design/architecture.md": "docs/02-design/ARCHITECTURE.md",
}

def get_mtime(path: Path) -> float:
    if not path.exists():
        return 0.0
    return path.stat().st_mtime

def format_mtime(mtime: float) -> str:
    if mtime == 0.0:
        return "なし"
    return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

def sync_file(src: Path, dst: Path, direction: str) -> bool:
    """src から dst へファイルを同期し、必要なメタデータを調整する。"""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        # コピーを実行
        shutil.copy2(src, dst)
        print(f"SUCCESS [{direction}]: {src.name} を {dst} へコピーしました。")
        return True
    except Exception as e:
        print(f"ERROR: {src} から {dst} への同期に失敗しました: {e}", file=sys.stderr)
        return False

def build_stories_summary(spec_stories_dir: Path, target_docs_story: Path):
    """.spec/design/stories/ の個別ストーリーファイルを統合して docs/02-design/domain-story.md を作成する"""
    if not spec_stories_dir.exists():
        return
    
    stories = sorted(list(spec_stories_dir.glob("story-*.md")))
    if not stories:
        return
        
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
        ""
    ]
    
    for sf in stories:
        content.append(f"## {sf.stem.replace('story-', '').upper()}")
        try:
            story_text = sf.read_text(encoding="utf-8")
            # frontmatter があれば除外
            if story_text.startswith("---"):
                parts = story_text.split("---", 2)
                if len(parts) >= 3:
                    story_text = parts[2].strip()
            content.append(story_text)
            content.append("\n---\n")
        except Exception as e:
            content.append(f"エラー: ストーリーの読み込み失敗: {e}")
            
    target_docs_story.parent.mkdir(parents=True, exist_ok=True)
    target_docs_story.write_text("\n".join(content), encoding="utf-8")
    print(f"SUCCESS [pull]: {len(stories)} 件のストーリーを {target_docs_story} へ統合しました。")

def do_pull(root: Path):
    """.spec -> docs (specの成果物をdocsに展開)"""
    print(">>> 同期実行中: .spec/ (マスター) -> docs/ (ナラティブ)")
    success_count = 0
    for spec_rel, docs_rel in DEFAULT_MAPPING.items():
        spec_path = root / spec_rel
        docs_path = root / docs_rel
        
        if not spec_path.exists():
            print(f"SKIP: ソース仕様 {spec_rel} が存在しません。")
            continue
            
        # pullのルール: spec 側が新しい、または docs 側が存在しない場合に同期
        spec_mtime = get_mtime(spec_path)
        docs_mtime = get_mtime(docs_path)
        
        if spec_mtime > docs_mtime or docs_mtime == 0.0:
            if sync_file(spec_path, docs_path, "pull"):
                success_count += 1
        else:
            print(f"UP-TO-DATE: {docs_rel} は最新です。")
            
    # 特殊な統合ルール: ドメインストーリーの集約
    spec_stories_dir = root / ".spec/design/stories"
    target_docs_story = root / "docs/02-design/domain-story.md"
    if spec_stories_dir.exists():
        build_stories_summary(spec_stories_dir, target_docs_story)
        success_count += 1
        
    print(f"--- 同期完了: {success_count} ファイルを更新しました。---")

def do_push(root: Path):
    """docs -> .spec (人間がdocs側で修正した内容をspecに逆反映)"""
    print(">>> 逆同期実行中: docs/ (手動修正) -> .spec/ (マスター)")
    success_count = 0
    for spec_rel, docs_rel in DEFAULT_MAPPING.items():
        spec_path = root / spec_rel
        docs_path = root / docs_rel
        
        if not docs_path.exists():
            print(f"SKIP: ドキュメント {docs_rel} が存在しません。")
            continue
            
        # pushのルール: docs 側の手動修正の方が新しい場合に逆反映
        spec_mtime = get_mtime(spec_path)
        docs_mtime = get_mtime(docs_path)
        
        if docs_mtime > spec_mtime:
            if sync_file(docs_path, spec_path, "push"):
                success_count += 1
        else:
            print(f"UP-TO-DATE: {spec_rel} は最新です（docsの変更はありません）。")
            
    print(f"--- 逆同期完了: {success_count} ファイルを更新しました。---")

def do_diff(root: Path):
    """.spec と docs のタイムスタンプ・乖離状況を表示"""
    print(">>> 仕様とドキュメントの同期状態:")
    print(f"{'成果物パス':<35} | {'.spec最終更新':<20} | {'docs最終更新':<20} | {'ステータス'}")
    print("-" * 95)
    for spec_rel, docs_rel in DEFAULT_MAPPING.items():
        spec_path = root / spec_rel
        docs_path = root / docs_rel
        
        spec_mtime = get_mtime(spec_path)
        docs_mtime = get_mtime(docs_path)
        
        status = "同期済み"
        if spec_mtime == 0.0 and docs_mtime == 0.0:
            status = "両方未作成"
        elif spec_mtime == 0.0:
            status = "docs側のみ存在 (pushが必要かも)"
        elif docs_mtime == 0.0:
            status = "spec側のみ存在 (pullが必要)"
        elif spec_mtime > docs_mtime:
            status = "spec側が新しい (pullが必要)"
        elif docs_mtime > spec_mtime:
            status = "docs側が新しい (pushが必要)"
            
        print(f"{docs_rel:<35} | {format_mtime(spec_mtime):<20} | {format_mtime(docs_mtime):<20} | {status}")

def main():
    parser = argparse.ArgumentParser(description="BitzSDD: .spec ⇄ docs 双方向同期ツール")
    parser.add_argument("action", choices=["pull", "push", "diff"], help="同期アクション")
    parser.add_argument("--root", default=".", help="リポジトリルートのパス")
    args = parser.parse_args()
    
    root_path = Path(args.root).resolve()
    
    if args.action == "pull":
        do_pull(root_path)
    elif args.action == "push":
        do_push(root_path)
    elif args.action == "diff":
        do_diff(root_path)

if __name__ == "__main__":
    main()
