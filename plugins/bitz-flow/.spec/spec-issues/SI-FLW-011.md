---
id: SI-FLW-011
raised_by: M0 第3ラウンド codex-cli 実測（2026-08-06）
target: flow-core dispatcher の NEXT ヒントと snapshot 検証の契約
proposed_change_type: modify
status: open
---
- **目的**: `flow.py` の `NEXT` 行が提示する引数を指示どおりそのまま渡すと、同じ `flow.py` が
  `snapshot-mismatch` で拒否する。**dispatcher が自分の提示した引数を自分で拒否する**状態である。

  ```text
  $ flow.py --format compact git status
  OK   git.status snapshot=sha256:6d5b branch=main changed=8
  NEXT git.diff-summary base=HEAD snapshot=sha256:6d5b

  $ flow.py --format compact git diff-summary --base HEAD --snapshot sha256:6d5b
  STALE git.diff-summary cause=snapshot-mismatch stage=validate
  （exit 6）
  ```

  原因は **snapshot digest が operation ごとに異なる**ことである。同一 repo・同一時点でも
  次のように別の値になる。

  | operation | snapshot |
  |---|---|
  | `repo inspect` | `sha256:7545` |
  | `git status` | `sha256:5ec3` |
  | `git diff-summary --base HEAD` | `sha256:8f18` |

  ところが compact 出力では、どの operation でも同じ `snapshot=` ラベルで表示され、
  `NEXT` は**直前 operation の値をそのまま次の operation へ引き渡す**。エージェントは
  これをリポジトリ状態のトークンと解釈するため、`NEXT` に従うほど失敗する。

  `digest_matches()`（`flowlib/result.py`）は短縮形を許容する実装であり、短縮そのものは
  原因ではない。渡している値が**そもそも別 operation の digest** である点が原因である。

- **顕在化の経緯**: `SI-FLW-008` の裁定で v2 SKILL.md へ「**`NEXT` が示した操作と引数は、
  そのまま渡す**」を明記した。これにより codex-cli が `NEXT` へ忠実に従うようになり、
  潜在していた本欠陥が systematically に露出した。M0 第3ラウンドの実測では
  **v2 条件 30 trial 中 10 trial**（`diff-summary` 8 / `dirty-status` 2）が exit 6 を受けて
  `--snapshot` を外して再実行し、`self_retried` として減点された。結果として codex-cli の
  SFCR は第2ラウンドの **100% から 53.3%** へ後退し、`FLW-NFR-001` の platform 別 90% 要件を
  満たさない。第2ラウンドで顕在化しなかったのは、当時のエージェントが `NEXT` の引数を
  そのまま使っていなかったためである。

  すなわち **agy の入口遵守を改善した修正が、codex では後退を招いた**。SKILL.md の指示は
  正しく、拒否しているのは dispatcher 側である。エージェントの非遵守ではない。

- **提案する修正**: 次のいずれかを裁定する。いずれも公開契約（`FLW-DSN-005` の診断 cause、
  `flow-core/references/output-contract.md` の result 契約）に触れるため、エージェントが
  独断で決めてよい事項ではない。

  1. **NEXT に snapshot を載せない**（最小変更）。`NEXT` は operation と比較元・path だけを示し、
     snapshot は載せない。楽観ロックを使いたい呼び出し側は、対象 operation を一度読んでから
     その operation 自身の snapshot を渡す。`SI-FLW-008` の「そのまま渡す」規範と矛盾しなくなる。
  2. **snapshot を operation 横断の repo 状態 digest に統一する**。全 operation が同じ入力
     （worktree + index + HEAD）から同一 digest を導出し、`NEXT` の引き渡しを正当化する。
     ただし operation ごとに観測範囲が異なるため、変更検出の粒度が落ちる副作用がある。
  3. **NEXT の snapshot を別名にする**（例 `observed-at=`）。次操作へ渡す値ではなく、
     直前結果の同一性を示す情報であることを表記で分離する。呼び出し側の混同は減るが、
     「そのまま渡す」規範との衝突は残る。

  併せて、`STALE` / `snapshot-mismatch` の `NEXT` が `git.diff-summary`（引数なし）を示す点も
  見直す。現状は「snapshot を外して再実行せよ」という回復手順が暗黙であり、実測でも
  エージェントは正しく回復できているが、回復経路が契約として明文化されていない。

- **対象ファイル**:
  - `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py`（`NEXT` 生成と snapshot 検証）
  - `plugins/bitz-flow/skills/flow-core/scripts/flowlib/result.py`（`digest_matches` / cause 語彙）
  - `plugins/bitz-flow/skills/flow-core/references/output-contract.md`（snapshot の意味の定義）
  - `plugins/bitz-flow/.spec/design/FLW-DSN-005.md`（診断 cause と result 契約）
  - `evals/flow-core/fixtures/v2-skill/SKILL.md`（案1採用時は `NEXT` の例を修正）
  - `tests/test_flow_contract.py`（`NEXT` が示した引数をそのまま渡すと成功することの機械検査）

- **確認観点**:
  - `NEXT` が示した引数をそのまま渡した場合に、`snapshot-mismatch` が発生しないこと
    （回帰テストで固定する。これが本 issue の受け入れ条件）
  - 楽観ロックとしての snapshot 本来の機能（他者が repo を変更したら検出する）が失われないこと
  - 変更後に M0 eval を再実測し、codex-cli の SFCR が 90% 以上へ回復すること
  - `SI-FLW-008` の「`NEXT` の引数はそのまま渡す」規範と矛盾しないこと

- **影響推定・ロールバック**: v2 は Promotion Gate 前の prerelease であり（`FLW-DSN-011`）、
  安定版入口として案内していないため利用者影響はない。M0 の read-only operation のみが対象で、
  変更は `flowlib/cli.py` の `NEXT` 生成箇所に局所化できる（案1の場合）。
  ロールバック単位は本 issue に対応する PR 1件。

- **依存**: `SI-FLW-008`（本欠陥を顕在化させた裁定）。`FLW-NFR-001`（platform 別 SFCR 90%）の
  達成可否に直結するため、**M0 出口判定より前に裁定が必要**である。
