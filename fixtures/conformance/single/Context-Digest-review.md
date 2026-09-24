# Context Digest fixture review

`SINGLE-042`、`SINGLE-043-01/02`、`SINGLE-044-01/02`、`SINGLE-045`を扱う。
`SINGLE-042`は単一workspaceのgolden Canonical JSONとDigestを所有する
（[適合fixture仕様 §4](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#4-共通normalizer)）。
いずれもreview済みの期待値であり、Coreの挙動を観測したものではない。

## 共通の入力

固定した1組の入力を各fixtureへcopyする。symlinkや親directoryの参照で共有しない。

| path | 役割 |
|---|---|
| `.spec/bitz.yaml` | `schemaVersion`、`language`、`earsAi`と、`{tests}` templateを持つ`default` command 1件 |
| `.spec/requirements/REQ-001.md` | 起点。`AC-01`はMUST／ALWAYS／CONSTRAINT、`AC-02`は`[REASON]`付きのSHOULD／WHEN／THEN |
| `.spec/technical/TECH-001.md` | `refines: [REQ-001]`、`related: [ADR-001]`、`implements` 2件、`tests` 2件、`x-owners` |
| `.spec/decisions/ADR-001.md` | 弱い関係の参照先としてだけ置く |
| `src/*.py`、`tests/*.py` | 宣言した`implements`と`tests[].path`は通常fileとして存在しなければならない |

## review済みの判断

1. **purposeは`verify`とする。** 閉包で`command`を扱うのは`verify`だけであり
   （[関係・トレースモデル §6.3](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#63-verify)）、
   `settings.commands`と`settings.verifyTimeouts`を埋めるpurposeである。Digestのsettings材料が最も多くなる。
   §6.6のverify fixtureもtargetごとのDigestを持つため、goldenはそれらが再利用するpurposeで計算する。
2. **`addressed`は空、`unaddressed`は全target規範文とする。** `verify`ではTASKが閉包に入らないため、
   targetを`addresses`する文書がない。`CTX-COVERAGE-TASK-*`は`purpose=implement`だけに登録されている
   （[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)）ので、
   `unaddressed`が空でなくてもDiagnosticは出ず、statusは`passed`のままである。
   両targetともtest済みなので、`CTX-COVERAGE-TEST-*`も当たらない。
3. **extensionはどこにも置かない。** Core 1.0はProfile Manifestを読まないため、すべてのextension名前空間は未知であり、
   `EAI-EXT-UNKNOWN-001`／警告を返す。これはmatrixの`passed`／0と両立しない。そのため全fixtureで
   `statements[].extensions`は`[]`であり、
   [Digest正規化 §3.1.3](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#313-statements)の
   extensionの並び順の規則は、このfixture群では検査**しない**。警告を許す期待statusのfixtureが必要である
   （後に`SINGLE-123`で検査した）。
4. **unbornのrepositoryで、`revision: null`とする。** `context`には`--base` optionがなく、`setup.baseCommit`を持つ
   fixtureは`--base`を渡さなければならないため、Digest fixtureは基準commitを持てない。Digestは`revision`を材料に
   しないので、goldenは弱まらない。
5. **Digest材料では`ALWAYS`の`activation.text`を`null`とし、結果では省略する。** Digest材料は任意keyを作れない
   （[§5](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#5-serializationとhash)）一方、
   `result.schema.json`は`activation.text`がある場合に空でない文字列を要求する。2つの表現は意図して異なる。
6. **結果の`frontmatter`は宣言したfieldだけを持ち、Digestの`frontmatter`は固定keyをすべて埋める。**
   [context仕様 §5](../../../docs/03.詳細設計/03_操作仕様/01_context.md#5-projection)は許可された宣言fieldを提示し、
   [Digest正規化 §3.1.1](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#311-frontmatterのprojection)は
   relation keyを5つと空配列に固定する。`x-owners`はどちらにも現れない。CoreはContextに`x-`を使わず、
   それを`SINGLE-045`が固定する。
7. **`TECH-001`の`reachedBy`は`refines:TECH-001`とする。** この文書は、自身の`refines` edgeを起点から逆にたどって
   到達する。§5はtokenを`<relation>:<source-id>`と定め、そのedgeの参照元は`TECH-001`である。
8. **`TECH-001`は`full`で提示する。** `standard`は距離1の文書を`full`で提示する（context仕様 §5）ため、
   `SINGLE-043-01`の`--detail full`は`projection.detail`だけを、`SINGLE-043-02`の`--expand TECH-001`は
   `projection.expanded`だけを変える。どちらも`documents[]`とDigestを変えず、これがmatrixの求める性質である。

## 独立した2系統の参照計算

Gate Aは、goldenが独立した2系統の参照計算で一致することを要求する。

| 参照計算 | Digest材料の出所 | serializer |
|---|---|---|
| A（`digest_reference.py`） | review済みのliteral | 再帰的な文字列組立て。keyはUTF-16BEのbyte列で整列 |
| B（`digest_crosscheck.py`） | fixture自身の`repo/` tree | 逐次的なbyte出力。keyは明示したcode unitの列で整列 |

BはAのliteralを1つも読み込まない。この入力の形に限定した読取り処理で`bitz.yaml`とMarkdown文書を読み直し、
Frontmatterを取り出し、本文を正規化し、規範文を構文解析し、重複排除と整列の規則を自分で適用する。監査はfixtureごとに
新しく作ったrepositoryへBを2回適用し、そのbyte列をA、およびcommitした`expected/context.canonical.json`と比べる。

Bを独立に書いたことで、B自身の欠陥が1件見つかった。規範文のpatternが、EBNFでは`[SHOULD]`にだけ許される
`[MUST] [REASON]`を受理していた。現在のBはこれを拒否し、回帰試験で固定している。

## 限界

- Coreは実行していない。期待値はすべてreview済みのもので観測値ではない。Coreとの一致はGate Bで判定する。
- Bはこの入力に限定している。review済みの閉包の外にある強いedgeは、一般化せずに拒否するため、target展開の実装ではない。
- 複合workspaceのgolden（`MULTI-002-01`）は本reviewの対象外であり、
  [複合workspace golden Digest fixture review](../multi/複合workspace-golden-Digest-review.md)で扱う。
- `SINGLE-042/043/045`の一致はhash文字列だけでなくCanonical JSONのbyte列で検査する。serializerの変更が
  hashの一致に隠れることはない。

## 2026-09-17: reason、full projection、versionの専用fixture

`SINGLE-101-01`、`SINGLE-106-01`、`SINGLE-121`は既存golden corpusを使用する。
理由付きSHOULDはREQの第2句に存在し、LedgerのreasonとCanonical JSON内の全statementを
固定する。fullは`--detail full`を明示し、各文書の必須fieldと禁止fieldを結果Schemaで検証する。
versionはCanonical JSONのdigestVersionとresolverVersionがともに1.0であることを固定する。
いずれも入力、manifest、完全期待JSON、Canonical JSON、副作用snapshotを保持し、
独立2系統の計算と2回の隔離setupを既存goldenと同じ検証へ通す。
reason除去、fullへのexpandable追加・bodyText欠落、両version改変を拒否する回帰検査を追加した。
Core実行や出力観測は含まない。

## 2026-09-17: 内部Parser受入とescape・normative

ユーザー裁定により、公開context Schemaへsourceを追加せず、完全IRの比較を内部Parser受入へ分離した。
適合fixture仕様 §4.1とmanifestのparserChecksが入力path・期待JSONを固定する。
Step 0Bではreview済み値を入力byte列と照合し、Step 2のGate Bでは実Parserから得た
全IRを比較する。fixture referenceを呼ぶだけでCore受入とはしない。

- SINGLE-097-01: 5種類の既知escapeを1行で検査する。reference Aは解除後textを明示した
  literal、reference Bは入力から左→右のescape解除を行う。完全IRはline 15/16、column 3、
  raw候補行、source path、全意味fieldを固定し、公開JSONとCanonical JSONは従来どおり完全比較する。
- SINGLE-101-01: 同じ内部受入を追加し、理由付きSHOULDの全IRを固定する。
- SINGLE-106-02: TECH-001をrefineする距離2のTECH-002を追加する。statementやtestを増やさず、
  documentCountだけが3となる。TECH-002のprojectionはnormative、statementRefsは空配列、
  frontmatter/bodyText/expandableは省略する。新文書を含むDigestは2系統の計算で照合する。

source位置、raw、解除後text、reasonの改変、normativeへのbodyText追加とstatementRefs欠落、
Parser期待値の不存在・path逸脱・重複を拒否する。新しいreference readerはcode spanを
未対応のまま受理せず、専用vectorの確定を要求する。

## 2026-09-17: quoted extension

SINGLE-098-01のmatrix statusをユーザー裁定に従いpassed_with_warningsへ訂正した。
quality:LEVELのquoted値にescaped DQUOTEを置き、解除後の値 `say "hello"` を固定する。
未知namespaceのDiagnosticはline 15、column 19に1件だけ出す。Ledgerの規範意味は
goldenと同じだが、Digestにはopaque extensionと原文が入るため別の値となる。
完全IRのextensionsとunknownExtensionsは同じ要素を出現順で保持する。
原文、解除値、unknownExtensions、warning省略、診断位置の改変を拒否する。
入力、完全IR、公開JSON、Canonical JSON、副作用snapshotは独立した実fixtureとして保存する。

## 2026-09-17: code span

ユーザー裁定に従い、Semantic IRへはcode spanの外側delimiterを除いた内容を保持する。
SINGLE-096-01は1・2・3 backtickのspanを同一行に置く。内部の異なる長さのrun、
[MUST]、backslashと角括弧は解釈せず保持する。reference Aは解除後の文字列をliteralで固定し、
reference Bは極大runの長さを数え、同長runだけで閉じる。rawとbodyTextは原文を保持する。
完全IR・JSON・Canonical JSON・source・副作用を検証し、外側delimiterの残留、内部run欠落、
未閉鎖runの誤受理を拒否する。matrix §6.10の全20件の準備が完了した。
