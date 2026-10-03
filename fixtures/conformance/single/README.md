# 初回の実fixture: 導入と設定

2026-09-08。対象は`SINGLE-001`、`002`、`003`、`004-01`、`004-02`、`005-01`、`005-02`、`006-01`、`006-02`。
この9件は、入力、唯一の期待JSON、副作用の期待値を持つ。Coreの実行結果ではない。

## 設計と単一原因のレビュー

| ID | 独立した原因 | 実行 | 結果の状態／終了コード |
|---|---|---|---|
| SINGLE-001 | なし。最小設定だけ | `doctor --format json` | `passed`／0 |
| SINGLE-002 | 設定の不在だけ | `doctor --format json` | `blocked`／2 |
| SINGLE-003 | `schemaVersion`を文字列の2.0に変更 | `check --full --base HEAD --format json` | `blocked`／2 |
| SINGLE-004-01 | `language`を整数の42に変更 | `check --full --base HEAD --format json` | `error`／3 |
| SINGLE-004-02 | 必須の`earsAi`だけを削除 | `check --full --base HEAD --format json` | `error`／3 |
| SINGLE-005-01 | 未知のキー`futureOption`だけを追加 | `check --full --base HEAD --format json` | `passed_with_warnings`／0 |
| SINGLE-005-02 | 予約されたキー`profiles`だけを追加 | `check --full --base HEAD --format json` | `passed_with_warnings`／0 |
| SINGLE-006-01 | コマンドの実行ファイルだけが不在 | `doctor --format json` | `blocked`／2 |
| SINGLE-006-02 | コマンドの作業ディレクトリ（`cwd`）だけが不在 | `doctor --format json` | `blocked`／2 |

最小設定は、`doctor`仕様の`schemaVersion: "1.0"`、`language: ja`、`earsAi: "1.0"`とする。
コード、テスト、仕様文書、`multiWorkspace`の宣言は置かず、別の原因の診断を混ぜない。
コマンド`default`の定義（`verify.commands.default`）を1件、006系だけに置く。
`check`は、入力を固定したメタデータでコミットして、明示した`HEAD`を比較の基準版にする。Git不在やコミットのないリポジトリでの縮退を混ぜない。
`doctor`は、Gitを利用可能な、コミットのないリポジトリで実行し、履歴の差分の検査は要求しない。
SINGLE-002の空のリポジトリをGitで保持するためだけに`.gitkeep`を置き、準備手順で除去してから実行する。
すべてのコピーは物理的に独立し、共通の入力へのリンクは使わない。

根拠は[適合fixture仕様 §6.1](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#61-導入と設定)、
[設定仕様 §5](../../../docs/03.詳細設計/02_仕様文書モデル/01_ワークスペース・設定仕様.md#5-スキーマ)、
[`doctor`仕様](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md)、
[結果契約 §2・§5](../../../docs/03.詳細設計/00_共通契約/01_結果・診断・終了コード.md)、
[診断レジストリ](../../../docs/03.詳細設計/00_共通契約/05_診断レジストリ.md)。

## 今回固定する完全期待値

従来の仕様が語彙と意味だけを規定していた部分も、今回のfixtureは、次の一意な値で固定する。
比較のときに`summary`、`suggestedAction`、`checks`、任意のフィールドを除外する規則は追加しない。

- SINGLE-001の`checks`は、処理の順に`core, workspace, config, schema, ears, git, command, impact`とする。
  `impact`は`info`、他は`passed`とする。プラグインの要求がなく、単一ワークスペースなので、プラグイン、対応機能の要求、カタログの項目は置かない。
  コマンドの定義が0件であることは、検査項目`command`の成功、影響候補が0件であることは、検査項目`impact`の`info`とし、追加の診断は出さない。
- SINGLE-002は`core: passed, workspace: blocked, git: passed`とする。
  独立したGitの確認を続け、設定に依存する後続の検査項目は出力しない。複合ワークスペースの依存遮断の診断は、単一ワークスペースへ追加しない。
- 未知のメジャーバージョンのSINGLE-003は、構造的に有効な設定から、既定の同一性`root`を確定した後、互換性の検査で停止する。
  型の不正、必須のキーの欠如、設定の不在のケースは、同一性の確定前なので`workspace.id: null`とする。
- `check`の診断は、`source.key`をそれぞれ`schemaVersion`、`language`、`earsAi`とする。
  行と列、証跡、`specRefs`、`extensions`、`suggestedAction`は、この3件では付加しない。
  `summary`は、各`expected/check.json`の日本語の文字列を固定値とする。
- 設定の不在は、発生元の種類`environment`の`component: workspace, identifier: .`とし、
  `suggestedAction`へ、作成先、貼り付けられる最小設定、`.gitignore`への追記、次の`check`を含める。
- 005系は、診断`SPEC-CONFIG-UNKNOWN-001`（重大度`warning`、結果への効果`passed_with_warnings`）を1件だけ返す。
  `source.key`はそれぞれ`futureOption`、`profiles`とする。未知のキーの値`preserve-me`と、予約されたキーの値
  `legacy-profile`は保持し、`profiles`を設定の機能として解釈しない。文書が0件の全体検査は、2つの検査件数（`checkedDocumentCount`と`checkedStatementCount`）を0とする。
- 006系は、診断`SPEC-DOCTOR-COMMAND-001`（重大度`error`、結果への効果`blocked`）を1件だけ返す。
  発生元は、診断レジストリのとおり種類`file`で、`workspaceId: root`、`path: .spec/bitz.yaml`、キーはそれぞれ
  `verify.commands.default.argv`、`verify.commands.default.cwd`とする。行と列、証跡、修復案は付加しない。
  `checks`は001と同じ順序で、`command`だけ`blocked`とする。独立した検査項目`impact`は続けて`info`とし、別の診断は追加しない。
  005系と006系とも、`summary`は各期待JSONの固定した文字列とする。
- 所要時間は0、Coreのパッチは0、GitのコミットIDは40桁の0を、期待JSONの代表値とする。
  実際の値は、既存の共通の正規化器だけで比較する。Gitの`dirty`、Coreのメジャーバージョンとマイナーバージョン、対応機能の順序は除外しない。

これらは今回追加した受入の期待値の選択であり、既存のCoreで観測した値ではない。
将来変更する場合は、仕様との整合をレビューし、期待値とレビュー記録を同じ変更で更新する。

## 副作用の期待値と検証

各fixture直下の`side-effects.json`は、`side-effects.schema.json`に従う補助の証拠とする。
マニフェストの公開フィールドは増やさず、期待する出力の`expected/`とは分離する。
`before`と`after`に、リポジトリの全パス、種別、実行ビット、SHA-256、`git status`（porcelain v1形式）とGitのインデックス、
`HOME`・`XDG_CACHE_HOME`・`TMPDIR`の3つの隔離した木構造を固定する。許可する書込みは0件で、`before`と`after`は完全に一致する。
`.git`の内部のファイルは、既存のスナップショットの契約に従って除外し、`git status`とGitのインデックスは別に比較する。
レポートのディレクトリ、永続的なキャッシュ、ロック、作業用のファイルの残存を許可しない。明示したレポートを許すfixtureは、このスキーマの対象外である。

`uv run fixtures/validate_conformance.py`の`initial_fixtures`は、次を検査する。

1. マニフェスト、結果、副作用のスキーマへの適合と、操作、結果の状態、終了コード、単一の原因との整合。
2. 各入力を新しい隔離したディレクトリで2回準備し、各回が固定した`before`のスナップショットと一致すること。
3. 入力のバイト列がレビュー済みの単一の原因と一致し、読取り専用の期待する`after`が`before`と一致すること。
4. 回帰試験で、結果の状態、`source.key`、引数列、修復の手順、副作用の期待値の破損を拒否すること。
5. 005系の警告を重大度`error`へ変更した場合や診断の重複、006系の原因のキーや検査項目の状態の破損を拒否すること。

006-01は`argv: ["./missing-command"]`、`cwd: .`とする。実行ファイルの明示したパスが存在しないことを確認し、
ホストの`PATH`に同名のコマンドがあっても結果が変わらない構成とする。
006-02は`argv: ["/bin/true"]`、`cwd: missing-directory`とする。このfixtureの環境は、Linux/POSIXで
`/bin/true`が通常の実行可能なファイルとして利用可能であることを要求し、未導入または実行不可は、準備検証のエラーとする。
実効の作業ディレクトリが不在でも、実行ファイルの絶対パスは独立に確認できる。`PATH`は上書きせず、Gitの利用を壊さない。
準備検証でコマンドを起動することはない。実際の`doctor`がコマンドを起動しないことは、Gate Bで別途確認する。

検証は、CoreもYAMLの設定の判定も実装しない。`after`は期待値だけであり、Core実行後の実測値ではない。
Coreの実装後のGate Bで、実際の標準出力と終了コード、実際の`before`と`after`、索引の構築へ進まないことを確認する。
この9件に加えて、[EARS-AI構文・候補抽出・拡張の12件](EARS-AI構文・候補抽出のレビュー記録.md)と
[文書構造・UTF-8の9件](文書構造とUTF-8のレビュー記録.md)、[関係・パス・カバレッジの6件](関係・パス・カバレッジのレビュー記録.md)、[ID重複・循環の4件](文書IDの重複と循環のレビュー記録.md)、[基準版の5件](基準版・状態遷移のレビュー記録.md)、[保護対象外変更の5件](approvedのREQの保護対象外の変更のレビュー記録.md)と[TASK境界の3件](TASK境界・対象選択のレビュー記録.md)、[Gitの対象選択・影響候補の4件](Gitの対象選択・影響候補のレビュー記録.md)、[基準版のエラー・Git不在の3件](基準版のエラー・Git不在のレビュー記録.md)、[コンテキストの非成功の5件](コンテキストの非成功のレビュー記録.md)を準備した。
計65/311件、matrixの残りは246件で、goldenのコンテキストのハッシュ値、全体の副作用の期待値、
新しいチェックアウトでのGate Aの全検証は残る。
