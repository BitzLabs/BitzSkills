---
id: FLW-REV-012
title: "M2 worktree safety詳細設計 再レビュー"
status: pending
version: 1.0
updated: 2026-08-12
owner: claude
decision: CONDITIONAL_PASS
---

# 設計レビュー統合レポート — M2 worktree safety 詳細設計（FLW-DSN-016）

- **review_id**: FLW-REV-012
- **対象**: `FLW-DSN-016`、および同じ変更セットで更新した `FLW-DSN-015` / `FLW-DSN-012` /
  `FLW-DSN-006`、`SI-FLW-043` / `044` / `045`
- **判定**: **CONDITIONAL_PASS**（3.62。PASS ≥ 3.5 / CONDITIONAL_PASS ≥ 2.5）
- **前レビュー**: `FLW-REV-011`（FAIL、2.47、P0 5系統 / GP 18件）

## レビューの性質（判定に織り込むこと）

**本レビューは `FLW-DSN-016` の起案者自身による検証であり、独立性が無い。**
`FLW-REV-011` は独立した多観点レビューとして実装 grep（`git_sync.py:234` の literal `"main"`、
不在 path での `_case_sensitive_filesystem` の戻り値）まで裏取りして P0 5系統を検出した。
本レビューは同じ深度の独立性を持たない。P0 1件・P1 1件を自己検出できてはいるが、
見落としの可能性を残す（`SYN-008`）。

## 観点別スコア

| 観点 | スコア | 主要所見 |
|---|---:|---|
| consistency | 3.70 | GP 18件すべてに対応節がある。session 合計と namespace 表の抜けを是正 |
| data-integrity | 3.60 | guard key への instance 混入という **P0 を新たに作っていた**（是正済み） |
| operations | 3.50 | 解放経路の最頻ケースに穴があった（是正済み）。独立性の欠如が残る |
| risk | 3.60 | 44 fixture で検証可能。ABA capability の実在性が未確定 |
| business | 3.80 | budget が `SI-FLW-045` と一致。区分超過の再提示規則あり |

findings: 統合前 9 件 → 重複排除後 **8 件**（P0: 1 / P1: 1 / P2: 4 / P3: 2）

## FLW-REV-011 の Gate 前提条件 18件の充足

| GP | 内容 | 対応 | 判定 |
|---|---|---|---|
| GP-001 | enum を `FLW-DSN-012` / `FLW-DSN-006` と一致・三者照合の機械化 | §2 | 充足 |
| GP-002 | repo 外承認の capability 化 | §4 | 充足 |
| GP-003 | index 包含規約 | §3 | 充足 |
| GP-004 | instance identity の CAS 照合 | §5 | 充足（**当初 key へ混入していた。SYN-001 で是正**） |
| GP-005 | quarantine 解除区分と解放経路 | §6 | 充足（**最頻ケースの穴を SYN-002 で是正**） |
| GP-006 | finish / resume を3者 guard の対象へ | operation catalog | 充足 |
| GP-007 | `worktree-dir` の CAS 相当と capability 縮退 | §5 | 充足 |
| GP-008 | binding 検証と `worktree_id` の canonical 導出 | §3 | 充足 |
| GP-009 | case 感度の祖先遡り・判定不能は `BLOCKED` | §3 | 充足 |
| GP-010 | permissions ＋ フックによる機械強制層 | §4 | 充足 |
| GP-011 | 承認の単回化 | §4 | 充足 |
| GP-012 | 設計・schema・実装の三者照合テスト | §2 | 充足 |
| GP-013 | `M2-FLT-*` の採番と recovery matrix 行 | §8 / §9 | 充足（44件） |
| GP-014 | 多重語一覧の機械導出 | §2 | 充足 |
| GP-015 | closed enum 値追加の互換性条文 | §2 | 充足（互換性根拠を「未公開だから影響が無い」へ置換） |
| GP-016 | 表記規則の判定基準と反例 | §2 | 充足 |
| GP-017 | `ORPHAN` の起因限定と外部起因の復旧 | §7 | 充足 |
| GP-018 | `FLW-DSN-006` / `FLW-DSN-012` の表記統一と version 更新 | §2 ＋ 実ファイル更新 | 充足 |

**18件すべてに対応節が存在する。** ただし GP-004 / GP-005 は初版の対応に欠陥があり、
本レビューで是正した（下記）。

## 本レビューが新たに検出した欠陥

### P0 — instance identity を guard key へ含めていた（SYN-001）

初版 §3 は `worktree-dir` の canonical key を
「common-dir identity ＋ path digest ＋ **instance identity**」と定義していた。

**これは `FLW-REV-011:SYN-004` を防ぐどころか悪化させる。** key に instance を含めると、
旧 instance の `discard` と新 instance の `create` が**別 key になり互いに排他しない**。
同一 path に対する直列化そのものが失われ、両者が同時に進行し得る。

`FLW-REV-011:GP-004` の文言も「instance identity を **precondition に入れ** apply 直前に
CAS 照合する」であり、key へ入れるとは書いていない。原文の読み違いであった。

**是正（v1.1）**: key は path に対して安定（instance 非依存）とし、全 operation を同じ key で
直列化する。instance の同一性は precondition（`snapshot_digest`）で照合する。
役割分担（直列化＝key / 同一性照合＝precondition）を表で明示した。

### P1 — registry entry だけ残存する最頻ケースに解放経路が無い（SYN-002）

初版 §6 の quarantine 解除区分は `no-effect` / `residue-retained`（directory だけ残存）/
`unresolved` の3種だった。しかし外部要因（手動削除・外部ツール）で**実体だけが消える**形が
最も起きやすく、これは directory 不在・registry entry 残存であり3区分のどれにも当たらず
`unresolved` へ落ちる。**回復可能な状態が恒久 quarantine に固定される。**
GP-005 が求める「正規の解放経路」が最頻ケースで存在しないことになる。

**是正（v1.1）**: `worktree-registry-stale` 区分を追加。`gitdir` が指す path の非存在証明を
必須とし、stale entry の除去を正規の残 step として許可する。単に見えないだけ
（mount 未接続・権限不足）と区別できない場合は `unresolved` とする。

### P2 4件（すべて v1.1 で是正）

| ID | 内容 |
|---|---|
| SYN-003 | session 合計が 18 で `SI-FLW-045` の 17 と 1 ずれていた → 再配分して 17 へ |
| SYN-004 | `nonexistence_digest` を全 operation の署名対象に一律列挙していた → `create` 専用とし、既存 target 側は `instance_identity_digest` |
| SYN-005 | namespace 表に `trial_kind` / `cause` が無く三者照合の対象範囲が曖昧 → 追加し対象を明示 |
| SYN-006 | ABA 検出 capability の実在性が未検証のまま経路が分岐（**未解決。GP-004 で追跡**） |

## Gate 前提条件（blocking）

`FLW-DSN-016` を active へ進め M2 の契約を凍結するには次が必要である。

| ID | 条件 |
|---|---|
| GP-001 | `SI-FLW-043`（`FLW-NFR-007` の改訂）が accepted かつ要件改訂が承認されるまで、worktree 実体の作成・削除を実装しない |
| GP-002 | `SI-FLW-044`（`FLW-CON-006` の CAS 厳格化）が accepted かつ要件改訂が承認されるまで、`git.delete-remote-branch` を実装しない |
| GP-003 | `SI-FLW-045`（M1 confirmation 負債の受け側）が accepted となり `FLW-DSN-014` の M2 行と縮退規則3が改訂されるまで、M2 出口条件を凍結しない |
| GP-004 | ABA 検出 capability の実在性を M2-5 着手前に確認し、実在しなければ分岐を削除して単一経路へ確定させる |

GP-001 / GP-002 は **approved 要件の受入基準変更**であり、設計承認だけでは足りない。

## 人間への裁定依頼

1. `SI-FLW-043` / `044` / `045` の accept / reject を裁定する（各 issue に推薦を記載）。
   `SI-FLW-045` は案 A / B / C の選択を含む（推薦は案 A）。
2. 要件改訂3件（`FLW-NFR-007` / `FLW-CON-006` / `FLW-FR-007`）の可否を裁定する。
3. 本レビューが**起案者 self-review** であることを踏まえ、M2 契約凍結前に
   **独立レビュー（クロスモデル検証）を実施するか**を判断する。
   `FLW-REV-011` は独立レビューだったからこそ P0 5系統を検出できた。
4. 上記が揃った時点で `FLW-DSN-016` を active 化し、M2 Design Gate を起票する。

## 判定の意味

`FLW-REV-011` が挙げた Gate 前提条件 18件すべてに対応節ができ、
P0 5系統は設計上閉じた。**PASS ではなく CONDITIONAL_PASS とするのは、**
要件改訂3件が未裁定であること、ABA capability の実在性が未確定であること、
そして本レビューに独立性が無いことの3点による。
