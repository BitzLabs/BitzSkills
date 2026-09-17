# catalogと環境の事前検査 fixture review

[適合fixture仕様 §7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#7-最小matrix-複合workspace)の
`MULTI-005`、`MULTI-006`、`MULTI-007-01`、`MULTI-019`を扱う。いずれもreview済みの期待値であり、
Coreの挙動を観測したものではない。

## 停止の段階を4つに分ける

[複合workspace仕様 §8](../../../docs/03.詳細設計/02_SPECモデル/05_複合workspace仕様.md#8-全体操作の共通規則)は、
全体事前検査が非成功ならmember処理、Context解決、verify commandを開始せず`workspaces: []`で結果を返すと定める。
この群は、そこへ至る4つの入口を1件ずつ固定する。

| fixture | 停止の原因 | 結末 |
|---|---|---|
| `MULTI-005` | catalogにない`--workspace` | 操作結果なし、終了コード4 |
| `MULTI-006` | Gitが知るcatalog未登録の設定 | `SPEC-MULTI-UNREGISTERED-001`／`blocked` |
| `MULTI-007-01` | memberが別memberの配下 | `SPEC-MULTI-PATH-001`／`failed` |
| `MULTI-019` | Git不在 | `SPEC-MULTI-GIT-001`／`blocked` |

`MULTI-005`だけが操作結果を持たない。workspace selectorのinvocation errorは、字句不正でもcatalog不在でも
終了コード4であり、標準出力の結果もreportも作らない。期待値は`cli-output.json`に置き、終了コードと
標準エラー出力1行という契約を、単一workspaceの引数不正fixtureと同じhelperで検査する。
これは`MULTI-025-01/02`の`CTX-ROOT-MISSING-001`（結果を返す終了コード1）と対になる。

## 未登録の設定は「member候補」ではない

`MULTI-006`のcorpusは、goldenのcatalog（`web`、`api`）へ`libs/native/.spec/bitz.yaml`を加える。この設定は
Gitが認識するがcatalogにない。Coreはこれを暗黙memberにせず、全体操作を`blocked`で止める。Diagnosticの`source`は
そのfileだが、所有workspaceがないので`workspaceId`はnullとする。監査は、このpathがcatalogのmember pathと
一致しないことと、fileが実在することを入力から確かめる。

## 入れ子は、設定の有無と切り離す

`MULTI-007-01`のcatalogは`web`（`apps/web`）と`inner`（`apps/web/inner`）を登録する。両memberとも自身の
`bitz.yaml`を持つので、member設定不在（`SPEC-MULTI-MEMBER-001`）ではなくmember pathの入れ子
（`SPEC-MULTI-PATH-001`）だけが原因になる。監査は、片方のpathがもう片方のpathのsegment境界の配下にあること、
各memberが設定を持つことを入力から確かめる。member pathをflatに直した写しは拒否する。

`doctor --all-workspaces`の結果は、globalな検査を最上位の`checks[]`へ置く。`core`、`git`、`catalog`の順とし、
member処理を始めないので`workspaces`は空配列である。同じcatalog診断をmemberへ複製しない。

## Git不在は縮退ではなく遮断である

単一workspaceのGit不在は`checks[]`の`git`をwarningにして失われる保証を列挙する縮退だが、複合workspaceでは
repository境界と所有範囲を確定できないため`blocked`とする
（[doctor仕様 §6](../../../docs/03.詳細設計/03_操作仕様/04_doctor.md#6-git不在)）。
`MULTI-019`は`setup.git: false`と起動環境の`PATH`からGitを外すことでこれを表し、`git`検査を`blocked`、
`catalog`検査は実行しない。副作用の期待値は、空の成功したGit statusではなく明示的なnullを記録する。

## 限界

- Coreは実行していない。Diagnosticの文面、doctorの検査名と並びの実際の値はGate Bで判定する。
- member pathの不正のうち、submodule（`MULTI-007-02`）と別worktree（`MULTI-007-03`）は、fixtureが
  Gitのmetadataを作る手段を必要とするため、この群では扱わない。
- `MULTI-006`は現在snapshotに未登録の設定を置く。base snapshotだけが未登録設定を持つ場合の扱いは、
  `MULTI-017`と`MULTI-018`のbase比較の群で扱う。
