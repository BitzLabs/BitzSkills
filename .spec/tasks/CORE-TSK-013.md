---
implements: CORE-FR-012
depends_on: []
boundary: plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py,tests/test_spec_status.py
status: done
---

### spec_status.py に accepted 未着手 spec-issue 検知を追加

- **作業内容**:
  1. `tests/test_spec_status.py` にテストを追加する（テスト先行）:
     `status: accepted` の spec-issue を含み、いずれの requirement の `origin:` にも
     その ID への言及が無い fixture を構築し、
     - テキスト出力に「未着手の accepted」件数・ID一覧が現れること
     - `--json` 出力に `accepted_unaddressed`（ID一覧）フィールドが現れること
     - `origin:` に ID の言及がある場合は「未着手の accepted」に含まれないこと
     - 既存の全テストが引き続き green であること
     を検証する。
  2. `spec_status.py` の `next_actions`（L88-111付近）と、集計を組み立てる箇所に実装を追加する:
     - 各 workspace の accepted spec-issue ID と、全 workspace の requirements の `origin:`
       フィールド文字列を突合（部分一致、正規表現でゆるく）し、参照が無い ID を集める
     - 集計結果を `next_actions` に反映（`n_open` の直後、要件系候補より前に追加）
     - JSON 出力に `accepted_unaddressed`（ID配列）を追加
     - 既存の出力キー・既存の EARS 受入基準（CORE-FR-003）は一切変更しない
  3. `.venv/bin/pytest`（**全件**。共有スクリプトへの変更のため部分実行不可 — SDD-FR-112）が
     green であることを確認する。
  4. 実リポジトリのルート workspace で `python3 scripts/spec status .` を実行し、
     SI-CORE-007/008/009/010/013/014/018 が「未着手の accepted」として実地検出されることを
     確認する（受入基準の example-test 相当）。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
