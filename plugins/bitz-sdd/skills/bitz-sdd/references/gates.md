# 派生と Promotion Gate

## docs/ → .planning/ の派生（半自動）

- planエージェントが docs/ の該当節から requirements/ の **draft** と specs/<feature>/ の骨子を生成する
- 生成物の frontmatter に `derived_from: docs/…@<コミットSHA>` を必ず記録
- draft → approved は人間専権。**生成は速く、統制は保つ** — 派生の自動化と契約の承認を分離する設計

## Promotion Gate（verified → promoted、人間承認）

feature 完了時の唯一の逆流点。planエージェントがドラフト一式を用意し、人間が以下のチェックリストで裁定する:

1. □ docs/ 更新ドラフトの承認（ARCHITECTURE 変更・ADR 追記・glossary 新語）
2. □ LESSONS_LEARNED 候補の取捨選択
3. □ tombstone テストの削除可否判定（後継テスト green を確認）
4. □ stale マークゼロの確認（spec_inspect.py レポートの目視）
5. □ specs/<feature>/ を `.planning/archive/<date>-<feature>/` へアーカイブ

エージェントの役割: 各項目のドラフト・証跡を揃えてチェックリスト形式で提示すること。**自分でチェックを付けて通過させない。**

Gate を自動化しない理由: ここが緩むと docs/ が「エージェントの作業ログ置き場」に劣化し、永続層の信頼が死ぬ。
