# `context`の早期に返す結果の`revision`のfixtureのレビュー記録

[適合fixture仕様 §6.11](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#611-公開結果スキーマと既定表示)の
`SINGLE-166-01`〜`11`を扱う。いずれもレビュー済みの期待値であり、Coreの挙動を観測したものではない
（ADR-051の追加。実装の確認事項C45）。群は`fixtures/conformance/context_stop_revision_fixtures.py`、Stepは3である。

## 2026-10-24: 追加

### 何を固定するか

単一ワークスペースの`context`は、コンテキスト一式を作る前に結果を返す場合がある。設定がない、設定の停止、起点がない、
強い関係の検査の失敗（2つの経路）、閉包の上限の超過、集合外の`--expand`、提示の絶対上限の超過、`--expect-digest`の不一致である。
Coreは、この早期に返す結果の9つの経路すべてで、Gitとコミットがあっても`revision`を常に`null`にしていた
（複合ワークスペースだけは、別の関数で`revision`を入れていた）。コンテキスト一式を作って返す経路（成功と、`--detail`の提示で失敗しない結果）は、
規範どおりだった。
既存の`context`の失敗のfixture（`SINGLE-046`〜`050`、`147`〜`148`、`150`〜`152`など）は、準備手順がコミットを作らない
（コミットのないリポジトリ）ので、`revision: null`が正しく、この欠陥を検出できなかった。

### 根拠の規範文

| 規範文 | 内容 |
|---|---|
| [結果・診断・終了コード §2](../../../docs/03.詳細設計/00_共通契約/01_結果・診断・終了コード.md#2-結果の形) | 「`context`または`verify`の`null`でないオブジェクトは、40桁の小文字16進数の`commit`と真偽値の`dirty`だけを持つ」。「単一ワークスペースでGit不在、またはコミットのないリポジトリであれば、`revision: null`とする」。`null`にする条件は、この2つ（Git不在、コミットなし）だけで、結果の状態や、コンテキスト一式を作ったかどうかを条件にしない |
| 同 §2 | 「非成功でも、選択した種類に必須のフィールドを省略しない」。`context`は`revision`を必須のフィールドとする |
| [`context` §3](../../../docs/03.詳細設計/03_操作仕様/01_context.md#3-処理)、診断レジストリ | 診断の種類ごとの状態（`failed`／`blocked`／`error`）と、状態の検査と強い関係の検査が独立した原因として両方の診断を返すこと |

`dirty`は「実行時の状態」であり、作業ツリーの変更または未追跡のファイルの有無で決まる。`SINGLE-166-09`は未追跡のファイル1つで固定する。

### fixtureごとの期待値

期待値は、元のfixtureがレビュー済みの完全結果から`revision`だけを変えたものである。元のfixtureは、同じ入力・同じ起動をコミットのない
リポジトリで実行する対照（`revision: null`）なので、この群は同じ入力に、Gitの状態だけを加える。状態、終了コード、診断、`resolution`、
`contextDigest`は、元のfixtureが規範文から導いてレビュー済みの値のままである。診断の文言は新しく足していない。

| fixture | 元のfixture | 原因（早期に返す結果） | Git | 状態／終了コード | `workspace.id` | `revision` |
|---|---|---|---|---|---|---|
| `SINGLE-166-01` | `SINGLE-152` | 設定がない（`SPEC-WORKSPACE-MISSING-001`） | コミットあり、クリーン | `blocked`／2 | `null` | `{commit, dirty: false}` |
| `SINGLE-166-02` | `SINGLE-150` | 設定の型の不正（`SPEC-CONFIG-SCHEMA-001`） | コミットあり、クリーン | `error`／3 | `null` | `{commit, dirty: false}` |
| `SINGLE-166-03` | `SINGLE-050` | 起点がない（`CTX-ROOT-MISSING-001`） | コミットあり、クリーン | `failed`／1 | `root` | `{commit, dirty: false}` |
| `SINGLE-166-04` | `SINGLE-020`の入力 | 強い関係の参照切れ（`SPEC-RELATION-MISSING-001`）。対象展開は誤りを返さない | コミットあり、クリーン | `failed`／1 | `root` | `{commit, dirty: false}` |
| `SINGLE-166-05` | `SINGLE-148` | 状態の診断と型制約の診断が重なる（`CTX-RELATION-TYPE-001`、`CTX-STATE-001`） | コミットあり、クリーン | `failed`／1 | `root` | `{commit, dirty: false}` |
| `SINGLE-166-06` | `SINGLE-048-01` | 閉包の文書数の上限の超過（`CTX-LIMIT-001`） | コミットあり、クリーン | `blocked`／2 | `root` | `{commit, dirty: false}` |
| `SINGLE-166-07` | `SINGLE-047` | 集合外の`--expand`（`CTX-PROJECTION-001`） | コミットあり、クリーン | `failed`／1 | `root` | `{commit, dirty: false}` |
| `SINGLE-166-08` | `SINGLE-046` | `--expect-digest`の不一致（`CTX-STALE-001`） | コミットあり、クリーン | `blocked`／2 | `root` | `{commit, dirty: false}` |
| `SINGLE-166-09` | `SINGLE-050` | 起点がない | コミットあり、未追跡の`docs/notes.md` | `failed`／1 | `root` | `{commit, dirty: true}` |
| `SINGLE-166-10` | `SINGLE-020`の入力 | 強い関係の参照切れ | コミットなし（ステージのみ） | `failed`／1 | `root` | `null` |
| `SINGLE-166-11` | `SINGLE-050` | 起点がない | Git不在（`PATH=/dev/null`） | `failed`／1 | `root` | `null` |

`SINGLE-166-04`だけは、元の`context`のfixtureがない（`SINGLE-020`は`check`の入力と診断）。期待結果は、`SINGLE-020`の入力を`context REQ-001`で
解決した形として書く。診断は`SINGLE-020`のレビュー済みの診断と同じ（`SPEC-RELATION-MISSING-001`、`evidence`は`REQ-999`）で、監査が一致を確かめる。
`contextDigest`は`null`、`resolution.complete`は`false`、`documentCount`は0、`unresolvedStrongRelations`は1、`documents`は空である
（`context` §3の「一部が欠けたコンテキスト一式を成功の結果として返さない」と、`MULTI-038-08`の同じ形による）。

`SINGLE-166-01`〜`08`は、早期に返す経路を1つずつ切り分ける。`04`は対象展開が誤りを返さず強い関係の検査だけが失敗する経路、`05`は対象展開が
状態の診断を返したうえで強い関係の検査の診断を重ねる経路で、別の経路である。

### 陰性対照と陽性対照

- 陰性対照（修正前のCore、コミット`c3110be3`）: `SINGLE-166-01`〜`09`の9件は、`revision`が`null`で不適合になる。`$/revision`の差異だけが報告される。
  `10`・`11`は`null`が正しいので、通過する。
- 陽性対照（修正後のCore）: 11件すべてが通過する。
- 陽性対照: コミットのないリポジトリ（`10`）とGit不在（`11`）で`revision: null`。「結果が早期に返すなら`null`」という誤った修正を検出する
  （修正前の実装は、この2件を通すので、2件の通過は`revision`の規則が2つの条件だけで決まることを固定する）。
  `dirty`の真偽の両方（`01`〜`08`と`09`）を持つ。

### 規範から導けず、fixtureにしなかったもの

- **提示の絶対上限の超過（`CTX-PROJECTION-LIMIT-001`、`SINGLE-049`）。** `revision`の規則は同じ（9つの経路の1つ）だが、入力が約1 MiBあり、
  この群に複製すると適合fixtureの容量が大きく増える。単体試験（`tests/bitz-core/test_context_stop_revision.py`）で確かめる。
- **複合ワークスペースの`context`の失敗。** 修正の前から`revision`を返しており、規範も変わらない。単体試験の対照で確かめる。
- **全体事前検査の停止（`--workspace`の不正など）。** 別の経路で、修正の前から`revision`を返している。この群の範囲外とする。

### 限界

- Coreは実行していない。Coreとの一致は、Gate Bで判定する。
- `dirty`の判定に含める変更の範囲（未追跡のファイルを含む）は、`SINGLE-166-09`が未追跡のファイル1つで固定する。無視されたファイルや、
  ステージされた変更だけの`dirty`は、このmatrixでは区別しない（`SINGLE-165-05`と同じ）。
- 期待値は元のfixtureに依存する。元のfixtureの期待値や準備手順を変える場合は、この群も同じ作業で見直す
  （監査は、元のfixtureの変更を検出して、この群を拒否する）。
