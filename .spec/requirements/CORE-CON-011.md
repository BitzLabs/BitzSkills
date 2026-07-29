---
id: CORE-CON-011
version: 1.0
status: verified
domain: tooling
priority: medium
origin: SI-CORE-036
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-011 CLIスクリプトの未知引数拒否

- **説明**: リポジトリが提供する CLI スクリプトは、解釈できない引数を受け取ったとき
  処理を続行してはならない。安全のために付けられたフラグ（`--help` / `--dry-run` 等）が
  黙って無視されると、ガードレールが要求する事前確認そのものが空振りするため
  （実際に `bump_version.py` で意図しない bump が発生した。CORE-FR-018 はその個別対処）。
  読み取り専用のスクリプトも「フラグが効いた」という誤認を作らないために対象とする。
  次の3種は本規約の対象外とする:
  - **stdin 駆動の hook スクリプト**（`agy_guard.py`、`plugins/bitz-env/scripts/env_guard.py`）
    — CLI 引数契約を持たず、プラットフォームが起動形を決める。厳格化すると
    プラットフォーム側の仕様変更でガードレールフック自体が機能停止する
  - **`__main__` を持たないライブラリ**（`spec_labels.py` ほか）— CLI ではない
  - **ディスパッチャ `scripts/spec`** — 残り引数を委譲先へ転送し、委譲先が拒否する
- **受入基準 (EARS)**:
  - WHEN 対象の CLI スクリプトへ解釈できない引数を渡した THEN 処理を実行せず非ゼロ終了すること SHALL
  - WHEN 対象の CLI スクリプトへ引数位置に関わらず `-h` または `--help` を渡した THEN 副作用を起こさず使用方法を出力すること SHALL
  - WHEN 新しい CLI スクリプトをリポジトリへ追加した THEN 明示的な除外宣言がない限り本規約の検証対象へ自動的に含まれること SHALL
  - WHERE 対象外と定めた3種のスクリプトにおいて THE 本規約は適用されないこと SHALL
- **検証手段**: tests/test_cli_contract.py で、リポジトリ内の CLI スクリプトを実行時に
  収集し（`scripts/*.py`、`plugins/*/scripts/*.py`、`plugins/*/skills/*/scripts/*.py` から
  除外リストを引いたもの）、各々へ解釈できない引数と `--help` を渡して終了コードを検証する。
  実行は一時ディレクトリを作業ディレクトリとして行い、契約違反時も副作用を閉じ込める。
  対象が空にならないこと（収集漏れによる素通り防止）もあわせて検証する。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-CORE-036 の残項目（提案2・3・4）から導出。
    hook スクリプトの対象外化は `.spec/reports/decision-2026-07-29-si-core-036.md` の
    「残項目の裁定」で確定。
