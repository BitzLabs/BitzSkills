---
id: ADR-049
title: Coreのsource配置と試験の構成を確定する
status: accepted
relations:
  requires:
    - ADR-016
    - ADR-045
    - ADR-046
---

# ADR-049 Coreのsource配置と試験の構成を確定する

## Context

[ADR-016](ADR-016_Agent-Plugins準拠の複数plugin配布.md)は、1つのmarketplace repositoryの`plugins/`配下に
自己完結したplugin directoryを置き、`bitz-core`をその1つとすることを確定した。
[ADR-045](ADR-045_実行環境と配布物の確定.md)は、配布物名・import package名・CLI実行体名を`bitz`とし、
runtime依存を標準libraryとlock fileで固定したYAML library 1つに限った。
[ADR-046](ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)は、harnessが検査対象Coreを
source directoryまたはwheelとして受け取り、`runner: package`が候補のsource treeとlock fileを検査すると定めた。

一方、次が決まっていない。Step 1ではCoreの最初のcodeとharnessの実行部を作るため、着手前に固定する必要がある。

- `plugins/bitz-core`の中でのPython project、lock file、import packageの配置
- harnessへ渡すsource directoryがどこか
- Core実装に固有の試験（単体試験、[適合fixture仕様 §4.1](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md#41-内部parser受入)の
  実装側test adapter）の置き場所と試験framework
- Coreに依存しない`fixtures/`との責務分担と参照の向き

## Decision

1. **Coreのsource tree**: `plugins/bitz-core`をCoreのsource treeとし、ADR-046のsource directoryはこのdirectoryを指す。
   plugin manifest（ADR-016 Decision 2のroot `plugin.json`）とPython projectは同じdirectoryを共有する。

   ```text
   plugins/bitz-core/
   ├── plugin.json        # Agent Plugins manifest（ADR-016）
   ├── pyproject.toml     # 配布物名 bitz、console script bitz、requires-python >=3.11
   ├── uv.lock            # runtime依存をexact versionへ固定する（ADR-045）
   ├── src/bitz/          # import package bitz（bitz.compatを含む）
   └── README.md
   ```

2. **独立したuv project**: `plugins/bitz-core`は単独のuv projectとし、lock fileを同じdirectoryに置く。
   repository rootには`pyproject.toml`、uv workspace、共有lock fileを置かない。

3. **src layout**: import package `bitz`は`src/bitz/`に置く。試験は作業directoryのsourceではなく、
   導入した`bitz`をimportする。

4. **Core固有の試験**: Core実装に固有の試験は`tests/bitz-core/`に置き、plugin directoryの外で管理する。
   適合fixture仕様 §4.1の実装側test adapterもここに置く。試験frameworkはPython標準libraryの`unittest`とし、
   試験のための依存をCoreのproject、lock fileへ加えない。

5. **`fixtures/`との責務分担**: `fixtures/`はCoreに依存しない適合fixture、参照計算、Gate Aの認定、
   Gate Bでmanifestを実行する参照harnessを持つ。参照harnessはADR-046 Decision 1のとおりCoreを
   CLI引数で受け取り、`bitz`をimportしない。

6. **参照の向き**: `tests/bitz-core/`は`plugins/bitz-core`（導入したpackageとして）と`fixtures/`を参照してよい。
   `plugins/bitz-core`は`tests/`と`fixtures/`を参照しない。`fixtures/`はCoreを引数で受け取る以外に
   `plugins/`と`tests/`を参照しない。

## Consequences

- Gate Bのharnessへは`plugins/bitz-core`（またはそこからbuildしたwheel）を渡す。`runner: package`が検査する
  `pyproject.toml`と`uv.lock`は、このsource treeの中にそろう。
- plugin導入時にcopyされるのは`plugins/bitz-core`だけであり、試験と適合fixtureは配布物に入らない。
  ADR-016 Decision 3の実行体同梱に必要なsource、metadata、lock fileはplugin directoryに含まれる。
- Core固有の試験は`uv run --project plugins/bitz-core python -m unittest discover -s tests/bitz-core`で実行する。
  uvはprojectを導入した環境で試験を実行するため、src layoutと組み合わせて未導入のsourceをimportしない。
- `fixtures/`は既存の構成とpathを変えない。Gate Aで認定したcommandと検証記録はそのまま有効である。
- 試験は`unittest`の機能に限られる。parametrize、fixture注入などは`subTest`とhelper関数で書く。

## Alternatives

1. **repository rootでuv workspaceを組む**: lock fileがrootに置かれ、`plugins/bitz-core`のsource treeの外に出る。
   `runner: package`はsource treeとlock fileを対で検査するため、候補を渡すたびにrootの状態へ依存する。採用しない。
2. **flat layout（`plugins/bitz-core/bitz/`）**: 作業directoryからの実行で未導入のsourceをimportでき、
   導入物の欠落（package dataの漏れなど）を試験が見逃す。採用しない。
3. **試験をplugin directoryの中へ置く**: plugin導入時に試験もcopyされる。配布物とsource treeの境界が曖昧になり、
   ADR-016の自己完結pluginに不要なfileが入る。採用しない。
4. **pytestを使う**: 記述は簡潔になるが、開発用依存がlock fileへ入り、依存の検査対象と固定対象が増える。
   `fixtures/`の自己試験も`unittest`で書かれており、同じframeworkに揃える。採用しない。
5. **`fixtures/`を`tests/`配下へ移す**: 適合fixtureは実装に依存しない正本であり、Core固有の試験と性質が異なる。
   Gate Aで認定したcommand、検証記録、文書のlinkもpathに依存する。採用しない。

## Notes

- 反映先: [システム構成 §7](../01_システム構成.md#7-配布と拡張)、
  [Core 1.0実装計画 §4](../../04.提案資料/12_Core-1.0実装計画.md#4-step-1-骨格とdoctor)。
- build backend、YAML libraryの選定、pluginからCLIを起動する方法は本ADRで決めない。
  build backendはbuild時だけの依存であり、ADR-045のruntime依存の制約を受けない。
- Decision 1の図にあるrequires-python（`>=3.11`）は、後続の
  [ADR-053](ADR-053_CPythonの下限を3.12へ引き上げる.md)で`>=3.12`へ部分改訂した。配置は変更していない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-24 | Coreのsource tree、独立uv project、src layout、`tests/bitz-core`と`unittest`、`fixtures/`との責務を確定 | 実装計画 §4 |
| 2026-09-24 | Decision 1のrequires-pythonを`>=3.12`へ部分改訂 | ADR-053 |
