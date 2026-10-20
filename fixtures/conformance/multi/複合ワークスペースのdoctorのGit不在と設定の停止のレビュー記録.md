# 複合ワークスペースの`doctor`のGit不在と設定の停止のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-040-01`〜`MULTI-040-10`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/multi_doctor_git_fixtures.py`である。

## 追加の理由

`doctor --all-workspaces`は、Gitを利用できず、かつリポジトリのルートの設定で全体事前検査が止まると、設定の診断だけを返し、
`SPEC-MULTI-GIT-001`を返さなかった（実装の確認事項C33）。全体事前検査は、Gitの境界を確定できないことを検査項目`git`の`blocked`には反映していたが、設定で止まった段階で診断を加えずに戻っていたためである。
[`doctor`仕様](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md) §3はGitの利用可否を設定と独立した検査（検査9）とし、
[ADR-065](../../../docs/02.設計書/10_決定記録/ADR-065_doctorのGit不在と設定の停止を独立した原因として返す.md)が、`doctor`だけについてADR-063の決定5を部分改訂して、
設定の診断に加えて`SPEC-MULTI-GIT-001`を返すと定めた。既存のfixtureは、Git不在の`doctor`（`MULTI-019`、`MULTI-036-11`）と、設定の停止の`doctor`（`MULTI-033`）を別々に固定し、
2つの原因が重なる場合を固定していなかったので、10件を追加する。既存の445件の入力と期待値は変えない。

## 根拠の規範文

- `doctor`仕様 §3: Gitの利用可否は設定と独立した検査（検査9）。ルートワークスペースの設定（構文、型、必須フィールド、スキーマまたはEARS-AIのメジャーバージョン）で
  全体事前検査が止まった場合も、Gitの境界を確定できなければ、設定の診断に加えて`SPEC-MULTI-GIT-001`（`blocked`）を返す。単独の`doctor`の全体事前検査も同じ。ほかの操作は設定の停止の診断だけ。
  スキーマまたはEARS-AIのメジャーバージョンが非対応で止まった場合は、最上位の`checks[]`に`catalog`を`blocked`で置く。
- ADR-065の決定2・3: 上の扱いは`doctor`だけ。`context`、`check`、`verify`は設定の停止の診断だけ（ADR-063の決定5のとおり）。
- ADR-063の決定4・5: 構文、型、必須フィールドが不正で読めないルートの設定は複合ワークスペースと判定せず、単一ワークスペースとして扱う。
  スキーマまたはEARS-AIのメジャーバージョンが非対応の設定は、`multiWorkspace`の宣言があれば複合ワークスペースと判定する。
  Gitを利用できないときは、最も近い設定が`multiWorkspace`を宣言していれば複合ワークスペースとする。決定6: Gitを利用できない状態の停止の`revision`は`null`。
- 結果・診断・終了コード §2.3: 全体事前検査がルートの設定の構文、型、ID不正で止まり、有効なルートのIDを構成できない場合だけ、`multiWorkspace`は`{id: null, path: "."}`、`workspaces`は空配列。
  §3: 診断の効果の最悪値が状態になる（`error`>`blocked`）。§5: 同一性を構成できない設定の診断は`workspaceId`が`null`。§7: 診断の順序。
- 診断レジストリ: `CONFIG-YAML-FORBIDDEN`、`CONFIG-SCHEMA-MAJOR`は`SPEC-CONFIG-SCHEMA-001`、`EARS-SCHEMA-MAJOR`は`SPEC-EARS-VERSION-001`、
  `doctor`のEARS-AIの非対応は`DOCTOR-EARS-VERSION`の`SPEC-DOCTOR-EARS-001`、`MULTI-GIT`は`SPEC-MULTI-GIT-001`（`environment`、`blocked`）。

## 入力と起動

基本のリポジトリは`MULTI-036`の群と同じ（ルート`platform`、メンバー`web`〈`apps/web`〉と`api`〈`services/api`〉）。ルートの設定だけを、停止の原因になる1か所だけ変える。
Git不在のfixtureは`setup.git: false`と`PATH=/dev/null`で、Gitの実行ファイルを見つけられない環境を作る（`MULTI-019`と同じ）。Gitのある対照はコミットし、`PATH`は変えない。

| fixture | 操作と実行ディレクトリ | ルートの設定 | Git | 結果 |
|---|---|---|---|---|
| `MULTI-040-01` | `doctor --all-workspaces`、`.` | `earsAi: "2.0"` | なし | `blocked`／2。`SPEC-MULTI-GIT-001`、`SPEC-DOCTOR-EARS-001`。`checks`は`core`・`git`（`blocked`）・`catalog`（`blocked`） |
| `MULTI-040-02` | `doctor --all-workspaces`、`.` | `schemaVersion: "2.0"` | なし | `blocked`／2。`SPEC-MULTI-GIT-001`、`SPEC-CONFIG-SCHEMA-001`。`checks`は`040-01`と同じ |
| `MULTI-040-03` | `doctor --all-workspaces`、`.` | `language: &label ja`（アンカー） | なし | `error`／3。`SPEC-CONFIG-SCHEMA-001`、`SPEC-MULTI-GIT-001`。`multiWorkspace.id`は`null`、`checks`は`core`・`git`（`blocked`） |
| `MULTI-040-04` | `doctor`（単独）、`.` | `earsAi: "2.0"` | なし | `040-01`と同じ診断と`checks`。単独結果 |
| `MULTI-040-05` | `doctor`（単独）、`docs` | `schemaVersion: "2.0"` | なし | `040-02`と同じ診断と`checks`。設定を持たないサブディレクトリから、最も近い設定はルート |
| `MULTI-040-06` | `check`、`.` | `earsAi: "2.0"` | なし | 対照: `blocked`／2。`SPEC-EARS-VERSION-001`だけ。`revision: null` |
| `MULTI-040-07` | `verify`、`.` | `schemaVersion: "2.0"` | なし | 対照: `blocked`／2。`SPEC-CONFIG-SCHEMA-001`だけ |
| `MULTI-040-08` | `context REQ-001`、`.` | `earsAi: "2.0"` | なし | 対照: `blocked`／2。`SPEC-EARS-VERSION-001`だけ |
| `MULTI-040-09` | `doctor`（単独）、`.` | `schemaVersion: "2.0"` | あり | 対照: `blocked`／2。`SPEC-CONFIG-SCHEMA-001`だけ。`git`は`passed` |
| `MULTI-040-10` | `doctor --all-workspaces`、`.` | `language: &label ja` | あり | 対照: `error`／3。`SPEC-CONFIG-SCHEMA-001`だけ。`checks`は`core`・`git`（`passed`） |

構文の不正の例にYAMLのアンカーを選んだのは、診断の`summary`「設定YAMLのアンカーは禁止です」と発生元のキー`language`が、既存のfixture（`MULTI-036-08`、`SINGLE-091`）で承認済みとして固定されているためである。
YAMLの構文そのものの不正（`SPEC-CONFIG-SCHEMA-001`、`CONFIG-YAML-SYNTAX`）の`summary`は、既存のfixtureが固定していないので、fixtureにせず単体試験で確かめる。
単独の`doctor`でルートの設定が構文の不正の場合は、ADR-063の決定4により複合ワークスペースと判定せず、単一ワークスペースの`doctor`（Git不在は`SPEC-DOCTOR-GIT-001`の警告）になるので、fixtureにせず単体試験で確かめる。

## 期待値の導き方（Coreの出力を根拠にしない）

1. **診断の集合と状態**。`reference_expected`が、ルートの設定の本文（`classify_root_config`）と、準備手順の後のGitの有無、操作から導く。
   設定の診断は停止の種類ごとに1件。`doctor`だけが、Gitを利用できなければ`SPEC-MULTI-GIT-001`を加える。状態は診断の効果と検査項目の最悪値で、構文などの不正は`error`／3、版の非対応とGitの不在は`blocked`／2。
2. **検査項目**。`core`は`passed`、`git`はGitの有無で`blocked`または`passed`。`catalog`は版の非対応のときだけ`blocked`（`doctor` §3）。構文などの不正は`catalog`を置かない（既存の`doctor --all-workspaces`でGitがあるときの構文の不正と同じ）。
3. **停止の種類の分類**。禁止されたYAML（構文の不正）、スキーマのメジャーバージョン、EARS-AIのメジャーバージョンの順に調べる。
4. **陰性対照**。`check_conditions`が、原因が1か所だけであること（その1か所以外は最小のカタログと同じ）、メンバーの設定が止まらないこと、Gitの有無、`docs`が設定を持たないこと、
   単独の`doctor`の対象が`multiWorkspace`を宣言すること（構文の不正を除く）を入力から確かめる。監査の回帰試験（`fixtures/test_conformance_audit.py`の`test_multi_doctor_git_*`）が、
   期待結果・起動条件・副作用の改変（406件）と、入力の欠落・追加・原因を消す書換えを拒否することを確かめる。

## 陰性対照（修正前のCoreでの実測）

修正前のCore（コミット`c0cdcc4e`の`plugins/bitz-core`）で実行した。

`run_conformance.py --step 5`を実行した。全455件（既存の445件と追加の10件）の結果は`passed` 450件、`failed` 5件、`error` 0件で、失敗した5件は`MULTI-040-01`〜`05`だけである（既存の445件と、対照の`06`〜`10`はすべて通過する）。
修正後のCore（コミット`052a503e`）では455件がすべて`passed`である。

| fixture | 修正前のCore | 失敗の内容 |
|---|---|---|
| `MULTI-040-01`〜`05` | 失敗 | `$/diagnostics`が1件（期待は2件）。設定の診断だけを返し、`SPEC-MULTI-GIT-001`を落とす。状態、`checks`、`multiWorkspace`・`workspace`は期待どおり |
| `MULTI-040-06`〜`08` | **通る** | 対照: `check`、`verify`、`context`は設定の診断だけ。修正後も通り続けることを要求する |
| `MULTI-040-09`、`10` | **通る** | 対照: Gitがあれば設定の診断だけ。修正後も通り続けることを要求する |

## 規範から導けなかった点・固定の程度

- **環境の発生元と`workspaceId: null`のファイルの発生元の相対順**（`MULTI-040-03`だけが依存する）。結果・診断・終了コード §7は、診断を発生元のワークスペースID、`path`、...の辞書順とし、
  同一性が確定する前の`workspaceId: null`を文字列のIDより前に置くと定めるが、IDを持たない環境の発生元との相対順は書かれていない。`MULTI-040-01`、`02`、`04`、`05`の相対順
  （環境の発生元が、ID`platform`のファイルの発生元より先）は、「IDを持たない発生元は文字列のIDより前」と読めば導けるが、`040-03`は導けない。
  2026-10-20、ユーザーがこの相対順を決め（ワークスペースIDを持たない発生元は`workspaceId: null`の発生元の後、文字列のIDの前）、結果・診断・終了コード §7に明記した。
  `040-03`の順序（`SPEC-CONFIG-SCHEMA-001`、`SPEC-MULTI-GIT-001`）はこの規範から導ける。
- 構文などの不正の例は、承認済みの文言があるアンカーの禁止に限った（上述）。型、必須フィールドの不正と、YAMLの構文そのものの不正は、単体試験（`tests/bitz-core/test_doctor_git_absent_config_stop.py`）が診断の集合を確かめる。
