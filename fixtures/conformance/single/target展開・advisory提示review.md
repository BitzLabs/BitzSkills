# 共通の対象展開と参考（`advisory`）の提示のfixtureのレビュー記録

2026-09-17。SINGLE-106-03、107-01／02、108-01／02、109、110、113の8件を追加する。
根拠は[関係・トレースモデル §6・§7](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#6-目的ごとの閉包)、
[`context`仕様 §4・§5](../../../docs/03.詳細設計/03_操作仕様/01_context.md#4-コンテキスト一式)、
[`verify`仕様 §3・§4](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#3-検証対象)、
[コンテキストのハッシュ値の正規化仕様](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md)である。

## 作成前の裁定

期待値を一意に決められない規範の欠落3件と矛盾1件を、作成前に次のとおり裁定し、正本へ反映した。
経緯は[診断の網羅表の再レビュー](../Diagnostic意味網羅review.md)に記録した。

| 論点 | 裁定 | 反映先 |
|---|---|---|
| `requires`または`addresses`の参照先の役割 | REQは役割`requirement`、TECHと`accepted`のADRは役割`constraint`。複数に該当する場合は表の上から | 関係・トレースモデル §7 |
| 参考（`advisory`）の発生経路 | 目的`interpret`で、閉包内の文書を`refines`する`draft`の文書を参考（`advisory`）として含め、その先はたどらない | 関係・トレースモデル §6.1 |
| 規範文を起点にしたときの提示 | `statementRefs`は所有するすべての規範文、制約台帳とカバレッジは対象規範文だけ、`coverage.adjacent`は兄弟句 | `context`仕様 §4・§5 |
| `verify`の起点のTASKの`requires` | §6.3（含めない）を正とし、matrixの110の行とtarget vectorを修正 | matrix、`targets/cases.json` |

## 入力と期待展開

| ID | 起動 | corpus | `contextDocuments`（役割／提示形式） | 対象規範文 |
|---|---|---|---|---|
| SINGLE-106-03 | `context REQ-001 --purpose interpret` | REQ-001と、その規範文を`refines`する`draft`のTECH-005 | REQ-001（`root`／`full`）、TECH-005（`advisory`／`reference`） | なし |
| SINGLE-107-01 | `context REQ-001 --purpose verify` | REQ-001が、REQ-009を`requires`、REQ-099を`related`で参照する。TECH-002がAC-01を、TECH-003がTECH-002:AC-01を具体化 | REQ-001（`root`）、REQ-009（`requirement`）、TECH-002（`refinement`）、TECH-003（`refinement`／`normative`） | REQ-001:AC-01、AC-02、TECH-002:AC-01、TECH-003:AC-01 |
| SINGLE-107-02 | `verify REQ-001` | 107-01と同じ | — | 107-01と同じ |
| SINGLE-108-01 | `context TECH-001 --purpose verify` | 規範文を持つTECH-001が、TECH-009を`requires`で参照する。TECH-004がTECH-001:AC-01を具体化 | TECH-001（`root`）、TECH-004（`refinement`）、TECH-009（`constraint`） | TECH-001:AC-01、AC-02、TECH-004:AC-01 |
| SINGLE-108-02 | `verify TECH-001` | 108-01と同じ | — | 108-01と同じ |
| SINGLE-109 | `context REQ-001:AC-01 --purpose implement` | TECH-002がAC-01を具体化し、`open`のTASK-001が2つの規範文を`addresses`する | REQ-001（`root`）、TECH-002（`refinement`）、TASK-001（`work`） | REQ-001:AC-01、TECH-002:AC-01。隣接規範文はAC-02 |
| SINGLE-110 | `context TASK-001 --purpose verify` | `open`のTASK-001が、`done`のTASK-002を`requires`で参照し、REQ-001:AC-01を`addresses`する。TASK-002はREQ-009:AC-01を`addresses`する | TASK-001（`root`）、REQ-001（`requirement`） | REQ-001:AC-01 |
| SINGLE-113 | `verify REQ-001:AC-01 REQ-001 REQ-001:AC-01` | 107-01と同じ | — | 下記 |

すべての規範文は`MUST`で、目的が`verify`または`implement`の対象規範文にはテスト対応を置き、カバレッジの不足による警告を原因へ混ぜない。
109では、2つの規範文を`open`のTASKが`addresses`するため、目的`implement`で未対応による警告も生じない。
兄弟句AC-02は対象規範文でないので、カバレッジの各規範強度に入らない。

距離は、起点を0、直接の`requires`、`refines`、`addresses`を1とする。詳細度`standard`では、距離2の役割`refinement`の文書
（107-01のTECH-003）を提示形式`normative`で、役割`advisory`の文書を提示形式`reference`（`expandable: true`）で提示する。
`reachedBy`は、到達したエッジの参照元の文書で表す
（`requires:REQ-001`、`refines:TECH-002`、`addresses:TASK-001`）。コンテキスト一式の`frontmatter`は、SINGLE-042と同じく、
空の関係のキーと空の配列を省略する。

110のカバレッジの`addressed`には、コンテキストに含まれる起点のTASK-001が`addresses`するAC-01を入れる。SINGLE-054
（目的`implement`で、閉包内の`open`のTASKが`addresses`する規範文を`addressed`とする）と同じ読みである。`done`のTASK-002と、
その対象のREQ-009は、コンテキストに含めない。

113は起点を正規化して重複排除し、`REQ-001`と`REQ-001:AC-01`の2つの検証対象を辞書順に返す。各検証対象は別のコンテキストと
ハッシュ値を持ち、文書を起点にした場合は107-01と同じ4つの規範文、規範文を起点にした場合はAC-01、TECH-002:AC-01、
TECH-003:AC-01の3つの規範文である。共有するテスト割当て`root::default`は1回だけ実行し、テストのパスと`covers`を
重複排除して辞書順に並べる。

## ハッシュ値

ハッシュ値の材料は、本モジュールのリテラル（参照計算A）と、入力の木構造から導出する参照計算B（`digest_crosscheck.py`）で
バイト一致を確認する。参照計算Bは、`requires`の追跡、規範文への`refines`、目的`interpret`の`draft`の参考
（`applicability: advisory`）、目的`verify`の起点のTASKで`requires`をたどらない規則、目的`implement`の`open`のTASKの追加へ拡張した。
既存のfixtureの正規JSONは変わらないことを監査で確認した。
107-02と108-02のコンテキストのハッシュ値は、同じ起点の`context`のfixtureの値と一致することも確認する。

## 準備検証

`expansion_fixtures.py`は、マニフェスト・完全な期待JSON・副作用の期待値のスキーマ、入力のバイト列、YAMLのレビュー済みの解釈と
フロントマターのスキーマ、隔離した2回の準備手順のGitの状態とスナップショットを照合する。4つの集合は`context`の結果から独立に読み戻して
リテラルと比較する。回帰試験は、役割の入替え、距離2の`full`化、参考（`advisory`）への`statementRefs`の追加と制約台帳への収録、
`statementRefs`の対象規範文への絞込み、`adjacent`の欠落、兄弟句のカバレッジへの混入、先行のTASKのコンテキストへの混入、
`verify`と`context`の集合・ハッシュ値の不一致、検証対象とテストのパスの重複を拒否する。
Core実装の結果ではなく、Gate Bで実出力と副作用を比較する。

## 2026-09-26追記: 距離2以上の役割の例外（`SINGLE-106-06`）と詳細度`compact`（`SINGLE-106-07`）

2026-09-25に管理者が承認した方針を反映したコミットで、[`context`仕様 §5](../../../docs/03.詳細設計/03_操作仕様/01_context.md#5-提示形式)へ、
詳細度`standard`の提示形式の規則（役割が`root`、`work`、`replacement`、`requirement`、`constraint`のいずれかなら`full`、
それ以外で距離2以上の役割`refinement`なら`normative`、役割`advisory`なら`reference`）と、ADR-014の`Decision` 4・5に基づく理由
（役割`requirement`と役割`constraint`を距離で下げると、`MUST`の本文が制約台帳からも提示からも失われる）が明記された。
あわせて、詳細度`compact`が役割を問わず全文書を提示形式`reference`で提示することも明記された。これに合わせ2件を追加した。

- `SINGLE-106-06`: `corpus_distance()`（REQ-001が`requires`でTECH-010（距離1、規範文なし）を、TECH-010が`requires`で
  REQ-020（距離2、`REQ-020:AC-01`の`MUST`を1件持つ）を参照する、新しいcorpus）で、距離2の`TECH-010`とその先のREQ-020が
  ともに提示形式`full`になり、`REQ-020:AC-01`の`MUST`の本文が`REQ-020`の`bodyText`に現れることを固定する。
  `TECH-010`は規範文が0件のため、ハッシュ値の材料の末尾の正規化（`digest_crosscheck.normalize_body`が行う、末尾の空行の除去）と
  一致するよう、corpusの側でも、本文の末尾に余分な空行を持たせないようにした（`technical()`の共有テンプレートをそのまま
  使うと末尾に空行が残るため、その1箇所だけ`rstrip`する）。
- `SINGLE-106-07`: `corpus_refinement()`（`SINGLE-107-01`と同じcorpus）を`--detail compact`で解決し、全文書が
  提示形式`reference`（`expandable`を持ち、`statementRefs`、`frontmatter`、`bodyText`を持たない）になること、
  コンテキストのハッシュ値が`--detail`を省略した場合の`SINGLE-107-01`と同じ値であることを固定する。`reviewed_context`の
  `projection.detail`を、`plan`の`detail`キー（既定`standard`）から読むよう一般化した。

いずれも、ハッシュ値の材料（参照計算AとB）の一致、読取り専用の副作用、準備手順の2回の適用の決定性を、既存のケースと同じ監査で検査する。
根拠は[`context`仕様 §5・§6](../../../docs/03.詳細設計/03_操作仕様/01_context.md#5-提示形式)、
[ADR-014](../../../docs/02.設計書/10_決定記録/ADR-014_Semantic-IRと段階的Context-Projection.md)。
Core実装の観測出力を根拠にしていない。
