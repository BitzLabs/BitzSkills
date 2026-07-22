---
id: SI-SDD-015
raised_by: SI-FLW-001の実施マーカー未記録振り返り（2026-07-18）
target: verified要件に対応するspec-issue実施記録漏れの機械検出
proposed_change_type: modify
status: accepted
---
- **目的**: SI-SDD-005でspec-issue完了記録を `- **実施**:` に統一し、sdd-issueの手順7へ
  明文化済みである。一方、SI-FLW-001はorigin要件FLW-FR-001がverifiedへ到達しても実施マーカーがなく、
  `spec status` はorigin参照により「未着手ではない」と正しく判定するものの、spec-issue単体を読むと
  実装根拠・PR・verified要件が分からない。既存規律を再定義せず、記録漏れを機械的に警告する。
- **提案する修正**:
  1. accepted spec-issueをoriginに持つrequirementがverified/promotedへ到達した際、issue本文に
     `**実施**:` が無ければ `completion_record_missing` として集計する
  2. `accepted_unaddressed`とは別フィールド・別警告にし、実装済みを未着手へ戻す誤判定を避ける
  3. 読み取り専用で修正候補（要件ID・status・検証根拠の参照先）を提示し、自動追記はしない
  4. sdd-test/implement完了チェックリストにも実施マーカー確認を接続し、fixtureで漏れ有無を検証する
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py`、
  `plugins/bitz-sdd/skills/sdd-issue/SKILL.md`またはsdd-implement/testの完了チェックリスト、
  `tests/test_spec_status.py`、lifecycle説明、CORE-FR-012の改訂または後継要件、bitz-sddマニフェスト。
- **確認観点**: SI-SDD-005の固定語彙を再利用し、新statusを追加しないこと。origin参照あり・マーカーなし、
  軽量レーンのマーカーあり、複数要件、deprecated/superseded、open issueを区別すること。
- **影響推定・ロールバック**: `--impact CORE-FR-012` はルートのタスク・テスト2件。JSONへの加法的
  フィールドと警告追加だが公開CLI契約に触れるため通常SDDフローを推奨。新集計をrevertしても
  accepted_unaddressedの既存判定は維持される。
- **依存**: SI-SDD-005（実施語彙と運用規律、実装済み）。CORE-FR-012（未着手集計）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。SI-SDD-005の規律を機械検出で補強する |
| ガードレール抵触 | なし。自動書込みを行わない |
| 影響範囲 | spec_statusの追加警告・JSON・完了チェックリスト・テスト |
| 軽量レーン適否 | 不適。公開JSON出力と完了判定補助の契約追加 |

**推薦: accept**。既に制度化した必須記録が実運用直後に漏れ、手順だけでは再発を防げなかったため。

- **実施**: 2026-07-22 accepted 化（人間裁定）。SDD-FR-142（`completion_record_missing` 機械警告）へ
  要件化し実装・検証（SDD-DSN-004 と co-design、SDD-FR-141 と同一 PR）。SDD-FR-142 verified 済み。
