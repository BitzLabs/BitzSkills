# 裁定記録 — M0 の v2 SKILL.md を eval fixture として分離する

- **日付**: 2026-07-31
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `FLW-TSK-010`（M0 flow-core SKILL.md の Mandatory entry protocol）の着手条件
- **裁定の形式**: 対話で提示した2案からの明示選択。エージェントは選択結果を成果物へ反映する。

## 論点

M0 のタスク分解中に、承認済み設計の間で実装できない食い違いが判明した。

- `FLW-DSN-011`: Promotion Gate 完了まで **v1-current（`FLW-FR-001/002`、`FLW-DSN-001`、現行4スキル）**が
  実行契約であり、「v2 script を安定版入口として案内しない」。
- `FLW-DSN-010`: Mandatory entry protocol は「Git / GitHub 操作は `flow.py` を使う。raw fallback を
  しない」と宣言する。
- `FLW-DSN-014`: M0 eval の baseline は「skill なしと v1 skill の**両方**」であり、
  同一時点で v1 と v2 の両方の skill が必要になる。

稼働中の `plugins/bitz-flow/skills/flow-core/SKILL.md` を M0 時点で v2 へ置き換えると v1-current の
案内が失われる。逆に v1 の手順を残したまま v2 の節を加法的に足すと、Dispatcher Invocation Rate が
設計の良し悪しと無関係な理由で低下し、M0 出口条件の測定が意味を失う。

## 裁定

**v2 の `flow-core` SKILL.md は M0 では eval fixture として分離し、稼働中の SKILL.md は
Promotion Gate まで v1 のまま据え置く。**

1. M0 で作成する v2 SKILL.md の配置先は `evals/flow-core/fixtures/v2-skill/SKILL.md` とする。
2. 稼働中の `plugins/bitz-flow/skills/flow-core/SKILL.md` は M0〜M5 の間、v1 の内容を保持する。
   v2 への切り替えは `FLW-DSN-011` の切替シーケンス手順9（v1 design / skills / scripts の撤去）と
   同じ変更セットで行う。
3. M0 eval は3条件（skill なし / v1 skill / v2 skill fixture）を同一 harness で比較する。
   v1 条件は稼働中の SKILL.md、v2 条件は上記 fixture を指す。
4. `FLW-TSK-010` の status を `blocked` から `pending` へ戻し、boundary を fixture パスへ変更する。

## 根拠

- `FLW-DSN-011` の canary 表は M0 の cohort を「3platform の**保存 fixture** + 本 repo read-only」と
  規定しており、fixture ベースの評価を既に想定している。
- v1-current を M0 の時点で壊さないため、`FLW-DSN-011` の規範セット定義を変更せずに済む。
- 縮退出荷（M0 read-only prerelease だけを維持する境界）が成立する。稼働 SKILL.md を先に
  書き換えると、M1 以降で No-Go になったときに v1 へ戻す作業が別途必要になる。

## 反映先

| 反映先 | 内容 |
|---|---|
| `.spec/design/FLW-DSN-011.md` | 切替シーケンスへ M0〜M5 の SKILL.md 据え置きを明記（version 1.5） |
| `.spec/tasks/FLW-TSK-010.md` | status を pending へ、boundary を fixture パスへ |
| `.spec/tasks/FLW-TSK-012.md` | boundary を `evals/flow-core/m0-eval/` へ限定（TSK-010 と互いに素にする） |

## 残る前提

v2 SKILL.md を fixture として評価する以上、**fixture と稼働ファイルの乖離**が新たなリスクになる。
Promotion Gate で稼働 SKILL.md へ移す際に、eval で測定した fixture と同一内容であることを
確認する手順を `FLW-DSN-011` の移行検査へ含める。
