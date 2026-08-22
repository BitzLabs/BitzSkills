---
id: SI-FLW-077
raised_by: FLW-REV-021準備レビュー（DIN-201）
target: approval-mode 宣言の完全性と plan/apply 間の束縛
proposed_change_type: modify
status: accepted
github_issue: https://github.com/BitzLabs/BitzSkills/issues/257
---
- **目的**: 承認強度を決める `approval-mode.json` を、差替え可能な任意のテキストとして扱わず、配備意図と plan/apply の両方に束縛する。

- **発見した事実**:
  1. `read_approval_mode_declaration()` は `Path.exists()` と `read_text()` だけで読んでおり、symlink を通常の宣言と同じように通す。通常ファイル・所有者・権限・Git追跡の確認が無い。
  2. plan の snapshot / operation ID は宣言の内容 digest を含まない。plan 作成後に宣言を `signed-capability` から `plan-digest` へ差し替えても、apply は変更後の弱いモードで実行できる。
  3. signed-capability を意図した配備の registry 削除は既に停止するが、宣言自体の置換を検出できないため、同じ fail-closed 境界が閉じていない。

- **提案する修正**:
  - 宣言を Git追跡された owner-expected regular file として読み、symlink・非通常ファイル・未追跡・不正 mode を `BLOCKED` にする。
  - plan 時に宣言の canonical content digest と repository binding を snapshot / capability context に含め、apply 直前と各 mutation 直前に再照合する。
  - 宣言が無い配備は現行どおり `plan-digest` とする。ただし plan 後の新規作成・削除・内容変更は `STALE` または `BLOCKED` とし、副作用を起こさない。

- **対象ファイル**: `plugins/bitz-flow/.spec/requirements/FLW-NFR-011.md`、`plugins/bitz-flow/.spec/design/FLW-DSN-016.md`、`plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py`、`plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py`、`tests/test_flow_m2_runtime.py`、関連schema/fixture。

- **確認観点**: symlink・directory・未追跡 file・plan後の内容変更・削除・新規作成の各陽性対照で、apply が副作用なしに停止すること。追跡済み不変宣言の signed-capability / plan-digest は回帰なく利用できること。

- **影響推定・ロールバック**: 承認 capability と plan snapshot の契約に触れるため、軽量レーンではなく通常の要件改訂と Design Gate を要する。未公開 M2 operation に限る内部契約変更であり、裁定前は現行の mode 判定以外を変更しない。

- **依存**: `FLW-NFR-011`、`FLW-DSN-016` §4、`SI-FLW-073`。review finding `DIN-201`。

- **予備判定（推薦）**: **accept を推薦**。既存の signed-capability 降格防止を、宣言ファイル自身の差替えへ一貫して拡張する。ただし capability context / schema への影響があるため、人間の要件承認を経てから実装する。

- **裁定**: 2026-08-22 ユーザーが採用し、設計へ進めることを指示した。
