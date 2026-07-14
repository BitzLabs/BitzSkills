---
id: SI-SDD-003
raised_by: 2026-07-14 SI-CORE-021 開発の振り返り（語彙外値が approved 後に spec_inspect FAIL）
target: spec_scaffold.py の frontmatter 語彙検証（verification_method/domain/DSN status）
proposed_change_type: fix
status: accepted
---
- **目的**: `spec_scaffold.py` が frontmatter の統制語彙を生成時に検証しないため、語彙外の値が
  そのまま雛形に入り、**人間が approved 化した後**に `spec_inspect.py` が初めて FAIL する。
  誤りを早期（生成時）に fail させ、承認後の手戻りを防ぐ。
- **背景（実事例）**: 2026-07-14 の SI-CORE-021 開発で、要件を `--verification-method inspection`／`test`
  で生成した。これらは `VMETHODS`（`pbt`/`example-test`/`benchmark`/`sast`/`dep-audit`/`load-test`/`manual-check`）
  の語彙外だが scaffold は無検証で通過。6要件を approved 化した後に spec_inspect が7件 FAIL し、
  `manual-check`/`example-test` へ事後修正した。**②統合**: 設計ノート DSN-001 も `status: design`（`STATUSES` 語彙外）で
  FAIL した。DSN には scaffold サブコマンドが無く手書きしたため。いずれも「frontmatter が生成/手書き時点で無検証」という同根の問題。
- **提案する修正（人間が取捨選択）**:
  1. **【主提案】`spec_scaffold.py` に生成時語彙検証を追加**: `--verification-method` を `VMETHODS`、
     `--domain` を当該ワークスペースの `requirements/domains.md` の語彙、要件 status を `STATUSES` に照合し、
     語彙外なら**非ゼロで即 fail**（雛形を生成しない）。語彙は spec_inspect と単一定義を共有（重複定義しない）。
  2. **設計ノート（DSN）scaffold の新設**: `spec_scaffold.py <ws> design --prefix ...-DSN` を追加し、
     `status` に妥当な既定値（例 `active`）と検証を与える。手書き起因の frontmatter 誤りを構造的に防ぐ。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py`、
  語彙定義の共有元（`spec_inspect.py` の `VMETHODS`/`STATUSES` を import 可能な形に切り出す等）、
  必要なら sdd-core/SKILL.md の起票手順の追記。テスト先行（tests/）。
- **確認観点**:
  - 語彙外の `--verification-method`/`--domain`/status で **exit≠0・雛形非生成** になること
  - 正常な語彙では従来どおり生成できること（後方互換）
  - 語彙定義が spec_inspect と scaffold で二重管理にならないこと（単一の正）
  - DSN 生成物が spec_inspect PASS の書式互換であること
- **影響推定・ロールバック**: 検証の追加（生成の厳格化）。既存の正しい呼び出しには非破壊。単独 revert 可能。
- **依存**: なし（CORE-FR-004 の spec_scaffold 実装を前提に拡張）。
