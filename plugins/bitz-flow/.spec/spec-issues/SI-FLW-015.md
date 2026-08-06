---
id: SI-FLW-015
raised_by: M0 第7ラウンド claude-code 実測（2026-08-06）
target: flow-core dispatcher の truncation / cursor 契約
proposed_change_type: modify
status: open
---
- **目的**: `TRUNCATED` 行は `cursor=<snapshot>#<shown>` を提示するが、**その値を受け取る引数が
  存在しない**。エージェントは提示された値を使おうとして `INVALID_INPUT`（exit 2）で弾かれる。

  第7ラウンドの `claude-code / v2-skill / diff-summary#6`（large）の実例。

  ```text
  flow.py git diff-summary --base HEAD
    → OK git.diff-summary snapshot=sha256:1ec4 base=HEAD files=122 ...
      TRUNCATED shown=50 total=122 cursor=sha256:1ec4#50

  flow.py git diff-summary --base HEAD --limit 122 --cursor sha256:1ec4#50
    → INVALID_INPUT flow.invalid-input stage=validate（exit 2）

  flow.py git diff-summary --base HEAD --limit 122
    → OK（--cursor を外して成功）
  ```

  `cli.py` の引数定義に `--cursor` は無い（`--repo` / `--format` / `--timeout-seconds` /
  `--base` / `--limit` / `--snapshot` / `--apply` / `--confirm` / `--approval-ref` のみ）。
  `cursor` は `result.py` の `paginate()` が生成して出力するだけで、**入力経路が無い**。

- **`SI-FLW-011` と同じ構図である**: dispatcher が値を提示しているのに、その値を受け取る口が
  無い。`SI-FLW-011` は「`NEXT` が提示した snapshot を dispatcher 自身が拒否する」ものだったが、
  本件は「`TRUNCATED` が提示した cursor を渡す引数がそもそも無い」。いずれも
  **出力が入力契約と噛み合っていない**。

  今回の trial は `--cursor` を外して再実行し成功したため `self_retried` として減点されたが、
  SFCR は 96.7% で閾値内に収まった。ただし放置すれば同種の失敗が再発する。

- **設計上の位置づけを先に確定する必要がある**: `cursor` が何のために公開されているのかが
  現状の契約から読み取れない。次のどちらかである。

  1. **ページングの継続位置を表す入力値**（＝ `--cursor` を受け付けるべき）
  2. **打ち切り位置の同一性を示す出力専用の情報**（＝入力ではない）

  現在の実装は 2 の形（`snapshot#shown` を組み立てて出すだけ）だが、`cursor` という語と
  `shown` / `total` と並ぶ提示のされ方は 1 を強く示唆する。エージェントが 1 と解釈するのは
  自然であり、実測でもそう解釈された。

- **提案する修正**: 次のいずれかを裁定する。

  1. **`--cursor` を受け付ける**（機能追加）。`snapshot` 部を照合して `STALE` 判定に使い、
     `#<offset>` から続きを返す。ページングの意味論が完成し、`--limit` を大きくして
     全件取り直す現在の回避策より効率的になる。ただし M0 の scope 拡大にあたる
  2. **`cursor` を出力から落とす**（最小変更）。継続位置は `--limit` の指定で足りており、
     `TRUNCATED shown=… total=…` だけで「全件ではない」ことは伝わる。**受け取れない値を
     見せない**という点で `SI-FLW-013`（選択肢を見せなければ選べない）と同じ方針
  3. **名前を変えて出力専用であることを示す**（例 `at=`）。混同は減るが、
     「続きを取る手段」を求めるエージェントの動機自体は残る

  案2が M0 の scope に収まり、`SI-FLW-011` / `SI-FLW-013` で採った方針
  （**受け取れない・使わせない値は見せない**）とも一貫する。案1は M1 以降で
  ページング要求が実際に生じたときに改めて検討すればよい。

- **対象ファイル**:
  - `plugins/bitz-flow/skills/flow-core/scripts/flowlib/result.py`（`paginate` / compact 描画）
  - `plugins/bitz-flow/skills/flow-core/references/output-contract.md`（truncation 行の定義）
  - `evals/flow-core/fixtures/v2-skill/SKILL.md`（`TRUNCATED` の読み方）
  - 案1を採る場合のみ `plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py`
  - `tests/test_flow_contract.py`（`test_truncation_is_visible_and_snapshot_bound` が
    `cursor` の snapshot 拘束を検査しているため、案2なら要更新）

- **確認観点**:
  - 修正後、`TRUNCATED` を見たエージェントが `INVALID_INPUT` を受け取らないこと
  - 打ち切りが**可視である**という性質を失わないこと（`silent_truncation` は現在 3 platform
    とも 0 件であり、これを悪化させない）
  - 案2を採る場合、`cursor` が担っていた「打ち切り位置の snapshot 拘束」を失っても
    `TRUNCATED` + `snapshot` で同じ情報が読み取れることを確認する

- **影響推定・ロールバック**: v2 は Promotion Gate 前の prerelease であり（`FLW-DSN-011`）、
  安定版入口として案内していないため利用者影響はない。案2なら変更は `result.py` の
  描画と `paginate` の戻り値に局所化できる。ロールバック単位は本 issue に対応する PR 1件。

- **依存**: `SI-FLW-011`（出力が入力契約と噛み合っていない同種の欠陥。裁定方針を踏襲する）。
  `SI-FLW-013`（受け取れない・使わせない値は見せないという方針）。
