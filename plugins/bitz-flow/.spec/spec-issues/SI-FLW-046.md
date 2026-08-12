---
id: SI-FLW-046
raised_by: M2設計セッションでの実事故（未マージブランチ見落としによるID二重採番）
target: FLW-FR-007・FLW-DSN-006・FLW-DSN-016
proposed_change_type: modify
status: open
---
- **目的**: **着手前に「同じ主題の in-flight な作業が既にあるか」を発見させる。**
  v2 は列挙・分類の能力を既に持つが、(a) 見ることが義務になっておらず、
  (b) 主題の重なりを示す情報が result に無いため、実際に事故が起きた。

- **実際に起きた事故（本 issue の起票契機）**: 2026-08-12、bitz-flow M2 の設計補強に着手する際、
  `docs/bitz-flow-m2-design`（**未 push・PR なし・3コミット**）の存在を確認せずに始めた。結果:

  1. `SI-FLW-041` / `SI-FLW-042` / `FLW-REV-011` を**別内容で二重採番**した
  2. 同ブランチに含まれる**人間裁定「補強詳細設計は作らない」に反する成果物**を作った
  3. 1セッション分の設計をやり直した

  `git worktree list` は確認していた。見落としたのは **worktree として展開されておらず
  push もされていない**ブランチであり、PR 一覧にも worktree 一覧にも現れなかった。

- **現状で足りている部分（新規能力は不要）**:

  | 既存 | 内容 |
  |---|---|
  | `FLW-FR-007` | 「default branch と symref を除く local/remote branch を**列挙**する」 |
  | `branch_audit_state` | **`ACTIVE`**（local branch が進んでおり PR なし）を分類語彙に持つ |

  **v2 の branch audit を走らせていれば、当該ブランチは `ACTIVE` として出ていた。**
  本 issue は能力の追加ではなく、**義務化と情報の追加**を求めるものである。

- **提案する修正**:

  1. **着手前 reconnaissance を entry protocol の一部にする**。
     `flow-core` の Mandatory entry protocol は「dispatcher を通せ」という規律であり、
     「着手前に in-flight な WorkUnit を棚卸しせよ」ではない。
     **新しい書込み WorkUnit を開始する前に、repo 全体の in-flight 作業の列挙を必須**にする。
     `FLW-FR-006` の plan が照合するのは path / branch / work ID の**衝突**であり、
     **branch 名が違えば主題が同じでもすり抜ける**（事故ではまさにこれが起きた）。

  2. **result へ「触れているファイル」を載せる**。
     各 `ACTIVE` branch について `git diff --name-only origin/main...<branch>` 相当を取り、
     **これから触る path との重なり**を返す。事故時、両ブランチは branch 名も work ID も
     違ったが `FLW-DSN-015.md` と `.spec/spec-issues/` を共に触っていた。
     read-only で安く、`FLW-FR-007`（状態変更を行わない）の制約に収まる。

  3. **共有カウンタの衝突を分類語彙へ加えるか裁定する**（本 issue で最も設計判断を要する点）。
     `.spec/` の採番は `spec_scaffold.py` が**作業ツリーの最大値 + 1**で行うため、
     未マージの2ブランチが独立に同じ ID を取る。これは path の衝突ではなく
     **共有された単調増加カウンタの衝突**であり、`branch_audit_state` の
     どの語（`ACTIVE` / `MERGED_EXACT` / `REMOTE_ADVANCED` / `WORKTREE_IN_USE` / `ORPHAN`）にも
     対応する概念が無い。
     - 採番そのものは **bitz-sdd の所管**（`spec_scaffold.py`）であり、
       bitz-flow は「in-flight branch が未マージの採番を保持していること」を
       **可視化するだけ**に留めるのが境界として正しいと考える。
     - 検出を bitz-flow が持つのか、`SI-SDD-*` へ委託するのかを裁定に含める。

- **対象ファイル**: `plugins/bitz-flow/.spec/requirements/FLW-FR-007.md`（受入基準の追加）、
  `plugins/bitz-flow/.spec/design/FLW-DSN-006.md`（audit）、
  `plugins/bitz-flow/.spec/design/FLW-DSN-016.md`（M2 の audit 決定表）、
  `plugins/bitz-flow/skills/flow-core/SKILL.md`（entry protocol）。

- **確認観点**:
  - 未 push・PR なし・worktree 未展開の local branch が列挙結果に現れること
    （**事故で見落とした条件そのもの**を fixture 化する）。
  - これから触る path と重なる in-flight branch が、重なり付きで返ること。
  - reconnaissance を省いて書込み WorkUnit を開始しようとすると止まること。
  - audit が状態変更を行わないこと（`FLW-FR-007` の既存制約を維持）。

- **影響推定・ロールバック**: **v2 の scope 追加**である。`FLW-DSN-014` は
  M2 を 5 PR / 17 session（`SI-FLW-045` の移送後）に固定しており、
  「新しい要件・operation・platform 固有分岐を追加する場合は予算内であっても
  scope 変更として人間へ提示する」と定める。したがって**budget 再提示が必要**。
  公開 operation を増やさず `worktree.audit` の result 拡張と entry protocol の
  改訂に留めれば増分は小さいが、その判断も裁定に含める。
  却下しても既存能力は失われない（branch audit は列挙・分類できるまま）。

- **裁定の適時（推薦）**: **M2 着手前**。branch audit は M2 の実装位置であり、
  M2-3（create / resume / audit）へ相乗りできれば増分が最小になる。
  ここを逃すと `1.1.0` 以降の Should 昇格待ちになり、
  **v2 開発そのものが同じ事故を繰り返す期間が延びる**。

- **依存**: `FLW-FR-006`（衝突照合の範囲）、`FLW-FR-007`（branch audit）、
  `FLW-DSN-016`（M2 audit 決定表・budget）、`FLW-DSN-014`（scope 変更時の再提示規則）、
  `SI-FLW-045`（M2 budget）。採番衝突は bitz-sdd の `spec_scaffold.py` に接続する。
  **推薦: accept**（ただし 3 は「可視化のみ」に限定し、採番の是正は bitz-sdd へ委託）。
  v2 はエージェント向けのツールであり、**今回失敗したのはエージェント自身である**。
  自分の開発で再発する事故を自分のツールで防げる、ドッグフーディングの直接の題材にあたる。
