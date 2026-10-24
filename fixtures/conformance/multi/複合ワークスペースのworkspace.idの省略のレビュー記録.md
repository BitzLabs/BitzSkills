# 複合ワークスペースのworkspace.idの省略のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-043-01`〜`MULTI-043-12`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/multi_workspace_id_fixtures.py`である。

## 追加の理由（実装の確認事項C42）

複合ワークスペース仕様 §2は、ルートワークスペースと全メンバーで`workspace.id`を必須とし、カタログの`id`とメンバー設定の`workspace.id`を一致させると定める。
§4.1は、省略時の既定値`root`を`multiWorkspace`のない基準版の写像だけに限る。修正前のCore（`a2ca532b`〜`b50d1596`）は、次の2つを通していた。

- 複合ワークスペースのルートの`.spec/bitz.yaml`が`workspace.id`を省略しても、既定値`root`をルートのIDとして成功した。
- メンバーが`workspace.id`を省略し、カタログの`id`が`root`のときも、既定値`root`をメンバーのIDとして一致とみなした。

この群は、省略を全体事前検査で止めること、止めた結果の`multiWorkspace`・`workspace`・`source.workspaceId`の`null`の扱い、
ほかのカタログの不備との優先、既定値`root`を明示した対照を固定する。既存のfixtureのルートとメンバーは、すべて`workspace.id`を明示しているので、既存の入力と期待値は変えない。

## 根拠の規範文

- 複合ワークスペース仕様 §2: 「ルートワークスペースと全メンバーで`workspace.id`を必須」、「カタログの`id`とメンバー設定の`workspace.id`は一致させる」。§4.1: 既定値`root`は`multiWorkspace`のない基準版の写像だけ。
- 診断レジストリ: `MULTI-CONFIG`（`SPEC-MULTI-CONFIG-001`、`error`／`failed`、`stop-multi-workspace`、900、「ルートの条件」）、
  `MULTI-MEMBER`（`SPEC-MULTI-MEMBER-001`、910、「カタログのIDと不一致」）。
- 結果・診断・終了コード §2: 有効なルートワークスペースのIDを構成できない全体結果は`multiWorkspace`を`{"id": null, "path": "."}`、`workspaces`を空配列にする。
  停止した単独結果の`workspace.id`は、ルートでは明示した有効なIDを持つときだけ、メンバーではカタログのIDと一致するときだけそのID、それ以外は`null`。
  §5: ルートのIDの不正で同一性を構成できない診断の`source.workspaceId`は`null`。
- `doctor`仕様 §3: 全体事前検査が非成功なら、最上位の`checks[]`の`catalog`で結果を表す。`doctor`仕様 §8: `suggestedAction`を付ける診断の表。`SPEC-MULTI-CONFIG-001`と`SPEC-MULTI-MEMBER-001`は表にないので付けない。
- 終了コード: `failed`は1（結果・診断・終了コード §3）。
- 単独の操作の全体事前検査: 複合ワークスペース仕様 §7、[ADR-063](../../../docs/02.設計書/10_決定記録/ADR-063_複合ワークスペースの単独操作の全体事前検査を確定する.md)。

ユーザーの決定（2026-10-20、2026-10-25）で固定した点は次のとおりである。

- ルートの省略は、全体事前検査で`SPEC-MULTI-CONFIG-001`の1件だけで、単独に止める。ほかのカタログの不備（メンバーの設定の不在、IDの不一致、未登録の設定）より優先する。
- `summary`は管理者が承認した「ルートワークスペースの設定キーworkspace.idがありません」（[Coreの出力文言のレビュー記録](../Coreの出力文言のレビュー記録.md)の2026-10-25の節）。一字も変えない。
- `source`は`{"kind": "file", "workspaceId": null, "path": ".spec/bitz.yaml", "key": "workspace.id"}`。
- メンバーの省略は、既存の承認済みの文言「メンバーの設定キーworkspace.idがカタログのIDと一致しません」（`SPEC-MULTI-MEMBER-001`）を再利用する。新しい承認ではない。

## 入力と起動

基本のリポジトリは、ルート（`.`）、メンバー`web`（`apps/web`）と`api`（`services/api`）で、すべてコミットし、`--format json`で起動する。
ルートにREQ-001を1件置く（修正前のCoreが成功する構成にするため）。

| 入力の種類 | 内容 | 使うfixture |
|---|---|---|
| `root-omitted` | ルートの設定が`workspace`キーを持たない。メンバーは`id: web`、`id: api`を明示し、カタログのIDと一致する | `01`〜`07` |
| `root-omitted-member-absent` | `root-omitted`から`services/api/.spec/bitz.yaml`を除き（ディレクトリは`src/session.py`で残す）、Gitで追跡するカタログ未登録の`tools/x/.spec/bitz.yaml`を足す | `08` |
| `root-omitted-id-mismatch` | `root-omitted`で、`web`の設定の`id`をカタログと異なる`frontend`にする | `09` |
| `member-omitted` | ルートは`id: platform`を明示。カタログの`id`が`root`のメンバー（`apps/web`）の設定が`workspace`キーを持たない。`api`は明示 | `10`、`11` |
| `explicit-root` | `MULTI-001`の入力の`platform`を`root`にする（ルートの`workspace.id: root`と、メンバーの修飾した参照`root::`）。ルートが`root`を明示する対照 | `12` |

| fixture | 実行ディレクトリと引数 | 結果 |
|---|---|---|
| `MULTI-043-01` | `.`、`check --all-workspaces --base HEAD` | `failed`／1。`SPEC-MULTI-CONFIG-001`の1件。`multiWorkspace`は`{null, .}`、`workspaces`は空 |
| `MULTI-043-02` | `.`、`verify --all-workspaces` | 同上。`revision`は`commit`と`dirty` |
| `MULTI-043-03` | `.`、`doctor --all-workspaces` | 同上。`checks[]`は`core`・`git`が`passed`、`catalog`が`failed`。`suggestedAction`なし |
| `MULTI-043-04` | `.`、`check --base HEAD` | 同じ診断。`workspace`は`{null, .}`。`scope`は`changed`、`selection`の件数は0 |
| `MULTI-043-05` | `apps/web`、`check --base HEAD` | 同じ診断。`workspace`は`{web, apps/web}`（`web`が明示したIDがカタログのIDと一致する） |
| `MULTI-043-06` | `.`、`verify` | 同じ診断。`workspace`は`{null, .}`。`scope`は`all`、`targetResults`・`commands`は空 |
| `MULTI-043-07` | `.`、`doctor` | 同じ診断。`workspace`は`{null, .}`。`checks[]`は`catalog`が`failed` |
| `MULTI-043-08` | `.`、`check --all-workspaces --base HEAD` | `01`と同じ。メンバーの設定の不在と未登録の設定が重なっても、`SPEC-MULTI-CONFIG-001`の1件だけ |
| `MULTI-043-09` | `.`、`check --all-workspaces --base HEAD` | `01`と同じ。メンバーのIDの不一致が重なっても、`SPEC-MULTI-CONFIG-001`の1件だけ |
| `MULTI-043-10` | `.`、`check --all-workspaces --base HEAD` | `failed`／1。`SPEC-MULTI-MEMBER-001`の1件（`source.workspaceId`は`platform`、`key`は`multiWorkspace.members`）。`multiWorkspace`は`{platform, .}`、`workspaces`は空 |
| `MULTI-043-11` | `apps/web`、`check --base HEAD` | `10`と同じ診断。`workspace`は`{null, apps/web}` |
| `MULTI-043-12` | `.`、`check --all-workspaces --base HEAD` | `passed`／0。`MULTI-001`と同じ形で、`multiWorkspace`は`{root, .}`、`workspaces`は`root`・`api`・`web` |

## 期待値の導き方（Coreの出力を根拠にしない）

1. **原因と`workspace`**。`reference_decision`が、入力の木構造だけから、ルートの`workspace.id`の有無、メンバーの明示したIDとカタログのIDの一致、実行ディレクトリの最も近い設定を導き、
   停止の原因（`root-id`、`member-id`、なし）、`multiWorkspace.id`（ルートが明示したID、省略なら`null`）、単独の操作の`workspace`を返す。リテラルの期待値がこの結果と一致することを要求する。
   - ルートの省略はメンバーの確認より先に判定する（ユーザーの決定）。そのため`08`と`09`の原因は`root-id`になる。
   - メンバーからの単独の操作の`workspace.id`は、そのメンバーの明示したIDがカタログのIDと一致するときだけ（`05`は`web`、`11`は省略なので`null`）。
2. **診断の発生元**。ルートの省略は、ルートのIDを構成できないので`source.workspaceId`が`null`、`key`が`workspace.id`。
   メンバーの省略は、ルートのIDが明示した有効な値なので`workspaceId`が`platform`、`key`が`multiWorkspace.members`（`MULTI-036-03`のメンバーの設定の不在の診断と同じ発生元の形）。
3. **原因だけを持つ入力であること**。`check_conditions`が、準備手順の後の入力とGitの状態から、次を確かめる。
   - `01`〜`07`: ルートの設定が`workspace`キーを持たない（`workspace: {}`などの別の形ではない）。メンバーは明示したIDがカタログのIDと一致し、未登録の設定を持たない。
     つまり、修正前のCoreが成功する構成で、原因はルートの省略だけである。
   - `08`: `api`のディレクトリは実在し、設定は存在しない。カタログにない設定がGitで追跡されている。
   - `09`: `web`の明示したIDだけがカタログのIDと異なる。
   - `10`、`11`: ルートは明示し、カタログの`id`が`root`のメンバーだけが省略する。
   - `12`: ルートが`workspace.id: root`を明示し、メンバーも明示する。
   - すべて: Gitのリポジトリで、作業ツリーはコミット済みと同じ。

## 陰性対照（修正前のCoreでの実測）

修正前のCore（コミット`b50d1596`の`plugins/bitz-core`を`git archive`で取り出したもの）で、`run_conformance.py --step 5`を実行した。

全492件（既存の480件と追加の12件）の結果は`passed` 481件、`failed` 11件、`error` 0件で、失敗した11件は`MULTI-043-01`〜`11`だけである（既存の480件と`MULTI-043-12`は通過する）。
修正後のCore（コミット`fbbd89c8`）では492件がすべて通過する。内訳は次のとおりである。

| fixture | 修正前のCore | 失敗の内容 |
|---|---|---|
| `MULTI-043-01` | 失敗 | `passed`／0。`multiWorkspace.id`が`root`、`workspaces`が3件、診断なし |
| `MULTI-043-02` | 失敗 | `blocked`／2（検証対象なし）。`multiWorkspace.id`が`root`、`workspaces`が3件、診断なし |
| `MULTI-043-03` | 失敗 | `passed`／0。`catalog`が`passed`、`multiWorkspace.id`が`root`、`workspaces`が3件 |
| `MULTI-043-04` | 失敗 | `passed`／0。`workspace.id`が`root` |
| `MULTI-043-05` | 失敗 | `passed`／0。診断なし（`workspace`は同じ） |
| `MULTI-043-06` | 失敗 | `blocked`／2。`workspace.id`が`root`、`targetResults`が1件 |
| `MULTI-043-07` | 失敗 | `passed`／0。`workspace.id`が`root`、`checks`が9件 |
| `MULTI-043-08` | 失敗 | 診断が`SPEC-MULTI-MEMBER-001`（「メンバーの.spec/bitz.yamlがありません」）。ルートの省略を見ない |
| `MULTI-043-09` | 失敗 | 診断が`SPEC-MULTI-MEMBER-001`（「メンバーの設定キーworkspace.idがカタログのIDと一致しません」）。ルートの省略を見ない |
| `MULTI-043-10` | 失敗 | `passed`／0。メンバーの省略をカタログの`id: root`と一致とみなす |
| `MULTI-043-11` | 失敗 | `passed`／0。`workspace.id`が`root` |
| `MULTI-043-12` | **通る** | 対照。修正後も通り続けることを要求する |

## 規範から導けなかった点・固定の程度

- `SPEC-MULTI-MEMBER-001`（メンバーのIDの不一致、省略）の`source`。診断レジストリは発生元の種別（`file`）だけを定め、`path`と`key`は定めない。
  この群は、既存のメンバーの設定の不在の診断（`MULTI-036-03`）と同じ、ルートの`.spec/bitz.yaml`の`multiWorkspace.members`を発生元にする既存の形に合わせた。
- ルートの`workspace`キーが空のマッピング（`workspace: {}`）、`id`が文字列でない、空文字列の場合。この群は`workspace`キーそのものを持たない形だけを固定する。
  ほかの形が`SPEC-MULTI-CONFIG-001`になるかは、設定のスキーマ（`SPEC-CONFIG-SCHEMA-001`など）の規則に属し、この群の範囲外とする。
- メンバーの設定の不在とIDの不一致が、ルートの省略なしに重なる場合の診断の並び。この群は、ルートの省略が単独で止めることだけを固定する（`08`、`09`）。
- 入れ子の複合ワークスペース（`multiWorkspace`を宣言したメンバー）。`SPEC-MULTI-MEMBER-001`の別の原因で、この群の範囲外とする。

この群の範囲外とするもの。

- `context`。複合ワークスペースの単独の`context`が止まる経路は`MULTI-036-02`と`MULTI-036-07`が固定しており、この群の原因（IDの省略）は同じ全体事前検査の分岐に入る。
  単体試験（`tests/bitz-core/test_multi_root_workspace_id.py`）が`context`を含めて押さえる。
- テキスト形式の出力。この群はJSONだけを固定する。
