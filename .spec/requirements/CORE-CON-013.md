---
id: CORE-CON-013
version: 1.0
status: verified
domain: tooling
priority: medium
origin: SI-CORE-038
verification_method: unit-test
derived_from: CORE-FR-011
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-013 ラッパーが公開するツール一覧と規約文書を一致させる

- **説明**: `scripts/spec` ラッパーが公開するサブコマンドの集合（`TOOLS`）と、それを説明する
  規約文書（`AGENTS.md` の定型手順節）の記述が、宣言と実体として一致していることを機械検証する。
  `SI-CORE-038` が求めた「決定した規約を AGENTS.md へ反映し、**宣言と実体を一致させる**」の
  実効化であり、`release_check.py` がフェーズ語彙マーカーで `PHASE_CODES` と散文リストの一致を
  検査しているのと同型。手作業で同期する限り、ツールを増減したときに文書だけが取り残される。

  あわせて、ラッパー経由で呼ぶツールと直接実行するツールの境界を規約文書に明記する。
  現状の境界は `TOOLS` の4つがラッパー経由で、`sdd_sync` / `docs_inspect` / `sdd_report` /
  `spec_verify` は直接実行である（`CORE-FR-011` の必須解決集合が sdd-core の4ツールであるため）。

- **受入基準 (EARS)**:
  - WHEN 規約文書がラッパーの公開サブコマンドを列挙する THEN 機械検証用マーカーを併記し、`scripts/spec` の `TOOLS` のキー集合と一致することを検査すること SHALL
  - WHEN 両者が一致しない THEN 差分（文書のみ・実体のみに現れるサブコマンド）を特定して非ゼロで報告すること SHALL
  - WHEN 規約文書が直接実行のツールを列挙する THEN ラッパー経由のツールと重複しないことを検査すること SHALL
  - WHEN `scripts/spec` が存在しないリポジトリで検査する THEN 当該検査をスキップし違反として報告しないこと SHALL
- **検証手段**: `tests/test_cli_contract.py` に追加して unit-test する（同ファイルが既に
  `scripts/` のスクリプト契約を扱っているため）。`scripts/spec` を import せずソースから
  `TOOLS` のキーを抽出し、`AGENTS.md` のマーカー付きリストと突き合わせる。
- **Revision History**:
  - 1.0 (2026-07-30) 初版（draft 起票）。`SI-CORE-038` 提案4 と
    `decision-2026-07-30-order7-scope.md` 裁定F から導出。
