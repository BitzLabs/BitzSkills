---
id: ADR-046
title: 適合harnessの検査対象・実行環境・runnerを確定する
status: accepted
relations:
  requires:
    - ADR-043
    - ADR-045
---

# ADR-046 適合harnessの検査対象・実行環境・runnerを確定する

## Context

[適合fixture仕様](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)はmanifestの形とsetup手順を定めるが、
harnessの外部仕様は次の点で閉じていない。このため`SINGLE-127-15`〜`19`、`MONO-023`、`MONO-024`の期待値と
起動方法を一意に書けない。

- `runner: bitz`が「検査対象の`bitz` entry point」をどこから得るか。Python versionを切り替える手段もない。
- manifestの`env`は固定文字列だけなので、一時directoryに置いた偽のGitを`PATH`で指せない。Git 2.30以上の場合は
  偽のGitが実Gitへ処理を委ねる必要があるが、その実Gitのpathはhostに依存する。Coreが版をどう取得するかも規範にない。
- CPython 3.11での動作を保証する`SINGLE-127-19`は、doctorを1回起動するだけでは「3.11で利用できない構文・APIへの
  依存がない」ことを示せない。
- `runner: consumer`と`runner: migration`は「Core配布物に含める固定compatibility harness」とあるだけで、argv、
  出力、終了コードが未定義である。`SINGLE-127-17`／`18`はpackage metadataとlock fileを検査するが、lock fileは
  配布物ではなくsource treeにあり、Coreが自分自身を申告する形では独立した証拠にならない。

## Decision

1. **検査対象の受取り**: harnessは検査対象Coreをsource directoryまたはwheelとしてCLI引数で受取り、manifestへ
   書かない。要求されるCPython minorごとに`uv`でrepositoryと隔離HOMEの外に環境を作り、候補とlock済み依存だけを
   導入する。`runner: bitz`はその環境のconsole script `bitz`をshellなしで起動する。環境構築はinvocationの前に行い、
   Coreの副作用比較には含めない。
2. **Python version**: `runner: bitz`のinvocationは任意の`python`（`<major>.<minor>`）を持てる。指定時はそのminorの
   CPythonで環境を作り、見つからなければfixtureをerrorとし、skipしない。省略時は基準環境のCPythonを使う。
   `SINGLE-127-19`は`python: "3.11"`でdoctorを起動する。加えてGate Cでは、全matrixを下限CPython 3.11と基準環境の
   2環境で通すことを要求する。`python`を指定したfixtureは指定versionだけで判定する。
3. **Git versionの差替え**: `runner: bitz`のinvocationは任意の`gitVersion`（`<major>.<minor>.<patch>`）を持てる。
   harnessはinvocation専用の空directoryへ`git` shimを置き、そのdirectoryを`PATH`の先頭へ加える。shimは
   `git --version`にだけ`git version <gitVersion>`の1行を返して終了0とし、それ以外のargvはshim作成時に解決した
   実Gitへそのまま渡す。setupはshimを使わない。`gitVersion`と`env.PATH`は同時に指定しない。
   Coreは`git --version`の標準出力1行目を`git version <major>.<minor>[.<残り>]`として解析し、major・minorを数値で
   比較する。非0終了や解析できない出力は、実行不能と同じくGit不在とする。
4. **JSON互換runner**: `runner: consumer`と`runner: migration`はCore配布物のmodule `bitz.compat`を
   `python -m bitz.compat <runner> <argv...>`としてshellなしで起動する。標準出力は`{"outcome": "<値>"}`の
   JSON 1件とLFで、終了コードは`accepted`と`passed`が0、`rejected`が1とする。それ以外の終了はfixture errorとする。
   consumerの`result-shape <path>`は、指定JSONを共通結果契約の排他的外形で判定する。migrationのcase名と引数は
   `MONO-024`の作成時に同じ形で固定する。
5. **package runner**: package metadataとlock fileの検査は、Core配布物ではなくfixture harnessの参照実装が行う
   `runner: package`とする。Core実行体を起動せず、候補のsource tree、build成果物、Decision 1の隔離環境の導入
   metadataを検査し、Decision 4と同じ出力・終了コードを返す。caseは`metadata`（配布物名、import package名、
   console script名が`bitz`で、requires-pythonが3.11以上を許す）と`dependencies`（runtime依存が標準libraryと
   lock fileでexact versionへ固定したYAML library 1つだけ）の2つとする。

## Consequences

- `SINGLE-127-15`〜`19`を、host固有のpathをmanifestへ書かずに固定できる。Gitの下限判定は版の取得方法まで
  決まるため、実装間で縮退の判定が分かれない。
- 3.11の保証はfixture 1件の起動確認と、Gate Cの全matrix実行の2段になる。Gate Cの実行時間はおよそ2倍になる。
- `bitz.compat`はCore配布物の一部になり、dual-read consumerの判定をadapterやCIが再利用できる。
  公開構文は`consumer`／`migration`の2 runnerとcase名に限る。
- package検査はharness側にあるため、Coreが自分の配布形態を自己申告するだけでは合格しない。
- harnessは`uv`と、`python`指定に応じたCPythonをhostに要求する。不足はfixture errorであり、合格扱いにしない。

## Alternatives

1. **manifestの`env`にplaceholderを許す**: `${FIXTURE_ROOT}`や`${HOST_GIT}`を展開させればrepo内のshimを指せるが、
   manifestへhost依存の展開規則が入り、同じ規則を全env値へ適用する必要が生じる。採用しない。
2. **相対PATH要素をinvocation cwd基準で解決する規則をCoreへ課す**: fixtureがGit版の判定とは別のCore挙動に依存し、
   単一原因の原則に反する。採用しない。
3. **`SINGLE-127-19`を削除してGate Cだけにする**: 下限versionで実際に起動できることを適合matrixの1行として
   早期に確認できなくなる。採用しない。
4. **package検査も`bitz.compat`へ含める**: lock fileは配布物に含まれず、Coreの自己申告になる。採用しない。
5. **全runnerをharness側の参照実装にする**: `MONO-023`がCoreではなくharnessを検査することになり、Core受入の
   証拠にならない。採用しない。
6. **検査対象を実行file pathだけで受け取る**: 単純だが、Python versionの切替えと導入metadataの検査に
   別の手段が必要になる。採用しない。

## Notes

- 本ADRは[提案27](../../04.提案資料/27_適合harness外部仕様の検討.md)の裁定である。
- ADR-043の適合matrixとADR-045の実行環境・配布物を変更せず、未確定だった適合harnessの外部仕様を追加する。
  Decision 3の版取得方法とDecision 4の`bitz.compat`はADR-045を具体化するもので、下限versionと配布物名は変えない。
- 反映先: [適合fixture仕様](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md)、
  [Core実行環境・CLI基盤契約](../../03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md)、
  [実装計画](../../04.提案資料/12_Core-1.0実装計画.md)、`fixtures/conformance/manifest.schema.json`。
- fixture ID `MONO-023`、`MONO-024`は、後続の[ADR-047](ADR-047_複合workspaceの識別子をmultiWorkspaceへ改名する.md)で`MULTI-023`、`MULTI-024`へ改名した。
- fixtureが`repo/`で表せない入力（上限境界の生成入力、member pathのsubmodule／別worktree）は、後続の[ADR-048](ADR-048_適合fixtureの生成入力とGit構造operationを確定する.md)で`setup.generate`とGit構造operationとして加えた。
- Decision 2の下限版（`python: "3.11"`とGate Cの下限CPython 3.11）とDecision 5の`metadata` caseのrequires-pythonは、
  後続の[ADR-053](ADR-053_CPythonの下限を3.12へ引き上げる.md)で3.12へ部分改訂した。`invocation.python`の意味と
  他のDecisionは変更していない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-17 | 検査対象の受取り、Python・Git versionの指定、JSON互換runner、package runnerを確定 | 提案27 |
| 2026-09-17 | 複合workspaceの識別子の改名を後続決定へ接続 | ADR-047 |
| 2026-09-18 | fixtureの生成入力とGit構造operationを後続決定へ接続 | ADR-048 |
| 2026-09-24 | Decision 2の下限版とDecision 5のrequires-pythonを3.12へ部分改訂 | ADR-053 |
