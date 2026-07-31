---
id: SI-FLW-007
raised_by: M0 eval harness の予備計測（TSK-012、2026-07-31）
target: FLW-NFR-002 が前提とする fixture corpus と raw baseline command が未定義で、byte 削減率の合否が測定条件の選び方で反転する
proposed_change_type: modify
status: open
---
- **目的**: `FLW-NFR-002` は受入基準で「**status fixture corpus** を compact renderer で測定する」
  「**raw baseline 比** median byte 削減 70%以上」と書き、検証手段でも「固定 fixture corpus、
  **raw baseline command**」を要求している。しかし **corpus も baseline command も、どこにも
  定義されていない**。`FLW-DSN-014` の M0 出口条件も `discovery/metrics.md` の
  Token / Output Efficiency 表も、閾値だけを述べて測定条件を固定していない。

  M0 eval harness（`evals/flow-core/m0-eval/`）を実装し、その動作確認として fixture 上で
  直接測ったところ、**測定条件の選び方で合否が反転する**ことが分かった。

  | task | 生 CLI baseline | v2 compact | 削減率 | 閾値 |
  |---|---:|---:|---:|---:|
  | `repo-inspect` | 78 B（`git status --short --branch`） | 120 B | **-54%** | 規定なし |
  | `dirty-status` | 464 B（`git status`） | 170 B | **63%** | 70% |
  | `diff-summary` | 458 B（`git diff HEAD`） | 155 B | **66%** | 80% |

  問題は3つある。

  1. **baseline command が未定義**。`git status`（長形式、464 B）を基準にすると 63%、
     `git status --short`（短形式）を基準にすると compact のほうが**大きい**。
     同じ実装が、比較対象の選び方だけで合格にも不合格にもなる。
     `repo-inspect` 行の -54% は、短形式 baseline と比較するとどうなるかの実例である。
  2. **corpus の規模が未定義**。上表の fixture は変更 4 件しかなく、compact の固定部分
     （判定行・`NEXT` 行・`TRUNCATED` 行）の比重が大きい。削減率は変更件数が増えるほど
     有利になる一方、`status` の長形式 baseline は件数に依存しない定型ヒント文
     （`(use "git restore ..." )` 等）を多く含むため、件数を増やすと逆に compact 側が
     不利になる可能性もある。**どちらへ動くかは実測しないと分からない。**
  3. **閾値の根拠が `[proto / 未検証]`**。`discovery/metrics.md` は 70% / 80% を
     `[proto / 未検証]` と明記し、「実装前に fixture と計測方法を固定してからベースラインを
     取得する」と述べている。つまり本 issue が指す作業は Discovery 時点で予定されていたが、
     成果物として固定されないまま要件が approved / implementing へ進んだ。

  現状では M0 の出口判定を「測定条件を選んだ人の裁量」で通せてしまう。数値を通すために
  fixture を差し替えたり baseline を弱い command へ変えたりしないことを harness の
  README と `FLW-TSK-012` の備考へ明記したが、これは規律であって仕様ではない。

- **提案する修正**:
  1. **raw baseline command を operation ごとに固定する**成果物を作る
     （`flow-core/references/output-contract.md` の benchmark 節、または
     `evals/flow-core/m0-eval/` 配下の version 管理 manifest）。
     初期案は「エージェントが同じ情報を得るために実際に打つ既定形」とし、
     `dirty-status` は `git status`、`diff-summary` は `git diff <base>` とする。
     `--short` / `--porcelain` は機械向け短縮形で人間可読な情報が落ちるため baseline にしない、
     という**選定理由も併せて固定する**（理由が無いと次に同じ議論が起きる）。
  2. **fixture corpus を定義する**。単一 fixture ではなく、変更件数の異なる複数 fixture
     （例: 小 4 件 / 中 30 件 / 大 100 件超）を corpus とし、median をその横断で取る。
     corpus は `fixture.py` と同じく決定論的に構築できる形にする。
  3. **corpus 確定後に閾値を実測して再校正する**。`discovery/metrics.md` の
     `[proto / 未検証]` を外す手順（誰がいつ、どの実測を根拠に確定するか）を定める。
  4. 削減率の緩和と情報欠落の取引を禁止する。`FLW-NFR-002` は必須 field 保持 100% と
     blocking 項目保持 100% を同時に要求しており、**閾値を下げる裁定をする場合でも
     この2つは緩めない**ことを明記する。

- **対象ファイル**: `.spec/discovery/metrics.md`（Token / Output Efficiency の測定条件）、
  `.spec/design/FLW-DSN-014.md`（M0 出口条件の byte 削減行）、
  `evals/flow-core/m0-eval/fixture.py`（corpus 構築）、
  `evals/flow-core/m0-eval/README.md`（予備計測節の更新）、
  `skills/flow-core/references/output-contract.md`（benchmark 節を設ける場合）。

- **確認観点**:
  - 重複: `SI-FLW-006` は cause 語彙の不足であり対象が異なる。他に測定条件を扱う
    spec-issue は無い。
  - 既存要件との関係: **提案1 と提案2 は `FLW-NFR-002` の EARS を変更しない**。
    条文は「fixture corpus」「raw baseline」という未定義語を参照しており、その定義を
    与えるだけで条文の意味は変わらない（緑を赤にし得ない）。
    一方 **提案3 で閾値そのものを動かす場合は受入基準の意味的変更**にあたり、
    `FLW-NFR-002` は implementing で EARS 節が書き換え不可のため **supersede が必要**になる。
    提案1・2 を先に実施し、実測値を持ってから提案3 の要否を裁定するのが安全である。
  - ガードレール: 測定条件を後から選べる状態を残さない。corpus と baseline は
    version 管理された成果物として固定し、変更は decision reference つきで行う。
  - 検証: 固定 corpus と固定 baseline で `score.py` が再現可能な median を出すこと、
    corpus を差し替えたときに判定が変わることを確認できること。
  - 軽量レーン適否: **不適**（M0 出口条件の合否を左右する）。

- **影響推定・ロールバック**: 提案1・2 は測定条件の追加であり、実装コードを変更しない。
  提案3 を採る場合は `FLW-NFR-002` の後継要件を起票し、旧要件を deprecated にする通常の
  supersede 手順に従う。いずれも単独 revert できる。

- **依存**: `FLW-TSK-012` の実測開始前に裁定が必要。裁定前に実測すると、測定条件が
  後から動いたときに全 trial を取り直すことになる（3platform × 3条件 × 3task × 10 trial）。

- **予備判定（推薦）**: **accept 推奨（提案1・2・4 を先行、提案3 は実測後に再裁定）**。
  測定条件の未定義は「実装の良し悪し」と「測り方の選択」を分離できない状態であり、
  M0 の目的（write 機能へ進む前に dispatcher の価値を実証する）を成立させない。
  閾値を先に動かすと「通るように測った」疑いが残るため、条件を固定 → 実測 → 必要なら
  閾値を裁定、の順を推す。
