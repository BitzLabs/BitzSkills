# ハッシュ値の材料の完全な順序とバックスラッシュのfixtureのレビュー記録

2026-09-17。SINGLE-122、123、124の3件を追加する。
根拠は[コンテキストのハッシュ値の正規化仕様 §3・§4](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#3-ハッシュ値の材料)、
[`context`仕様 §4・§5](../../../docs/03.詳細設計/03_操作仕様/01_context.md#4-コンテキスト一式)、
[文書・フロントマター・状態仕様 §5](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md#5-テスト対応)、
[EARS-AI仕様](../../../docs/03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md)である。

全件が、SINGLE-042のcorpusを1点だけ変え、`context REQ-001 --purpose verify --format json`を実行する。
正規JSONを`expected/context.canonical.json`へ置き、goldenと異なることも確認する。

## 入力と期待値

| ID | 変更 | 期待 |
|---|---|---|
| SINGLE-122 | TECH-001のテスト対応を、同じパスの4件にし、宣言の順序を崩す。1件は`command`を省略し、文書の`verify: default`で解決する。コマンド`other`を設定へ追加する | `passed`／0 |
| SINGLE-123 | REQ-001:AC-01へ未知の拡張タグを5件置く（`quality:LEVEL`の値`b`、値なし、値`a`、`perf:LEVEL="x"`、`quality:AREA="z"`） | `passed_with_warnings`／0 |
| SINGLE-124 | TECH-001の`title`、AC-01のテキスト（`\\`のエスケープ）、コマンドの引数列テンプレートにバックスラッシュを含める | `passed`／0 |

122の正規の順序は`(path, commandSortKey, covers)`で、`command`なし、`default`の`[AC-01]`、`default`の
`[AC-01, AC-02]`（接頭辞の短い方が先）、`other`の順になる。ハッシュ値の材料では`command: null`、コンテキスト一式の
`frontmatter.tests[]`では、SINGLE-042の`null`・空の値の省略と同じく、`command`のキーを省略する。コンテキスト一式も同じ正規の順序で返す。
コンテキスト一式が参照するコマンドは`default`と`other`の2件で、名前順に収録する。

123の正規の順序は`(namespace, term, valueSortKey)`で、`perf:LEVEL="x"`、`quality:AREA="z"`、`quality:LEVEL`
（値なし）、`quality:LEVEL="a"`、`quality:LEVEL="b"`になる。Core 1.0は既知の名前空間を持たないため、全件が
診断`EAI-EXT-UNKNOWN-001`（重大度`warning`）である。各拡張タグは、出現位置の異なる元の原因なので、開始角括弧の
行と列ごとに1件ずつ、位置の順で返す（SINGLE-098-01の1件と同じ`summary`）。制約台帳は
拡張タグを持たない。

124では、パス型のフィールドだけが、バックスラッシュをスラッシュへ変換する対象である。`title`は`認証の実装方針\補足`、
規範文のテキストはエスケープの解除後の`値 a\b を出力しない`、引数列テンプレートは`--pattern=src\auth`のまま保持する。
設定では、引数列の要素をYAMLのプレーンなスカラーで書き、エスケープの解釈を挟まない。

## ハッシュ値

参照計算A（本モジュールのリテラル）と参照計算B（入力の木構造から導出）で、バイト単位の一致を確認する。参照計算Bには、
`command`の省略時に文書の`verify`で解決する規則と、拡張タグの正規の順序での並べ替えを追加した。

## 準備検証

`ordering_fixtures.py`は、マニフェスト、完全な期待JSON、副作用の期待値のスキーマ、正規JSONのバイト列、入力のバイト列、
フロントマターのスキーマ、2回の隔離環境での準備手順のスナップショットを照合する。正規JSONから、テスト対応と拡張タグの順序、
コマンドの集合、バックスラッシュの保持を、独立に確かめる。回帰試験は、宣言の順序のままの並び、スラッシュへの変換、
警告の集約を拒否する。Coreの実装の結果ではなく、Gate Bで実際の出力と副作用を比較する。
