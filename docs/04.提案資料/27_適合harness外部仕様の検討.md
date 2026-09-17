# 適合harness外部仕様の検討

- 状態: Accepted / Reflected（2026-09-17裁定。ADR-046と正本へ反映済み）
- 起草日: 2026-09-17
- 基準branch: `bitz_next`
- 基準commit: `6318817`
- 対象: [適合fixture仕様](../03.詳細設計/00_共通契約/04_適合fixture仕様.md) §3、
  [Core実行環境・CLI基盤契約](../03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md) §4
- 目的: 保留中の`SINGLE-127-15`〜`19`と、後続の`MONO-023`／`024`を作成できる状態にするため、
  適合harnessの外部仕様を確定する

## 1. 結論

単一workspaceの適合fixtureは`SINGLE-127-15`〜`19`の5件を残して準備済みになった。残る5件は、いずれも
fixtureの書き方ではなく、harnessが何を起動し、どの環境を用意するかが規範で決まっていないために作成できない。
次の4論点を裁定し、[ADR-046](../02.設計書/10_決定記録/ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)
として記録した。

| 論点 | 対象fixture | 裁定 |
|---|---|---|
| H1 検査対象の受取り | 全`runner: bitz`、127-17、127-19 | source directoryまたはwheelをCLI引数で受け、Python minorごとに`uv`で隔離環境を作り、console script `bitz`を起動する |
| H2 Git versionの差替え | 127-15、127-16 | manifestの`invocation.gitVersion`で宣言し、harnessが`git --version`だけを偽装するshimを生成する。Coreの版取得を`git --version`の解析と規範化する |
| H3 CPython 3.11 | 127-19 | `invocation.python`で起動版を指定し、加えてGate Cで全matrixを3.11と基準環境の2環境で通す |
| H4 consumer／migration／package runner | 127-17、127-18、MONO-023、MONO-024 | JSON互換はCore同梱の`python -m bitz.compat`、package検査はharness側の新runner `package` |

## 2. 現状の欠落

### 2.1 H1: 検査対象の受取り

適合fixture仕様 §3は「`runner: bitz`はrepositoryで検査対象の`bitz` entry pointを実行する」とだけ述べる。
検査対象をどう受け取り、どの環境へ導入するかがない。127-17は導入済みpackageのmetadataを、127-19は
CPython 3.11での起動を検査するため、実行fileのpathだけを受け取る形では足りない。

### 2.2 H2: Git versionの差替え

`SINGLE-093`は`env.PATH`を`/dev/null`にしてGit不在を再現した。127-15（2.29）と127-16（2.30）は
「Gitはあるが版が異なる」状態を要求する。manifestの`env`は固定文字列なので、一時directoryに置いたshimを
`PATH`で指せない。127-16ではshimがdoctorの他のGit呼出しを実Gitへ渡す必要があり、その実Gitのpathはhostに依存する。
また、Coreが版を`git --version`で得るのか別の手段で得るのかが規範になく、shimが何を偽装すればよいか決まらない。

### 2.3 H3: CPython 3.11

manifestには起動するPythonを指定する手段がない。matrixの必須確認「3.11で利用できない構文／標準library APIへの
依存なし」は、doctorを1回起動するだけでは、doctorが通らないcode pathについて証明できない。

### 2.4 H4: runnerの定義

`runner: consumer`と`runner: migration`は「Core配布物に含める固定compatibility harnessをshellなしで実行」とあるが、
argv、標準出力、終了コードが未定義である。127-17／18はmatrix上`consumer test`だが、JSON consumerではなく
package metadataとlock fileの検査であり、lock fileはsource treeにしか存在しない。Coreの配布物に含めた検査で
Core自身を判定すると自己申告になる。

## 3. 裁定内容

### 3.1 H1

harnessは検査対象をsource directoryまたはwheelで受け取る（manifestへ書かない）。要求されるCPython minorごとに
`uv`でrepositoryと隔離HOMEの外に環境を作り、候補とlock済み依存だけを導入する。`runner: bitz`はその環境の
console script `bitz`をshellなしで起動する。環境構築はinvocation前に行い、Coreの副作用比較には含めない。

代替案の「実行file pathだけを受け取る」は単純だが、H3のversion切替えと127-17の導入metadata検査に別の手段が要る。

### 3.2 H2

`runner: bitz`のinvocationへ任意の`gitVersion`（`<major>.<minor>.<patch>`）を追加する。harnessは
invocation専用の空directoryへ`git` shimを置いて`PATH`の先頭へ加え、shimは`git --version`にだけ
`git version <gitVersion>`を返し、他のargvは作成時に解決した実Gitへ渡す。setupはshimを使わない。
`gitVersion`と`env.PATH`の同時指定は禁止する。

Core実行環境・CLI基盤契約 §4へ、Coreは`git --version`の出力1行目を`git version <major>.<minor>[.<残り>]`として
解析し、major・minorを数値比較すること、非0終了や解析不能はGit不在とすることを追加する。

代替案は、`env`値へ`${FIXTURE_ROOT}`等のplaceholderを許す案と、相対PATH要素をinvocation cwd基準で解決する規則を
Coreへ課す案である。前者はmanifestへhost依存の展開規則を持ち込み、後者はfixtureをGit版判定とは別のCore挙動へ
依存させるため採らない。

### 3.3 H3

`runner: bitz`のinvocationへ任意の`python`（`<major>.<minor>`）を追加する。指定時はそのminorのCPythonで
環境を作り、見つからなければfixture errorとし、skipしない。127-19は`python: "3.11"`でdoctorを起動する。
併せて実装計画のGate Cへ「全matrixを下限CPython 3.11と基準環境の2環境で通す」を追加する。

127-19を削除してGate Cだけにする案は、下限versionでの起動を適合matrixの1行として早期に確認できなくなるため採らない。

### 3.4 H4

`runner: consumer`と`runner: migration`はCore配布物の`bitz.compat`を`python -m bitz.compat <runner> <argv...>`で
起動する。標準出力は`{"outcome": "<値>"}`のJSON 1件とLF、終了コードは`accepted`／`passed`が0、`rejected`が1。
consumerの`result-shape <path>`は共通結果契約 §2の排他的外形で判定する。migrationのcase名は`MONO-024`作成時に
同じ形で固定する。

127-17／18はmatrix上の`consumer test`を新しい`package test`へ改め、fixture harnessの参照実装が行う
`runner: package`とする。caseは`metadata`と`dependencies`で、出力と終了コードはconsumerと同じである。

全runnerをCore同梱にする案はlock fileに届かず自己申告になり、全runnerをharness側にする案は`MONO-023`が
Coreではなくharnessを検査することになるため採らない。

## 4. 反映先

- [ADR-046](../02.設計書/10_決定記録/ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)
- 適合fixture仕様 §3（runner表、manifest key、§3.4 検査対象と実行環境）、matrix 127-17／18のoperation表記
- Core実行環境・CLI基盤契約 §4（Git版の取得方法）
- 実装計画 §9.1 Gate C
- `fixtures/conformance/manifest.schema.json`（`python`、`gitVersion`、`runner: package`）

## 5. 作成するfixture

裁定の反映後、`SINGLE-127-15`〜`19`を作成する。Core実装とharnessの実行部はまだ存在しないため、
Step 0Bではmanifest、期待結果、shimと環境指定の規則との整合だけを検証する。実際のshim生成、`uv`環境構築、
`bitz.compat`と`runner: package`の起動は、Core実装後のGate Bで確認する。
