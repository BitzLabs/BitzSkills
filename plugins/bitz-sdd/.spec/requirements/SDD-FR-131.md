---
id: SDD-FR-131
version: 1.0
status: verified
domain: workflow
priority: medium
origin: SI-SDD-019
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-131 spec-issue の accepted→rejected 再裁定遷移

- **説明**: SDD-FR-122 の前提再検証で「乖離が趣旨自体を変える」と判定され人間の再裁定へ戻された
  accepted spec-issue について、再裁定の結果「不採用」を status に反映できるよう、
  `spec_update.py` の権限マトリクスに人間専用遷移 `accepted → rejected` を提供する。
  再裁定で不採用にする場合は、遷移前に当該 spec-issue 本文へ `- **再裁定**: <日付> <理由>` を
  記録する（完了記録 `- **実施**:` と同格の固定語彙）。
- **受入基準 (EARS)**:
  - WHEN 人間が `--by-human` を明示して spec-issue の `accepted → rejected` 遷移を実行する THEN spec_update.py は遷移を適用し STATE.md に記録 SHALL
  - IF `--by-human` なしで spec-issue の `accepted → rejected` 遷移が要求された場合 THEN spec_update.py は遷移を拒否し status を変更しない SHALL
  - WHILE 既存の遷移（open→accepted / open→rejected / accepted→superseded ほか）が使われる間 THE spec_update.py は従来どおりの権限判定を維持 SHALL
- **検証手段**: tests/test_spec_update.py に accepted→rejected の許可（--by-human あり）・
  拒否（--by-human なし）・既存遷移の回帰テストを追加し、pytest green を確認する（unit-test）。
- **Revision History**:
  - 1.0 (2026-07-19) 初版（draft 起票。SI-SDD-019 の accept を受けて要件化）
