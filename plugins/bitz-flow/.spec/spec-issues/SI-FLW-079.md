---
id: SI-FLW-079
raised_by: FLW-REV-021
target: FLW-NFR-013 の派生要件トレーサビリティ
proposed_change_type: modify
status: accepted
github_issue: https://github.com/BitzLabs/BitzSkills/issues/257
---
- **目的**: `FLW-NFR-013` の承認モード契約を、直接の既存要件から双方向に追跡できるようにする。
- **提案する修正**: `FLW-NFR-013` の派生・参照を `FLW-FR-006`（追跡下の承認モード宣言）および `FLW-NFR-007`（file identityと原子性）へ接続し、`FLW-NFR-011` は今回の起票経緯・confirmation関連の補助参照として区別する。
- **対象ファイル**: `plugins/bitz-flow/.spec/requirements/FLW-NFR-013.md`、`plugins/bitz-flow/.spec/design/FLW-DSN-017.md`。
- **確認観点**: `spec_inspect`で幽霊参照・孤児要件が無いこと、要件→設計→実装候補が `FLW-FR-006` と `FLW-NFR-007` から辿れることを確認する。
- **影響推定・ロールバック**: 契約本文を変えないメタデータ・設計参照の訂正であるが、承認済み要件に触れるため人間裁定を要する。誤りがあれば参照変更だけをrevertできる。
- **依存**: `FLW-REV-021:SYN-008`、`FLW-FR-006`、`FLW-NFR-007`、`FLW-NFR-013`。
- **予備判定（推薦）**: **acceptを推薦**。現行の `derived_from: FLW-NFR-011` だけでは、承認モードと永続file安全性の契約へ遡れない。

- **裁定**: 2026-08-22 userが要件系譜の訂正を採用。
