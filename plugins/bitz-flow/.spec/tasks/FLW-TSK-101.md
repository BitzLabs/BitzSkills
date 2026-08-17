---
implements: FLW-NFR-011
depends_on: []
boundary: scripts/agy_guard.py, tests/test_agy_guard.py
status: done
---

### 測定系ガードを正規化後のパス判定と読み取り allowlist へ改める

- **作業内容**: `scripts/agy_guard.py` は eval harness が所有する測定系保全の統制であり、
  bitz-flow の配布物ではない（設計上の持ち主は `FLW-DSN-014`）。実測で2つの構造的な穴がある。
  - **パス正規化**: `ASK_PATTERNS` が生文字列の正規表現なので `/./` や重複スラッシュを
    挟むだけで外れる。payload から候補文字列を再帰的に取り出し（既存の `_strings` は
    定義済みだが**未使用**である。これを実際に使う）、`~` 展開・`.` / `..` / 重複スラッシュの
    解決を経た**正規化後の文字列**へ照合する。正規化前の生文字列だけを見る照合を残さない。
  - **極性の反転**: ガード資産の保護が `(chmod|chown|mv|cp|rm|truncate|tee)` という
    書き込み動詞の列挙であり、`sed -i` / リダイレクト / `install` / `dd` / `patch` /
    `ln -sf` / インタプリタからの `open(..., "w")` が素通りする。動詞の列挙に安全性を
    載せる方式は成立しない。**ガード資産のパスに言及する payload は既定で deny** し、
    読み取り専用の許可形（`cat` / `grep` / `head` / `tail` / `diff` / `git show` 等の
    enumerate された read allowlist に完全一致するもの）だけを通す fail-closed へ改める。
  - 評価順 DENY → ASK → ALLOW は維持する。
- **範囲外**: bitz-flow が配布する product 側の承認強度（別タスク）。
- **検証**: 変種を**表としてテスト側に持つ**。パス正規化の変種（`/./`・`//`・`..` を含む形、
  `~` 表記）、書き込み動詞の変種（上記の各例）を列挙し、**deny / force_ask にならない
  ケースが1つでもあれば FAIL** とする。既存の M2 confirmation subject の許可形が
  引き続き通ることも回帰として確認する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
