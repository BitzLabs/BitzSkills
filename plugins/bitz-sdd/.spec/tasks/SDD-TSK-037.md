---
implements: SDD-FR-147
depends_on: []
boundary: skills/sdd-core/scripts/spec_inspect.py, tests/test_spec_inspect.py
status: done
---

### 実装コードディレクトリを参照走査対象へ加える

- **作業内容**: `scan_refs()` の走査対象へ `scripts`、`hooks`、`skills`（配下の
  `scripts/` ディレクトリのみ）を加える。追加対象ではコード拡張子のファイルだけを
  走査し、Markdown を実装参照として数えない。既存の `.spec/specs` / `.spec/tasks` /
  `tests` / `test` / `src` の走査条件（Markdown を含む）は変更しない。
  未参照判定が「テスト/実装からの参照」と見なすパス接頭辞にも追加対象を反映する。
  `tests/test_spec_inspect.py` に、`skills/<name>/scripts/` のコードによる解消・
  同ディレクトリの Markdown のみでは非解消・追加対象内の幽霊参照の検出継続・
  追加ディレクトリを持たないワークスペースの結果不変を検証する unit-test を追加する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
