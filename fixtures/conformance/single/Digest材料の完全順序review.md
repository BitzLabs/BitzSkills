# Digest材料の完全順序・reverse solidus fixture review

2026-09-17。SINGLE-122、123、124の3件を追加する。
根拠は[Context Digest正規化仕様 §3・§4](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#3-digest-input)、
[context仕様 §4・§5](../../../docs/03.詳細設計/03_操作仕様/01_context.md#4-context-bundle)、
[文書・Frontmatter・状態仕様 §5](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md#5-test対応)、
[EARS-AI仕様](../../../docs/03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md)である。

全件がSINGLE-042のcorpusを1点だけ変え、`context REQ-001 --purpose verify --format json`を実行する。
Canonical JSONを`expected/context.canonical.json`へ置き、goldenと異なることも確認する。

## 入力と期待値

| ID | 変更 | 期待 |
|---|---|---|
| SINGLE-122 | TECH-001のtest対応を同一path 4件にし、宣言順を崩す。1件は`command`を省略し、文書`verify: default`で解決する。`other` commandを設定へ追加する | passed／0 |
| SINGLE-123 | REQ-001:AC-01へ未知extensionを5件置く（`quality:LEVEL`のvalue `b`・なし・`a`、`perf:LEVEL="x"`、`quality:AREA="z"`） | passed_with_warnings／0 |
| SINGLE-124 | TECH-001のtitle、AC-01のtext（`\\`のescape）、command argv templateにreverse solidusを含める | passed／0 |

122の正規順は`(path, commandSortKey, covers)`で、`command`なし、`default`の`[AC-01]`、`default`の
`[AC-01, AC-02]`（接頭辞の短い方が先）、`other`の順になる。Digest材料では`command: null`、Bundleの
`frontmatter.tests[]`ではSINGLE-042のnull・空値省略と同じく`command` keyを省略する。Bundleも同じ正規順で返す。
Bundleが参照するcommandは`default`と`other`の2件で、名前順に収録する。

123の正規順は`(namespace, term, valueSortKey)`で、`perf:LEVEL="x"`、`quality:AREA="z"`、`quality:LEVEL`
（null）、`quality:LEVEL="a"`、`quality:LEVEL="b"`になる。Core 1.0は既知namespaceを持たないため、全件が
`EAI-EXT-UNKNOWN-001`／warningである。各extensionは出現位置の異なるraw原因なので、開始角括弧の
line／columnごとに1件ずつ、位置順で返す（SINGLE-098-01の1件と同じsummary）。Constraint Ledgerは
extensionを持たない。

124では、path型fieldだけがreverse solidusをsolidusへ変換する対象である。titleは`認証の実装方針\補足`、
statement textはescape解除後の`値 a\b を出力しない`、argv templateは`--pattern=src\auth`のまま保持する。
設定ではargv要素をYAMLのplain scalarで書き、escape解釈を挟まない。

## Digest

reference A（本moduleのliteral）とreference B（入力treeから導出）でbyte一致を確認する。reference Bには、
`command`省略時に文書`verify`で解決する規則と、extensionの正規順sortを追加した。

## 準備検証

`ordering_fixtures.py`は、manifest・完全期待JSON・副作用期待値のSchema、Canonical JSONのbyte列、入力byte列、
Frontmatter Schema、2回の隔離setupのsnapshotを照合する。Canonical JSONからtest対応とextensionの順序、
command集合、reverse solidusの保持を独立に確かめる。回帰試験は、宣言順のままの並び、solidusへの変換、
warningの集約を拒否する。Core実装の結果ではなく、Gate Bで実出力と副作用を比較する。
