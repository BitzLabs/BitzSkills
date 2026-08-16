---
id: FLW-REV-017
title: "M2 Exit 再々レビュー"
status: active
version: 1.0
updated: 2026-08-16
owner: hide
decision: CONDITIONAL_PASS
---

# M2 Exit 再々レビュー

- **review_id**: FLW-REV-017
- **対象**: `FLW-REV-016`（FAIL 2.85）が立てた `GP-001`〜`GP-004` の消化判定と、
  M2 是正5 PR（`SI-FLW-061` / `062` / `057` / `058` / `059`）の効果測定
- **判定**: **CONDITIONAL_PASS**
- **集計スコア**: **3.13 / 5.00**（前回 2.85、**+0.28**）
- **実施方式**: 観点ごとに独立エージェントを**順次1体ずつ**起動した
  （5時間の利用上限を並列起動で使い切らないため。個票は `individual/flw-rev-017-*.json`）

## 観点別スコア

| 観点 | 今回 | 前回 | 差 | 重み |
|---|---:|---:|---:|---:|
| operations | **3.60** | 2.90 | **+0.70** | 0.20 |
| data-integrity | **3.25** | 2.65 | **+0.60** | 0.25 |
| consistency | 3.00 | 3.00 | ±0.00 | 0.15 |
| risk | 2.70 | 2.70 | ±0.00 | 0.25 |
| business | **欠測** | 3.20 | — | 0.15 |

findings: 統合前54件 → 重複排除後12件（P0: 4 / P1: 5 / P2: 3）。うち**8件は本レビュー後に解消**。

## business 観点の欠測について

Claude Code の自動モード分類器が独立エージェントの起動をブロックしたため未実施である
（プロンプトを簡潔にして2回試行したが同じ結果。回避は試みていない）。

**測定できた重みは 0.85 / 1.00** であり、集計スコアは欠測を除いた正規化値である。
感度は次のとおりで、判定を左右しない。

| 仮定 | 集計 |
|---|---:|
| 欠測を除いて正規化（採用値） | **3.13** |
| 前回 business 3.20 を据え置き | 3.14 |

business は前回 3.20 で**最高スコアの観点**であり、欠測による偏りは「実態より低く見える」方向に働く。
判定を甘くする方向ではないため、保守的な材料としては使用できる。

## 判定の根拠と、その限界

**CONDITIONAL_PASS とした理由**:

- 集計が 2.85 → 3.13 へ改善し、`operations` と `data-integrity` は +0.7 / +0.6 と大きく前進した
- **critical 4件はすべて是正済み**（`SYN-001` / `002` / `003` / `004`）
- `GP-003` は3観点が discharged と判定した

**この判定の重大な限界**（`GP-005` として起票）:

本レビューの4観点は**是正前後の異なる commit を見ている**。
`data-integrity` / `risk` / `operations` は `a7c1545`（PR #289 / #290 の前）を、
`consistency` は `56418fc`（#289 / #290 の後）を評価した。
**最終状態を独立に評価した観点は無い。** critical 4件が「解消済み」なのは司令塔の作業であり、
独立の検分を経ていない。

## M2出口条件の再判定

| 出口条件 | REV-016 | 今回 | 根拠 |
|---|---|---|---|
| repo identity衝突0 | PASS | PASS | M2 guard fixture |
| repo外rootの単回capability | PASS | PASS | M2-FLT-007〜015 |
| `M2-FLT-*` 全件（create/resume/audit） | PASS | PASS | 欠番0 |
| enum三者照合 | PASS | PASS | M2-FLT-023 |
| create/resume の in-band capability検証 | BLOCKED | **PASS** | 公開dispatcher経由 E2E（`SI-FLW-059`）。operations が独立に再現 |
| operation外変更のaudit検出・quarantine接続 | BLOCKED | **部分** | 検出は成立（`SI-FLW-064`）。**quarantine への接続語彙が未整備**（`SYN-011`） |
| 3platform 被測定物confirmation | BLOCKED | **PASS** | hazard/residual を実測化、raw log 保持、TTL 再照合、attempt 台帳。是正後の最終状態で**再試行 0 回の 3platform PASS**（173件・runtime check 35/35） |
| reconnaissance entry必須 | PASS | PASS | M2-FLT-045〜047/051 |

**8項目中7項目が PASS、1項目が部分達成**である（前回は3項目 BLOCKED）。

`operations` 観点が `OPS-104` で指摘した「codex の初回 timeout が証跡から消える」問題は、
attempt 台帳の導入に加えて**原因側でも解消**した。切り分けの結果、失敗はすべて
harness をバックグラウンド実行したときに起きており、フォアグラウンド実行では再現しない。
是正後の最終状態を**フォアグラウンドで実走したところ、3platform とも初回 PASS（再試行 0 回）**である。
被測定物ではなく計測環境の性質であり、「恒常欠陥に再試行条項を当て続けている」という
評価は司令塔の誤った説明に基づいていた。

## P0 — すべて是正済み

| finding | 内容 | 是正 |
|---|---|---|
| `SYN-001` | ガード迂回。事故で使われた操作種別（commit・ガード無力化）が PR #272 の是正後も allow を通っていた | `SI-FLW-063`（実測ベース allowlist） |
| `SYN-002` | receipt payload が変更対象を指さず、出口条件が実装不能だった | `SI-FLW-064` |
| `SYN-003` | 既定の出力形式が `KeyError` で落ちる状態を出荷しかけた | `SI-FLW-065` |
| `SYN-004` | 例外分類の是正が復旧経路に届いていなかった | `SI-FLW-063` |

`SYN-003` は特に構造的な見落としだった。公開経路 E2E が `--format json` を固定しており、
**dispatcher テストが既定 renderer を一度も通っていなかった**（`grep render_compact tests/` は 0 件）。
既定形式は利用者が実際に見る出力である。

## 未解消（CONDITIONAL_PASS の通過条件）

- [ ] `SYN-008` 是正 PR に対応するタスクが無く boundary が実体とずれている
- [ ] `SYN-009` 覆った「実装不能」宣言が `FLW-TSK-086` に残置、audit の新振る舞いが catalog へ未反映
- [ ] `SYN-011` SKILL.md が catalog と矛盾。audit の出力語彙に **quarantine 接続に対応する語が無い**
- [ ] `SYN-012` M2 出口4要件が approved のまま、検証証跡0件、出口条件×証拠の対応表が無い
- [ ] `GP-005` 是正後の最終状態を独立レビューで検分する
- [ ] business 観点の欠測を埋める

## 予算の経過

| 枠 | 承認 | 実績 |
|---|---|---|
| 第1次（2026-08-15） | 4 PR / 13 session | 4 PR / 8 session で自動停止 |
| 第2次（2026-08-16） | 5 PR / 15 session（本体3＋予備2） | **3 PR / 9 session（本体枠を使い切り予備枠に入った）** |

第1次の付帯条件（run manifest の記録を着手条件とする）が効き、
**初めて実績に基づく見積もりができた**。上昇トレンド（session 1→2→2→3、
レビュー修正 0→0→1→2）が見えたことが第2次で最悪値＋予備を採る根拠になった。

## 人間への裁定依頼

1. **Completion Gate は保留を継続**する。出口条件は 7/8 まで到達したが、
   「quarantine 接続」が未整備であり、かつ**最終状態が独立レビューを経ていない**（`GP-005`）。
2. 上記の通過条件6件について、追加予算の要否を裁定する。
   第2次枠は本体 3 PR / 9 session を**使い切って予備枠に入った**（残 2 PR / 6 session）。
   予備の使用に裁定は不要だが、裁定条件どおりここで報告する。
3. `business` 観点の欠測を埋めるか、4観点で確定とするかを裁定する。

`write_target: remote` は M3 まで `UNSUPPORTED` を維持する方針に変更はない。
