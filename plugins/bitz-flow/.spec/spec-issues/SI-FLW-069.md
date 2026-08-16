---
id: SI-FLW-069
raised_by: FLW-REV-018（RSK-201 / RSK-207 / RSK-204 / OPS-302）
target: 実行環境ガードの覆域と、承認強度の無言降格
proposed_change_type: modify
status: accepted
---
- **目的**: 2026-08-15 の harness 事故と同じ操作種別が**今も止まらない**状態を解消する。
  `SI-FLW-063`（PR #289）が閉じたのは「allow が禁止操作を覆う」ことであって
  「禁止操作を止める」ことではない。

- **発見した事実**（独立レビュア2名が別経路で実測）:
  1. **`force_ask` の迂回**（`RSK-201`）— allow 分岐が `ASK_PATTERNS` より先に評価されるため、
     `--repo /home/hide/.claude/skills` が **`force_ask` を迂回して allow になる**。
     `Cwd` が無検証で相対 script path の実体が変わり得る点、`RunPersistent` /
     `WaitMsBeforeAsync` が無検査である点も残る。
  2. **ガードの覆域が事故の操作種別を含まない**（`RSK-207`）—
     単独の `CommandLine` としての `git commit` / `git push` / `git branch -D` /
     `chmod 000 scripts/agy_guard.py` はいずれも `{}`（deny でない）を返す。
     `.agents/hooks.json` の matcher は `run_command` のみで、
     **ファイル編集系ツールは1つもフックされていない**。
  3. **承認強度の無言降格**（`RSK-204`）— `signature_mode_available` が registry の
     `chmod 644` / 削除 / 空化のいずれでも例外を握り潰して `False` を返し、
     `apply()` が**警告も evidence も無く** `plan-digest` へ降格する。
     高保証配備の承認強度が、common-dir へ書ける主体によって無言で外せる。
  4. **裁定スコープの allow に失効・撤去・登録の機構が無い**（`OPS-302`）—
     confirmation のための例外が恒久化している。

- **提案する修正**:
  - DENY / ASK / ALLOW の評価順を「DENY → ASK → ALLOW」に固定し、テストで順序を拘束する
  - 禁止操作を allow の有無と独立に deny する（`{}` を返さない）
  - ファイル編集系ツールを matcher に加える
  - `signature_mode_available` が registry の**存在を期待する配備**で降格するときは
    `warnings` と `evidence` に必ず残す（無言降格を禁止する）
  - 裁定スコープ allow に失効期限と撤去手順を持たせる

- **対象ファイル**: `scripts/agy_guard.py`、`tests/test_agy_guard.py`、`.agents/hooks.json`、
  `flowlib/worktree_capability.py`、`flowlib/worktree_runtime.py`

- **確認観点**: 事故で実際に使われた操作種別（コミット・ガード編集）を陽性対照に置く。
  正規経路が通ることを陰性対照で守る（PR #289 の教訓 — 推測で絞ると正規経路が落ちる）。

- **影響推定・ロールバック**: ガードを厳しくするため、正規の confirmation 経路が
  落ちないことを実走で確認してから入れる。

- **依存**: confirmation を実走させる限り、出荷面の縮退では緩和されない実行環境の問題。
