---
id: SI-ENV-024
raised_by: SI-CORE-032 実装（PR #74）の振り返り（2026-07-19）
target: 既展開環境のレジストリに展開時バージョン記録が無く env-update が常に安全側停止する
proposed_change_type: modify
status: accepted
origin: root（SI-CORE-032 の実装振り返り）
---
- **目的**: env-update（ENV-FR-011）が読むバージョン記録 `bitz-env-version` は
  PR #74 で env-init に追加された stamp 機構であり、**それ以前に env-init で展開済みの
  全環境（本リポジトリ自身を含む）にはレジストリに記録が無い**。このため既展開環境では
  env-update が仕様どおり即・安全側停止し、実質使えない。stamp の後付け救済パスを
  正式に用意する。
- **提案する修正**:
  1. env-doctor に診断項目を追加する: レジストリ（`.claude/bitz-env.local.md`）に
     `bitz-env-version` が無い場合を検出し、「stamp 後付け手順」を修正案として提示する
     （doctor は読み取り専用のまま。ENV-FR-011 との整合を明記）
  2. stamp 後付けの正式手順を規定する。候補: (a) env-update 自身が「記録なし」を検出した際、
     現状の生成物と各バージョンの照合で D を推定し、ユーザー確認のうえ stamp して続行する
     救済フロー、(b) env-init の再実行（冪等展開）で stamp させる案内のみ。
     いずれにするかは要件化時に判断（推奨は (a)。(b) は env-init の二重初期化防止との
     整合確認が必要）
  3. env-update SKILL.md の安全側停止の文言に、救済手順への誘導を追記する
- **対象ファイル**: `plugins/bitz-env/skills/env-doctor/SKILL.md`、
  `plugins/bitz-env/skills/env-update/SKILL.md`（文言追記）、必要なら env-init、
  マニフェスト bump。
- **確認観点**:
  - 記録なし環境で env-doctor が欠如を検出し修正案を提示すること
  - 救済手順の実施後に env-update が正常系（D 比較→差分更新）へ進めること
  - doctor の読み取り専用が維持されること
- **影響推定・ロールバック**: 既存スキルへの診断項目・文言の追加が中心。単独 revert 可能。
- **依存**: ENV-FR-011（実装済み・前提）。関連: CORE-CON-008/009。
- **実施**: 2026-07-19 ENV-FR-012 として要件化（案 (a) 採用・ENV-DSN-002 設計記録）し、
  ENV-TSK-015 で実装・verified 到達（`evals/env-update/stamp-rescue/` R1〜R4 PASS）。
- **予備判定（推薦・裁定は人間）**: **accept を推薦**。既展開環境で env-update が
  機能しないという実害があり、放置すると「update があるのに使えない」状態が続く。
  ガードレール抵触なし（stamp 書き込みはユーザー確認つき・対象プロジェクト内）。
  軽量レーン適否: 救済フロー (a) を採る場合はレジストリ書式（契約）に触れるため通常フロー推奨。
