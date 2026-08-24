---
id: FLW-REV-028
title: "M2 Local Safety Profile 是正後再レビュー"
status: active
version: 2.0
updated: 2026-08-24
owner: claude
decision: FAIL
---

# M2 Local Safety Profile 是正後再レビュー

- **対象**: `FLW-DSN-017` v2.3、`FLW-FR-006` v2.1、`FLW-NFR-014` v2.3、`FLW-CON-008`、
  `FLW-TSK-106`〜`122`、flow-core の CLI・platform・runtime・transaction・recovery・
  operability、関連 schema・test・runbook、confirmation 証跡
- **判定**: **FAIL**（v1.0 の CONDITIONAL_PASS から訂正。理由は §訂正の経緯）
- **集計スコア**: **2.52**（`FLW-REV-027` は 2.12）。`risk` 2.00 が floor 2.5 に未達
- **公開判断**: worktree operation は現在の gated 状態を維持する。
  下記 GP-001〜008 の消化まで Promotion Gate を通さない。
- **セカンドオピニオン**: codex（OpenAI）判定 **FAIL**、antigravity（Gemini）追加欠陥6件。
  記録は `individual/flw-rev-028-secondopinion-{codex,agy}.json`。

## 観点別スコア

| 観点 | v2.0 | v1.0 | 前回 | 重み | 主要所見 |
|---|---:|---:|---:|---:|---|
| consistency | 3.00 | 3.70 | 2.65 | 0.15 | §3.2 の self-test 要求と実装が乖離し、v1.0 はそれを申告しなかった |
| data-integrity | 3.50 | 4.65 | 2.00 | 0.25 | crash 空隙は解消。ただし case alias を畳めず競合直列化に穴 |
| operations | 2.00 | 2.90 | 2.30 | 0.20 | macOS で traceback、Windows は固定不支持。動くのは case-sensitive Linux のみ |
| risk | **2.00** | 4.00 | 1.33 | 0.25 | **floor 2.5 未達**。未捕捉例外・symlink 逸脱・恒真 self-test |
| business | 2.00 | 3.00 | 2.85 | 0.15 | 実質 Linux 専用であり 3 OS の価値仮説が成立しない |

findings: 統合前 18 件 → 重複排除後 12 件（**P0: 1** / P1: 8 / P2: 3 / P3: 0）。

集計 2.52 は閾値 2.5 をわずかに上回るが、**`risk` が floor 2.5 に未達**のため FAIL とする。

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

## 訂正の経緯（v1.0 → v2.0）

v1.0 は **CONDITIONAL_PASS 3.75** と判定した。その後、同一レビュー活動の一部として
クロスモデルのセカンドオピニオンを実施し、**実測で確認できた追加欠陥により判定を FAIL へ訂正**した。

v1.0 の判定を本書から削除していない。**自己レビューの限界の実例として残す。**
v1.0 は是正を実装した本人が書いており、`worktree_platform.py` の中核欠陥
（symlink 追随、恒真 self-test、case-insensitive クラッシュ）を**1件も検出できなかった**。
いずれも自分が書いたコードである。

セカンドオピニオンの内訳は次のとおり。

| レビュアー | モデル | 判定 | 追加指摘 |
|---|---|---|---|
| codex | OpenAI | **FAIL** | 3件（symlink 追随、恒真 self-test、case semantics）＋ SYN-001／003 の解消判定に異議 |
| antigravity | Gemini | 判定は求めず | 6件（folded_component 欠落、evidence 不整合、fuse 分類、bind mount、不在 target、supervision 固定値） |

**指摘は自己申告として受け取らず、1件ずつ再現して検証した。**

- `AGY-001`（folded_component 欠落）は**指摘より重い**と判明した。再現すると
  `ContractError` が送出され、CLI が捕捉する3型のいずれでもないため traceback になる。
- `ADD-001`（symlink）は symlink 経由の 0700 ディレクトリが `SUPPORTED` /
  `non_follow_walk=True` を返すことを実測した。
- `ADD-003`（case semantics）は判定が path 全体の反転存在確認であることを実測した。

v1.0 で挙げた新規 P1 4件（GP-001〜004）は取り下げない。すべて有効な指摘として残る。

## v1.0 が甘かった理由

判定の分かれ目は「新規 P1 はすべて fail-closed であり、データ破壊や誤った完了主張に
至る経路は無い」という v1.0 の根拠だった。これは**誤りだった**。

`SYN-007` の未捕捉例外は fail-closed ではない。closed result 契約の違反であり、
`FLW-CON-008` の「状態意味保存」にも反する。また `SYN-008`（symlink 逸脱）は
信頼境界の外へ出る経路であり、fail-closed の反対である。

自分が書いたコードの**主張と実証の差**（`non_follow_walk=True` と実際の追随、
`semantic_self_test=True` と恒真性）を、書いた本人は「そう書いたから正しい」と
読んでしまう。この差は他者が読むまで見えなかった。

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

## FAIL とした根拠

1. **P0 が 1 件ある**（`SYN-007`）。case-insensitive volume で `plan()` が未捕捉例外に
   なり closed result 契約を破る。macOS の既定 APFS は case-insensitive であり、
   実際に動作するのは case-sensitive な Linux のみである。
2. **`risk` 2.00 が floor 2.5 に未達**である。`FLW-REV-027` が FAIL となった構造と同じで
   ある（当時 1.33）。未捕捉例外・symlink 逸脱・恒真 self-test はいずれも安全境界に
   関わる欠陥である。
3. 前回 P0/P1 のうち **`SYN-001` と `SYN-003` は解消と言い切れない**。前者は
   production 到達性という元の文面に対して未解消、後者は operation 全体の deadline が
   未実装で 30 秒収束が保証されない（`SYN-011`）。
4. `FLW-CON-008` の 7 観点に `実証済み` が 1 件も無い。

前回から改善した点は否定しない。crash 空隙の解消、`QUARANTINED` の誤分類是正、
closure 順序の是正、証跡の過大主張の解消はいずれも実効性がある。しかし
**probe という新規コードが新しい安全境界の穴を作った**ため、通算では FAIL である。

## Gate blocking 条件（GP-001〜008）

8 件すべて `basis: verified`（ソースまたは実測で確認済み）、`response: accepted`。

| GP | 内容 | 由来 |
|---|---|---|
| GP-001 | `acl-not-owner-only` の operator action を closed result と runbook へ与える | v1.0 |
| GP-002 | snapshot 出力上限を設計値として分離定義し、operation 全体 deadline と 10,000 event／100 MiB 収束を実測する | v1.0＋codex |
| GP-003 | §1.1 の 3 OS 保証を実装能力へ揃える | v1.0 |
| GP-004 | 旧形式 chain の復旧手順を doctor から出力するか前提条件として明示する | v1.0 |
| **GP-005** | **folded_component を導出して plan を成立させ、未捕捉例外 0 件を機械検査する** | agy |
| GP-006 | component 単位の非追随 walk で symlink を実証検出する | codex |
| GP-007 | §3.2 の semantic self-test 要求と実装の乖離を解消する | codex |
| GP-008 | case semantics と filesystem 種別を mount 単位で解決する | codex＋agy |

**着手順は GP-005 を最優先とする**（未捕捉例外は他の是正の検証を妨げる）。
次に GP-001（既定 umask）、GP-006（symlink）である。

## carried over 台帳

先行レビューの未解決 P0/P1 **93 件**を `carried_over[]` へ収録した（`FLW-REV-027` 時点の
86 件＋本レビューで新規に tracked とした 7 件）。`SI-FLW-091` が導入した機械検査により
**欠落が起きないことは保証されている**が、86 件の個別照合は未了である（`SYN-005`）。

## 裁定

worktree operation は gated を維持する。`GP-001`〜`GP-008` を消化し、
公開集合の復帰後に production E2E と `target OS` 実観測を得たうえで、
同じ5観点で三度目のレビューを行うこと。spec-issue の accept/reject は人間専権であり
本レビューは行わない。

## Revision History

- 2.0 (2026-08-24) クロスモデルのセカンドオピニオン（codex / antigravity）の指摘を
  実測で検証し、判定を CONDITIONAL_PASS 3.75 から **FAIL 2.52** へ訂正。P0 1 件
  （case-insensitive volume での未捕捉例外）と P1 4 件を追加し、GP-005〜008 を起票。
  v1.0 の判定と、それが甘かった理由を本文に残した。
- 1.0 (2026-08-24) 是正後の初回判定（CONDITIONAL_PASS 3.75）。是正を実装した本人による
  自己レビューであり、probe の中核欠陥3件を検出できなかった。
