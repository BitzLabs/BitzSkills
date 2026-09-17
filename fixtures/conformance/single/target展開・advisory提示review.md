# 共通target展開・advisory提示fixture review

2026-09-17。SINGLE-106-03、107-01／02、108-01／02、109、110、113の8件を追加する。
根拠は[関係・トレースモデル §6・§7](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#6-purpose別の閉包)、
[context仕様 §4・§5](../../../docs/03.詳細設計/03_操作仕様/01_context.md#4-context-bundle)、
[verify仕様 §3・§4](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#3-対象)、
[Context Digest正規化仕様](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md)である。

## 作成前の裁定

期待値を一意に決められない規範の欠落3件と矛盾1件を、作成前に次のとおり裁定し、正本へ反映した。
経緯は[Diagnostic台帳の再review](../Diagnostic意味網羅review.md)に記録した。

| 論点 | 裁定 | 反映先 |
|---|---|---|
| `requires`／`addresses`先のrole | REQは`requirement`、TECHとaccepted ADRは`constraint`。複数該当は表の上から | 関係・トレースモデル §7 |
| advisoryの発生経路 | interpretで閉包内の文書を`refines`する`draft`文書をadvisoryとして含め、先を辿らない | 関係・トレースモデル §6.1 |
| statement起点の提示 | `statementRefs`は所有する全規範文、Ledgerとcoverageは対象statementだけ、`coverage.adjacent`は兄弟句 | context仕様 §4・§5 |
| verifyの起点TASKの`requires` | §6.3（含めない）を正とし、matrix 110行とtarget vectorを修正 | matrix、`targets/cases.json` |

## 入力と期待展開

| ID | 起動 | corpus | contextDocuments（role／projection） | target statement |
|---|---|---|---|---|
| SINGLE-106-03 | `context REQ-001 --purpose interpret` | REQ-001と、その句を`refines`するdraft TECH-005 | REQ-001（root／full）、TECH-005（advisory／reference） | なし |
| SINGLE-107-01 | `context REQ-001 --purpose verify` | REQ-001が`requires` REQ-009、`related` REQ-099。TECH-002がAC-01を、TECH-003がTECH-002:AC-01を具体化 | REQ-001（root）、REQ-009（requirement）、TECH-002（refinement）、TECH-003（refinement／normative） | REQ-001:AC-01、AC-02、TECH-002:AC-01、TECH-003:AC-01 |
| SINGLE-107-02 | `verify REQ-001` | 107-01と同じ | — | 107-01と同じ |
| SINGLE-108-01 | `context TECH-001 --purpose verify` | 規範文ありTECH-001が`requires` TECH-009。TECH-004がTECH-001:AC-01を具体化 | TECH-001（root）、TECH-004（refinement）、TECH-009（constraint） | TECH-001:AC-01、AC-02、TECH-004:AC-01 |
| SINGLE-108-02 | `verify TECH-001` | 108-01と同じ | — | 108-01と同じ |
| SINGLE-109 | `context REQ-001:AC-01 --purpose implement` | TECH-002がAC-01を具体化し、open TASK-001が2句を`addresses` | REQ-001（root）、TECH-002（refinement）、TASK-001（work） | REQ-001:AC-01、TECH-002:AC-01。adjacentはAC-02 |
| SINGLE-110 | `context TASK-001 --purpose verify` | open TASK-001が`requires` done TASK-002、`addresses` REQ-001:AC-01。TASK-002はREQ-009:AC-01を`addresses` | TASK-001（root）、REQ-001（requirement） | REQ-001:AC-01 |
| SINGLE-113 | `verify REQ-001:AC-01 REQ-001 REQ-001:AC-01` | 107-01と同じ | — | 下記 |

全規範文はMUSTで、verifyとimplementの対象句にはtest対応を置き、coverage不足のwarningを原因へ混ぜない。
109では2句をopen TASKが`addresses`するため、implementのaddressed不足warningも生じない。
兄弟句AC-02は対象でないのでcoverageの各modalityに入らない。

距離は起点0、直接の`requires`・`refines`・`addresses`で1とし、standardでは距離2のrefinement（107-01のTECH-003）を
normative、advisoryをreference（`expandable: true`）で提示する。`reachedBy`は到達edgeのsource文書で表す
（`requires:REQ-001`、`refines:TECH-002`、`addresses:TASK-001`）。Bundleの`frontmatter`は、SINGLE-042と同じく
空のrelation keyと空配列を省略する。

110のcoverage `addressed`には、Context内の起点TASK-001が`addresses`するAC-01を入れる。SINGLE-054
（implementで閉包内のopen TASKが`addresses`する句をaddressedとする）と同じ読みである。done TASK-002と
その対象REQ-009はContextに含めない。

113は起点を正規化して重複排除し、`REQ-001`と`REQ-001:AC-01`の2 targetを辞書順に返す。各targetは別のContextと
Digestを持ち、文書起点は107-01と同じ4句、statement起点はAC-01、TECH-002:AC-01、TECH-003:AC-01の3句である。
共有binding `root::default`は1回だけ実行し、test pathとcoversを重複排除して辞書順に並べる。

## Digest

Digest材料は本moduleのliteral（reference A）と、入力treeから導出するreference B（`digest_crosscheck.py`）で
byte一致を確認する。reference Bは、`requires`の追跡、statementへの`refines`、interpretのdraft advisory
（`applicability: advisory`）、verifyの起点TASKで`requires`を辿らない規則、implementのopen TASK追加へ拡張した。
既存fixtureのCanonical JSONは変わらないことを統合検証で確認した。
107-02と108-02のContext Digestは、同じ起点のcontext fixtureの値と一致することも確認する。

## 準備検証

`expansion_fixtures.py`は、manifest・完全期待JSON・副作用期待値のSchema、入力byte列、YAMLのreview済み解釈と
Frontmatter Schema、2回の隔離setupのGit状態とsnapshotを照合する。4集合はcontext結果から独立に読み戻して
literalと比較する。回帰試験は、roleの入替え、距離2のfull化、advisoryへのstatementRefs追加とLedger収録、
statementRefsの対象句への絞込み、adjacentの欠落、兄弟句のcoverage混入、先行TASKのContext混入、
verifyとcontextの集合・Digestの不一致、targetとtest pathの重複を拒否する。
Core実装の結果ではなく、Gate Bで実出力と副作用を比較する。
