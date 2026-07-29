---
id: SI-CORE-037
raised_by: SI-SDD-011/014/016 実装後の振り返り（2026-07-29）
target: plugin-creator / skill-creator が仕様駆動の対象外
proposed_change_type: new
status: open
---
- **目的**: AGENTS.md は「このリポジトリ自身の開発も sdd-core 準拠で行う（ドッグフーディング）」と
  定めているが、実測では **plugin-creator と skill-creator の要件が 0 件**である
  （`.spec/` ディレクトリは存在するが `requirements/` が空）。マーケットプレイスの
  6 プラグイン中 2 つが仕様駆動の外にあり、とくに skill-creator は
  「スキル開発の全工程を統括する」中核プラグインである。契約（SKILL.md frontmatter 仕様・
  skill-packager の配置先パス・validator のチェックリスト）を持ちながら、その契約が
  EARS 要件として起票されておらず、変更時に spec_inspect の検査対象にならない。
- **提案する修正**:
  1. 両プラグインを reverse-derived で起票するか、意図的に対象外とするかを裁定する
     （bitz-sdd / bitz-env の前例に倣うブラウンフィールド起票が既に確立している）
  2. 対象外とする場合、その理由と適用範囲を `.spec/PROJECT.md` または AGENTS.md に明記し、
     「ドッグフーディング」の宣言と実体の乖離を解消する
  3. 起票する場合は namespace（`SKC-` / `PLG-` 等）と番号ブロック割当を決め、
     `.claude-plugin/marketplace.json` の登録プラグインと `.spec/` を持つワークスペースの
     対応を機械検証できるようにする（現状は乖離しても誰も気づけない）
  4. 検証の canonical コマンド（`--workspace . plugins/*`）は既に両プラグインを走査しており、
     要件 0 件でも PASS するため、**空のワークスペースが正常なのか未着手なのかを区別できない**。
     この区別を可能にする
- **対象ファイル**: `plugins/plugin-creator/.spec/`、`plugins/skill-creator/.spec/`、
  `.spec/PROJECT.md`、`AGENTS.md`、`scripts/release_check.py`（marketplace と .spec の対応検証）、
  関連する CORE-FR / CORE-CON 要件、関連テスト。
- **確認観点**: 宣言（ドッグフーディング）と実体が一致すること。意図的な対象外が
  「未着手」と区別できること。既存 5 ワークスペースの判定を変えないこと。
  reverse-derived を行う場合、実装から起票した要件が実装の写像に堕さないこと。
- **影響推定・ロールバック**: 2 は文書のみで軽量レーン可。1・3・4 はリポジトリ全体の
  ドッグフーディング方針に触れるため通常フロー。起票を選ぶ場合は 2 プラグイン分の
  reverse-derived が発生するため、bitz-sdd（30 件）・bitz-env（19 件）と同規模を見込む。
  問題時はワークスペースごと revert して現状（要件 0 件）へ戻せる。
- **依存**: CORE-CON-* のドッグフーディング宣言、SI-CORE-023（canonical 検証コマンド）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。宣言と実体の乖離を解消する方向であり、既存要件は変えない |
| ガードレール抵触 | なし |
| 影響範囲 | 2 プラグインの `.spec/`、リポジトリ方針文書、release_check |
| 軽量レーン適否 | 2 のみ可。1・3・4 は不適（方針と検証契約に触れる） |

**推薦: accept、ただしスコープを分割する**。「宣言と実体の乖離を明示的に解消する」（2・4）は
低コストで効果が確実なため先行させ、reverse-derived の実施（1・3）は工数が大きいので
方針裁定の後に別途起票するのが妥当。skill-creator は他プラグインより変更頻度が低く、
起票の緊急性は SI-SDD-028 / 029 より低い。
