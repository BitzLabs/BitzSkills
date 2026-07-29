---
id: SDD-FR-152
version: 1.0
status: verified
domain: verification
priority: high
origin: SI-SDD-016
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-152 検証証跡における秘密値と環境固有情報の非保存

- **説明**: 証跡は version 管理へコミットされるため、raw な標準出力・環境変数・認証情報・
  実行者のホームパスを保存すると、秘密値の恒久的な漏洩と環境依存の差分を招く。
  証跡には許可リストの要約項目だけを書き、それ以外は保存しない。記録の入力である
  コマンド引数についても、秘密値らしき語や環境固有の絶対パスを含む場合は記録を拒否する。
  本要件は公開契約に該当し、リポジトリのガードレール（認証情報を出力しない）に対応する。
- **受入基準 (EARS)**:
  - WHEN 証跡を書き出すとき THEN システムは検証コマンドの標準出力・標準エラー出力の本文を証跡へ保存しない SHALL
  - WHEN 証跡を書き出すとき THEN システムは環境変数を証跡へ保存しない SHALL
  - IF コマンド引数に token / secret / password / api-key / credential 等の語が含まれる THEN システムはコマンドを実行せず、証跡を書き出さずに非ゼロ終了する SHALL
  - IF コマンド引数に実行者のホームディレクトリを含む絶対パスが含まれる THEN システムはコマンドを実行せず、証跡を書き出さずに非ゼロ終了する SHALL
  - WHEN コマンド引数がワークスペース配下の絶対パスであるとき THEN システムはワークスペース相対パスへ正規化して記録する SHALL
  - WHEN 検証コマンドが出力を生成したとき THEN システムはその実出力を呼び出し元の標準出力・標準エラー出力へそのまま流す SHALL
- **検証手段**: `tests/test_spec_verify.py` の unit-test（証跡 JSON のキー集合が許可リストに
  一致すること、秘密値らしき引数とホームパス引数の拒否、絶対パスの相対化、実出力の透過）。
- **Revision History**:
  - 1.0 (2026-07-29) 初版（draft 起票）。SI-SDD-016 から導出。
