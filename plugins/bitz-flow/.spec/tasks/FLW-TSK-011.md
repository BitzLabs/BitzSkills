---
implements: FLW-FR-003, FLW-CON-002
depends_on: [FLW-TSK-009]
boundary: tests/test_flow_contract.py, tests/fixtures/flow/
status: pending
---

### M0 golden fixture と契約 unit test

- **作業内容**: M0 の公開契約を機械検証する unit test と golden fixture を作る。
  検証対象は次のとおり。

  - 公開入口が `flow.py` だけであること（`flowlib` の直接呼出しを公開契約として扱わない）
  - 3 operation の result が operation 別 JSON Schema に一致すること（golden schema 一致 100%）
  - compact renderer の固定 token・固定 field 順・1項目1行・0件 field と null の省略
  - 終了コードの写像（0 / 2 / 3 / 5 / 6 / 8 と M0 で到達し得ないコードの非発生）
  - truncation の可視化（`shown` / `total` / snapshot 拘束 cursor と絞込み next action）
  - `result_digest` の決定論性と、result を1保存単位として再計算できること
  - raw command・stdout・stderr・environment・credential が出力に現れないこと
  - 未対応 operation で raw fallback を提示しないこと
  - `git status` / `git diff-summary` の byte 数を記録し、回帰判定の基準値として fixture manifest へ固定する

  Git fixture は dirty、rename、binary、非 ASCII path、detached HEAD、空リポジトリを含める。
  既存の `tests/` 規約（`conftest.py` の共有 fixture、動的収集される検査との整合）に合わせる。
- **完了条件**: `.venv/bin/pytest -q` が全件 PASS すること。
  fixture manifest に operation 別の p90 と absolute byte 上限が記録され、以後の回帰判定に使えること。
  変異試験（renderer の順序を崩す・schema field を落とす）で当該テストが落ちることを確認すること。
- **備考**: byte 削減率そのもの（status 70%・diff-summary 80%）の判定は FLW-TSK-012 の
  3platform 実測で行う。本タスクは測定の基準値と回帰検出力を用意する。
