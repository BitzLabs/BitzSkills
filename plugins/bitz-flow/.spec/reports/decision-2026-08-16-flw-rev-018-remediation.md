# 裁定記録 — FLW-REV-018 の全件対処と、単純化を優先する方針

- **日付**: 2026-08-16
- **裁定者**: hide
- **対象**: `FLW-REV-018`（CONDITIONAL_PASS 3.60）の16 finding すべて
- **裁定原文**: 「予算を度外視で、FLW-REV-018 の指摘内容をすべて対処しましょう。
  ただし、変に複雑な機能追加せずにシンプルな構成を目指します、m0,m1 の経緯を
  きちんと確認しながら進めましょう」
- **記録者**: claude（裁定者の明示指示に基づく代行記録・実行者未検証）

## 1. 予算

**第2次予算（5 PR / 15 session、`5 PR / 11 session` で到達し自動停止）の上限を解除する。**
本裁定以降、`FLW-REV-018` の16 finding の対処については PR 数・session 数の上限を設けない。
`record_run.py` への記録は継続し、実績は次のレビューへ報告する。

## 2. 設計方針 — 「機能を足す」より「主張を正す」

裁定者の指示は**シンプルな構成**である。`FLW-REV-018` の指摘には、機械を作れば閉じるものと、
**過大な主張を実態へ合わせれば閉じるもの**が混在する。後者に機械を作らない。

適用した判断は次のとおり。

| finding | 複雑な解 | **採る解（単純）** |
|---|---|---|
| `SYN-005` enum 閉集合外 | `ORPHAN` を `worktree_state` へ追加する | **公開 result から `worktree_state` を外す** |
| `SYN-004` release_class が定数 | 新しい分類器を作る | **既存 `classify_quarantine` を実データで駆動する** |
| `SYN-001` chain 無検証 | 署名や外部台帳を導入する | **既に書いてある digest と連番を読み出し時に検証する** |
| `SYN-006` 解除経路が無い | `worktree.release` operation を新設する | **解除は人間手順と明記し、必要な入力を result で示す** |
| `SYN-002` 事故の実体を検出しない | 任意コミットの正当性を判定する | **判定範囲を「worktree の由来と現況」と明記し、HEAD 変化は事実として報告する** |

### `ORPHAN` の扱い（M0 / M1 の経緯確認の結果）

`FLW-DSN-016` §2 の閉集合は `worktree_state` = `ABSENT, CLEAN, DIRTY, MISMATCH` であり、
**`ORPHAN` は `branch_audit_state` の値**である。schema（`worktree-state-v1.schema.json`）・
設計・実装の三者はこの点で一致していた。

PR #292 が公開 result へ `worktree_state: "ORPHAN"` を載せたのが**唯一の逸脱**である。
`ORPHAN` は `FLW-DSN-006` / §7 が使う**起因の呼称**（散文）であって field 値ではない。
よって閉集合を広げず、**公開 result から当該 field を外す**。新しい enum は1つも増やさない。

### receipt chain 検証は新概念ではない

`FLW-DSN-015` は evidence ledger について「未取込 lease、重複 ID、**欠番、chain 破損**で
Gate を `blocked` にする」と既に定めている。receipt の書き込み側も
`record_digest` / `previous_record_digest` / 連番を正しく作っている。
**読み出し側が検証していないだけ**であり、同じ規則を receipt へ適用する。

## 2.5 個別裁定（2026-08-16）

| # | 論点 | 裁定 |
|---|---|---|
| A | 出口条件6の読み方 | **案1** — worktree の生成・消失・binding 不整合に限る |
| B | `agy_guard` の覆域 | `run_command` のみのまま。**禁止操作を allow の有無と独立に deny** し、評価順を DENY→ASK→ALLOW に固定する |
| C | `required_checks` / `positive_controls` | **field を削る**。測っていないものを主張しない |
| D | 検証証跡の commit 到達不能 | **bitz-sdd へ spec-issue を起票して委託**。bitz-flow 側は限界を明記するに留める |
| E | quarantine の解除経路 | `worktree.release` operation を**新設しない**。解除は人間手順と明記し、result は必要な入力を示す |
| F | TTL 時限故障 | テストを「現行証跡がいま有効であること」から「**TTL 判定が正しく働くこと**」の検査へ変える |
| G | nonce の袋小路 | dir fsync と temp 名衝突は直す。reconcile operation は**新設しない** |
| H | `SI-FLW-067`〜`071` | **accepted** として着手する（`GP-006` の M3 予算計上のみ M3 入口で別途裁定） |

### B の補足 — なぜ matcher を広げないか

事故で使われた「ガード自身の書き換え」まで止めるにはファイル編集系ツールを matcher へ
加える必要があるが、このリポジトリは常に複数セッションが並行しており、
**全セッションの編集がガードを通る**副作用が大きい。
`run_command` 経路で禁止操作を独立に deny すれば、`chmod` / `mv` によるガード無力化は塞がる。

### D の補足 — なぜ bitz-flow で回避しないか

squash merge で commit SHA が変わるのは `spec_verify` の構造的欠陥であり、
**M0 期の証跡も同じ状態**である。bitz-flow だけ独自方式にすると
他ワークスペースと証跡の読み方が割れる。正しい持ち主へ渡す。

## 3. 出口条件6の読み方（裁定: 案1）

条件6は「operation 外の変更を audit が検出し quarantine へ接続する」である。
文字どおり読むと「managed worktree 内で開発者が行うコミット」も *operation 外の変更*だが、
それは M2 が実現しようとしている**正常な作業そのもの**であり、検出対象にすると
恒常的な偽陽性になる。

本対処では条件6を次の意味に確定する。

> **operation 外の worktree の生成・消失・binding 不整合**を audit が検出し、
> §6 の解除区分へ接続する。任意のコミットの正当性は判定しない。
> managed worktree の HEAD 変化は**事実として報告**するが違反としない。

**2026-08-16 に案1で確定した。**

commit 由来判定（案2）を検討した結果、**M2 単独では原理的に成立しない**ことが判明した。
`commit_causality` の founding principle は「条件の一致する commit を後から検索して
今回の成功と見なすことをしない。**CAS を実行した writer の receipt** を `DONE` の必須条件と
する」であり、由来は受領書でしか判定しない。ところが `git.commit` は M1 の operation で
現在 `UNSUPPORTED` であり、bitz-flow は commit を1つも作らない。
よって由来を裏付ける receipt が存在し得ず、**すべての commit が由来不明**になる。
全件 `INDETERMINATE` は運用できない。

commit 単位の由来判定は **M1 `git.commit` の公開に依存する**ため、M3 入口条件へ計上する
（`GP-006`）。なお 2026-08-15 の事故の検出は `SI-FLW-062` の harness 側
`repo_state_digest` 前後比較として既に成立しており、そちらが正しい持ち場である。

## 4. 範囲

対象は `FLW-REV-018` の `SYN-001`〜`SYN-016` と、追跡先 `SI-FLW-067`〜`071`。
`SYN-016`（M3 残債）は実装せず M3 入口条件へ計上する（`GP-006`）。
出荷面は M0 read-only のままとし、worktree 系の公開はしない。
