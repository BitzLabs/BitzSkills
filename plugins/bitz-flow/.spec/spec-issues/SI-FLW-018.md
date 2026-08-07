---
id: SI-FLW-018
raised_by: M0 第10ラウンド claude-code 実測（2026-08-07）
target: plugins/bitz-flow/skills/flow-core/SKILL.md の description（発動条件）
proposed_change_type: modify
status: open
---
- **目的**: claude-code が「Skill を使う」と**宣言しながら Skill tool を呼ばず**、
  そのまま生 git を実行する。SKILL.md 本文が一度も読み込まれないため、
  入口拘束（`SI-FLW-008`）もパス解決手順（`SI-FLW-016`）も一切効かない。
  `FLW-DSN-014` の M0 出口条件「raw fallback 0 件」を直接割る。

  第10ラウンドの実例（`claude-code / v2-skill / diff-summary#2`）。

  ```text
  thinking
  text     「Skill を使って git の変更差分を確認します。」   ← 宣言のみ
  Bash     cd <repo> && git diff --stat HEAD && git diff --numstat HEAD   ← 生 git
  text     「直前のコミット(55b0747)からの変更…」            ← 生 git の結果で回答
  ```

  Skill tool の呼出は **1 度も無い**。`init` イベントでは `flow-core` が
  `skills` に列挙され `Skill` tool も利用可能であったため、**環境の不備ではない**。

- **本文の修正では届かない**: `SI-FLW-008` / `SI-FLW-013` / `SI-FLW-016` はいずれも
  SKILL.md 本文を読んだあとの挙動を正す修正であった。本件は**本文が読まれる前**に
  分岐しているため、本文へ何を書いても効果が無い。効き得るのは
  **frontmatter の `description`（発動条件そのもの）**だけである。

- **発生率と履歴**: claude-code の v2 trial を全ラウンドで数え直した。

  | ラウンド | v2 | gate bypass | うち生 git 直行 | raw_fallback |
  |---|---:|---:|---:|---:|
  | 第1R（08-03） | 30 | 1 | 0（`first=none`） | 0 |
  | 第2R | 30 | 0 | 0 | 0 |
  | 第6R | 30 | 1 | 0（`first=none`） | 0 |
  | 第7R | 30 | 0 | 0 | 0 |
  | 第8R（08-07） | 30 | 0 | 0 | 1（`SI-FLW-016`） |
  | **第10R** | 30 | **1** | **1** | **1** |

  **生 git 直行は第10ラウンドで初めて観測された**。claude の v2 trial 累計約 210 件で 1 件であり、
  **発生率は 1 件からは決められない**。第1R・第6R の bypass は「コマンドを1つも実行せず
  回答した」（`first=none`）別の事象で、生 git は実行していない。

  codex-cli は全ラウンドで bypass 0、antigravity は第2R の 5 件以降 0 である。
  **claude-code 固有の事象**とみてよい（`SI-FLW-016` と同じく、claude だけが
  ネイティブ機構でスキルを読み込む点が関係している可能性がある）。

- **これは正当な失敗である**: `SI-FLW-012` / `SI-FLW-014` / `SI-FLW-017` と違い、
  測定系の取り違えではない。エージェントは実際に生 git を実行して回答しており、
  `FLW-DSN-014` の危険事象として数えるのが正しい。

- **出口条件どうしの緊張**: `FLW-DSN-014` は Dispatcher Invocation Rate を **95% 以上**と
  しながら raw fallback を **0 件**と定める。30 trial では bypass 1 件が
  Invocation 96.7%（合格）でありながら raw fallback 1 件（不合格）になる。
  **bypass が生 git 経路を取る限り、raw fallback 0 件は実質的に Invocation 100% を要求する。**
  第1R・第6R が素通りしたのは bypass が `first=none` だったためにすぎない。
  この緊張を「意図した設計」とするか「閾値の不整合」とするかは裁定が要る。

- **提案する修正**: 次のいずれか、または併用を裁定する。

  1. **`description` を発動条件として鋭くする**（推奨）。現行 description は
     「Git / GitHub 操作の唯一の実行入口」から始まり長い。本件の trial が取り違えた
     `git diff --stat` は description に明示されている語であるにもかかわらず発動しなかった。
     **冒頭を「git / gh を実行する前に必ずこのスキルを開く」という発動命令に置き換える**ことで、
     description を「何ができるか」から「いつ開くか」へ寄せる（`FLW-DSN-010` に沿う）
  2. **発生率を先に確定させる**。累計 1 件では修正の効果を測れない。
     claude-code の v2 を **trial 数を増やして測り直し**、発生率の下限を得てから
     修正の要否を判断する。ただしセッション上限（第8R・第9Rで2度到達）があり
     大きな増加は現実的でない
  3. **`FLW-DSN-014` の出口条件を見直す**。raw fallback を「0 件」から
     「Invocation Rate の許容内に収まること」へ改める。
     **採らない方向で検討する** — 生 git 実行は M0 の中核的な禁止事項であり、
     数値を通すために基準を緩めるのは `SI-FLW-012` の裁定で自ら定めた方針に反する
  4. **本ラウンドを不合格のまま記録し、M0 出口判定を保留する**。
     原因も対策も未確定のまま出口を通さない、という選択

- **対象ファイル**:
  - `plugins/bitz-flow/skills/flow-core/SKILL.md`（frontmatter の `description`）
  - `evals/flow-core/fixtures/v2-skill/SKILL.md`（同 `description`。実測はこちらで行う）
  - 案3を採る場合のみ `plugins/bitz-flow/.spec/designs/FLW-DSN-014`

- **確認観点**:
  - 修正後の再実測で **gate bypass が 0 件**になること
  - **raw fallback が 0 件へ戻ること**（M0 出口条件）
  - description の変更で **v1 / no-skill 条件の baseline が動かない**こと
    （v2 fixture の description だけを変える）
  - codex-cli / antigravity の既達水準を落とさないこと（両者は bypass 0）
  - 累計 1 件の事象であり、**0 件が続いても「直った」とは言い切れない**ことを
    成果物へ明記すること

- **影響推定・ロールバック**: 案1は v2 fixture の frontmatter に閉じ、単独 revert できる。
  配布側 SKILL.md へ及ぼすのは v2 の Promotion Gate 時とする（`FLW-DSN-011`）。
  案3は設計文書の変更であり、M0 の合否基準そのものを動かすため影響が大きい。

- **依存**: `SI-FLW-008`（入口拘束。**本文側の対策であり本件には届かない**）。
  `SI-FLW-016`（claude だけがスキルの所在を知らされないという platform 差の先例）。
  `FLW-DSN-014`（M0 出口条件。案3を採る場合の変更対象）。
  `FLW-DSN-010`（文章を長くせず description・入口名・next action を直す方針）。
