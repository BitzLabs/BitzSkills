# Context非成功・coverage fixture review

`SINGLE-046`、`SINGLE-047`、`SINGLE-048-01/02`、`SINGLE-049`、`SINGLE-054`を扱い、
[適合fixture仕様 §6.5](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#65-contextとdigest)を完了する。
いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## このfixture群に共通する2つの規則

1. **非成功のContextはBundleの材料を返さない。**
   非成功のfixtureでは、`documents`、`constraintLedger.statements`、`coverage`をすべて空にする。
   `stop-operation`は「操作全体を停止する」と定義され
   （[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)）、
   [context仕様 §7](../../../docs/03.詳細設計/03_操作仕様/01_context.md#7-stale検出)はstaleなContextを暗黙に受け入れない
   ことを求める。Bundleを返さないのが安全側であり、`status`を無視したadapterでも材料を使えない。
   `CTX-LIMIT-001`は「部分Bundleを返さない」と明記しており、他のcodeにもcodeごとの規則を作らず同じ形を適用する。
2. **`contextDigest`は、完全解決が成立した場合に限りnullでない。**
   [Digest正規化 §2](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#2-全体手順)の手順1は、
   完全解決なしにDigestを計算することを禁じる。したがって`resolution.complete`とDigestの有無は同じ事実を2回
   示すものであり、監査は両者が食い違わないことを検査する。

| fixture | `complete` | `documentCount` | `contextDigest` |
|---|:--:|--:|---|
| `SINGLE-046` stale | true | 2 | `SINGLE-042`がcommitしたgolden |
| `SINGLE-047` 集合外のexpand | true | 2 | `SINGLE-042`がcommitしたgolden |
| `SINGLE-048-01/02` 閉包の上限 | false | 0 | `null` |
| `SINGLE-049` 提示のhard limit | true | 4 | 固有に計算した値 |

`SINGLE-046`と`SINGLE-047`はDigestの入力を変えずに再利用するため、返すDigestは別に作った定数ではなく
`SINGLE-042`がcommitした値である。これを回帰試験で固定する。

## fixtureごとの判断

- **`SINGLE-046`**は`--expect-digest sha256:00…0`を渡す。sourceは`invocation`、`argument: "--expect-digest"`
  であり、registryが`CTX-DIGEST-STALE`に定める`invocation` sourceと一致する。呼出し側は、optionを付けずに
  再実行して現在の値を知る。拒否した結果はBundleを持たない。
- **`SINGLE-047`**は`ADR-001`をexpandする。この文書はworkspaceに存在するが閉包の外にある（`related`は閉包を
  広げない）。存在しないIDより鋭い入力であり、「依存へ追加しない」ことも固定できる。`documentCount`は2のまま、
  `projection.expanded`は`[]`である。
- **`SINGLE-048-01/02`**は、大量の入力ではなく設定で上限を与える。`context.maxDocuments`は1〜100、
  `context.maxBytes`は4,096〜1,048,576を受け付ける
  （[workspace・設定仕様](../../../docs/03.詳細設計/02_SPECモデル/01_workspace・設定仕様.md)）。2文書の閉包に対する
  `maxDocuments: 1`と、4,776 byteの提示に対する`maxBytes: 4096`は、それぞれ設定した上限を1回だけ越える。
  監査はfixture自身のbyte列から両方の差分を計算し直すため、詰め物が上限を越えなくなっても見逃さない。
- **`SINGLE-049`**は、*固定の*上限を越える必要がある唯一のfixtureである。提示のhard limitは設定によらず1 MiBである。
  閉包が通過するよう閉包の2つの次元を最大値に設定し、入力は`REQ-001 ← TECH-001 ← TECH-002 ← TECH-003`の
  refinementの連鎖で、間接の2件だけを大きくする。`standard`ではこの2件を`normative`で提示し`bodyText`を
  含めない（[context仕様 §5](../../../docs/03.詳細設計/03_操作仕様/01_context.md#5-projection)）ため、測る量である
  「ContextのSemantic IRと標準提示」
  （[安全な入出力・互換性 §4](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#4-resource上限)）は
  小さく、`--detail full`では本文が1,071,063 byteになる。各fileは1文書あたり1 MiBの入力上限を下回る。
- **`projection.detail`は要求したmodeを、`projection.expanded`は実際に適用したものを示す。**
  そのため`SINGLE-049`は`detail: "full"`と`expanded: []`を、`SINGLE-047`は`detail: "standard"`と
  `expanded: []`を返す。
- **`SINGLE-054`**はこの群で唯一の成功statusであり、完全なBundleと固有のDigestを持つ唯一のfixtureである。
  `TASK-001`は`AC-02`だけを`addresses`し、MUSTの`AC-01`はunaddressedのまま残る。`CTX-COVERAGE-TASK-001`の
  警告がちょうど1件出て、`must`と`should`にわたってcoverageの5区分がすべて意味のある値を持つ。
  監査は、`addressed`／`unaddressed`と`tested`／`untested`がそれぞれ`total`を分割することを検査する。

## implementのDigest材料は別物である

`SINGLE-054`は`--purpose implement`で実行し、matrixはそのDigestが固有の値であることを求める。
[関係・トレースモデル §6.2](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#62-implement)は、
implementの閉包に`implements`、test対応、TASKの`changes`を挙げるが、`command`は挙げない。`command`を挙げるのは
§6.3の`verify`だけである。そのため`implement`では`settings.commands`と`settings.verifyTimeouts`が空になり、
`addresses`するTASKが`documents`に加わる。`purpose`自体がDigest材料なので、2つのCanonical JSONは衝突しない。
両者が異なることを回帰試験で確認する。

この群のために参照計算Bを拡張した。どちらの拡張も、Bに実在した欠落の補完であり、言い換えではない。
既定値を仮定せずworkspaceの設定から`context.maxDocuments`／`maxBytes`を読むようにし、起点を直接具体化する文書だけで
なく、推移的なrefinementの連鎖をたどるようにした。review済みの規則で説明できない強いedgeは、引き続き拒否する。

## 限界

- Coreは実行していない。Coreとの一致はGate Bで判定する。
- 提示のbyte数は、提示した文書の本文として測る。Coreが直列化したBundle全体を数える場合も、差が20 KiBを超えるため
  `SINGLE-049`の判定は変わらないが、ちょうど境界のcaseはこのfixtureでは固定しない。
- `SINGLE-048-01/02`は、起点文書をDiagnosticのsourceとする。registryはsourceの*種類*を`file`と定めるが、
  どのfileかは定めない。起点は閉包の出発点である。
