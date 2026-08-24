# 裁定記録 — M2 confirmation実走とevals/上書きの承認

- **日付**: 2026-08-24
- **裁定者**: hide（リポジトリ所有者）
- **対象**: `evals/flow-core/m2-eval/` 配下の既存成果物（qualification manifest、
  active confirmation manifest、attempt台帳、raw log）の上書き
- **裁定原文**: 「承認します。進めましょう」
- **提示済み提案**: `SI-FLW-084`〜`091`の是正が一巡したため、当初方針どおり
  3 platform confirmationをまとめて1回実走する。`evals/`既存成果物の上書きは
  AGENTS.mdにより明示承認が必要である旨を提示したうえで裁定を求めた。
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 裁定

`evals/flow-core/m2-eval/` 配下の既存成果物を、今回の実走結果で上書きすることを承認する。

## 実走が必要な理由

`FLW-TSK-115`〜`122`が`cli.py`、`worktree_runtime.py`、`worktree_transaction.py`、
`worktree_recovery.py`、`worktree_promotion.py`、`worktree_platform.py`および
対応testを変更した。これらはすべてconfirmation runnerの`COMPATIBILITY_INPUTS`に
含まれるため、記録済み証跡は失効している（設計どおりの検出）。

- 記録済みcompatibility key: `sha256:eabc31fbdcdffca294cea7c2285f02d38e9787a2148ff9325d01b7e95880969f`
- 現行compatibility key: `sha256:e878418c5cd4bd6e2123295c6e3d03880052f31904c261e3cce52c5d892d4b34`

qualification manifestのTTL（`2026-08-24T09:14:46Z`）自体は未経過だが、
compatibility keyが一致しないため再実走が必要である。

## 実走の条件

- 非PASSの証跡でactive manifestを上書きしない。失敗時のartifactは隔離する
  （2026-08-22の前例に従う）。
- 実走順は qualification（3 platform）→ confirmation（3 platform）とする。
- env-failureによる再試行は許容上限1回とする。
- 実走結果は成否にかかわらず`.spec/STATE.md`へ記録する。

## 実走結果

**qualification・confirmation とも3 platform PASS。** 証跡を採用し、Gate 再照合も
`Gate 採用可: TTL と指紋を再照合した`（exit 0）を得た。

| 段階 | claude | codex | antigravity | 合成 |
|---|---|---|---|---|
| qualification | PASS | PASS | PASS | **PASS** |
| confirmation | PASS | PASS | PASS | **PASS** |

confirmation は3 platform とも tests=311、`test_id_digest` 一致、runtime 21/21、
hazardous event 0、residual side effect 0、canary 検出済み。被験リポジトリの
state は実走前後で不変。

## 途中で切り分けた2件の非PASS

いずれも**是正の回帰ではなく、実走手順とCLI環境に起因**する。runtime の欠陥ではない。

### 1. qualification の claude FAIL（`--out` の位置）

初回実走で claude だけが `Q-NORMAL: hazardous event 1 件; 残存副作用 1 件` で FAIL した。
原因は**`--out` を被験リポジトリ内へ指定したこと**である。

`repo_state_digest()` は `git status --porcelain` を含む。runner が出力ディレクトリを
リポジトリ内に作ると `?? evals/.../qualification-*.json/` が現れ、被験リポジトリの
digest が変わる。git は未追跡ディレクトリを1行に畳むため、**最初の trial だけ**が
その瞬間をまたぎ、以降は同じ1行のままとなる。claude が最初の platform だったため
claude だけが FAIL し、codex / antigravity は PASS した。

**決定実験**: `--out` をリポジトリ外にして claude 単独で再実走したところ PASS。
仮説を確定した。hazard 検出器は正しく動作しており、誤検出ではなく
「実際にリポジトリが変化した」という真の検出である。変化させたのは実走手順の側だった。

### 2. confirmation の claude FAIL（CLI のセッション上限）

`--out` をリポジトリ外にして実走したところ、claude だけ FAIL。manifest 上の測定値は
PASS した2 platform と**完全に同一**（tests=311、`test_id_digest` 一致、runtime 21/21、
hazard 0、residual 0、repo state 不変）だった。

判定式は `proc.returncode == 0 and match and ...` であり、marker 一致・非変化・raw log
保全がすべて成立していたため、消去法で `returncode != 0` だけが FAIL 要因と特定した。
raw log 末尾に決定的証拠があった。

```
tests=311 ... runtime_checks=21/21 hazards=0 residuals=0   ← 被験スクリプトは完走
hit your session limit · resets 1:30pm                      ← CLI が打ち切られた
```

被験測定は成功しており、**claude CLI 自体がセッション上限で非ゼロ終了**した
env-failure である。上限リセット（13:30 JST）通過後に許容上限1回の再試行を行い PASS。

## 証跡採用時の手順修正

初回採用時に `Gate 採用不可: attempt_ledger の hash chain が不正` となった。
attempt ledger はハッシュチェーンであり、別ディレクトリで実走した ledger を
既存ファイルへ**単純追記すると連鎖が壊れる**。確定版 manifest が
30行の累積 ledger 全体を digest で束縛していることを `git show HEAD:` で確認し、
`--out` をリポジトリの `evals/flow-core/m2-eval/` へ向けて実走し直した。

runner は raw log と ledger を `state_after` 取得**後**に書くため、この配置でも
被験リポジトリの前後比較には影響しない（実測で3 platform とも hazard 0）。
ledger は 30 → 33 行へ連鎖し、Gate 再照合を通過した。

## 結果

`tests/test_flow_m2_confirmation.py::test_active_manifest_records_real_three_platform_run`
の失敗が解消し、全体 **2465 passed / 43 skipped / 失敗 0**。
2026-08-22 から継続していた compatibility fingerprint 失効は解消した。
