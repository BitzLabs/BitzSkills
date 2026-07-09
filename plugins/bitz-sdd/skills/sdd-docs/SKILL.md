---
name: sdd-docs
description: BitzSDD の docs/（人間ナラティブ層）を初期化・検証し、.spec/（仕様マスター）と双方向同期（pull/push/diff）するスキル。同梱テンプレートから docs/ ツリー（MASTER.md・01-context〜08-knowledge・ADR）を立ち上げ、docs_inspect.py で構造検証し、sdd_sync.py で .spec/ との間を同期する。「docs/ を初期化して」「同期して」「docsの変更を spec に反映して」「docs を検証して」と言われたときに使用する。
metadata:
  version: "0.2.0"
  author: br7.hide
  created: "2026-07-07"
  updated: "2026-07-09"
---

# sdd-docs

BitzSDD の docs/ 層（人間の意図・永続ナラティブ）を管理し、マスターである `.spec/` との間で双方向同期を行います。

## 1. 責務
1.  **初期化**: `docs/` テンプレートから必要なナラティブドキュメントをセットアップ。
2.  **双方向同期**:
    *   **Pull**: `.spec/` にある最新の設計やディスカバリー成果物を `docs/` に展開する。
    *   **Push**: 人間が `docs/` で編集した設計変更などを検知し、`.spec/` 側のソースファイルに逆反映（マージ）する。
3.  **検証**: `docs_inspect.py` を実行して、docs 側の frontmatter や MASTER.md との乖離、`.spec/requirements.yaml` と ADR の一貫性を検証。

## 2. 実行手順

### 初期化
1.  **project_type の確認**: `app` / `library` / `both` をユーザーに確認する。
2.  **テンプレート展開**: `assets/docs-templates/docs/` を対象リポジトリの `docs/` へコピーする。
3.  **最小起動セットに絞る**: MASTER.md、01-context/mission-vision、glossary、non-goals、02-design/ARCHITECTURE、08-knowledge/LESSONS_LEARNED の6点（library の場合は 02-design/public-api.md を加えた7点）に絞る。
4.  **検証**: `docs_inspect.py` を実行し 0 件通過を確認する。

### 双方向同期
`.spec/` ⇄ `docs/` 間の差分同期には、`sdd_sync.py` スクリプトを使用します。

```bash
# 1. 差分・同期ステータスの確認
python3 scripts/sdd_sync.py diff

# 2. マスターからドキュメントへの同期 (.spec -> docs)
python3 scripts/sdd_sync.py pull

# 3. ドキュメントの手動修正をマスターへ逆反映 (docs -> .spec)
python3 scripts/sdd_sync.py push
```

### ドキュメントの構造検証
```bash
python3 scripts/docs_inspect.py <repo-root>            # → docs-inspection-report.md
python3 scripts/docs_inspect.py <repo-root> --json     # 機械可読出力
python3 scripts/docs_inspect.py <repo-root> --strict   # WARN も失敗扱い
```

## 3. 同期マッピングのルール
*   `.spec/discovery/vision.md` ⇄ `docs/01-context/mission-vision.md`
*   `.spec/discovery/scope.md` ⇄ `docs/01-context/non-goals.md`
*   `.spec/design/domain-model.md` ⇄ `docs/02-design/domain-model.md`
*   `.spec/design/api-design.md` ⇄ `docs/02-design/public-api.md`
*   `.spec/design/architecture.md` ⇄ `docs/02-design/ARCHITECTURE.md`
*   `.spec/design/stories/` の個別ファイルは自動集計され `docs/02-design/domain-story.md` へ Pull 展開されます（Push による逆書き戻しは非対応）。
