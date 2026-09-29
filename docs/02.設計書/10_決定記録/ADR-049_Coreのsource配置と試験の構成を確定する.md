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

[ADR-016](ADR-016_Agent-Plugins準拠の複数plugin配布.md)は、1つのマーケットプレイスのリポジトリの`plugins/`配下に、
自己完結したプラグインのディレクトリを置き、`bitz-core`をその1つとすることを確定した。
[ADR-045](ADR-045_実行環境と配布物の確定.md)は、配布物名・インポートパッケージ名・CLI実行体名を`bitz`とし、
ランタイムの依存を、標準ライブラリと、ロックファイルで固定したYAMLライブラリ1つに限った。
[ADR-046](ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)は、harnessが検査対象Coreを
ソースのディレクトリまたはwheelとして受け取り、`runner: package`が候補のソースの木構造とロックファイルを検査すると定めた。

一方、次が決まっていない。Step 1ではCoreの最初のコードとharnessの実行部を作るため、着手の前に固定する必要がある。

- `plugins/bitz-core`の中での、Pythonのプロジェクト、ロックファイル、インポートパッケージの配置
- harnessへ渡すソースのディレクトリがどこか
- Coreの実装に固有の試験（単体試験、[適合fixture仕様 §4.1](../../03.詳細設計/00_共通契約/04_適合fixture仕様.md#41-内部の構文解析器受入)の
  実装側のテストアダプター）の置き場所と、試験のフレームワーク
- Coreに依存しない`fixtures/`との責務分担と参照の向き

## Decision

1. **Coreのソースの木構造**: `plugins/bitz-core`をCoreのソースの木構造とし、ADR-046のソースのディレクトリはこのディレクトリを指す。
   プラグインのマニフェスト（ADR-016の`Decision`の2番目の項目にある、最上位の`plugin.json`）とPythonのプロジェクトは同じディレクトリを共有する。

   ```text
   plugins/bitz-core/
   ├── plugin.json        # Agent Plugins manifest（ADR-016）
   ├── pyproject.toml     # 配布物名 bitz、console script bitz、requires-python >=3.11
   ├── uv.lock            # runtime依存をexact versionへ固定する（ADR-045）
   ├── src/bitz/          # import package bitz（bitz.compatを含む）
   └── README.md
   ```

2. **独立したuvのプロジェクト**: `plugins/bitz-core`は単独のuvのプロジェクトとし、ロックファイルを同じディレクトリに置く。
   リポジトリのルートには`pyproject.toml`、uvのワークスペース、共有のロックファイルを置かない。

3. **`src`レイアウト**: インポートパッケージ`bitz`は`src/bitz/`に置く。試験は作業ディレクトリのソースではなく、
   導入した`bitz`をインポートする。

4. **Core固有の試験**: Coreの実装に固有の試験は`tests/bitz-core/`に置き、プラグインのディレクトリの外で管理する。
   適合fixture仕様 §4.1の実装側のテストアダプターもここに置く。試験のフレームワークはPython標準ライブラリの`unittest`とし、
   試験のための依存をCoreのプロジェクト、ロックファイルへ加えない。

5. **`fixtures/`との責務分担**: `fixtures/`はCoreに依存しない適合fixture、参照計算、Gate Aの認定、
   Gate Bでマニフェストを実行する参照harnessを持つ。参照harnessはADR-046の`Decision`の1番目の項目のとおり、Coreを
   CLI引数で受け取り、`bitz`をインポートしない。

6. **参照の向き**: `tests/bitz-core/`は`plugins/bitz-core`（導入したパッケージとして）と`fixtures/`を参照してよい。
   `plugins/bitz-core`は`tests/`と`fixtures/`を参照しない。`fixtures/`はCoreを引数で受け取る以外に
   `plugins/`と`tests/`を参照しない。

## Consequences

- Gate Bのharnessへは`plugins/bitz-core`（またはそこからビルドしたwheel）を渡す。`runner: package`が検査する
  `pyproject.toml`と`uv.lock`は、このソースの木構造の中にそろう。
- プラグインを導入するときにコピーされるのは`plugins/bitz-core`だけであり、試験と適合fixtureは配布物に入らない。
  ADR-016の`Decision`の3番目の項目にある実行体の同梱に必要なソース、メタデータ、ロックファイルは、プラグインのディレクトリに含まれる。
- Core固有の試験は`uv run --project plugins/bitz-core python -m unittest discover -s tests/bitz-core`で実行する。
  uvはプロジェクトを導入した環境で試験を実行するため、`src`レイアウトと組み合わせて、未導入のソースをインポートしない。
- `fixtures/`は既存の構成とパスを変えない。Gate Aで認定したコマンドと検証記録はそのまま有効である。
- 試験は`unittest`の機能に限られる。`pytest`のパラメーター化やfixtureの注入などは`subTest`とヘルパー関数で書く。

## Alternatives

1. **リポジトリのルートでuvのワークスペースを組む**: ロックファイルがリポジトリのルートに置かれ、`plugins/bitz-core`のソースの木構造の外に出る。
   `runner: package`はソースの木構造とロックファイルを対で検査するため、候補を渡すたびにルートの状態へ依存する。採用しない。
2. **フラットレイアウト（`plugins/bitz-core/bitz/`）**: 作業ディレクトリからの実行で未導入のソースをインポートでき、
   導入物の欠落（パッケージデータの漏れなど）を試験が見逃す。採用しない。
3. **試験をプラグインのディレクトリの中へ置く**: プラグインを導入するときに試験もコピーされる。配布物とソースの木構造の境界が曖昧になり、
   ADR-016の自己完結したプラグインに不要なファイルが入る。採用しない。
4. **`pytest`を使う**: 記述は簡潔になるが、開発用の依存がロックファイルへ入り、依存の検査対象と固定対象が増える。
   `fixtures/`の自己試験も`unittest`で書かれており、同じフレームワークに揃える。採用しない。
5. **`fixtures/`を`tests/`配下へ移す**: 適合fixtureは実装に依存しない正本であり、Core固有の試験と性質が異なる。
   Gate Aで認定したコマンド、検証記録、文書のリンクもパスに依存する。採用しない。

## Notes

- 反映先: [システム構成 §7](../01_システム構成.md#7-配布と拡張)、
  [Core 1.0実装計画 §4](../../04.提案資料/12_Core-1.0実装計画.md#4-step-1-骨格とdoctor)。
- ビルドバックエンド、YAMLライブラリの選定、プラグインからCLIを起動する方法は本ADRで決めない。
  ビルドバックエンドはビルドのときだけの依存であり、ADR-045のランタイムの依存の制約を受けない。
- `Decision`の1番目の項目の図にある`requires-python`（`>=3.11`）は、後続の
  [ADR-053](ADR-053_CPythonの下限を3.12へ引き上げる.md)で`>=3.12`へ部分改訂した。配置は変更していない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-24 | Coreのsource tree、独立uv project、src layout、`tests/bitz-core`と`unittest`、`fixtures/`との責務を確定 | 実装計画 §4 |
| 2026-09-24 | Decision 1のrequires-pythonを`>=3.12`へ部分改訂 | ADR-053 |
| 2026-09-29 | 説明文を日本語表記へ書き直した（意味の変更なし） | 表記規則 |
