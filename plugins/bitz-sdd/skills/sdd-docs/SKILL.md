---
name: sdd-docs
description: BitzSDD の docs/（人間ナラティブ層）を日本語6章で初期化・検証し、.spec/（仕様マスター）と双方向同期（pull/push/diff）するスキル。必須6章、宣言式の任意リファレンス章、管理対象外パス、安全な旧8章移行を扱う。「docs/ を初期化して」「同期して」「docsを日本語化して」「旧8章を移行して」「docs を検証して」と言われたときに使用する。
metadata:
  version: "1.0.0"
  author: br7.hide
  created: "2026-07-07"
  updated: "2026-07-18"
---

# sdd-docs

BitzSDD の docs/ 層（人間の意図・永続ナラティブ）を管理し、マスターである `.spec/` との間で双方向同期を行います。

## 1. 責務
1.  **初期化**: 日本語の必須6章テンプレートからナラティブドキュメントをセットアップ。
2.  **双方向同期**:
    *   **Pull**: `.spec/` にある最新の設計やディスカバリー成果物を `docs/` に展開する。
    *   **Push**: 人間が `docs/` で編集した設計変更などを検知し、`.spec/` 側のソースファイルに逆反映（マージ）する。
3.  **検証**: `docs_inspect.py` を実行して、docs 側の frontmatter や MASTER.md との乖離、`.spec/requirements.yaml` と ADR の一貫性を検証。

## 2. 実行手順

### 初期化
1.  **project_type の確認**: `app` / `library` / `both` をユーザーに確認する。
2.  **テンプレート展開**: `assets/docs-templates/docs/` を対象リポジトリの `docs/` へコピーする。
    `00_はじめに`、`01_システム仕様`、`02_ユースケース`、`03_設計仕様`、
    `04_テスト仕様`、`05_リリース・運用` の6章は必須で削除しない。
3.  **project_type の反映**: `MASTER.md` と各文書の `project_type` を合わせる。`app` で
    `03_設計仕様/公開API.md` を削除する場合はMASTERの同レジストリ行も同時に削除する。
    `library` / `both` では公開API文書を必須とする。
4.  **任意章と管理対象外**: 外部API・CLI/SDK・移行ガイドが多い場合だけ
    `assets/docs-templates/optional/06_リファレンス/` をdocsへコピーし、MASTERへ
    `optional_chapters: reference` と文書行を追加する。調査・アーカイブはdocsルート相対パスを
    `excluded_paths` にカンマ区切りで宣言する。必須/任意章自身は除外しない。
5.  **検証**: `docs_inspect.py --strict` を実行し、ERROR/WARNとも0件を確認する。

### 旧英語8章からの移行

既存docsは手作業で一括移動せず、dry-run既定の移行CLIを使う。

```bash
# 予定・衝突だけを表示（変更なし）
python3 scripts/migrate_docs.py --root <repo-root>

# 全preflight成功後に適用。hash付きmanifestをdocs/へ保存
python3 scripts/migrate_docs.py --root <repo-root> --apply

# manifestと移行後hashを照合して旧章へ戻す
python3 scripts/migrate_docs.py --root <repo-root> --rollback
```

apply後は必ず `docs_inspect.py --strict` と `git diff` を確認する。衝突、旧新混在、
移行後の手動変更がある場合は安全側に停止し、暗黙上書きしない。

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
*   `.spec/discovery/vision.md` ⇄ `docs/00_はじめに/ミッション・ビジョン.md`
*   `.spec/discovery/scope.md` ⇄ `docs/00_はじめに/対象外.md`
*   `.spec/design/domain-model.md` ⇄ `docs/03_設計仕様/ドメインモデル.md`
*   `.spec/design/api-design.md` ⇄ `docs/03_設計仕様/公開API.md`
*   `.spec/design/architecture.md` ⇄ `docs/03_設計仕様/アーキテクチャ.md`
*   `.spec/design/data-model.md` ⇄ `docs/03_設計仕様/データモデル.md`
*   `.spec/design/stories/` の個別ファイルは自動集計され `docs/03_設計仕様/ドメインストーリー.md` へ Pull 展開されます（Push による逆書き戻しは非対応）。
