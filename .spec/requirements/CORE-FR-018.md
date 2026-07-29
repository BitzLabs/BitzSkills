---
id: CORE-FR-018
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

### CORE-FR-018 副作用を持つ運用スクリプトの引数契約

- **説明**: ファイルを書き換える運用スクリプトが、解釈できない引数を黙って無視したまま
  変更を適用してはならない。安全のために付けられたフラグ（`--help` / `--dry-run`）が
  空振りすると、ガードレールが要求する事前確認そのものが無効化されるため。
  本要件は `scripts/bump_version.py` を対象とする。読み取り専用ツールと
  stdin 駆動の hook スクリプトは副作用を持たないため対象外
  （全スクリプトへの共通契約化は SI-CORE-036 の残項目として未着手）。
- **受入基準 (EARS)**:
  - WHEN `bump_version.py` へ解釈できない引数を渡した THEN マニフェストを変更せず非ゼロ終了すること SHALL
  - WHEN `bump_version.py` へ引数位置に関わらず `-h` または `--help` を渡した THEN マニフェストを変更せず使用方法を出力すること SHALL
  - WHEN `bump_version.py` へ `--dry-run` を渡した THEN 新旧 version を出力し3マニフェストのいずれも書き換えないこと SHALL
  - WHEN `bump_version.py` へ従来の呼び出し形（`<plugin名>` 単独、または `<plugin名> major|minor|patch`）を渡した THEN 従来と同一の bump 結果を適用すること SHALL
- **検証手段**: `tests/test_bump_version.py` で、未知引数・位置違いの `--help`・`--dry-run` の
  各ケースについて終了コードと3マニフェストの before/after 内容を unit-test する。
  後方互換は part 省略時（patch）と major/minor/patch 明示時の bump 結果で検証する。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-CORE-036 から導出。
