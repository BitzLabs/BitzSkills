---
id: SI-FLW-053
raised_by: FLW-REV-013（独立5観点レビュー・FAIL 2.31）
target: FLW-DSN-014・ROADMAP.md
proposed_change_type: modify
status: open
---
- **目的**: **残債の移送に伴う budget 配賦を記録し、上流の再校正が下流へ伝わる経路を作る。**
  現在、上流が下流へ負債を送るとき、**下流にそれを受け取る器が無い**。この構造欠陥は
  milestone 境界（M2→M3）とプラグイン境界（bitz-flow→bitz-sdd）の両方で確認された。

- **確認済みの欠陥**（`FLW-REV-013:SYN-001` / `SYN-002` / `SYN-024` / `SYN-025`。
  2026-08-13 に実ファイルで機械確認）:

  1. **M3 が受けた残債に budget 増分が無い**

     `FLW-DSN-014.md:635` の M3 budget は `3 + 3 = 6 PR` / 20 session。これは
     **2026-08-08 の一律再校正値**（M1 / M3 / M4 に同じ「実装3＋検証3」を当てた値）で、
     **残債を受け取る前の数字**である。

     2026-08-12 に M2 は2件を M3 へ送った（`FLW-DSN-014.md:676-683`）:
     remote-write class の被測定物 confirmation と、coordinator 証明手段の確定。
     出口条件欄には「残債confirmation」が追記されたが、**budget 欄は据え置き**。

     同じ状況で M1-6 から confirmation を受けた M2 は、`+1 PR / +3 session` を
     **内訳表へ明記して増額**していた（`FLW-DSN-014.md:664-671`）。
     `SI-FLW-045` が M1→M2 で是正した非対称が、**そのまま M2→M3 に再現している**。

  2. **上位計画への影響評価が無い（書く場所が無い）**

     `plugins/bitz-sdd/.spec/ROADMAP.md:485-487`:
     「bitz-flow V2の公開operation / result / SDD opaque ID接続が安定してから、
     bitz-sdd V4 Charterと正式設計を開始する」
     → bitz-flow V2 は bitz-sdd V4 の**直列の前提**（並行不可）。

     ところが同 `:660-663` のフェーズ4 の記述は2行のみで、**budget 値を持たない**。
     したがって bitz-flow V2 が 13 PR / 52 session → 30 PR / 100 session へ膨張しても、
     **消費側にそれを記録する欄が存在しない**。影響評価が「書かれていない」のではなく
     「書く場所が無い」。

  3. **M2-6 の過負荷**（`SYN-024`）。移送した +3 session が実質的に新規実装費へ流用されている
  4. **M2 に early quick win が無い**（`SYN-025`）。縮退が二値のため、
     20 session を投じて**出荷可能増分ゼロ**になり得る

- **裁定済みの部分**（2026-08-13、人間裁定）:

  | 項目 | 確定値 |
  |---|---|
  | M3 budget | **8 PR / 26 session**（一律再校正 6/20 ＋ remote-write confirmation 移送 +1/+3 ＋ coordinator 証明手段の設計 +1/+3） |
  | M2 設計再整備 | **2〜3 PR / 6〜9 session** を M2 実装予算の**別枠**として新設 |

  この2件は本 issue の accept と同時に文書へ反映する。

- **提案する修正**（**残る論点について裁定を求める**）:

  1. **M3 budget の内訳表を追加**（裁定済みの値で。M2 と同形式）。
     あわせて「coordinator 証明手段の具体形が未裁定（`ROADMAP.md` 未裁定論点1）であり、
     **設計結果が分散状態を要するなら +1 PR / +3 session では収まらず、
     裁定3 の『分散 lock は v2 外』という境界自体の再検討になる**」ことを
     M3 着手時の scope 再提示ポイントとして明文化する

  2. **M2 設計再整備を別枠として計上**（裁定済み）。
     `ROADMAP.md` の budget 一覧と `FLW-DSN-014` の milestone 表へ反映する

  3. **上位計画への伝達経路を作る**（**裁定を求める**）:

     | 案 | 内容 | 評価 |
     |---|---|---|
     | **案A** | `plugins/bitz-sdd/.spec/ROADMAP.md` のフェーズ4 へ **bitz-flow V2 の budget 総計を参照値として明記**し、「上流 budget が再校正されたら本欄を追随させる」義務を書く | **推奨。** 器を作る最小の変更。正は `FLW-DSN-014` に置き、消費側は参照のみ持つ |
     | 案B | 参照値の一致を `release_check.py` で機械照合する | より確実だが、ワークスペースを跨ぐ照合の実装が要る。`SI-FLW-052` の枠組みに乗せられるなら案A と併用が望ましい |
     | 案C | 記録しない（現状維持） | 同じ断絶が M3→M4、M4→M5 で再発する。非推奨 |

  4. **M2 の early quick win を定義する**（**裁定を求める**）。
     現在 M2 は「全部終わるか、M0 read-only へ縮退するか」の二値。
     `SI-FLW-051` で capability 縮退による段階公開を採るなら、
     **M2-1〜M2-3 完了時点で出荷可能な増分**（例: worktree audit の read-only 公開）を
     定義できる。M2-6 の過負荷解消と併せて実装区分を再配分する

  5. **残債移送の記録を成果物化する**（**裁定を求める**）。
     `FLW-DSN-014` 自身が「散文の予算は機械から見えず、M0では一度も発動しなかった」と
     認めている。移送元・移送先・移送量を機械可読な形で持ち、
     **受け側の budget に増分が無ければ検出する**ことを `SI-FLW-052` の検査に含めるか

- **対象ファイル**:
  - `plugins/bitz-flow/.spec/design/FLW-DSN-014.md`（milestone 表・M3入口条件・budget 内訳）
  - `plugins/bitz-flow/.spec/ROADMAP.md`（budget 一覧・フェーズ4）
  - `plugins/bitz-sdd/.spec/ROADMAP.md`（フェーズ4 への参照値追加。**別 PR とする**）

- **確認観点**:
  - 残債を送った側と受けた側の**両方**に、移送量が記録されていること
  - v2 総計と各 milestone の和が一致すること
  - 上流 budget の変更が下流の参照値へ伝わる経路が存在すること

- **影響推定・ロールバック**: 文書のみの変更。ただし `plugins/bitz-sdd/` は
  **別ワークスペースかつ他セッションが触る可能性がある**ため、
  bitz-flow 側の変更とは**別 PR に分ける**（1 PR = 1 関心事）。

- **依存**: `SI-FLW-051`（M2 の実装区分再配分と連動）。
  `SI-FLW-052`（(5) の機械検証を含める場合）。
