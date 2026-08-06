---
id: SI-FLW-013
raised_by: M0 第3ラウンド antigravity 実測の再分析（2026-08-06）
target: evals/flow-core/fixtures/v2-skill/SKILL.md の出力形式の誘導（compact 既定）
proposed_change_type: modify
status: open
---
- **目的**: antigravity だけが v2 SKILL.md の compact 誘導に従わず、compact で取得した直後に
  **同じ operation を `--format json` で取り直す**。この再取得だけで `dirty-status` の
  byte 削減 median が閾値を割る。

  第3ラウンド（`*-r3`）の v2 `dirty-status` 10 trial の内訳は次のとおりである。

  | 挙動 | 件数 | 削減率 |
  |---|---:|---:|
  | compact のみ | 3 | +44.8〜58.4% |
  | **`--format json` で再取得** | **4** | **−406〜−428%** |
  | `--limit` で全件取得（large corpus） | 3 | +37.0% |

  再取得の実例（raw log）。compact で取得済みの `git status` を JSON で叩き直している。

  ```text
  flow.py git status                      → 239 B
  flow.py --format json git status        → 3004 B（約12.6倍）
  ```

  `_task_output` は最後の該当実行を採点対象にするため、再取得した JSON が採点値になる。

- **閾値ではなく挙動が原因である**: `--format json` の再取得だけを解消した場合の median を
  実データで再計算すると **44.8%** となり、閾値 40% を**超える**。

  ```text
  +37.0% +37.0% +37.0% +44.8% +44.8% +44.8% +58.4% +58.4% +58.4% +58.4%
                              ↑ median = 44.8%
  ```

  すなわち `--limit` による全件取得（打ち切りを見て残りを取りに行く**正当な**挙動。
  `silent_truncation` は 0 件で打ち切りは可視化されている）は、単独では閾値を割らない。
  **`FLW-NFR-008` の閾値 40% を見直す必要はない。**

  当初「閾値が正当なページングを減点している」と読んだのは、`--format json` の影響を
  分離していない粗い分析であった。本 issue でこれを訂正する。

- **platform 差である**: 同一の v2 SKILL.md を読んでいるにもかかわらず、`--format json` を
  実際に実行したのは antigravity だけである。

  | platform | v2 trial 数 | `--format json` を実行した trial |
  |---|---:|---:|
  | claude-code（第6R） | 30 | **0** |
  | codex-cli（第6R） | 30 | **0** |
  | antigravity（第3R） | 30 | **4**（すべて `dirty-status`） |

  現行の v2 SKILL.md は次のように書いており、文面としては既に compact を指示している。

  ```text
  - **compact のまま読む。** 判断に必要な field はすべて compact に出る。
    `--format json` は result を別のプログラムへ渡すときだけ使う。同じ判定を返すが
    桁違いに長く、文脈を無駄に消費する。自分が読んで判断するなら compact を使う。
  ```

  第1ラウンドで「機械処理には `--format json`」という誘導を上記へ是正済みだが、
  **agy にだけ効いていない**。`SI-FLW-008`（agy だけが入口拘束に従わない）と同じ構図であり、
  agy は「読んでも拘束されない」傾向がある。

- **提案する修正**: `FLW-DSN-010`（SFCR 未達時は文章を長くするのではなく description・入口名・
  command 命名・result の next action を直す）に沿って、次のいずれかを裁定する。

  1. **`--format json` の記述を SKILL.md 本文から落とす**（最小変更）。JSON が要る場面は
     M0 の read-only では存在しない（自分で読んで判断するため）。参照が要るなら
     `references/output-contract.md` 側にのみ残す。**選択肢を見せなければ選べない。**
  2. **禁止形の単文へ寄せる**。`SI-FLW-008` で入口拘束に効いた手法をそのまま適用し、
     「同じ operation を二度呼ばない」「`--format json` を使わない」を「してはならない」形で書く。
  3. **`--format json` に警告を出させる**（dispatcher 側の変更）。compact で取得済みの
     operation を JSON で叩き直したときに result の `warnings` へ載せる。ただし
     dispatcher は状態を持たないため実装コストが高く、M0 の read-only 契約にも合わない。

  案1と案2は併用できる。`SI-FLW-008` の裁定では「共通文面で効く言い回しを優先し、
  platform 別の文面分岐は最後の手段」と定めており、本件も同じ方針を踏襲する。

- **対象ファイル**:
  - `evals/flow-core/fixtures/v2-skill/SKILL.md`（出力形式の誘導）
  - 案3を採る場合のみ `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py`

- **確認観点**:
  - 修正後の再実測で antigravity の `--format json` 再取得が 0 件になること
  - `dirty-status` の byte 削減 median が 40% 以上へ回復すること
  - **claude-code / codex-cli の既達水準を落とさないこと**（両者は現状 0 件であり、
    文面変更で悪化させない）
  - `--limit` による全件取得は**引き続き許容する**。打ち切りを見て残りを取りに行くのは
    正当な判断であり、これを抑止する文面にしない

- **影響推定・ロールバック**: 変更は `evals/flow-core/fixtures/v2-skill/SKILL.md` に閉じ、
  稼働中の v1 と配布物へ影響しない（`FLW-DSN-011` により v2 は Promotion Gate まで fixture 扱い）。
  単独 revert できる。案3を採る場合のみ配布物へ及ぶ。

- **依存**: `SI-FLW-008`（agy が文面に拘束されない同種の論点。裁定方針を踏襲する）。
  `FLW-NFR-008`（byte 削減の閾値。**本 issue では変更しない**）。
  `FLW-DSN-010`（未達時の対処手段の規定）。
