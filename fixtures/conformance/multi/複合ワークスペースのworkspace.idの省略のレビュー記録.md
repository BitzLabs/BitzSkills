# 複合ワークスペースのworkspace.idの省略のfixtureのレビュー記録

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合ワークスペース)の
`MULTI-043-01`〜`MULTI-043-18`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（[ADR-051](../../../docs/02.設計書/10_決定記録/ADR-051_適合fixtureの変更手続きを確定する.md)の追加）。
生成器と監査は`fixtures/conformance/multi_workspace_id_fixtures.py`である。

## 追加の理由（実装の確認事項C42）

複合ワークスペース仕様 §2は、ルートワークスペースと全メンバーで`workspace.id`を必須とし、カタログの`id`とメンバー設定の`workspace.id`を一致させると定める。
§4.1は、複合ワークスペースでは既定値`root`を有効なIDとみなさず、既定値`root`の写像は`multiWorkspace`のない基準版との比較だけに使うと定める。
欠陥は`a2ca532b`より前からあり、陰性対照に使ったコミットは`b50d1596`（と、前回の修正の時点の`8040e4ab`）である。修正前のCoreは、次の4つを通していた。

- 複合ワークスペースのルートの`.spec/bitz.yaml`が`workspace.id`を省略しても、既定値`root`をルートのIDとして成功した。
- メンバーが`workspace.id`を省略し、カタログの`id`が`root`のときも、既定値`root`をメンバーのIDとして一致とみなした。
- ルートが`workspace.id`を省略したまま、スキーマまたはEARS-AIのメジャーバージョンの非対応で止まるとき、ルートの同一性（`multiWorkspace.id`と診断の`source.workspaceId`）に
  設定の読込みが補った既定値`root`を使った（`8040e4ab`まで）。
- `multiWorkspace:`をキーだけ（値なし）で宣言したルートを、宣言なしと見て、`workspace.id`の省略を通した。

この群は、省略を全体事前検査で止めること、止めた結果の`multiWorkspace`・`workspace`・`source.workspaceId`の`null`の扱い、
ほかのカタログの不備との優先、既定値`root`を明示した対照を固定する。既存のfixtureのルートとメンバーは、すべて`workspace.id`を明示しているので、既存の入力と期待値は変えない。

## 根拠の規範文

- 複合ワークスペース仕様 §2: 「ルートワークスペースと全メンバーで`workspace.id`を必須」、「カタログの`id`とメンバー設定の`workspace.id`は一致させる」。§4.1: 既定値`root`は`multiWorkspace`のない基準版の写像だけ。
- 診断レジストリ: `MULTI-CONFIG`（`SPEC-MULTI-CONFIG-001`、`error`／`failed`、`stop-multi-workspace`、900、「ルートの条件」）、
  `MULTI-MEMBER`（`SPEC-MULTI-MEMBER-001`、910、「カタログのIDと不一致」）。
- 結果・診断・終了コード §2: 有効なルートワークスペースのIDを構成できない全体結果は`multiWorkspace`を`{"id": null, "path": "."}`、`workspaces`を空配列にする。
  停止した単独結果の`workspace.id`は、ルートでは明示した有効なIDを持つときだけ、メンバーではカタログのIDと一致するときだけそのID、それ以外は`null`。
  §5: ルートのIDの不正で同一性を構成できない診断の`source.workspaceId`は`null`。複合ワークスペースのルートの設定が有効な`workspace.id`を明示しない場合も、
  停止の原因（スキーマまたはEARS-AIのメジャーバージョンの非対応、Gitの境界を確定できないことを含む）によらず、有効なルートワークスペースのIDを構成できないものとし、
  既定値`root`を有効なIDとみなさない（2026-10-25の明記、コミット`706eae6d`）。
- 複合ワークスペース仕様 §2.1: `multiWorkspace`の宣言はキーの有無で判定する。
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
| `root-omitted-ears` | `root-omitted`で、ルートの`earsAi`を`2.0`にする（Coreが対応するメジャーバージョンは1） | `13`、`15` |
| `root-omitted-schema` | `root-omitted`で、ルートの`schemaVersion`を`2.0`にする | `14`、`16` |
| `root-omitted-empty-declaration` | ルートが`workspace`キーを持たず、`multiWorkspace:`をキーだけ（値なし）で宣言する。メンバー`web`、`api`の設定は`id: web`、`id: api`を明示して置く。ルートのREQ-001を置く | `17`、`18` |

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
| `MULTI-043-13` | `.`、`check --all-workspaces --base HEAD` | `blocked`／2。`SPEC-EARS-VERSION-001`の1件（`source`は`{file, workspaceId: null, path: .spec/bitz.yaml, key: earsAi}`）。`multiWorkspace`は`{null, .}`、`workspaces`は空 |
| `MULTI-043-14` | `.`、`check --all-workspaces --base HEAD` | `blocked`／2。`SPEC-CONFIG-SCHEMA-001`の1件（`key`は`schemaVersion`、`workspaceId`は`null`）。`multiWorkspace`は`{null, .}` |
| `MULTI-043-15` | `.`、`doctor --all-workspaces` | `blocked`／2。`SPEC-DOCTOR-EARS-001`の1件（`workspaceId`は`null`、`suggestedAction`つき）。`checks[]`は`core`・`git`が`passed`、`catalog`が`blocked`。`multiWorkspace`は`{null, .}` |
| `MULTI-043-16` | `.`、`doctor --all-workspaces` | `blocked`／2。`SPEC-CONFIG-SCHEMA-001`の1件（`workspaceId`は`null`）。`checks[]`は`15`と同じ |
| `MULTI-043-17` | `.`、`check --all-workspaces --base HEAD` | `failed`／1。`01`と同じ（`SPEC-MULTI-CONFIG-001`の1件、`multiWorkspace`は`{null, .}`、`workspaces`は空） |
| `MULTI-043-18` | `.`、`check --base HEAD` | `failed`／1。`04`と同じ（`workspace`は`{null, .}`） |

## 期待値の導き方（Coreの出力を根拠にしない）

1. **原因と`workspace`**。`reference_decision`が、入力の木構造だけから、ルートの`workspace.id`の有無、メンバーの明示したIDとカタログのIDの一致、実行ディレクトリの最も近い設定を導き、
   停止の原因（`root-id`、`member-id`、`ears-version`、`schema-version`、なし）、`multiWorkspace.id`（ルートが明示したID、省略なら`null`）、単独の操作の`workspace`を返す。リテラルの期待値がこの結果と一致することを要求する。
   - ルートの省略はメンバーの確認より先に判定する（ユーザーの決定）。そのため`08`と`09`の原因は`root-id`になる。
   - ルートの設定の版の非対応は、設定の検査より先にその診断で止める。ルートが有効な`workspace.id`を明示しなければ、停止の原因によらず同一性は`null`のままである（`13`〜`16`）。
     診断のコードは既存の版の非対応の fixture（`MULTI-033`、`MULTI-040-02`、`MULTI-040-06`）に揃える。`doctor`のEARS-AIの非対応だけ`SPEC-DOCTOR-EARS-001`（修復手順つき）、`catalog`は`blocked`。
   - メンバーからの単独の操作の`workspace.id`は、そのメンバーの明示したIDがカタログのIDと一致するときだけ（`05`は`web`、`11`は省略なので`null`）。
2. **診断の発生元**。ルートの省略は、ルートのIDを構成できないので`source.workspaceId`が`null`、`key`が`workspace.id`。
   版の非対応で止まる場合も、`workspaceId`は`null`で、`key`は`earsAi`または`schemaVersion`。
   メンバーの省略は、ルートのIDが明示した有効な値なので`workspaceId`が`platform`、`key`が`multiWorkspace.members`（`MULTI-036-03`のメンバーの設定の不在の診断と同じ発生元の形）。
3. **原因だけを持つ入力であること**。`check_conditions`が、準備手順の後の入力とGitの状態から、次を確かめる。
   - `01`〜`07`: ルートの設定が`workspace`キーを持たない（`workspace: {}`などの別の形ではない）。メンバーは明示したIDがカタログのIDと一致し、未登録の設定を持たない。
     つまり、修正前のCoreが成功する構成で、原因はルートの省略だけである。
   - `08`: `api`のディレクトリは実在し、設定は存在しない。カタログにない設定がGitで追跡されている。
   - `09`: `web`の明示したIDだけがカタログのIDと異なる。
   - `10`、`11`: ルートは明示し、カタログの`id`が`root`のメンバーだけが省略する。
   - `12`: ルートが`workspace.id: root`を明示し、メンバーも明示する。
   - `13`〜`16`: ルートの`earsAi`だけ、または`schemaVersion`だけが`2.0`（ほかの版は`1.0`）で、ルートは`workspace`キーを持たない。メンバーは明示し、未登録の設定を持たない。
   - `17`、`18`: `multiWorkspace`はキーがあって値がない（メンバーの一覧を持たない）。メンバーの設定は実在し、明示したIDを持つ。
   - すべて: Gitのリポジトリで、作業ツリーはコミット済みと同じ。

## 陰性対照（修正前のCoreでの実測）

修正前のCoreとして、次の2つのコミットの`plugins/bitz-core`を`git archive`で取り出し、それぞれ`run_conformance.py --step 5`を実行した。
修正後のCore（コミット`abdaee78`）では498件（既存の480件と追加の18件）がすべて通過する。

- `b50d1596`（`workspace.id`の省略を全く止めない状態）: `passed` 481件、`failed` 17件、`error` 0件。失敗した17件は`MULTI-043-01`〜`11`と`13`〜`18`だけで、
  既存の480件と`MULTI-043-12`は通過する。
- `8040e4ab`（ルートの省略とメンバーの省略は止めるが、版の非対応と空の宣言を見落とす状態）: `passed` 492件、`failed` 6件、`error` 0件。失敗した6件は`MULTI-043-13`〜`18`だけである。

`b50d1596`での内訳は次のとおりである（`13`〜`18`の差は`8040e4ab`でも同じ）。

| fixture | `b50d1596` | 失敗の内容 |
|---|---|---|
| `MULTI-043-01` | 失敗 | `passed`／0。`multiWorkspace.id`が`root`、`workspaces`が3件、診断なし |
| `MULTI-043-02` | 失敗 | `blocked`／2。ルートの省略を見ず、既定値`root`のルートのREQ-001を検証対象にする（ルートが`CTX-COVERAGE-TEST-001`による`blocked`、`targetResults`は1件、メンバー`api`・`web`は`SPEC-VERIFY-BLOCKED-002`の警告）。`multiWorkspace.id`が`root`、診断なし |
| `MULTI-043-03` | 失敗 | `passed`／0。`catalog`が`passed`、`multiWorkspace.id`が`root`、`workspaces`が3件 |
| `MULTI-043-04` | 失敗 | `passed`／0。`workspace.id`が`root` |
| `MULTI-043-05` | 失敗 | `passed`／0。診断なし（`workspace`は同じ） |
| `MULTI-043-06` | 失敗 | `blocked`／2。`workspace.id`が`root`、ルートのREQ-001が`CTX-COVERAGE-TEST-001`による`blocked`（`targetResults`は1件） |
| `MULTI-043-07` | 失敗 | `passed`／0。`workspace.id`が`root`、`checks`が9件 |
| `MULTI-043-08` | 失敗 | 診断が`SPEC-MULTI-MEMBER-001`（「メンバーの.spec/bitz.yamlがありません」）。ルートの省略を見ない |
| `MULTI-043-09` | 失敗 | 診断が`SPEC-MULTI-MEMBER-001`（「メンバーの設定キーworkspace.idがカタログのIDと一致しません」）。ルートの省略を見ない |
| `MULTI-043-10` | 失敗 | `passed`／0。メンバーの省略をカタログの`id: root`と一致とみなす |
| `MULTI-043-11` | 失敗 | `passed`／0。`workspace.id`が`root` |
| `MULTI-043-12` | **通る** | 対照。修正後も通り続けることを要求する |
| `MULTI-043-13`〜`16` | 失敗 | 版の非対応の診断の`source.workspaceId`と`multiWorkspace.id`（`doctor`も同じ）が`root`（期待は`null`） |
| `MULTI-043-17` | 失敗 | `blocked`／2。診断が`SPEC-MULTI-UNREGISTERED-001`の2件（メンバーの設定がカタログにない）で、`multiWorkspace.id`が`root` |
| `MULTI-043-18` | 失敗 | `passed`／0。`workspace.id`が`root` |

`MULTI-043-02`と`06`の差は、2026-10-25にレビューの指摘で実測し直した。当初は「検証対象なし」と書いたが誤りで、修正前のCoreは既定値`root`のルートのREQ-001を検証対象にした。

## 規範から導けなかった点・固定の程度

- `SPEC-MULTI-MEMBER-001`（メンバーのIDの不一致、省略）の`source`。診断レジストリは発生元の種別（`file`）だけを定め、`path`と`key`は定めない。
  この群は、既存のメンバーの設定の不在の診断（`MULTI-036-03`）と同じ、ルートの`.spec/bitz.yaml`の`multiWorkspace.members`を発生元にする既存の形に合わせた。
- ルートの`workspace`キーが空のマッピング（`workspace: {}`）、`id`が文字列でない、空文字列の場合。この群は`workspace`キーそのものを持たない形だけを固定する。
  ほかの形が`SPEC-MULTI-CONFIG-001`になるかは、設定のスキーマ（`SPEC-CONFIG-SCHEMA-001`など）の規則に属し、この群の範囲外とする。
- メンバーの設定の不在とIDの不一致が、ルートの省略なしに重なる場合の診断の並び。この群は、ルートの省略が単独で止めることだけを固定する（`08`、`09`）。
- 入れ子の複合ワークスペース（`multiWorkspace`を宣言したメンバー）。`SPEC-MULTI-MEMBER-001`の別の原因で、この群の範囲外とする。
- ユーザーの決定（2026-10-25）で、次の2点を定めた。
  1. ルートの`workspace.id`の省略は、複合ワークスペース仕様 §2.1の除外を信用できる条件を変えない。条件は`multiWorkspace`の設定不適合だけを見る。
     単体試験（`tests/bitz-core/test_multi_root_workspace_id.py`の`ExcludeTrustTests`）が固定し、この群の fixture では固定しない。
  2. Gitの境界を確定できず止まるときも、ルートの同一性は`null`である（既定値`root`を使わない）。単体試験（同じファイルの`test_git_boundary_unknown_keeps_null_identity`、
     `test_doctor_without_git_has_null_identity`）が固定し、この群の fixture では固定しない。Gitの不在と設定の不備が重なる`doctor`の診断の並びが、既存の`MULTI-040-01`〜`03`の規則
     （ADR-065）にどう載るかは、この群で新たに固定しないため。
  ルートの版の非対応で止まるときの`null`（`13`〜`16`）は、規範の明記（コミット`706eae6d`）で規範になった。この明記より前は、規範文に書かれていなかった。
- 基準版が`multiWorkspace`ありでルートのIDを省略していた（修正前のCoreでは通っていた）リポジトリで、現在版に`workspace.id`を加えると、
  `check --all-workspaces --base <基準版>`は`SPEC-STATE-TRANSITION-001`（「管理済みの仕様文書が削除されています」、`workspaceId`は`root`）で`failed`になる。
  複合ワークスペース仕様 §4.1（写像は`multiWorkspace`のない基準版だけ。ID変更は旧ワークスペースの削除と新しいワークスペースの追加）と整合する既知の挙動であり、fixtureにはしない。

この群の範囲外とするもの。

- 実装の確認事項C58: ルートが`workspace.id`を明示した、`multiWorkspace:`の値のない宣言が、メンバー0件の複合ワークスペースとして成功する（複合ワークスペース仕様 §2に反する）。別の確認事項で扱う。

- `context`。複合ワークスペースの単独の`context`が止まる経路は`MULTI-036-02`と`MULTI-036-07`が固定しており、この群の原因（IDの省略）は同じ全体事前検査の分岐に入る。
  単体試験（`tests/bitz-core/test_multi_root_workspace_id.py`）が`context`を含めて押さえる。
- テキスト形式の出力。この群はJSONだけを固定する。
