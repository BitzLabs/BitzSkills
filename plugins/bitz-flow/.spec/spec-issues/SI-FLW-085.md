---
id: SI-FLW-085
raised_by: FLW-REV-027
target: flow-core CLI legacy approval path
proposed_change_type: modify
status: open
---
- **目的**: create/resumeのCLIをM2のplan-digest専用契約へ一致させ、廃止済みsigned-capability経路と旧context参照を除去する。
- **提案する修正**: `resolve_approval_mode`、capability解析、鍵registry選択、`worktree_dir_guard_key`参照をCLIから除去する。旧宣言・file・registryの検出は共通preflightでmutation前に`UNSUPPORTED / unsupported-approval-mode`へ閉じる。
- **対象ファイル**: `flowlib/cli.py`、旧承認互換module、operation catalog、CLI/architecture tests。
- **確認観点**: current `ApprovalContext.target_collision_key`だけを使うこと。旧承認コードがproduction handlerから参照されず、入力の内容を解析・降格しないこと。例外をclosed resultへ写像すること。
- **影響推定・ロールバック**: M2 create/resumeのCLIだけに限定する。旧互換APIの即時拒否契約は保持し、削除範囲をCLI選択経路に閉じる。
- **依存**: なし。`SI-FLW-084`より先行。accept推薦（platform evidence接続後に旧経路が再活性化するため）。
