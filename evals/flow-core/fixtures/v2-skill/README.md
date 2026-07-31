# v2 flow-core SKILL.md（eval fixture）

このディレクトリの `SKILL.md` は **M0 eval 用の fixture** であり、配布される
`plugins/bitz-flow/skills/flow-core/SKILL.md` ではない。

## なぜ分離するか

`FLW-DSN-011` は v2 Promotion Gate 完了まで **v1-current（現行スキル）を実行契約**とし、
「v2 script を安定版入口として案内しない」と定める。一方 `FLW-DSN-010` の
Mandatory entry protocol は「Git / GitHub 操作は必ず `flow.py` を使う」と宣言し、
`FLW-DSN-014` の M0 eval は **skill なし / v1 skill / v2 skill の3条件**を比較する。

稼働中の SKILL.md を M0 で置き換えると v1-current の案内が失われ、逆に v1 の手順を
残したまま v2 の節を加法的に足すと Dispatcher Invocation Rate が設計と無関係な理由で
低下して出口条件の測定が成立しない。このため v2 SKILL.md を fixture として分離した。

裁定記録: `plugins/bitz-flow/.spec/reports/decision-2026-07-31-m0-skill-fixture-separation.md`

## eval での使い方

M0 eval（`FLW-TSK-012`）は3条件を同一 harness で比較する。

| 条件 | 使う SKILL.md |
|---|---|
| skill なし | なし |
| v1 skill | `plugins/bitz-flow/skills/flow-core/SKILL.md`（稼働中のもの） |
| v2 skill | 本ディレクトリの `SKILL.md` |

v2 条件では、本ディレクトリの `SKILL.md` を flow-core スキルの構成（`scripts/` /
`references/` / `schemas/`）と組み合わせて配置する。`<このスキル>` 表記はその配置先を指す。

## Promotion Gate での扱い

`FLW-DSN-011` の切替シーケンス手順9（v1 撤去）で、本 fixture の内容を稼働 SKILL.md へ移す。
そのとき **eval で測定した fixture と稼働ファイルが同一内容であること**を照合する
（移行検査に規定済み。fixture と稼働ファイルの乖離検出）。
