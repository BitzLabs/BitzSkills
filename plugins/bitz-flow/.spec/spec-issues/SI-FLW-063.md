---
id: SI-FLW-063
raised_by: FLW-REV-017 M2 Exit再々レビュー（3観点完了時点）
target: FLW-REV-017 が指摘した残存欠陥（ガード迂回・承認由来の偽装・復旧経路・証跡）
proposed_change_type: modify
status: accepted
---

- **目的**: `FLW-REV-017` の3観点（data-integrity / risk / operations）が指摘し、
  司令塔が実測で検収した残存欠陥を是正する。

- **裁定**: 2026-08-16 の第2次予算裁定が7項目を列挙し着手順を定めているため、
  本 issue はその実行単位として accepted で起票する
  （`.spec/reports/decision-2026-08-16-m2-remediation-budget-2.md`）。

- **発見した事実**:
  1. **ガード迂回が閉じていない**（`RSK-201` / `OPS-301`、critical）。
     `agy_guard` の allow 述語は「args のどこかに正規形があり、他の値にシェルメタ文字が
     無ければ allow」だった。`git commit -am pwned` / `git push origin main` /
     `git branch -D main` / `mv scripts/agy_guard.py /tmp/z` /
     `chmod 000 scripts/agy_guard.py` はいずれもメタ文字を含まないため相乗りで allow を通る。
     **2026-08-15 の事故で実際に使われた操作種別が PR #272 の是正後も通っていた。**
  2. **承認由来の偽装**（`RSK-204` / `OPS-303`）。`cli.py` が無条件で
     `approval_source="signed-capability"` を名乗り、同じ result の
     `data.approval_mode: plan-digest` と矛盾する。承認強度を強く見せる危険側の誤り。
     検査するテストは0件だった。
  3. **例外是正が復旧経路に届いていない**（`DIN-101` / `RSK-202`）。
     mutation 境界の except ハンドラ内で `receipts.append(QUARANTINED)` が
     `try/finally` のみに包まれ `except` を持たず、receipt log が読めない状況で
     例外が `apply()` から脱出する。PR #282 の是正が届いていなかった。
  4. **TTL が起動時のみ**（`OPS-402`）。`FLW-NFR-011` は Gate 採用時の再照合を求めるが未実装。
  5. **再試行が証跡に残らない**（`OPS-104` / `RSK-403`）。成功分だけを manifest へ残すため、
     失敗 attempt が証跡から消える。
     **訂正（2026-08-16）**: 起票時は codex の初回 timeout を「恒常欠陥」と記したが、
     切り分けの結果 **失敗はすべてバックグラウンド実行時**であり、フォアグラウンドでは
     再現しない（runner 全体 51秒で 3platform PASS）。被測定物ではなく計測環境の性質であり、
     `FLW-NFR-011` の「instrument/environment failure は再試行1回」に照らせば
     条項どおりの運用だった。証跡へ残す是正（`attempts.jsonl`）自体は正しく、そのまま維持する。
  6. **指紋の穴**（data-integrity）。`canonical_bytes` / `sha256_of` を定義する `result.py` が
     `COMPATIBILITY_INPUTS` に無い。
  7. **receipt payload が変更対象を指さない**（`DIN-202` / `SYN-013`）。
     M2 出口条件「operation 外変更の audit 検出」の前提が立たない。**別 PR で扱う**。

- **提案する修正**: 1〜6 を本 issue で是正する。7 は規模が大きく `SI-FLW-060` とも
  重なるため後続 PR へ送る。

- **対象ファイル**: `scripts/agy_guard.py`、
  `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py`、`.../worktree_runtime.py`、
  `evals/flow-core/m2-eval/run_local_confirmation.py`、
  `tests/test_agy_guard.py`、`tests/test_flow_m2_runtime.py`、`tests/test_flow_m2_confirmation.py`

- **確認観点**:
  - 相乗りの各形が allow を通らないこと。正規形そのものは通ること（陰性対照）。
  - `approval.source` が `data.approval_mode` と一致すること。
  - 復旧経路が失敗しても `apply()` が例外を出さず判定を返すこと（陽性対照）。
  - Gate 採用時の再照合が失効証跡を弾き、現行証跡を通すこと（陽性・陰性対照）。
  - 失敗 attempt が append-only の台帳に残ること。

- **影響推定・ロールバック**: harness と公開 CLI に閉じる。
  allow 述語の厳格化で antigravity の confirmation が通らなくなる可能性があるため、
  3platform confirmation の実走で確認する。

- **依存**: `FLW-REV-017` の残り2観点（consistency / business）は未実施であり、
  追加の指摘が出る可能性がある。
