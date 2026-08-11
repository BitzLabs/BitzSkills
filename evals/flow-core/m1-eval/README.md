# M1 eval — qualification（計測器の適格化）

M0 の eval が「被測定物（v2 skill と dispatcher）が 3 platform で同じ判断に収束するか」を測ったのに対し、
ここで測るのは **harness そのものが 3 platform で等価に観測・分類できるか**である。

正式測定（confirmation）の前に計測器を適格化する二段階原則の前段にあたる。
プロトコルの正は `plugins/bitz-flow/skills/flow-core/references/qualification-protocol.md`、
schema の正は同 `schemas/qualification-manifest-v1.schema.json`。

## 構成

| パス | 役割 |
|---|---|
| `run-manifest-m1-entry.json` | M1 の予算・区分配賦・出口・縮退境界・消費実績 |
| `verify_budget.py` | 上記 manifest の内部整合を機械判定する |
| `compatibility.py` | compatibility key v1 と失効規則 |
| `ledger.py` | 正本台帳の合成と candidate 選択 |
| `recovery_ops.py` | backup / restore（RPO 0・RTO 4時間） |
| `isolation.py` | trial ごとの隔離 namespace |
| `raw_log_guard.py` | raw log の保存境界とライフサイクル |
| `qualification.py` | 3 trial の判定と Gate 合成 |
| `run_qualification.py` | 3 platform の実 CLI を起動する runner |
| `fixtures/` | 3 platform 分の qualification fixture（実 CLI を起動しない） |
| `qualification-runs/` | 実走の成果物 |

## 実走の記録

### 2026-08-12 — 3 platform qualification

| platform | CLI | 判定 | trial | 所要 |
|---|---|---|---:|---:|
| claude | 2.1.228 (Claude Code) | **PASS** | 3 | 69.9s |
| codex | codex-cli 0.147.0 | **PASS** | 3 | 61.1s |
| antigravity | agy 1.1.12 | **PASS** | 3 | 57.3s |

**合成: PASS**（`qualification-runs/active-manifest.json`）

- 各 platform で `Q-NORMAL` / `Q-REJECT` / `Q-CORRUPT` を**各ちょうど1件**実行した。
- 実行制約（10分以内・harness 再試行1回以内）を満たした。
- 隔離 namespace は trial ごとに独立し、解放漏れは 0。
- raw log は owner-only で保存し canary を検出した。**成果物には含めない**
  （owner と `evaluation-reviewer` のみ読取、最大 30 日保持）。

### 被測定物の confirmation は含まない

本実走が示すのは「**計測器が 3 platform で適格である**」ことに限られる。
M1 operation（read / local-write / remote-write / doctor）の confirmation は含まない。

理由（裁定: `plugins/bitz-flow/.spec/reports/decision-2026-08-12-m1-6-scope.md`）:

1. `FLW-DSN-014` の縮退規則3により、**M2 未完了の間は M1 Git write を公開しない**。
   公開しない operation を正式確認しても、公開時には worktree 境界が加わって前提が変わる。
2. 同設計は「cross-host で予約と lease を証明できなければ write confirmation を
   `UNSUPPORTED` にする」と定める。実 GitHub を使わない現状では remote-write の
   confirmation は成立しない。

M1 の出口条件（M1 所属 operation の contract 全行・fault fixture・重複 commit 0）は
M1-3 / M1-4 / M1-5 で機械検証済みである。

## 再実行

```bash
# 配線だけを検査する（CI はこちら。実 CLI を起動しない）
python3 <リポジトリ>/evals/flow-core/m1-eval/run_qualification.py --dry-run

# 3 platform で実走する（実 CLI を起動する。課金と時間がかかる）
python3 <リポジトリ>/evals/flow-core/m1-eval/run_qualification.py --repo <被験リポジトリ> --out <出力先>
```

`--platform` を指定すると単一 platform だけを実行できるが、**合成は platform が欠けると
PASS にならない**（1 platform の結果で全体を代表させない）。
