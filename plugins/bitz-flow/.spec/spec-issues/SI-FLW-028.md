---
id: SI-FLW-028
raised_by: 第11ラウンド実測（agy 21 trial 中 18 で self-retry。2026-08-08）
target: plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py の --base help、v2 SKILL.md の引数記述と入口規定
proposed_change_type: modify
status: open
---
- **目的**: 第11ラウンドで antigravity の SFCR が **71%（45/63）** となり、M0 出口条件
  （90%以上）に対する**唯一の未達**になった。失敗は `git.diff-summary` に 100% 集中しており
  （`repo.inspect` / `git.status` の self-retry は 0）、機序は
  **`--base` の意味論が記述から一意に読めないこと**である。
  現行の記述は既定値だけを述べ、**比較の左辺（作業ツリー）を書いていない**。

  | 記述箇所 | 現行の文言 |
  |---|---|
  | `cli.py` の `--base` help | 「git diff-summary の比較元（既定 HEAD。index と比較するなら `--base index`）」 |
  | v2 SKILL.md（`## 2` 末尾） | 「`diff-summary` の比較元は `--base <ref>`、既定は `HEAD`」 |

  「比較元」だけを示すと `git diff A B` 型の ref..ref 比較と読める。task prompt
  「直前のコミットからの変更量を教えてください」（`prompts/diff-summary.md`）を
  ref..ref と解釈すれば `--base HEAD~1` は筋の通った選択になる。
  corpus はコミット1個なので `HEAD~1` は実在せず `INVALID_INPUT cause=invalid-ref` を返す
  （**dispatcher の挙動は正しい**。手で再現済み）。

- **観測（第11ラウンド。v2-skill / diff-summary の flow.py 呼出順序を raw log から復元）**:

  | | `git status` を先に呼んだ | 最初の diff-summary 呼出 | self-retry |
  |---|---:|---|---:|
  | codex-cli | **21/21** | `--base HEAD`（21/21） | **0/21** |
  | antigravity | **1/21** | `--help` 15 / `--base HEAD~1` 5 | **18/21** |

  - **13/21 は `--help` を読んだ上で `HEAD~1` を選んでいる**（最頻の系列は
    `--help` → `--base HEAD~1` → `--base HEAD` が 7 件）。
    すなわち**既定値を知らなかったのではなく、比較の向きを取り違えている**。
    help に既定値を書き足すだけでは直らない。
  - codex が 100% なのは引数を自力で当てたからではない。`git.status` の成功 result が返す
    `NEXT git.diff-summary base=HEAD`（`cli.py:214`）をそのまま使っている。
    **正解の引数は NEXT 経由でしか流通しておらず**、status を経由しない入り方をすると
    記述だけが頼りになる。agy は 20/21 がその入り方だった。
  - 危険事象は 0 件（raw_fallback 0 / state_change 0 / secret_output 0 / silent_truncation 0、
    母数 63・95% 上側限界 4.64%）。Decision Parity は 100%、byte 削減は
    `diff-summary` 88.8% / `dirty-status` 46.4% でいずれも閾値を満たす。
    **未達は本件ただ1点**である。

- **提案する修正**:

  1. **`--base` の意味論を記述する**（推奨・本命）。help と v2 SKILL.md の両方を
     「**作業ツリーを `<base>` と比較する。既定 `HEAD` ＝ 直前のコミット以降の変更**」の形へ
     書き換える。`flow.py` の挙動・result・schema を一切変えないため配布物へのリスクが最小で、
     単独 revert できる。13/21 の失敗機序に直接当たる。
  2. **入口を拘束する**（保険）。v2 SKILL.md の入口規定へ「読み取りは `git status` /
     `repo inspect` から始める」を加え、NEXT 連鎖が必ず配られるようにする
     （`SI-FLW-008` の入口拘束の延長）。案1 が効けば NEXT 無しでも自立するため、
     **案1 の代替ではなく併用**を想定する。
  3. **棄却する案 — 実在しない ref を既定へフォールバックする**。SFCR は即座に改善するが、
     `FLW-DSN-010` の決定論的安全判定（推測しない）に反する。M1 以降の write 系へ同じ寛容さが
     波及すると事故になるため採らない。**棄却の理由をここに残す**。

- **対象ファイル**:
  - `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py`（`--base` の help 文字列）
  - `evals/flow-core/fixtures/v2-skill/SKILL.md`（引数の記述と、案2 を採るなら入口規定）
  - `plugins/bitz-flow/skills/flow-core/references/output-contract.md`（`NEXT` の位置づけ）

- **確認観点**:
  - 第12ラウンドで antigravity の v2 `diff-summary` の self-retry が減ること
    （SFCR 90% 以上が判定基準。母数は `TRIALS_PER_CELL` に従う）
  - codex-cli の SFCR 100% と Decision Parity 100% が退行しないこと
  - `--base HEAD~1` を渡したときの `INVALID_INPUT cause=invalid-ref` は**維持**されること
    （案3 を採らないことの確認。`tests/test_flow_contract.py`）
  - v2 fixture と `plugins/bitz-flow/skills/flow-core/` の記述が同じ文言であること
    （fixture 側だけ直すと配布物が取り残される）

- **影響推定・ロールバック**: 案1・案2 とも記述の変更に閉じ、`flow.py` の挙動・result・
  schema を変えない。プラグイン version の bump は不要。単独 revert できる。
  ただし**再測定が要る**ため、残予算（`decision-2026-08-08-m0-budget-overrun.md` により
  第11ラウンド実測で消費済み＝残 0）の超過として再提示が必要になる。

- **依存**: `SI-FLW-020`（result code ベース採点。本件は agy の失敗が初めて可視化された
  ラウンドの所見であり、第10ラウンド以前の agy SFCR とは直接比較できない）。
  `SI-FLW-008`（入口拘束。案2 はその延長）。`SI-FLW-026`（所要母数）。
  `SI-FLW-029`（同じ失敗の裏側 — 契約内の復帰経路が無い件）。
  `FLW-DSN-010`（決定論的安全判定。案3 を棄却する根拠）。
  実測記録は `evals/flow-core/m0-eval/trials-antigravity-2026-08-08-r11.jsonl`。
