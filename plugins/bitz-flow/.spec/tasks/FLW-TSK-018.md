---
implements: FLW-NFR-008
depends_on: FLW-TSK-012
boundary: evals/flow-core/fixtures/v2-skill/SKILL.md
status: done
---

### SI-FLW-013 の裁定に基づき v2 SKILL.md から出力形式の選択肢を落とす

- **作業内容**: `SI-FLW-013` の裁定（accept・案1＋案2 併用）に基づき、`--format json` を
  選択肢として提示するのをやめ、同じ operation の再取得を禁止形の単文で止める。

  | 箇所 | 変更 |
  |---|---|
  | 使用法の行 | `[--format compact\|json]` を削除し、形式の選択肢を見せない |
  | 出力の読み方（見出し直下） | 「既定の `--format compact` は」→「result は」 |
  | 読み方の規範 | 「`--format json` は…に使う」を削除し、**「同じ operation を、出力形式を変えて呼び直してはならない」**を追加 |
  | truncation | 「残りが要るなら `--limit` で取り直してよい」を明記 |

  `--limit` の全件取得は**正当な判断として明示的に許容**する。打ち切りを見て残りを
  取りに行くのを抑止すると情報の欠落を招くためである。文章量は増やしていない
  （`FLW-DSN-010`）。platform 別の文面分岐は行わない（`SI-FLW-008` の裁定方針を踏襲）。

- **完了条件**: 再実測で次を満たすこと。
  1. antigravity の `--format json` 再取得が **0 件**になること
  2. `dirty-status` の byte 削減 median が **40% 以上**へ回復すること
  3. **claude-code / codex-cli の既達水準を落とさないこと**（両者は現状 0 件であり、
     共通 fixture の変更で悪化させない）

- **備考**: 本タスクは fixture の変更のみで、稼働中の v1 と配布物には触れない
  （`FLW-DSN-011` により v2 は Promotion Gate まで fixture 扱い）。単独 revert できる。
  案3（dispatcher 側で警告を出す）は採らなかった。dispatcher は状態を持たないため
  「compact で取得済みか」を判定できず、M0 の read-only 契約にも合わないためである。
  裁定記録は `.spec/reports/decision-2026-08-06-si-flw-013-compact-only.md`。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
