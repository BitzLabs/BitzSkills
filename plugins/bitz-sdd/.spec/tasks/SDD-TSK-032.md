---
implements: SDD-FR-145
depends_on: []
boundary: skills/sdd-core/scripts/spec_update.py, spec_transaction.py, tests/test_spec_update.py, tests/test_spec_transaction.py
status: pending
---

### 代行可視化経路のCLI実装（update・transaction・schema v2）

- **作業内容**: `spec_update.py` へ `--on-behalf-of` / `--decision-ref` を追加し、
  人間裁定必須遷移の第2経路（provenance kind `agent-proxy-unverified`）を実装する。
  3項必須検査、decision-ref 検証（1〜512・制御文字なし・パス実在必須 / URL形式のみ）、
  複数 ID のバッチ受理（lock 1回・ID ごと独立 transaction・fail-fast・decision_ref 共有）、
  構造化 event の schema_version 2（`on_behalf_of` / `decision_ref` フィールド）と
  代行明示の表示行を実装し、unit-test を先行追加する。
- **備考**: 対話確認経路・エージェント許容遷移の既存挙動は変更しない（加算のみ）。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
