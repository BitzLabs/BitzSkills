---
id: SI-SDD-016
raised_by: FLW-FR-001の反復検証と実行時間差分振り返り（2026-07-18）
target: 検証コマンド結果の安定した機械可読証跡
proposed_change_type: new
status: open
---
- **目的**: FLW-FR-001の検証では同じ236件のpytestを複数回実行し、3.66秒・3.96秒・3.80秒と
  実行時間が変動した。test-specへ手作業で結果を書いた後にも最終検証を再実行したため、会話上の最新値と
  文書値が異なった。green判定に必要な安定情報と観測的な実行時間を分離し、コマンド実出力に基づく
  機械可読証跡を一度生成してsdd-report/test-specから参照できるようにする。
- **提案する修正**:
  1. `.spec/verification/<requirement-id>.json`等の配置、schema、statusをDesign Gateで定義する
  2. requirement ID、commit SHA、実行コマンド識別子、終了コード、passed/failed件数、UTC実行時刻、
     tool versionを安定項目として記録し、durationは非正規の観測値として分離する
  3. raw stdout/stderr・環境変数・token・絶対ホームパスを保存せず、許可リスト要約だけを生成する
  4. sdd-testが証跡を生成し、sdd-report/spec_inspectが参照切れ・失敗・古いcommitを検出する
  5. test-spec本文の手動数値更新は任意のナラティブに縮退し、機械判定の正をJSONへ一本化する
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-test/`の新規記録スクリプト候補、
  sdd-coreのartifact/lifecycle/verification契約、`spec_inspect.py`、`sdd-report`、関連テスト、
  SDD-FR-060/061・SDD-FR-110/111の改訂または後継要件、bitz-sddマニフェスト。
- **確認観点**: 同じcommit・同じ結果の再実行でgreen判定が変わらないこと。実行時間差だけでdiffを
  必須にしないこと。失敗・一部未実行・commit不一致・証跡改ざん・機密値混入を検出すること。
- **影響推定・ロールバック**: `--impact SDD-FR-060` はbitz-sddタスク1件、`--impact SDD-FR-110` は
  2件。新しい仕様成果物schemaと複数スキルの接続を伴うため通常SDDフロー + Design Gate必須。
  新artifactを加法的に導入し、問題時は参照機能ごとrevertして既存test-specへ戻す。
- **依存**: SDD-FR-060/061（テスト仕様・実行）、SDD-FR-110/111（レポート）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。実出力根拠を強化し、ナラティブ文書を置換しない |
| ガードレール抵触 | 条件付きでなし。許可リスト形式で機密値を保存しない |
| 影響範囲 | sdd-test/core/report、artifact schema、検査・テスト |
| 軽量レーン適否 | 不適。新しい仕様成果物schemaと検証ゲート接続を追加する |

**推薦: accept**。反復検証のたびに手動証跡が揺れ、最終結果との同期を人手に依存しているため。
