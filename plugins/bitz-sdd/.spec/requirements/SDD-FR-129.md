---
id: SDD-FR-129
version: 1.0
status: verified
domain: sync
priority: high
origin: SI-SDD-012
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-129 旧8章から日本語6章への安全な移行

- **説明**: 旧英語8章を持つ既存利用者が、衝突や文書消失を起こさず日本語6章へ移行できる
  dry-run既定の移行コマンドを提供する。
- **受入基準 (EARS)**:
  - WHEN 移行コマンドをフラグなしで実行したとき THEN システムは予定する移動・台帳リンク更新・衝突を表示し、ファイルを変更しない SHALL
  - WHEN `--apply` を指定し、全事前検査が成功したとき THEN システムは既知文書を日本語章へ移動し、`MASTER.md` の既知リンクを更新し、ロールバック用manifestを記録する SHALL
  - IF 移行先に内容の異なるファイル、旧新レイアウトの曖昧な混在、または未解決の移動先がある THEN システムは適用前に非ゼロ終了し、既存ファイルを変更しない SHALL
  - WHEN `--rollback` を指定し、manifestと現在のファイルが整合するとき THEN システムは移動と台帳リンク更新を元に戻す SHALL
- **検証手段**: `tests/test_migrate_docs.py` のdry-run、apply、衝突時原子停止、rollback、冪等性unit-test。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票）
