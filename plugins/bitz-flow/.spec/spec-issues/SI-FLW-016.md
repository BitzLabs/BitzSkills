---
id: SI-FLW-016
raised_by: M0 第8ラウンド claude-code 実測（2026-08-07）
target: evals/flow-core/fixtures/v2-skill/SKILL.md のスクリプト参照表記と回復手順
proposed_change_type: modify
status: open
---
- **目的**: `flow.py` の配置場所を解決できなかったエージェントが、回復手段として
  **`find /`（ファイルシステム全体の検索）**を選び、タイムアウトの末に生 git へ退避する。
  `FLW-DSN-014` の M0 出口条件「raw fallback 0 件」を直接割る。

  第8ラウンドの実例（`claude-code / v2-skill`）。

  ```text
  # repo-inspect#5 — 生 git へ退避（raw_fallback）
  python3 skills/flow-core/flow.py status              ← 誤ったパスを推測（exit 2）
  find / -maxdepth 8 -path '*flow-core/flow.py'        ← 全体検索
  find / -iname 'flow.py'                              ← 120s タイムアウト
  git branch --show-current && git status -sb && ...   ← 生 git（raw_fallback）

  # diff-summary#7 — 自己再試行（self_retried）
  python3 "$(find / -path '*/flow-core/scripts/flow.py' | head -1)" git diff-summary --base HEAD
                                                       ← 2m タイムアウト
  ls .../.claude/skills/flow-core/scripts/             ← 場所を確認
  python3 .claude/skills/flow-core/scripts/flow.py git diff-summary --base HEAD   ← 成功
  ```

  正しいパスは `.claude/skills/flow-core/scripts/flow.py` である。解決できた trial は
  これを正しく組み立てている。

- **発生率と platform 差**: 確率的に発生する。

  | ラウンド | platform | v2 trial | `find /` を実行した trial | raw_fallback |
  |---|---|---:|---:|---:|
  | 第7R | claude-code | 30 | **0** | 0 |
  | 第8R | claude-code | 30 | **2** | **1** |
  | 第8R | codex-cli | 48 | 0 | 0 |
  | 第8R | antigravity | 30 | 0 | 0 |

  第8ラウンドで claude-code だけが未達となった原因はこの 2 trial であり、
  必須 field 保持 96.7%（1 件）と raw fallback 1 件はいずれもここに由来する。

- **これは正当な失敗である**: `SI-FLW-012` / `SI-FLW-014` と違い、測定系の取り違えではない。
  エージェントは実際に生 git を実行しており、`FLW-DSN-014` の危険事象として数えるのが正しい。
  **本 issue は採点規則ではなくスキル設計の問題として扱う。**

- **原因の所在**: v2 SKILL.md は `<このスキル>/scripts/flow.py` という**プレースホルダ**で
  スクリプトを参照する（`CORE-CON-012` / `CORE-CON-013` が定める表記規約）。
  スキルはフォルダ単位で任意の場所へ配置されるため、この表記自体は正しい。
  問題は次の 2 点である。

  1. **プレースホルダの解決手順が本文に無い。** 「自分がいまどこに配置されているか」を
     どう確かめるかが書かれておらず、解決はエージェントの推測に委ねられている
  2. **推測を外したときの回復手段が定義されていない。** 結果として `find /` という
     最悪の手段が選ばれる。`find /` は環境によっては数分かかり、タイムアウト後の
     退避先が生 git になる

- **提案する修正**: `FLW-DSN-010`（文章を長くするのではなく description・入口名・
  next action を直す）に沿って、次のいずれか、または併用を裁定する。

  1. **絶対パスの確立手順を1行で示す**（推奨）。冒頭の Mandatory entry protocol に
     「まず自分の配置場所を確定してから実行する」ことと、その具体手順（例: SKILL.md が
     置かれたディレクトリからの相対で `scripts/flow.py` を解決する）を置く。
     解決を推測に委ねない
  2. **`find /` を禁止形の単文で止める**（`SI-FLW-008` / `SI-FLW-013` で効いた手法）。
     「スクリプトの場所を探すために `find /` を実行してはならない」を明記する。
     ただし禁止だけでは代替手段を与えないため、案1と併用する
  3. **配置場所を実行時に自己申告させる**（dispatcher 側の変更）。`flow.py` が
     `UNSUPPORTED` / `INVALID_INPUT` を返すときに自分の絶対パスを result へ載せる。
     ただし「そもそも起動できなかった」場合には効かないため、本件の主因には届かない

  案1＋案2の併用が、`SI-FLW-008`（入口拘束）・`SI-FLW-013`（選択肢を見せない）で
  実測により効果が確認された手法と同じ形になる。

- **対象ファイル**:
  - `evals/flow-core/fixtures/v2-skill/SKILL.md`（Mandatory entry protocol と参照表記）
  - 案3を採る場合のみ `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py`

- **確認観点**:
  - 修正後の再実測で `find /` の実行が 0 件になること
  - **raw fallback が 0 件へ戻ること**（M0 出口条件）
  - codex-cli / antigravity の既達水準を落とさないこと（両者は現状 0 件）
  - `CORE-CON-012` / `CORE-CON-013` のスクリプト参照表記規約に反しないこと
    （プレースホルダ表記そのものは維持する。解決手順を足すだけにとどめる）

- **影響推定・ロールバック**: 変更は `evals/flow-core/fixtures/v2-skill/SKILL.md` に閉じ、
  稼働中の v1 と配布物へ影響しない（`FLW-DSN-011` により v2 は Promotion Gate まで fixture 扱い）。
  単独 revert できる。案3を採る場合のみ配布物へ及ぶ。

- **依存**: `SI-FLW-008`（入口拘束を禁止形で強化した先例）。
  `SI-FLW-013`（選択肢を見せないことで挙動を変えた先例）。
  `CORE-CON-012` / `CORE-CON-013`（スクリプト呼び出しの表記規約。**本 issue では変更しない**）。
