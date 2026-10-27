# `verify`の早期に返す結果の`revision`とレポートのfixtureのレビュー記録

[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify)の
`SINGLE-165-01`〜`07`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（ADR-051の追加。実装の確認事項C41）。群は`fixtures/conformance/verify_stop_revision_fixtures.py`、Stepは4である。

## 何を固定するか

`verify`は、検証対象を解決して各テスト割当てを実行する前に結果を返す場合がある。ワークスペースの設定が停止した場合
（スキーマのメジャーバージョンの非対応、YAMLの構文の不正）と、引数なしで検証対象が0件の場合である。Coreは、この早期に返す結果だけ
`revision`を常に`null`にし、`--report`を無視していた。単一ワークスペースと、複合ワークスペース内の単独操作のほかの`verify`の結果（検証対象を解決した結果）では、どちらも規範どおりだった。
`--all-workspaces`の早期の結果（全体事前検査の停止と上限の超過）も`--report`を保存しない（`check --all-workspaces`も同じ。`revision`は正しい）が、
この群の範囲外とし、実装の確認事項C53として別に扱う。
このため、既存の`verify`のfixtureは、早期に返す結果を、コミットのあるリポジトリで`--report`付きで固定していなかった。

## 根拠の規範文

| 規範文 | 内容 |
|---|---|
| [結果・診断・終了コード §2](../../../docs/03.詳細設計/00_共通契約/01_結果・診断・終了コード.md#2-結果の形) | 「単一ワークスペースでGit不在、またはコミットのないリポジトリであれば、`revision: null`とする」。`context`または`verify`の`null`でない`revision`は、40桁の小文字16進数の`commit`と真偽値の`dirty`だけを持つ。「非成功でも、選択した種類に必須のフィールドを省略しない」 |
| 同 [§2](../../../docs/03.詳細設計/00_共通契約/01_結果・診断・終了コード.md#2-結果の形) | 設定の構文、型、ID不正などにより、ワークスペースの同一性を構成する前に停止した単独結果だけ、`workspace.id`を`null`とする。同一性が確定していれば（スキーマのバージョンの非対応）、単一ワークスペースでは設定した`workspace.id`、省略時は`root` |
| 同 [§8](../../../docs/03.詳細設計/00_共通契約/01_結果・診断・終了コード.md#8-レポート) | 「`check`と`verify`は、状態にかかわらず、指定された場合だけ`.spec/reports/`へ結果のJSONを保存する」。`--report`がなければ「新しいファイルも作らない」。保存の失敗は`SPEC-REPORT-WRITE-001`とするが、元の結果と診断は端末に保持する |
| 同 [§3](../../../docs/03.詳細設計/00_共通契約/01_結果・診断・終了コード.md#3-結果の状態と終了コード)、診断レジストリ | `SPEC-CONFIG-SCHEMA-001`（版の非対応は`blocked`、構文などの不正は`error`）、`SPEC-VERIFY-BLOCKED-002`（`blocked`）の効果から、状態と終了コードを導く |

`dirty`は「実行時の状態」であり、レポートの保存より前の作業ツリーで決まる。保存したレポートが未追跡のファイルとして`dirty: true`を
作ってはならない。`SINGLE-165-01`〜`03`は、コミットのクリーンなリポジトリで`--report`付きの結果が`dirty: false`であることで、
この順序も固定する（レポートを保存した後に`revision`を求める実装は、`dirty: true`を返して不適合になる）。

## fixtureごとの期待値

すべて`verify --format json`（`--report`の有無は表の「起動」）で、引数なしだから`scope`は`all`、`targetResults`と`commands`は空である。
入力は`SINGLE-062`と同じ設定とREQ-001（`draft`）に、既存のレポート`.spec/reports/existing.json`を加える。

| fixture | 原因 | 起動 | Git | 状態／終了コード | `workspace.id` | `revision` | レポート |
|---|---|---|---|---|---|---|---|
| `SINGLE-165-01` | `schemaVersion: "2.0"` | `--report` | コミットあり、クリーン | `blocked`／2 | `root` | `{commit, dirty: false}` | 1件 |
| `SINGLE-165-02` | `language: &label ja`（アンカー） | `--report` | コミットあり、クリーン | `error`／3 | `null` | `{commit, dirty: false}` | 1件 |
| `SINGLE-165-03` | 対象0件（`approved`のREQなし） | `--report` | コミットあり、クリーン | `blocked`／2 | `root` | `{commit, dirty: false}` | 1件 |
| `SINGLE-165-04` | 対象0件 | なし | コミットあり、クリーン | `blocked`／2 | `root` | `{commit, dirty: false}` | 0件 |
| `SINGLE-165-05` | `schemaVersion: "2.0"` | なし | コミットあり、未追跡の`docs/notes.md` | `blocked`／2 | `root` | `{commit, dirty: true}` | 0件 |
| `SINGLE-165-06` | `schemaVersion: "2.0"` | `--report` | コミットなし（ステージのみ） | `blocked`／2 | `root` | `null` | 1件 |
| `SINGLE-165-07` | 対象0件 | `--report` | Git不在（`PATH=/dev/null`） | `blocked`／2 | `root` | `null` | 1件 |

診断は、設定の停止が`SPEC-CONFIG-SCHEMA-001`の1件（`blocked`のときキー`schemaVersion`、`workspaceId`は`root`。`error`のときキー`language`、
`workspaceId`は`null`）、対象0件が`SPEC-VERIFY-BLOCKED-002`の1件（`SINGLE-062`と同じ。発生元は`{kind: invocation}`）である。
診断の文言は既存のfixtureが固定済みの承認済みの文字列を使い、新しい文言は足していない。

レポートの内容は、標準出力の結果と一致する必要がある。harnessは、新しいレポートを結果と同じスキーマで検証し、正規化器を適用して
期待結果と完全に比較する。

## 陰性対照と陽性対照

- 陰性対照（修正前のCore）: `SINGLE-165-01`〜`03`は`revision`が`null`で、レポートが0件。`04`・`05`は`revision`が`null`。`06`・`07`はレポートが0件
  （`revision: null`はこの2件では正しく、`--report`の無視だけを検出する）。7件すべてが不適合になる。
- 陽性対照: コミットのないリポジトリ（`06`）とGit不在（`07`）で`revision: null`、`--report`のレポートは1件という、規範の2つの規則の独立性。
  設定の停止と対象0件の両方、`blocked`と`error`の両方、クリーンと`dirty`の両方を持つ。
- 対照にならない組合せは、置かない。`--report`なしでレポートを作らないことは、`SINGLE-070-*`が検証対象を解決した結果で固定済みであり、
  この群の`04`・`05`が早期に返す結果でも固定する。

## fixtureにしなかったもの

- **設定がない（`.spec/bitz.yaml`がない）リポジトリの`verify --report`。** `.spec`がなければ保存先を作れず、`SPEC-REPORT-WRITE-001`が加わって
  `error`／3になる。これは`check --report`と同じ状態と終了コードである。診断の並びは、`verify`も`check`も結果・診断・終了コード §7に従い、
  `workspaceId: null`のファイルの発生元（`SPEC-REPORT-WRITE-001`）を環境の発生元（`SPEC-WORKSPACE-MISSING-001`）より先に並べる
  （`check`は以前、保存の失敗を診断の末尾に加えていた。2026-10-25の確認事項C51で§7の並びに入れ、`SINGLE-072`の期待値を訂正した）。
  並びは§7から導けるが、この群の範囲は`revision`と`--report`の独立性で、診断の並びの固定は別の関心事なので、
  この経路の`verify`のfixtureは置かず（追加するなら別の群として、ADR-051の追加の手順による）、単体試験（`tests/bitz-core/test_verify_stop_revision_report.py`）で
  `verify`の並びが§7に従うことと、状態・終了コード・診断の集合が`check`と同じことだけを確かめる。
- **複合ワークスペースの検証対象が0件の経路。** 規則は同じ（コミットがあれば`revision`を返し、作業ワークスペースの`.spec/reports/`へ保存する）だが、
  この群は単一ワークスペースだけを固定し、複合ワークスペースは単体試験で確かめる。

## 限界

- Coreは実行していない。レポートの内容が結果と一致することを含め、Coreとの一致はGate Bで判定する。
- `dirty`の判定に含める変更の範囲（未追跡のファイルを含む）は、`SINGLE-165-05`が未追跡のファイル1つで固定する。無視されたファイルや、
  ステージされた変更だけの`dirty`は、このmatrixでは区別しない。
- 参照計算は、`approved`のREQの件数で検証対象の有無を導く（この群の入力はREQだけを持つ）。TECHやTASKを含む入力には使えない。
