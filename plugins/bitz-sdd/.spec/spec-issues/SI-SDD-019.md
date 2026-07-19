---
id: SI-SDD-019
raised_by: SI-CORE-013/014 の再裁定セッション（2026-07-19。SDD-FR-122 前提再検証の実地適用）
target: spec_update.py の spec-issue 遷移語彙（accepted 後の再裁定を受け止める rejected 遷移の不在）
proposed_change_type: modify
status: accepted
---
- **目的**: SDD-FR-122 は「accepted spec-issue の着手時前提再検証で乖離が趣旨自体を変える場合、
  実装せず人間の再裁定へ戻す」と規定するが、`spec_update.py` の `TRANSITIONS["spec-issue"]` には
  再裁定の結果「不採用」を受け止める遷移が存在しない（`open→rejected` はあるが `accepted→rejected` が
  未定義。`accepted→superseded` は重複統合専用で `superseded_by:` を要求するため流用できない）。
  再裁定の判定結果を status に反映できず、当該 issue が `spec_status.py` の accepted 未着手検知
  （CORE-FR-012）に永久に残り続ける。SI-CORE-013/014 の再裁定（不採用）で実地に発生した欠落。
- **提案する修正**:
  1. `TRANSITIONS["spec-issue"]` に `("accepted", "rejected"): "human"` を追加する
     （人間専用。SDD-FR-122 の再裁定分岐の受け皿）
  2. sdd-core `references/lifecycle.md` の spec-issue 状態遷移図・補足を追随させる
     （再裁定で戻す場合は issue 本文に `- **再裁定**: <日付> <理由>` を記録する語彙も規定する）
  3. `tests/` の spec_update 遷移テストに accepted→rejected（--by-human 有/無）を追加する
  4. bitz-sdd マニフェスト bump
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_update.py`、
  `plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md`、対応するテスト、
  bitz-sdd 3マニフェスト。
- **確認観点**: `accepted→rejected` が `--by-human` なしで拒否されること（exit 3）、
  `--by-human` で遷移し STATE.md に記録されること、既存遷移の回帰がないこと、
  release_check / spec inspect / 全 pytest PASS。
- **影響推定・ロールバック**: 遷移マトリクスへの1エントリ追加で既存遷移の意味は不変。
  単独 revert 可能。SDD-FR-122（前提再検証）の第3分岐（人間の再裁定へ戻す）と整合し、
  裁定結果の記録先が閉じる。
- **依存**: なし（SDD-FR-122 は実装済み。本 issue はその受け皿の補完）。
- **予備判定（推薦）**: **accept 推奨**。SDD-FR-122 が規定する再裁定フローの出口が語彙に無く、
  規律とツールが矛盾している。SI-CORE-013/014 の status 反映が本 issue の実施を待っている。
- **実施**: 2026-07-19 SDD-FR-131 として要件化し verified 到達（SDD-TSK-016。テスト先行:
  tests/test_spec_update.py に許可/拒否テスト追加 → TRANSITIONS へ
  `("accepted", "rejected"): "human"` 追加 → lifecycle.md 追随、pytest 238 green、bitz-sdd 2.2.0）。
