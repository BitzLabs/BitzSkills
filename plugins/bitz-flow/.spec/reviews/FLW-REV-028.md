---
id: FLW-REV-028
title: "M2 Local Safety Profile 是正後再レビュー"
status: active
version: 1.0
updated: 2026-08-24
owner: claude
decision: CONDITIONAL_PASS
---

# M2 Local Safety Profile 是正後再レビュー

- **対象**: `FLW-DSN-017` v2.3、`FLW-FR-006` v2.1、`FLW-NFR-014` v2.3、`FLW-CON-008`、
  `FLW-TSK-106`〜`122`、flow-core の CLI・platform・runtime・transaction・recovery・
  operability、関連 schema・test・runbook、confirmation 証跡
- **判定**: **CONDITIONAL_PASS**
- **集計スコア**: **3.75**（`FLW-REV-027` は 2.12）
- **公開判断**: worktree operation は現在の gated 状態を維持する。
  下記 GP-001〜004 の消化まで Promotion Gate を通さない。

## 観点別スコア

| 観点 | スコア | 前回 | 重み | 主要所見 |
|---|---:|---:|---:|---|
| consistency | 3.70 | 2.65 | 0.15 | 設計・schema・実装の乖離は解消。成文化と機械検査が不足 |
| data-integrity | 4.65 | 2.00 | 0.25 | crash 空隙が構造的に消滅。旧形式 chain の復旧手段のみ未実装 |
| operations | 2.90 | 2.30 | 0.20 | 既定 umask 拒否と Windows 固定不支持で運用可能性に壁 |
| risk | **4.00** | 1.33 | 0.25 | floor をクリア。ただし是正が新規停止条件を持ち込んだ |
| business | 3.00 | 2.85 | 0.15 | 安全核は閉じたが利用可能な価値は依然 0 |

findings: 統合前 9 件 → 重複排除後 6 件（**P0: 0** / P1: 4 / P2: 2 / P3: 0）。

`risk` は M2 が単一プロセス・非分散のため分散システムリスクと Saga 設計の2次元を N/A とし、
残る重みを再正規化した。

## FLW-REV-027 の P0/P1 の解消状況

| 前回 finding | 内容 | 解消 |
|---|---|---|
| SYN-001 (P0) | 実環境 platform evidence から production CLI への経路が無い | **解消**（`FLW-TSK-116`。probe 実装＋共通生成器へ結線。plan の必ず停止する経路を除去） |
| SYN-002 (P0) | create/resume CLI が廃止済み承認契約と旧 context を参照 | **解消**（`FLW-TSK-115`。参照 0 件を機械検査、production black-box negative test） |
| SYN-003 (P1) | Git child の有限 timeout と 30 秒 terminal result が未実装 | **解消**（`FLW-TSK-117`。素の subprocess.run 0 件。hang／SIGTERM 無視／出力洪水を実測） |
| SYN-004 (P1) | intent と緊急 receipt の durable 確定間に crash 空隙 | **解消**（`FLW-TSK-118`。単一 durable record。4 publish 点すべて実測） |
| SYN-005 (P1) | `QUARANTINED` を confirmed-complete へ誤分類できる | **解消**（`FLW-TSK-119`。陽性・陰性対照つき） |
| SYN-006 (P1) | reconcile closure が marker 適格性確認より先行 | **解消**（`FLW-TSK-120`。lock order を AST で機械検査） |
| SYN-007 (P1) | verified・task done・予算が production 接続完了を過大主張 | **解消**（`FLW-TSK-121`＋`FLW-NFR-014` の verified 取り消し裁定） |

**前回の P0/P1 7 件はすべて解消した。** 本レビューの P1 4 件はいずれも**新規**である。

## P1 — Must Fix（すべて新規）

- **SYN-001** 既定 umask で作った worktree root が常に拒否され、回避手順が無い — `GP-001`
- **SYN-002** 必須 snapshot 経路へ 8 MiB 出力上限が新たに適用され、大規模 repository で plan が失敗する — `GP-002`
- **SYN-003** Windows は SID 取得手段が無く構造的に常に不支持で、§1.1 の 3 OS 保証と一致しない — `GP-003`
- **SYN-004** 旧形式 chain の復旧手段が fail-closed 以外に無い — `GP-004`

## P2 — Should Fix

- **SYN-005** 未解決 P0/P1 86 件が未照合のまま残り、件数を判断材料にできない — `SI-FLW-091`
- **SYN-006** production 判定基準と `platform` 語彙の禁止が規範文書に成文化・機械検査されていない — `SI-FLW-092`

## 最も重要な所見

**是正は成功したが、是正自体が新しい停止条件を3件持ち込んだ。**

`SYN-001`（owner-only 要求）、`SYN-002`（8 MiB 上限）、`SYN-003`（Windows 固定不支持）は
いずれも fail-closed であり安全側である。しかし**受入基準にも状態遷移意味表にも現れていない**。
これは `FLW-REV-018:SYN-005` および `FLW-REV-019:SYN-003`（是正が新規回帰を作る）と同型であり、
振り返り §3.1 が挙げた再発類型そのものである。安全性の証明が進んだ一方で、
**利用者が公開集合の復帰後に最初に踏むのはこの3件**である。

とくに `SYN-001` は重い。`create`/`resume` は利用者が `mkdir` した root を対象にするが、
既定 umask では必ず `acl-not-owner-only` で止まる。closed result は理由を載せるが
operator action を持たず、runbook にも記述が無い。gating を外しても機能しない。

## CONDITIONAL_PASS とした根拠

`PASS` にしない理由は次の3点である。

1. 新規 P1 が 4 件あり、うち3件は公開後に利用者が直面する停止条件である。
2. `FLW-REV-027` の Gate blocking 条件のうち、**production 既定 dispatcher の E2E** と
   **`target OS` 3 種の実観測**が未達である。前者は gating により構造的に不可、
   後者は Linux のみ実施で Windows は実装不足により不可である。
3. `FLW-CON-008` の 7 観点に `実証済み` が 1 件も無い。

`FAIL` にしない理由は次の3点である。

1. 前回の P0/P1 7 件がすべて解消し、**P0 が 0 件**になった。
2. `risk` が 1.33 → 4.00 へ改善し floor をクリアした。前回の FAIL 要因が消えている。
3. 新規 P1 はいずれも fail-closed であり、データ破壊や誤った完了主張につながる経路は無い。

## Gate blocking 条件（GP-001〜004）

4 件すべて `basis: verified`（ソースまたは実測で確認済み）、`response: accepted`。

1. `GP-001` — `acl-not-owner-only` の operator action を closed result と runbook へ与える。
2. `GP-002` — snapshot 観測の出力上限を設計値として分離定義し、10,000 event／100 MiB
   条件の収束を実測する。
3. `GP-003` — §1.1 の 3 OS 保証を実装能力へ揃える（Windows の追跡先・期限・再判定 Gate
   を置くか、保証を Linux／macOS へ限定する）。
4. `GP-004` — 旧形式 chain の復旧手順を doctor から出力するか、前提条件として明示する。

## carried over 台帳

先行レビューの未解決 P0/P1 **93 件**を `carried_over[]` へ収録した（`FLW-REV-027` 時点の
86 件＋本レビューで新規に tracked とした 7 件）。`SI-FLW-091` が導入した機械検査により
**欠落が起きないことは保証されている**が、86 件の個別照合は未了である（`SYN-005`）。

## 裁定

worktree operation は gated を維持する。`GP-001`〜`GP-004` を消化し、
公開集合の復帰後に production E2E と `target OS` 実観測を得たうえで、
同じ5観点で三度目のレビューを行うこと。spec-issue の accept/reject は人間専権であり
本レビューは行わない。
