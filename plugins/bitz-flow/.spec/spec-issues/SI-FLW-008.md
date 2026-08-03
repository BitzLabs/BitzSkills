---
id: SI-FLW-008
raised_by: M0 eval 第2ラウンド実測（FLW-TSK-012、2026-08-03）
target: antigravity だけが Mandatory entry protocol を守り切れず、v2 条件で生 git へ迂回する
proposed_change_type: modify
status: open
---
- **目的**: M0 eval 第2ラウンドで3 platform × 90 trial を実測したところ、
  **同一の v2 SKILL.md にもかかわらず antigravity だけが入口遵守を達成できなかった**。

  | 指標 | 閾値 | claude-code | codex-cli | antigravity |
  |---|---|---|---|---|
  | Dispatcher Invocation Rate | 95%以上 | 100% ✅ | 100% ✅ | **83.3%** ❌ |
  | SFCR | 90%以上 | 100% ✅ | 100% ✅ | **80.0%** ❌ |
  | 必須 field 保持 | 100% | 100% ✅ | 100% ✅ | **83.3%** ❌ |
  | raw fallback | 0件 | 0件 ✅ | 0件 ✅ | **5件** ❌ |

  v2 条件 30 trial のうち **5 件が生 git で開始**した（`first_git_action=raw-git`）。
  raw log で確認した最悪例（`v2-skill/diff-summary#6`）は、スキルを読んだうえで

  ```
  git diff --stat --summary HEAD~1 HEAD
  git log -2 --oneline
  git show --stat --summary HEAD
  git show --stat --summary HEAD > stats.txt   ← 状態変更
  write_to_file                                 ← 状態変更
  ```

  と、生 git を4回叩いたうえでファイル書き込みまで行っている。read-only の M0 で
  `FLW-CON-001`（状態を変更しない）に抵触する振る舞いである。

  `FLW-NFR-001` は「platform 別 90% 未満を全体平均で相殺しない」と定めるため、
  agy 単独の未達がそのまま M0 出口を塞ぐ。`FLW-DSN-010` は SFCR 未達時に
  「文章を長くするのではなく description・入口数・command 命名・result の next action を
  改善する」と定めており、本 issue はその適用対象である。

  なお第1ラウンドの agy 全滅（`first_git_action=none` 90件）は harness 側の
  `--sandbox` 指定ミスが原因で、本ラウンドで解消済み。今回の未達は**実際の振る舞い**である。

- **提案する修正**: いずれも SKILL.md の増量ではなく構造で解く。
  1. **description の trigger を platform 差に耐える形へ**。`FLW-DSN-010` は
     「git / gh / branch / commit / diff …の操作前に必ず発動」を要求するが、agy は
     スキルを読んだ後で生 git を選んでいる。発動はしているので description ではなく
     **本文冒頭の拘束力**が効いていない可能性が高い。Mandatory entry protocol を
     本文の最初の行に置き、禁止事項を「してはならない」形の単文へ寄せる。
  2. **`NEXT` を使わせる導線を強める**。`#6` は `git diff --stat --summary HEAD~1 HEAD` と
     いう「前のコミットとの比較」を自力で組み立てている。`repo inspect` → `git.diff-summary`
     の `NEXT`（`base` 引数つき）を提示済みなので、**`NEXT` を無視した場合の扱い**を
     本文で明示する（`NEXT` があるならそれを使う）。
  3. **agy 固有の逸脱パターンを踏まえた文面調整**を検討する。ただし platform 別に
     文面を分岐させるのは `CORE-CON-004`（スキルの自己完結）と保守性を損なうため、
     **共通文面で効く言い回し**を探すことを優先し、分岐は最後の手段とする。
  4. 上記を適用して M0 を再実行し、agy の Invocation / SFCR / raw fallback を再測する。

- **対象ファイル**: `evals/flow-core/fixtures/v2-skill/SKILL.md`（v2 候補の本文）、
  `.spec/design/FLW-DSN-010.md`（スキル本文の順序規定を変える場合）、
  `evals/flow-core/m0-eval/README.md`（再実測結果の記録）。

- **確認観点**:
  - 重複: `SI-FLW-009` は byte 削減の測定条件、`SI-FLW-010` は harness の corpus 共有で
    対象が異なる。入口遵守そのものを扱う spec-issue は他に無い。
  - 既存要件との関係: `FLW-NFR-001`（Invocation / SFCR の閾値）と `FLW-CON-001`
    （read-only）の条文は変更しない。**達成手段の改善**であり EARS の意味を変えない。
    文面変更で閾値に届かない場合に限り、`FLW-NFR-001` の platform 別要件を
    見直すかどうかを別途裁定する（本 issue では提案しない）。
  - ガードレール: 数値を通すために prompt へ `flow.py` を書き足さない。prompt が
    dispatcher に言及すると Invocation Rate が「指示に従えたか」の測定になり、
    スキル設計を測れなくなる（`evals/flow-core/m0-eval/README.md` の固定条件）。
  - 検証: 3 platform で M0 を再実行し、agy の Invocation 95%以上・SFCR 90%以上・
    raw fallback 0件を確認する。claude / codex が既に満たしている水準を落とさないこと。
  - 軽量レーン適否: **不適**（M0 出口条件の合否を左右する）。

- **影響推定・ロールバック**: v2 fixture の SKILL.md 本文の変更に閉じるため、
  稼働中の v1 スキルと配布物には影響しない（`FLW-DSN-011` により v2 は Promotion Gate まで
  fixture 扱い）。単独 revert できる。再実測のコストは3 platform × 90 trial。

- **依存**: `FLW-TSK-012` の M0 出口判定を塞いでいる3件のうちの1つ。
  `SI-FLW-010`（harness の corpus 共有）を先に解消すると、再実測時に state_change の
  真偽を raw log と突き合わせずに判定できる。
