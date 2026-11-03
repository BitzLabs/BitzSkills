# 複合ワークスペースの`doctor`のGit不在とカタログの不適合のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-058-01`〜`MULTI-058-06`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/multi_doctor_git_catalog_fixtures.py`である。

## 追加の理由

Gitを利用できない（またはリポジトリの外の）複合ワークスペースで、`doctor`は`SPEC-MULTI-GIT-001`だけを返し、ルートの設定の本文だけで判定できるカタログの不適合
（`multiWorkspace`の型と件数、除外のパス、ルートの`workspace.id`の省略）を隠していた（実装の確認事項C50）。Gitがあれば、同じ入力で`SPEC-MULTI-CONFIG-001`を返す。
ユーザーの決定（2026-11-03）に基づき、[`doctor`仕様](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md) §3と
[複合ワークスペース仕様](../../../docs/03.詳細設計/02_仕様文書モデル/05_複合ワークスペース仕様.md) §3が、`doctor`だけは設定の不適合とGitの不在を独立した原因とし、
Gitの境界を確定できずに止まる場合も、ルートの設定の本文だけで判定できるカタログの不適合を並べて返すと定めた（コミット`b1216175`）。既存のfixtureは、
Gitの不在とルートの設定の停止（版の非対応と構文の不正。`MULTI-040`）を固定していたが、カタログの不適合との併記を固定していなかったので、6件を追加する。
既存の入力と期待値は変えない。

## 根拠の規範文

- `doctor`仕様 §3: Gitの境界を確定できずに止まる場合も、ルートの設定の本文だけで判定できるカタログの不適合（ルートの`workspace.id`の省略、`multiWorkspace`の型と件数、
  除外のパスの不正。`SPEC-MULTI-CONFIG-001`）を並べて返し、検査項目`catalog`を`failed`とする。メンバーの設定、メンバーのパス、未登録の設定など、ルートの候補の位置に依存する検査は行わない。
  単独の`doctor`の全体事前検査も同じ。ほかの操作は設定の停止の診断だけ（`SPEC-MULTI-GIT-001`だけ）。
- 複合ワークスペース仕様 §3: `doctor`以外の操作は`SPEC-MULTI-GIT-001`だけを返す。§2: ルートワークスペースの`workspace.id`は必須で、既定値`root`を有効なIDとみなさない。
  除外のパスはADR-064。
- 結果・診断・終了コード §2.3: ルートの設定が有効な`workspace.id`を明示しないとき、`multiWorkspace`は`{id: null, path: "."}`、`workspaces`は空配列。
  それ以外の全体事前検査の停止では、明示した有効なルートのIDを使う（`MULTI-019`は`platform`）。§3: 診断の効果の最悪値が状態になる
  （`error` > `failed` > `blocked`）ので、`failed`と`blocked`が並べば`failed`／1。§5: 同一性を構成できない診断の`workspaceId`は`null`。§7: 診断の順序。
- 診断レジストリ: `MULTI-CONFIG`は`SPEC-MULTI-CONFIG-001`（`error`／`failed`）、`MULTI-GIT`は`SPEC-MULTI-GIT-001`（`environment`、`blocked`）。

## 入力と起動

基本のリポジトリは`MULTI-040`の群と同じ（ルート`platform`、メンバー`web`〈`apps/web`〉と`api`〈`services/api`〉）。ルートの設定だけを、原因になる1か所だけ変える。
Git不在の作り方も`MULTI-040-01`〜`08`と同じ（`setup.git: false`と`invocation.env.PATH=/dev/null`で、Gitの実行ファイルを見つけられない環境を作る）。
Gitのある入力は、この群にはない。

| fixture | 操作と実行ディレクトリ | ルートの設定 | 結果 |
|---|---|---|---|
| `MULTI-058-01` | `doctor --all-workspaces`、`.` | `multiWorkspace.members: []` | `failed`／1。`SPEC-MULTI-GIT-001`、`SPEC-MULTI-CONFIG-001`（`multiWorkspace.members`）。`checks`は`core`・`git`（`blocked`）・`catalog`（`failed`）。`multiWorkspace`は`{platform, .}` |
| `MULTI-058-02` | `doctor`（単独）、`.` | `multiWorkspace.exclude: [../x]` | `failed`／1。`SPEC-MULTI-GIT-001`、`SPEC-MULTI-CONFIG-001`（`multiWorkspace.exclude`）。`checks`は`058-01`と同じ。単独結果（`workspace`は`{platform, .}`） |
| `MULTI-058-03` | `doctor --all-workspaces`、`.` | `workspace`キーなし（ルートの`workspace.id`の省略） | `failed`／1。`SPEC-MULTI-CONFIG-001`（`workspace.id`、`workspaceId: null`）、`SPEC-MULTI-GIT-001`。`checks`は`058-01`と同じ。`multiWorkspace`は`{null, .}` |
| `MULTI-058-04` | `doctor --all-workspaces`、`.` | 妥当 | 対照: `blocked`／2。`SPEC-MULTI-GIT-001`だけ。`checks`は`core`・`git`（`blocked`）で`catalog`を置かない |
| `MULTI-058-05` | `doctor --all-workspaces`、`.` | 妥当。`web`の設定の`workspace.id`が`frontend`、カタログにない`tools/x`に設定がある | 対照: `blocked`／2。`SPEC-MULTI-GIT-001`だけ。ルートの候補の位置に依存する検査（メンバーのIDの不一致、未登録の設定）は行わない |
| `MULTI-058-06` | `check --all-workspaces`、`.` | `multiWorkspace.members: []`（`058-01`と同じ） | 対照: `blocked`／2。`SPEC-MULTI-GIT-001`だけ。`revision: null`、`scope: all-workspaces`、`workspaces`は空 |

診断の文言は、既存のfixtureが固定済みの承認済みの文字列だけを使う（`Coreの出力文言のレビュー記録.md`）。`members`の0件は「設定キーmultiWorkspace.membersは1件以上指定してください」
（`MULTI-037-26`）、除外のパスは「除外のパスの形式が不正です」（`MULTI-037-09`）、ルートのIDの省略は「ルートワークスペースの設定キーworkspace.idがありません」
（`MULTI-043-03`）、Gitの不在は「Gitのリポジトリの境界を確定できません」（`MULTI-019`）。生成器は、これらの文字列を既存の生成器から取り込む。

## 期待値の導き方（Coreの出力を根拠にしない）

1. **診断の集合と状態**。`reference_expected`が、ルートの設定の本文（`classify_catalog`）と操作から導く。全操作が`SPEC-MULTI-GIT-001`（`blocked`）を返す。
   `doctor`だけが、本文にカタログの不適合があれば`SPEC-MULTI-CONFIG-001`（`failed`）を加える。状態は最悪値で、不適合があれば`failed`／1、なければ`blocked`／2。
2. **診断の並び**。ルートの`workspace.id`の省略は、同一性を構成できない`workspaceId: null`のファイルの発生元なので、環境の発生元より前（`SPEC-MULTI-CONFIG-001`、`SPEC-MULTI-GIT-001`）。
   `members`と除外のパスの不正は`workspaceId: platform`なので、IDを持たない環境の発生元が先（`SPEC-MULTI-GIT-001`、`SPEC-MULTI-CONFIG-001`）。結果・診断・終了コード §7と、
   `MULTI-040`の並びの規則（2026-10-20のユーザーの決定）に従う。
3. **検査項目**。`core`は`passed`、`git`は`blocked`。`catalog`は、カタログの不適合があるときだけ`failed`で置く（`doctor` §3）。
4. **不適合の分類**。ルートの`workspace.id`の省略を最優先、次に`multiWorkspace.members`の形状、次に除外のパス（`..`の要素、絶対パス、空）の順に調べる（`MULTI-043`、ADR-064）。
5. **陰性対照**。`check_conditions`が、準備手順の後にGitのリポジトリでないこと、ルートの設定が原因の1か所以外は妥当なカタログと同じであること、`058-05`ではカタログの形状が妥当でメンバーの不備だけがあること、
   単独の`doctor`の対象が`multiWorkspace`を宣言することを入力から確かめる。監査の回帰試験（`fixtures/test_conformance_audit.py`の`test_multi_doctor_git_catalog_*`）が、
   期待結果・起動条件・副作用の改変、修正前のCoreの出力への取り違え、入力の欠落・追加・原因を消す書換えを拒否することを確かめる。

## 陰性対照（修正前のCoreでの実測）

修正前のCore（`origin/main`の`plugins/bitz-core`、コミット`496eecb8`）で、追加の6件を実行した。結果は`passed` 3件、`failed` 3件、`error` 0件で、失敗した3件は`MULTI-058-01`〜`03`だけである。
失敗の内容は3件とも同じで、診断が1件（期待は2件）、`checks`が2件（期待は3件）、状態が`blocked`（期待は`failed`）、終了コードが2（期待は1）である。
カタログの不適合を隠し、`SPEC-MULTI-GIT-001`だけを返す。対照の`058-04`〜`06`は修正前のCoreでも通り、修正後も通り続けることを要求する。
修正後のCore（このブランチ）では6件がすべて`passed`である。

| fixture | 修正前のCore | 失敗の内容 |
|---|---|---|
| `MULTI-058-01`〜`03` | 失敗 | `SPEC-MULTI-CONFIG-001`を返さない。`catalog`を置かない。`blocked`／2 |
| `MULTI-058-04`〜`06` | **通る** | 対照: カタログが妥当、またはルートの候補の位置に依存する検査の不備だけ、または`doctor`以外の操作は、`SPEC-MULTI-GIT-001`だけ |

## 規範から導けなかった点・固定の程度

- **メンバーのパスの形式の不正の扱い**。`doctor` §3が挙げるルートの設定の本文だけで判定できるカタログの不適合は、ルートの`workspace.id`の省略、`multiWorkspace`の型と件数、
  除外のパスの不正である（ADR-070）。メンバーのパス（`SPEC-MULTI-PATH-001`の字句の不正、重複、入れ子）は、メンバーの検査の一部としてルートの候補の位置に依存する検査と同じ段階で行うため、
  規範は「メンバーの設定、メンバーのパス、未登録の設定など、ルートの候補の位置に依存する検査は行わない」と書く。
  この群は、メンバーのパスの不正を固定しない（`058-05`はメンバーのIDの不一致と未登録の設定だけを置く）。
- **`multiWorkspace`の形状と除外のパスの例**。形状の不正には複数の種類がある（`multiWorkspace`の値の欠落、マッピングでない、`maxMembers`の範囲外、`members`の欠落・非配列・0件・要素の型）が、
  承認済みの文言を既存のfixtureが固定している`members: []`だけをfixtureにした。除外のパスも、字句の不正（`../x`）だけをfixtureにした。
  ほかの形状と、除外のパスの`.spec`・重複・入れ子・複数の要素の不正は、単体試験（`tests/bitz-core/test_doctor_no_git_catalog.py`）が、Gitがある場合の`doctor`と同じ診断と件数になることを確かめる。
  単体試験は、Gitはあるがリポジトリの外で実行した場合も確かめる（この群のfixtureはGit不在だけを置く）。
- **`failed`と`blocked`が並ぶときの`checks[]`**。最上位の`checks[]`の`git`は`blocked`、`catalog`は`failed`と、検査項目ごとの原因を保つ。状態の集約だけが最悪値の`failed`になる。
- **Git不在の`check --all-workspaces`の`multiWorkspace.id`**。ルートが有効な`workspace.id`を明示していれば、`MULTI-019`の`doctor`と同じく`platform`とする（`058-06`）。
  ルートの`workspace.id`を省略した`check`の`null`は、既存の`MULTI-045-11`が固定している。
