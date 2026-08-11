---
implements: FLW-NFR-011
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/schemas/qualification-manifest-v1.schema.json, plugins/bitz-flow/skills/flow-core/references/qualification-protocol.md
status: pending
---

### qualification manifest契約の凍結（必須field・合格条件・保存境界）

- **作業内容**: 実装より先に qualification の公開契約を固定する。FLW-DSN-015 を正として次を定義する。

  - **manifest の必須 field**（trial ごと）: credential class（**値は記録しない**）、capability、
    fixture 初期 digest / 最終 digest、sandbox 境界、CLI / model identity、host event-contract、
    raw-log digest、残留副作用、必須 check ID 集合、positive-control ID 集合、oracle digest。
  - **時刻 field**: coordinator clock 由来の `issued_at` / `completed_at` / `expires_at`。
    TTL は 24 時間で、trial 開始時と confirmation mutation 直前の2点で再検査する。
  - **trial 種別の閉集合**: `Q-NORMAL`（正常入口）/ `Q-REJECT`（既知拒否）/ `Q-CORRUPT`（観測破損）。
    platform × operation ごとに**各ちょうど1件**。
  - **合格条件**: 3 trial すべてが存在し、必須 check の denominator が各 1 以上、検出率 100%、
    positive-control 100%、hazardous event 0 件のときだけ `PASS`。
    **欠落 field・未知 enum・denominator 0 は `FAIL`** とし、**空集合を 100% として扱わない**。
    台帳不整合・TTL 超過・partition は `BLOCKED`（`gate_status` の語彙は既存 schema が正）。
  - **保存境界**: raw log は owner と `evaluation-reviewer` だけが読む。redaction version、
    保持期限（最大 30 日）、削除期限、削除担当を manifest へ持たせる。
    秘密値 canary 未検出・未許可 role・期限超過は Gate 停止。
  - **実行制約**: 10 分以内、harness 再試行 1 回以内。
  - `references/qualification-protocol.md` に上記を人間向けに記述し、schema と同じ field 集合・
    同じ enum を指すようにする。

- **完了条件**: schema が JSON として妥当で、`references/` の記述と同じ field 集合・enum 値を指すこと。
  合格条件（denominator 0 は FAIL、空集合を 100% としない）が schema か文書のどちらかに
  曖昧さなく書かれていること。`gate_status` を既存の evidence ledger schema から重複定義しないこと。
  `python3 <リポジトリ>/scripts/release_check.py` と canonical spec inspect が PASS すること。

- **備考**: 本タスクは契約固定フェーズであり実行コードを含まない。公開 operation を増やさない。
  credential の**値**を manifest へ書ける経路を作らない（class だけを持つ）。
