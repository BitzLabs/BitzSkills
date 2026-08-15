---
id: FLW-REV-016
title: "M2実動confirmationとExit再レビュー"
status: active
version: 1.0
updated: 2026-08-15
owner: hide
decision: FAIL
---

# M2実動confirmationとExit再レビュー

- **review_id**: FLW-REV-016
- **対象**: `FLW-REV-015:GP-001`（実動adapter・dispatcher統合）と`GP-002`（3platform実動confirmation）の消化判定、
  およびM2出口条件・Completion Gateの再裁定材料
- **判定**: **FAIL**
- **集計スコア**: **2.85 / 5.00**（前回 3.09、**-0.24**）
- **実施方式**: 5観点を独立エージェントへ並列委譲し、司令塔は統合と検収のみを行った
  （自己レビューのスコア膨張を避けるため。個票は `individual/flw-rev-016-*.json`）

## 観点別スコア

| 観点 | スコア | 前回 | 重み | 主要所見 |
|---|---:|---:|---:|---|
| consistency | 3.00 | 3.30 | 0.15 | 公開経路は開通したがGP原文の「全write」に届かない |
| data-integrity | 2.65 | 3.65 | 0.25 | 可観測になった結果、receipt prefix収束の破れが確定 |
| operations | 2.90 | 3.00 | 0.20 | 証跡が第三者検証不能、確認用ガード緩和が全面バイパス可能 |
| risk | 2.70 | 2.45 | 0.25 | 実動E2Eは前進、迂回不能性の全面実証には未達 |
| business | 3.20 | 3.10 | 0.15 | 前回の予算超過とtest母数不一致は解消、定量値の裏付けが不足 |

findings: 統合前57件 → 重複排除後20件（P0: 5 / P1: 6 / P2: 5 / P3: 4）。うち1件は本PR内で解消。

## M2出口条件の再判定

| 出口条件 | 前回 | 今回 | 根拠 |
|---|---|---|---|
| repo identity衝突0 | PASS | PASS | M2 guard fixture |
| repo外rootの単回capability | PASS | PASS | M2-FLT-007〜015 |
| M2-FLT-001〜057全件 | PASS | PASS | 欠番0 |
| enum三者照合 | PASS | PASS | M2-FLT-023 |
| 全worktree writeでin-band capability検証 | BLOCKED | **BLOCKED** | dispatcher経由は`create --plan`1件のみ（`SYN-006`） |
| operation外変更をaudit→quarantine | PASS | **BLOCKED** | 公開`worktree.audit`が契約層を通らず未接続（`SYN-011`） |
| 3platform local被測定物confirmation | BLOCKED | **BLOCKED** | 実走はしたがhazard/residualが恒真値・raw log破棄（`SYN-004`/`SYN-007`） |
| reconnaissance entry必須 | PASS | PASS | M2-FLT-045〜047/051 |

前回PASSだった「audit→quarantine」は、公開経路を実際に開いた結果として未接続が判明したため
**PASSから後退**させた。実装が悪化したのではなく、観測可能になったことで判定が是正された。

## 今回の実走結果（司令塔が再実行して検収した事実）

| 項目 | 実測 |
|---|---|
| qualification（3platform × 3trial） | 全PASS、必須check 21/21、陽性対照 9/9、hazard 0、residual 0 |
| 3platform confirmation | claude / codex / antigravity 全PASS |
| test件数・test ID digest | 3platformとも146件・`sha256:c9f83fda…`（完全一致） |
| runtime check | 3platformとも 8/8（`tests/test_flow_m2_runtime.py`の収集件数から導出） |
| compatibility key | `sha256:da64ef8c…`（qualificationとactive manifestで一致） |
| 全pytest | 1945 passed |
| release_check.py | PASS |

前回の`FLW-REV-015:SYN-003`（platform間でtest母数が138/138/137と不一致）は、
test ID集合digestの固定により**解消**した。

## P0 — Must Fix（M2 Exit裁定の前）

- **FLW-REV-016:SYN-001** [OPS-301, RSK-201] **解消済み（本PR）**
  confirmation用に足したallow経路がガードレール全体をバイパスしていた。
  allow判定がDENY走査より前にreturnし、args配下の任意フィールドが許可形に一致すれば
  全体がallowになった。実測で6経路（`;rm$IFS-rf$IFS/…`、`$(id)`、バッククォート、
  `&&sudo$IFS-i`、兄弟フィールドdict/listへの`sudo rm -rf /`）がdeny→allowに反転した。
  - 是正: deny走査をallowより前へ移し、許可形をshell metacharacter禁止と絶対パス正規表現で拘束し、
    同居フィールドの無害性も検査した。`tests/test_agy_guard.py` に全6経路を含む15ケースを追加。

- **FLW-REV-016:SYN-002** [DIN-201]
  receiptのstep語彙が安全核と不一致で、**GP-001の中心主張であるprefix収束が成立しない**。
  `worktree_runtime.MUTATING_STEPS["finish"]`は`git-worktree-remove`/`delete-local-branch`、
  `worktree_cleanup.FINISH_STEPS`は`verify-pr-merge`…`remove-worktree-dir`/`delete-local-branch`。
  実receiptの非空前置列をreconcile_stepsへ入力するとfinish/discardとも例外なくINDETERMINATEになる。

- **FLW-REV-016:SYN-003** [DIN-101, RSK-202]
  例外遮蔽により破壊的な部分適用がBLOCKEDとして誤報される。
  module内の`class RuntimeError(ValueError)`が組み込みを遮蔽し、mutation境界の
  `except (RuntimeError, OSError)`は素のValueError/KeyErrorを捕捉しない（plan側は捕捉する）。

- **FLW-REV-016:SYN-004** [OPS-101]
  raw logをdigest化直後に破棄しており、hazard 0 / residual 0 / test ID一致が第三者検証不能。
  FLW-NFR-011がSHALLで求める保持境界・redaction・削除証跡がM2 harnessに無い。

- **FLW-REV-016:SYN-005** [OPS-401, DIN-302]
  公開されていない`git.stage`/`git.commit`/`git.fetch`/`git.sync`をPASSとしてactive化している。
  縮退規則3の解除はまさにこの4 operationの公開を意味するため、証跡と主張が逆向きである。

## P1 — Should Fix

- **SYN-006** 公開dispatcher経由のwrite網羅が`create --plan`のみ（8件中7件はライブラリ直呼び）
- **SYN-007** hazard/residual/required_check/positive_controlが実測ではなく定数
- **SYN-008** `compatibility_key`が認可核（`worktree_capability`/`guard`/`worktree_cleanup`/`recovery`）とfixtureを覆わない
- **SYN-009** qualification 24時間・confirmation 7日のTTLが未強制（`expires_at`を読むコードが0件）
- **SYN-010** `--backup-receipt`が未実装でdiscardが未コミット変更を破壊しうる
- **SYN-011** 公開`worktree.audit`が契約層を通らずquarantineへ未接続

## P2 / P3

- **SYN-012** coordinator・lease・append-only台帳がM2 harnessで未使用、並行排他なし
- **SYN-013** receipt payloadに監査・復旧情報がなくchain切詰めが検出不能
- **SYN-014** M2出口4要件がapprovedのままで出口条件×証拠の対応表が無い（検証証跡0件）
- **SYN-015** 承認済み是正予算がbudget SSOTへ未反映、M2 run manifestが0件
- **SYN-016** 公開集合の二重定義と`--help`文言が実態と逆
- **SYN-017** `recovery.py`/`worktree_cleanup.py`がどこからもimportされていない
- **SYN-018** crash実証がhandled exceptionのみで境界も2/7
- **SYN-019** nonce ledgerのfsync・USED_PENDING回収が無く終端stepのfreshness検証が恒真
- **SYN-020** M2で公開した5 operationがoperation-catalogの11 field契約を満たさない

## Gate Precondition

| ID | 区分 | 状態 | 内容 |
|---|---|---|---|
| `GP-001` | blocking | **not-discharged** | 公開dispatcherから全worktree writeを起動し、capability検証とreceipt prefix収束をE2Eで確認する |
| `GP-002` | blocking | **partially-discharged** | 実動confirmationを再実行しactive manifestを置換する（実走・digest一致は達成、hazard/residualの実測が未達） |
| `GP-003` | blocking | open | receiptのstep語彙を統一し、mutation境界の例外分類を是正する |
| `GP-004` | blocking | open | confirmation証跡をFLW-NFR-011の契約へ適合させる |
| `GP-005` | agenda | open | M2是正の追加予算を人間が再裁定し、budget SSOTとrun manifestへ反映する |

## 人間への裁定依頼

1. **Completion Gateは保留を継続**する。M2出口条件8項目のうち3項目がBLOCKEDであり、
   M1 local-write と M2 worktree の同時公開（縮退規則3の解除）は現時点で根拠を欠く。
2. `SI-FLW-056`で承認された **2 PR / 最大6 session を消化済み**である。
   `SYN-002`〜`SYN-005`の是正には新たな予算裁定が要る。
3. P0のうち`SYN-001`のみ本PRで解消した。残りは本タスクのboundary外のため
   spec-issueとして起票済みであり、accept / rejectの裁定を仰ぐ。

| spec-issue | 対象 | 由来するfinding |
|---|---|---|
| `SI-FLW-057` | worktree receiptのstep語彙統一と例外分類是正 | `SYN-002`, `SYN-003` |
| `SI-FLW-058` | confirmation証跡のFLW-NFR-011適合 | `SYN-004`, `SYN-005`, `SYN-007`〜`SYN-009` |
| `SI-FLW-059` | 公開dispatcherのwrite網羅とaudit契約層接続 | `SYN-006`, `SYN-011`, `SYN-016` |

`write_target: remote`はM3まで`UNSUPPORTED`を維持する方針に変更はない。
