---
id: SI-QLT-001
raised_by: ユーザー要望: SDDでbitz-qualityを充実
target: レビュー基盤の仕様化とsdd-reviewからの段階的所有権移管
proposed_change_type: new
status: open
origin: SI-CORE-040
github_issue: https://github.com/BitzLabs/BitzSkills/issues/269
---
- **目的**: bitz-qualityのレビュー機能を、モデルごとの即興に依存しない再現可能なQA基盤へ発展させる。
  サブエージェントの役割・入力・出力、個別レビューと統合結果のschema、Gate判定、追跡、監査証跡を
  公開契約として定め、最終的にbitz-sddの`sdd-review`が持つ汎用レビュー責務を段階移管できる状態にする。
- **提案する修正**:
  1. Discoveryで利用者、成功指標、対象/対象外、移管のkill条件を確定する。
  2. review profile、perspective、reviewer invocation、individual result、synthesis、finding、
     gate preconditionのversion付きschemaを設計する。
  3. プラットフォーム固有のサブエージェント定義と、モデル非依存の論理Reviewer契約を分離する。
  4. 現行`sdd-review`の出力をgolden fixtureとして互換adapter/canaryを作り、parity確認後だけ所有権を移す。
- **対象ファイル**: `plugins/bitz-quality/.spec/discovery/`、`.spec/requirements/`、`.spec/design/`、
  将来の`skills/quality-review/`・`agents/`・schema・tests。移管段階では`plugins/bitz-sdd/skills/sdd-review/`
  とSDD側requirements/design/migrationへ波及する。
- **確認観点**: 同一入力の決定性、schema閉集合、未知/欠落field、finding ID一意性、P0/P1追跡、
  stale target SHA、部分失敗、timeout、重複排除、モデル/プラットフォーム差、token/時間上限、
  既存review成果物の読取互換、SSOTとstatus更新権限の非侵害。
- **影響推定・ロールバック**: 公開API・成果物schema・プラグイン間責務を変更するため通常フローと
  Discovery/Design Gateを必須とする。新基盤は加法的に導入し、canary完了まで`sdd-review`を正として残す。
  parity未達時はadapterを無効化し、既存成果物を変換・削除しない。
- **依存**: SI-CORE-040、SDD-FR-158/159/161、SI-SDD-031/041/042、bitz-flow V2 Promotion Gate。
- **推薦**: **accept**。ただし「quality側レビュー基盤の完成」と「sdd-review所有権移管」は別Gate・別PR系列に分ける。
