# verify出力・文書単位binding fixture review

[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify)の
`SINGLE-069-01`、`SINGLE-069-02`、`SINGLE-066`を扱う。`SINGLE-068`は未作成である（後述の「残る1行」を参照）。
いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## 抜粋が末尾であることを証明できるようにする

[安全な入出力・互換性 §9](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#9-process出力)は、
redaction後のstreamの末尾65,536 byteを保持し、元のstreamがそれを超えた場合にだけ`*Truncated`を立てる。一様な
詰め物だけの抜粋では、末尾を残す規則、先頭を残す規則、すべてを残す欠陥のどれでも同じ結果になるため、固定した
出力の両端に目印を置く。

- 1行目は先頭の目印、2〜1099行目は詰め物、1100行目は末尾の目印とする
- 各行をちょうど64 byteにして、65,536 byteが行の境界に来るようにし、期待する抜粋が行の分割を仮定しないようにする
- 1,100 × 64 = 70,400 byteなので、最初の76行は抜粋の外に出る

したがって期待する抜粋は末尾の目印を含み、先頭の目印を**含まない**。監査は両方を確認する。さらに
`check_excerpt_shape`は、ちょうど64 KiBでない抜粋と、redactionのkeywordと衝突する出力textを拒否する。これにより
redactionはこの出力を変えず、期待値がmaskingの規則で知らないうちに書き換わらない。

監査は各fixture自身のcommand fileを実行し、生成された末尾とcommitした抜粋をbyte単位で比べる。誰も生成していない
streamについての主張にはならない。

`SINGLE-069-01`は0、`SINGLE-069-02`は1で終了する。scriptの本文はDigest材料ではないので、両者は結果が異なっても
1つのContext Digestを共有する。Digestが実行ではなく仕様を追跡していることを示す性質なので、回帰試験で固定する。

## `SINGLE-066`: 規範文のないbinding

targetは、規範文を持たず文書単位のtestを宣言するTECHである。
[文書・Frontmatter・状態仕様](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)は、
このようなTECHに限って`covers`へ文書IDを書くことを許し、このfixtureに必要な形はまさに`covers: [TECH-001]`である。
[関係・トレースモデル §6.4](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#64-targetexpansionroot-purpose)
の規則5は、この種類の起点で`targetStatements`を空にし、文書単位のbindingを保持する。

そのため`targetResults[0]`は、`statements: []`と`bindingRefs: ["root::default"]`を同時に返す。matrixの行が挙げる
組合せである。入力のTECHは関係を持たず単独なので、閉包は起点だけであり、解決の論点は残らない。監査は文書を構文解析し
直し、規範文が現れた場合はfixtureを拒否する。

## 残る1行

`SINGLE-068`（done TASKの起点）は、意図してまだ作らない。期待値が、規範文書で決着していない論点に依存するためである。
起点TASKが`addresses`する参照先を所有する文書が、**verify**のContextに含まれるかという論点である。

- [関係・トレースモデル §6.2](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#62-implement)は、
  `implement`について`addresses`の閉包を明示している。
- §6.3の`verify`は「interpretに加えて対象statementのtest対応、command、実装pathを含める。TASKは起点指定時だけ
  含める。」とだけ述べ、`interpret`は`addresses`をたどらない。
- 一方、[verify仕様 §3](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#3-対象)はTASK targetが`addresses`する
  参照先を検証することを求めており、その文書がContextの外にあれば実行できない。

一貫した読み方は「含まれる」だが、これは規範上の決定であり、
[適合fixture仕様 §3.3](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#33-実成果物との対応)は
契約が未確定のfixtureの追加を禁じている。期待値は契約の変更と同時に追加するもので、先行してはならない。そのため、
この欠落はfixtureにせず報告する。（その後、§6.3へ明記して`SINGLE-068`を追加した。
[done TASK起点review](done-TASK起点review.md)を参照。）

## 限界

- Coreは実行していない。Coreとの一致はGate Bで判定する。
- この固定した出力では、redactionは値を変えない。上限を超えるstreamと、textを長くするredactionの組合せ
  （その場合も`*Truncated`は*元の*大きさに従う）は、この2件では検査しない（後に`SINGLE-126-16`で検査した）。
- 抜粋の境界は、ASCIIの行の境界でだけ検査している。64 KiBの境目でmulti-byte文字が分かれる場合の、
  コードポイント境界の規則はここでは固定しない。
