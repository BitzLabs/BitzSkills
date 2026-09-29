# Core 1.0の比較タスク

本ディレクトリは、仕様の記述とレビューの効果を評価する。機械の性能fixtureとは別である。各比較タスクは、
通常のMarkdownによる基準条件と、Bitzによる条件を同等に持つ。参加者は比較タスクを完了するまで
`answer-key.json`を読んではならない。

ADR-058により、実測は任意研究として扱い、Core 1.0のGate Cまたはリリースの条件にはしない。

手順の正本は`protocol.json`とする。条件はAB／BAの均衡した順序で割り当て、taskのclean copyを使い、networkと外部の
支援を禁止し、必須の4指標をすべて記録する。taskは、完了条件が盲検のreviewを通過した場合だけ完了とする。
5件のtask定義、protocol、正解表、結果Schemaはまとめてversion管理し、1つを変える場合はprotocolの新しいversionを作る。

`tasks/*.json`は`task.schema.json`、`protocol.json`は`protocol.schema.json`、`answer-key.json`は
`answer-key.schema.json`、観測値は`result.schema.json`で検証する。

repository rootで`uv run fixtures/validate_benchmarks.py`を実行すると、固定した入力とSchemaを、性能datasetとあわせて検証する。
将来の観測値Schemaは構造だけを検査し、参加者の結果はCoreができた後に集める。
[性能fixtureの対象外](../performance/README.md#6-対象外)に挙げたCore 1.0の対象外機能は、これらのtaskにも適用する。
