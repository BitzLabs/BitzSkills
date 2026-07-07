---
name: sdd-docs
description: BitzSDD の docs/（人間ナラティブ層）を初期化・検証するスキル。同梱テンプレートから docs/ ツリー（MASTER.md・01-context〜08-knowledge・ADR）を立ち上げ、docs_inspect.py で構造検証する。「docs/ を初期化して」「ドキュメント構成を作って」「ADR を書きたい」「docs を検証して」と言われたとき、または bitz-sdd スキル導入時に docs/ が未整備のときに使用する。.planning/ 側の運用（要件・EARS・タスク）は bitz-sdd スキルの管轄。
metadata:
  version: "0.1.0"
  author: br7.hide
  created: "2026-07-07"
  updated: "2026-07-07"
---

# sdd-docs

BitzSDD の docs/ 層（人間の意図・永続ナラティブ）を立ち上げ、健全に保つ。
docs/ が持つのは WHY と人間向け WHAT のみ。検証可能な契約・実行状態は `.planning/`
（`bitz-sdd` スキルの管轄）に置き、docs/ → .planning/ → code の一方向派生を守る。

## 初期化ワークフロー

1. **project_type の確認**: `app` / `library` / `both` をユーザーに確認する
   （library は公開APIの互換性管理が必須になり、必要文書が1つ増える）
2. **テンプレート展開**: `assets/docs-templates/docs/` を対象リポジトリの `docs/` へ
   コピーする。記憶から書き起こさない（書式ドリフト防止）
3. **最小起動セットに絞る**: まず ★6点だけを残す — MASTER.md /
   01-context/mission-vision / glossary / non-goals / 02-design/ARCHITECTURE /
   08-knowledge/LESSONS_LEARNED。library は ☆ 02-design/public-api.md を加えて7点。
   残りのテンプレートは削除し、後から必要になった層だけ `_scaling.md` の拡張トリガーに
   従って足す。空フォルダを先に切らない
4. **app/library 分岐の解決**: 各文書 frontmatter の `project_type` を設定し、本文中の
   `<!-- app 固有 -->` / `<!-- library 固有 -->` ブロックは該当しない側を削除する
5. **プレースホルダ埋め**: `<Project Name>` 等をヒアリングで埋め、MASTER.md の
   文書レジストリを実際に残した文書と一致させる
6. **検証**: docs_inspect.py を実行し 0 件通過を確認する

## 検証

```bash
python scripts/docs_inspect.py <repo-root>            # → docs-inspection-report.md
python scripts/docs_inspect.py <repo-root> --json     # 機械可読出力
python scripts/docs_inspect.py <repo-root> --strict   # WARN も失敗扱い
```

ERROR があれば終了コード 1（CI ゲート用）。チェック一覧と exempt 規則は
`scripts/README.md` を参照。`bitz-sdd` の Verify フェーズと Promotion Gate では、
.planning/ 側の spec_inspect.py（bitz-sdd 同梱）と本スクリプトの両方を実行する。

## 運用規約の要点

展開後は `docs/_conventions.md` が正。ここでは判断に必要な要点のみ:

- 全文書に共通 frontmatter（id / title / status / version / changeImpact /
  project_type / updated / owner）。id は `DOC-<area>-<slug>` 形式
- changeImpact → version bump: low=patch / medium=minor+CHANGELOG /
  high=major+CHANGELOG+Revision History+レビュー
- 新しい情報の置き場所は Decision Matrix で決める: 検証可能な契約→`.planning/`、
  決定の理由・不採用案→ADR、恒久的な学び→LESSONS_LEARNED、背景・用語→01-context、
  構造・設計→02-design
- ADR は `02-design/decisions/ADR-NNNN-<slug>.md`（4桁ゼロ埋め）。テンプレートは
  `assets/docs-templates/docs/02-design/decisions/ADR-template.md`
- エージェントは docs/ へ書き込まない。.planning/ からの閉じ戻しは
  Promotion Gate（人間承認）のみ
