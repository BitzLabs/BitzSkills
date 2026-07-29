---
implements: SDD-FR-146
depends_on: []
boundary: skills/sdd-core/scripts/spec_inspect.py, tests/test_spec_inspect.py
status: done
---

### canonical実行時にworkspace横断のテスト参照を集約する

- **作業内容**: `spec_inspect.py` の `main()` で複数ワークスペースを検査するとき、
  全入力ワークスペースの test/src 参照をグローバル ID で集約したコンテキストを構築し、
  `inspect()` へ渡す。`inspect()` の未参照判定は、自ワークスペース内の参照に加えて
  この外部参照も許容する。外部参照は `<workspace名>/<相対パス>` の形で保持し、
  レポートから参照元を識別できるようにする。単一ワークスペース検査では
  集約コンテキストを渡さず、既存の挙動を厳密に維持する。
  `tests/test_spec_inspect.py` に、ルート tests がプラグイン要件を参照する fixture での
  解消・単一実行での非解消・どこからも参照されない要件の残存・幽霊参照判定と
  終了コードの不変を検証する unit-test を追加する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
