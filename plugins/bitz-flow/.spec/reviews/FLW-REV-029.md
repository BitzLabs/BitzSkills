---
id: FLW-REV-029
title: "M2 read-only限定公開後の再レビュー"
status: active
version: 1.0
updated: 2026-08-24
owner: claude
decision: FAIL
---

# M2 read-only 限定公開後の再レビュー

- **対象**: `FLW-TSK-123`〜`129`（`FLW-REV-028` の GP-001〜008 是正と read-only 限定公開）、
  `FLW-DSN-017` v3.0、`FLW-NFR-014` v2.3、`FLW-FR-006` v2.1、flow-core の実装と test
- **判定**: **FAIL**
- **集計スコア**: **2.72**（閾値 2.5 は超えるが、**`risk` 2.33 が floor 2.5 に未達**）
- **公開判断**: **裁定記録の後退条件に該当する**（下記）
- **セカンドオピニオン**: codex（OpenAI）判定 **FAIL**、antigravity（Gemini）追加欠陥6件。
  **今回は統合判定より前に実施した**（前回は後だったため判定が覆った）

## 観点別スコア

| 観点 | 今回 | 前回(v2.0) | 重み | 主要所見 |
|---|---:|---:|---:|---|
| consistency | 2.00 | 3.00 | 0.15 | Linux 限定の裁定が規範3箇所へ未反映で内部矛盾。§13.5 が撤回済みの事実を主張 |
| data-integrity | 3.80 | 3.50 | 0.25 | crash 境界は回帰なし。判定 API が名前どおりの検証をしていない |
| operations | **1.80** | 2.00 | 0.20 | **公開した3 operation に 30 秒収束の保証が無い** |
| risk | **2.33** | 2.00 | 0.25 | **floor 2.5 に未達**。保証が成立しない経路を公開面へ露出させた |
| business | 3.50 | 2.00 | 0.15 | 初めて利用可能になり production 証跡も増えた。ただし保証未達のまま出荷 |

findings: 統合前 21 件 → 重複排除後 9 件（**P0: 1** / P1: 6 / P2: 2 / P3: 0）。

## 手順を変えたこと

前回 `FLW-REV-028` は本人が CONDITIONAL_PASS 3.75 と判定した**後**にセカンドオピニオンで
FAIL へ覆った。今回は**統合判定より前**にクロスモデル検証を実施した。
その結果、本レビューの P0 と P1 のうち **5 件は外部レビュアーが先に指摘したもの**である。
自己レビュー単独では見つけられなかった蓋然性が高い。

指摘は自己申告として受け取らず、**すべて実測で再現してから採用**した。

## P0 — Blocker

**`SYN-001` 公開した read-only 3 operation に 30 秒収束の保証が無い**

`FLW-TSK-129` で公開した `doctor` / `audit` / `verify-receipt` は `OperationDeadline` を
**生成も参照もしない**（`worktree_operability.py` に参照 0 件）。`FLW-NFR-014` が要求する
30 秒 closed terminal result が**公開面で構造的に成立しない**。

`FLW-TSK-127` で operation 全体 deadline を実装した**直後に、それを通らない経路を公開した**。
これが今回いちばん重い所見である。

## P1 — Must Fix

- **`SYN-002`** operation deadline に抜け道（`_common_dir` / `_head` / `_rederive`）— `GP-002` 未消化
- **`SYN-003`** Linux 限定の裁定が規範3箇所へ未反映で内部矛盾 — `GP-003` 部分消化
- **`SYN-004`** §13.5 が撤回済みの事実（tmpfs SUPPORTED、swapcase 判定）を主張し続けている
- **`SYN-005`** read-only guard の `persistent_state_digest` が全 bytes 読み。公開経路で 100 MiB 級 journal だと前後 2 回で 200 MiB
- **`SYN-006`** `verify_receipt` が receipts を検証せず、`audit_operation` が要復旧でも `OK` を返す
- **`SYN-007`** dispatcher の網が内部障害まで不可観測にしている

## P2

- **`SYN-008`** `current-bundle-digest-mismatch` に operator action が無い（`GP-001` の網羅漏れ）
- **`SYN-009`** source 文字列を照合するだけの test が保証になっていない

## 最も重要な所見 — 確認方法が誤っていた

P0 と P1 の多くに**共通の根**がある。**`GP` 消化の確認を source 文字列の照合で済ませた**ことである。

`GP-002`（operation deadline）の消化確認に書いた test は、`worktree_runtime.py` の source に
`deadline=self.deadline` が含まれるかを見るだけだった。実際に全 child へ伝播しているかは
検査していない。その結果 `_common_dir` / `_head` / `_rederive` の抜けを見逃し、
さらに **deadline を通らない経路をそのまま公開した**。

`GP-003` も同様で、§1.1 と §13.5 を直したことをもって「Linux 限定へ揃えた」と判断したが、
`FLW-NFR-014` と §7・§13.7 は確認していなかった。`GP-001` の網羅 test も platform 理由だけを
見て bundle problem を見ていなかった。

**「直した」と「直ったことを確かめた」の差**が、そのまま今回の finding になっている。

## 是正が前進した点（否定しない）

- crash 境界の原子性は回帰していない（data-integrity 3.80）。
- symlink 実証、mount 局所の case 判定、未捕捉例外の網、operator action は実装され機能している。
- read-only 限定公開により **production E2E が 1/21 → 4/21** へ増え、7 観点の
  「接続完全性」に初めて実証が入った。
- `business` は 2.00 → 3.50。M0 以来はじめて M2 の機能が利用可能になった。

## FAIL とした根拠

1. **P0 が 1 件ある。** 公開面が要件の収束保証を満たしていない。
2. **`risk` 2.33 が floor 2.5 に未達。** 集計 2.72 は閾値を超えるが floor で落ちる。
   前回 floor をクリアしたのに再び下回った。
3. `GP-002` / `GP-003` は消化と言い切れず、`GP-004` も前提の立証範囲を超えて断定していた。

## 裁定記録の後退条件に該当する

`.spec/reports/decision-2026-08-24-m2-readonly-canary.md` は後退条件をこう定めている。

> 次のいずれかで直ちに `PUBLISHED_OPERATIONS` から外す。
> …
> - `FLW-REV-029` が本公開に対して P0 を出した。

`SYN-001` は本公開に対する P0 である。したがって**条件は成立している**。

ただし選択肢は 2 つあり、いずれも人間裁定を要する。

- **後退**: 裁定記録どおり公開を戻す。得た production 証跡（4/21）は失われる。
- **前進**: `GP-001`（deadline 結線）を先に完了させ、そのうえで再判定する。
  read-only であること自体は保たれており、`_read_only_guard` の機械強制も効いている。

本レビューは**判定のみ**を行い、どちらを採るかは裁定に委ねる。

## Gate blocking 条件（GP-001〜006）

6 件すべて `basis: verified`、`response: accepted`。

| GP | 内容 |
|---|---|
| GP-001 | 公開集合の全 operation を deadline 配下に置き、大規模 journal での収束を実測する |
| GP-002 | deadline を operation 単位で 1 つにし全 child 経路へ配る。**伝播を振る舞いで検査する** |
| GP-003 | Linux 限定の裁定を規範全体へ適用する |
| GP-004 | §13.5 を実装と一致させ、一致を機械検査へ載せる |
| GP-005 | 判定 API の code・operator action・実際の検証対象を一致させる |
| GP-006 | **GP 消化の確認を振る舞いの検査に限定する**（source 照合を単独の根拠にしない） |

`GP-006` は今回の findings の共通原因に対する手当てであり、他の 5 件より優先度が高い。

## carried over 台帳

先行レビューの未解決 P0/P1 **102 件**を `carried_over[]` へ収録した。
`SI-FLW-091` の機械検査により欠落が起きないことは保証されているが、
個別照合は依然未了である。

## 裁定

`GP-001`〜`006` を消化すること。公開を戻すか前進させるかは人間裁定とする。
Promotion Gate は本レビューの判定により通さない。
