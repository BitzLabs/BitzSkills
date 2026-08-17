---
implements: FLW-CON-007
depends_on: FLW-TSK-096
boundary: tests/test_flow_contract_vocabulary.py, tests/test_flow_m2_worktree.py, plugins/bitz-flow/.spec/design/FLW-DSN-016.md
status: pending
---

### 三者照合を全 namespace へ拡張し照合の網羅性そのものを検査する

- **作業内容**: `FLW-CON-007` の受入基準を機械検証する。既存 `M2-FLT-023` は宣言された
  全 namespace ではなく3 namespace しか照合しておらず、`cause` を走査していなかったため
  schema 欠落が沈黙した。
  - `FLW-DSN-016` §2 の閉集合表と所在表をパースし、**表から得た namespace 集合**を回す。
    テストが知っている namespace だけを回す形にしない。
  - 設計 ⊆ schema / schema ⊆ 設計 / 設計 ⊆ 実装定数 / 実装定数 ⊆ 設計 の**4方向**を検査する。
  - 実装定数の所在が未宣言、あるいは解決できない namespace は skip せず FAIL させる。
  - 同一 namespace が複数 schema に現れる場合（`gate_status` / `guard_identity_kind`）は
    全出現を対象とし、schema 間不一致も FAIL させる。
  - 閉集合表・所在表・実際に照合した namespace の**3集合の完全一致**を別アサーションで検査する。
  - 多重語一覧は閉集合表から再生成し、`FLW-DSN-016` の
    `<!-- BEGIN GENERATED: multi-namespace-values -->` 区間との一致を検査する。
    比較は case-sensitive とする（`dirty` と `DIRTY` を同一視しない）。
  - 設計名 `result_code` と schema 上の field 名 `code` の対応は所在表から解決する。
- **範囲外**: schema と実装定数の新設そのもの（先行タスク）。
- **検証**: 意図的に壊した入力（schema から1値削る / 所在表の行を消す / 生成区間を書き換える /
  実装定数に値を足す）のそれぞれで**必ず FAIL する**ことを陽性対照で確認する。
  現状の実体に対して回して、`cause` と `result_code` の乖離を実際に検出することを示す。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
