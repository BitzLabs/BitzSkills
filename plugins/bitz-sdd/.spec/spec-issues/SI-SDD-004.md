---
id: SI-SDD-004
raised_by: 2026-07-14 SI-CORE-021 開発の振り返り（部分検収でマージ後 CI 回帰）
target: sdd-implement/sdd-test の検収規律：共有スクリプト変更時の全テストスイート実行
proposed_change_type: modify
status: open
---
- **目的**: 実装タスクの検収規律が「対象テスト＋部分実行」で足りると読める曖昧さがあり、
  共有スクリプト変更時に**全テストスイート未実行**で回帰を見逃す事故が起きた。検収の最小要件を明文化する。
- **背景（実事例）**: 2026-07-14 の SI-CORE-021 開発で、`scripts/release_check.py` に検査関数を追加した際、
  検収を「新規テストファイル＋実リポでの release_check 実行」で済ませ、**全 pytest スイートを回さなかった**。
  実リポには CLAUDE.md があるため新チェックは緑に見えたが、CLAUDE.md を持たない汎用 fixture の
  既存テスト `tests/test_release_check.py::test_release_check_pass` を落とし、**squash マージ済み PR の
  CI で初めて発覚**（事後に fix コミット＋回帰テストで復旧）。環境固有の前提（特定ファイルの実在）を
  暗黙に置くと、それを持たない fixture で回帰する。
- **提案する修正**:
  1. **`implementation-discipline.md` / `sdd-test` に検収規律を明記**: 共有スクリプト（`scripts/`・
     プラグイン同梱スクリプト）や広く参照される契約に触れる変更では、タスクを done にする前に
     **全テストスイート実行**（対象テストのみの部分実行で done としない）を必須とする。
  2. **環境固有前提の扱い**: 検査が特定ファイル（例 CLAUDE.md）の実在に依存する場合、不在は
     「違反」ではなく「スキップ」で扱う指針を明記（今回の fix はこの方針で解決した）。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-implement/references/implementation-discipline.md`、
  `plugins/bitz-sdd/skills/sdd-test/SKILL.md`（検収節）。ナラティブ規律の追記が中心。
- **確認観点**:
  - 「共有スクリプト変更時は全スイート実行」が検収規律として1箇所に明記されていること
  - 環境固有前提の不在＝スキップ指針が併記されていること
  - 過剰（毎回全リポの重い検証を強制）にならない粒度であること
- **影響推定・ロールバック**: 規律文書への追記のみ。既存挙動不変・単独 revert 可能。
- **依存**: なし。SI-CORE-021（委譲時の検収義務）と観点が近いが独立。
