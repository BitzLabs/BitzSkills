---
id: SI-FLW-082
raised_by: FLW-TSK-106実装前検査
target: FLW-TSK-106〜114のplugin version bump変更境界
proposed_change_type: modify
status: accepted
---
- **目的**: skill配下のscript/schemaを変更する各実装PRが、plugin version bump規約とtask boundary規律を
  同時に満たせるようにする。
- **発見した事実**:
  - AGENTS.mdはskill変更時にskill metadata version/updatedとplugin versionのbumpを要求する。
  - plugin versionは3マニフェストとmarketplaceで整合させる必要がある。
  - FLW-TSK-106〜114のboundaryは担当module/schema/testだけで、上記release metadataを含まない。
  - 6実装PRへ分割する設計のため、後回しの一括bumpでは各PR単体が規約を満たさない。
- **提案する修正**: **accept推薦**。各実装PRの先頭taskをrelease integration ownerとし、そのtask boundaryへ
  `flow-core/SKILL.md`、bitz-flowの3マニフェスト、root marketplaceを追加する。PRごとに
  `<リポジトリ>/scripts/bump_version.py bitz-flow patch`を1回実行し、SKILL metadataもpatch bumpする。
  PR1はFLW-TSK-106、PR2は111、PR3は108、PR4は112、PR5は109、PR6は110をownerとする。
- **対象ファイル**: `.spec/tasks/FLW-TSK-106.md`〜`114.md`、`plugins/bitz-flow/skills/flow-core/SKILL.md`、
  `plugins/bitz-flow/.claude-plugin/plugin.json`、`plugins/bitz-flow/plugin.json`、
  `plugins/bitz-flow/.codex-plugin/plugin.json`、`.claude-plugin/marketplace.json`。
- **確認観点**: 1 PRあたりbump 1回、3マニフェスト/marketplace/SKILL version一致、
  `release_check.py` PASS、並列PRへ同じrelease metadata boundaryを割り当てないこと。
- **影響推定・ロールバック**: 振る舞いは変えず配布versionだけをpatch更新する。各PRをrevertすれば対応bumpも
  同時に戻る。PR1/2はrelease metadata競合を避けるため直列化が必要になる。
- **依存**: AGENTS.mdのversion bump規約、FLW-DSN-017 v2.1 §9.1、FLW-TSK-106〜114。
