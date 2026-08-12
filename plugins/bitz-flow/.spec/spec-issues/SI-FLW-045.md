---
id: SI-FLW-045
raised_by: M2 worktree safety 設計（FLW-REV-011 対応）
target: FLW-DSN-014
proposed_change_type: modify
status: accepted
---
- **目的**: M1-6 が M2 以降へ送った**被測定物 confirmation の受け側が存在しない**。
  送った側の裁定と受けた側の設計が接続しておらず、このままでは
  Promotion Gate で「どの milestone で確認したか」を示せない。

- **現状の断絶**:

  `decision-2026-08-12-m1-6-scope.md` は M1-6 の範囲を qualification のみとし、
  「**被測定物の confirmation は M2 以降へ送る**」「M2 以降で worktree-first の安全境界が
  閉じた後、被測定物の confirmation を行う。そのときは本裁定の前提（縮退規則3・
  cross-host 証明）を再確認する」と裁定した。

  ところが受け側である `FLW-DSN-014` の M2 行は再校正されておらず、
  出口条件は「repo identity 衝突 0、repo 外承認、finish/discard fault 全通過」、
  budget は「4 PR / 14 session」のままである。**送られた残債がどこにも記録されていない。**

  同様に、縮退規則3「M2 未完了では worktree-first 安全境界が閉じないため M1 Git write を
  公開しない」は、**何が満たされれば公開できるかという解除条件を持たない**。

- **提案する修正**:

  1. **M2 出口条件へ confirmation を追加する**。
  2. **budget を再校正する**。M1-6 へ配賦されていた confirmation 分（1 PR / 3 session）を
     M2 へ移送する。ただし移送は**区分の付け替えであって M2 全体の余裕の増加ではない**ことを明記する
     （M2 は M1 に無い path 安全・repo 外境界・承認 capability を含み、
     M1 実績の下振れは M2 の下振れ根拠にならない）。
  3. **縮退規則3の解除条件を明文化する** — M2 出口条件を満たした時点で
     M1 Git write と M2 worktree を同時に公開できる、と参照可能な形で書く。
  4. **裁定3との干渉を解消する**（本件の中心論点）。
     `decision-2026-07-31` の裁定3は「cross-host GitHub create はスコープ境界として受入れ、
     分散 lock は v2 外、**coordinator 証明手段は M3 設計へ委譲**」と定めた。
     一方 M1-6 裁定は「cross-host で予約と lease を証明できなければ remote-write confirmation は
     成立しない」とする。したがって remote-write confirmation を M2 へ取り込むと、
     **M3 へ委譲したはずの coordinator 証明手段が M2 の前提になる**。

     - **案A（推薦）**: confirmation を write class で分割する。
       **local-write（`git.stage` / `commit` / `fetch` / `sync`、全 `worktree.*`）の
       confirmation を M2 で行い、remote-write（`git.publish-branch` /
       `git.delete-remote-branch`）は coordinator 証明手段が確定する M3 へ送る**。
       M2 出口では remote-write を `UNSUPPORTED` のまま維持する。
       裁定3を変更せずに済み、worktree-first 安全境界（local-write 主体）は M2 で閉じるため
       縮退規則3の趣旨も満たす。
     - **案B**: coordinator 証明手段を M3 から M2 へ前倒しし、全 confirmation を M2 で行う。
       裁定3の変更と M3 budget からの移送を伴う。
     - **案C**: confirmation 全体を M3 へ送る。M2 出口は現行のままで規則3の解除も M3 まで延びる。

  5. 案A を採る場合、remote-write confirmation の残債を **M3 の入口条件として
     `FLW-DSN-014` へ受け側の記述を作る**。本件と同じ断絶を繰り返さないための必須条件とする。

- **対象ファイル**: `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`（M2 行・縮退規則3・M3 入口条件）、
  `plugins/bitz-flow/.spec/ROADMAP.md`（フェーズ3の出口・縮退境界）、M2 開始時の run manifest。

- **確認観点**:
  - M2 出口条件が confirmation 対象 operation を**閉集合で列挙**していること。
  - 縮退規則3の解除条件が M2 出口条件を参照する形で機械的に判定できること。
  - 案A を採る場合、remote-write confirmation の残債が M3 側に**受け側の記述**を持つこと。
  - budget 再校正が M1 実績の run manifest を根拠として引用し、
    かつ「移送であって増加ではない」ことを明記していること。

- **影響推定・ロールバック**: milestone 出口条件・budget・縮退規則というゲート判定材料の変更であり
  軽量レーン不適・Design Gate 必須。公開 operation / result 契約は変更しない。
  却下した場合、M1-6 が送った残債の受け手が無い状態が継続する。

- **依存**: `decision-2026-08-12-m1-6-scope.md`、`decision-2026-07-31-bitz-flow-roadmap-open-issues.md`
  （裁定3）、`FLW-DSN-014`、`FLW-DSN-015`、`FLW-REV-011:GP-013`（fixture 採番）。
  **推薦: accept（案A）**。裁定3を変更せずに残債を回収でき、
  worktree-first 安全境界を M2 で閉じるという規則3の趣旨も満たす。
