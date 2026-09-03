# Core 1.0実装着手方針

- 状態: Accepted / Reflected
- 作成日: 2026-09-03
- 裁定日: 2026-09-03
- 裁定: G1〜G8を採用。G5を[ADR-044](../02.設計書/10_決定記録/ADR-044_MCP面をCore-1.0のscope外とする.md)、
  G7を[ADR-045](../02.設計書/10_決定記録/ADR-045_実行環境と配布物の確定.md)、
  その他を正本と[実装計画](12_Core-1.0実装計画.md)へ反映済み
- 基準commit: `c72ccc7`
- 対象: [02.設計書](../02.設計書/README.md)、[03.詳細設計](../03.詳細設計/README.md)の実装着手可能性
- 入力: 提案01〜23（提案12を除き全てClosed）、ADR-001〜043
- 前提: 実装コードは未着手であり、repositoryは設計文書だけを保持する

## 1. 総合判定

設計レビューのP0・P1・P2 gateは提案20〜23とADR-041〜043で全てClosedであり、
「Coreが何をするか」の規範契約は実装可能な水準に達している。単一workspaceと明示連合の
責務境界、Diagnostic所有者、status集約、所有境界、resource上限は相互に整合している。

一方で「実装が何を出力すれば適合と言えるか」を閉じる契約に欠落がある。以下のG1〜G4は、
仕様に忠実な2つの実装が互いに異なる出力を返せる箇所であり、着手前に閉じる。G5〜G9は
Phase 1と並行して閉じられる。

| ID | 区分 | 欠落 | 優先度 |
|---|---|---|---|
| G1 | 契約 | Context DigestのCanonical JSONが未定義 | P0 |
| G2 | 契約 | 適合fixtureと期待matrixが非規範文書にしかない | P0 |
| G3 | 契約 | 操作別Diagnostic表が閉じた集合か不明 | P1 |
| G4 | 契約 | 終了コード4の出力契約が未定義 | P1 |
| G5 | 境界 | MCP面が参照されるだけで未仕様 | P1 |
| G6 | 契約 | 非成功時のtext出力契約が未定義 | P2 |
| G7 | 実装 | 実行環境・配布物の規範記述がない | P2 |
| G8 | 衛生 | accepted ADRから旧構造への壊れたリンク | P2 |
| G9 | 実証 | 自身の`.spec/`が存在しない | P2 |

## 2. G1: Context DigestのCanonical JSON

[context仕様 §6](../03.詳細設計/03_操作仕様/01_context.md#6-context-digest)は材料のallowlistを
確定しているが、「Canonical JSON化」の内容を定義していない。次が未確定である。

- keyの並び順、byte単位かcode point単位か
- Unicode正規化の適用範囲（NFCの対象を`text`だけとするか全stringとするか）
- 数値、boolean、null、省略fieldの符号化と「nullと未設定」の区別
- 配列の順序規則（材料ごとに辞書順か、Bundle内の提示順か）
- 「現行本文の意味内容」の具体的なbyte表現

Context Digestは`--expect-digest`（`CTX-STALE-001`／blocked）、
[verifyの`targetResults[].contextDigest`](../03.詳細設計/03_操作仕様/03_verify.md#8-結果)、
適合fixture（`MONO-002`、`MONO-013`）の比較対象であり、公開契約である。定義がなければ
実装間でも同一実装のrefactoring前後でも再現しない。実装計画Phase 1の完了条件
「同一入力から同一IRとDiagnosticを再現」はDigestを含んでいない。

**方針**: `03.詳細設計/00_共通契約/`へ`03_Context Digest正規化仕様`を追加し、
serializationをbyte単位で規定する。固定入力に対する期待digest値を1件fixtureへ置き、
Phase 1の完了条件へ「固定fixtureのDigestが規定値と一致する」を追加する。

## 3. G2: 適合fixtureの正本位置

[実装計画 §6](12_Core-1.0実装計画.md)は適合matrixの正本を
[提案23 §8](23_モノレポ残存P2裁定案.md#8-f-適合fixtureと期待matrix)としている。しかし
[本ディレクトリのREADME §1](README.md)は「レビュー文書は裁定後の仕様の正にしない」と定めており、
1.0の受入基準が非規範文書にだけ存在する状態になっている。

加えて、`MONO-001`〜`MONO-024`は連合だけを対象とする。EARS-AI構文、状態遷移、承認済みREQ保護、
TASK境界、Git縮退、Context上限、projectionといった単一workspaceの契約に対応するmatrixがない。

**方針**: fixture配置、manifest Schema、共通normalizer、期待matrixを
`03.詳細設計/00_共通契約/04_適合fixture仕様`へ移し、`MONO-*`を転記した上で
`SINGLE-*`行を追加する。提案23は検討履歴として据え置く。

## 4. G3: 操作別Diagnostic表の閉包

各操作仕様のDiagnostic表が網羅か例示かを宣言していない。現状では網羅と読めない。

| 操作 | 表にないが発生し得るcode |
|---|---|
| context | `SPEC-CONFIG-SCHEMA-001`、`SPEC-INPUT-READ-001`、`SPEC-MONOREPO-*` |
| verify | `SPEC-CONFIG-SCHEMA-001`、`SPEC-INPUT-READ-001`、target Context解決由来の`CTX-ROOT-MISSING-001`、`CTX-CYCLE-001`、`CTX-STATE-001`、`CTX-STATE-SUPERSEDED-001/002`、`CTX-LIMIT-001` |
| doctor | `SPEC-INPUT-READ-001` |
| 共通 | `SPEC-REPORT-WRITE-001`はどの表にもなく§8本文だけにある |

4操作すべてが`bitz.yaml`を読むにもかかわらず、`SPEC-CONFIG-SCHEMA-001`はcheck仕様にしかない。
また`EAI-CORE-ID-003`はADR-032・037が言及するが詳細設計に定義がなく、
「削除したIDを別の意味へ再利用しない」という規則の保証主体が本文から読めない。

**方針**: 各表へ「本表は当該操作が返し得る全codeとする」を明記し、上記を追補する。
削除ID再利用はADR-037に従いreview責務であることを
[文書・Frontmatter・状態仕様](../03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)へ1文で明示する。

## 5. G4: 終了コード4の出力契約

引数不正・排他違反・解決不能なrevision・catalogにない`--workspace`は終了コード4とし、
「Core操作結果とreportを生成しない」とだけ定めている。`--format json`指定時に標準出力へ
何を返すか、診断文をどこへ書くかが未定義である。adapterは
[context仕様 §11](../03.詳細設計/03_操作仕様/01_context.md#11-adapter契約)でstatusにより分岐するが、
終了コード4はstatusもDiagnosticも持たない。

**方針**: [共通契約 §3](../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#3-statusと終了コード)へ、
終了コード4は形式指定にかかわらずJSON本体を出さず、標準エラーへ1行の理由を出すこと、
adapterは終了コードだけで判別することを規定する。

## 6. G5: MCP面の扱い

[詳細設計README §1](../03.詳細設計/README.md)と
[操作仕様README §1](../03.詳細設計/03_操作仕様/README.md)は「CLI/MCP入力」の所有を宣言し、
`source.kind: invocation`は「CLI/MCP呼出し」、doctorは`SPEC-DOCTOR-CORE-002`「Core/MCP起動不能」を持つ。
一方でtool名、引数Schema、transport、Capability対応はどこにも存在しない。

**方針**: Core 1.0はCLIとJSON結果だけを公開面とし、MCP serverはadapter側の責務としてscope外へ出す。
上記4か所の記述を修正する。ADR 1件で裁定する。MCPを1.0へ含める場合は操作仕様と同等の
入力・結果契約が新規に必要であり、Phase構成が変わる。

## 7. G6: 非成功時のtext出力

[共通契約 §7](../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#7-textとjson)は
成功時1行の内容と「textとJSONでstatus、件数、終了コードを変えない」ことだけを定め、
Diagnosticの描画形式を定めていない。適合fixtureはJSONだけを比較するため、
textは仕様もfixtureも持たない公開面になる。

**方針**: 1行あたり`code`、`severity`、`source`、`summary`を含む固定順の行形式を規定し、
`SINGLE-*` fixtureへtext比較を1件だけ加える。装飾と色はscope外とする。

## 8. G7: 実行環境と配布物

doctorの検査1は「Core実行体、Python version、起動」で不適合を`blocked`とするが、
最低versionが規範に存在しない。この検査は現状のままでは実装できない。実装言語と配布形態を
決めたADR-007・008はADR-009により置換済みで、現行の規範は
[運用手順 §1](../02.設計書/04_運用手順.md)の`uv tool install bitz`という手順例だけである。

**方針**: ADR 1件で、実行環境と最低version、配布物名、`bitz-core` pluginと自己完結CLIの対応、
依存lock方針を確定する。doctorの検査1へ具体的な下限versionを記載する。

## 9. G8: 文書衛生

`docs/`全体で相対linkの参照切れが181件ある。superseded ADRとClosedしたレビュー文書は
時点snapshotであり許容されるが、現行決定を保持する`accepted` ADRのうち次の8件が
ADR-039の再編前の構造（`02_SPECファイル規定/`、`02.設計書/0X_...`）を指している。

`ADR-005`、`ADR-018`、`ADR-020`、`ADR-028`、`ADR-029`、`ADR-031`、`ADR-034`、`ADR-035`

あわせて、doctorの`checks[].status`は`info`／`warning`を含む独自語彙を
[doctor仕様 §7](../03.詳細設計/03_操作仕様/04_doctor.md#7-結果)で定義しているが、
詳細設計README §1はstatusの所有を共通契約としている。

**方針**: accepted ADRの関連文書linkだけを現構造へ更新し、Revision Historyへ非意味的訂正として
1行記録する。superseded ADRとClosed提案は変更しない。`checks[].status`語彙は共通契約側へ移すか、
共通契約から所有を明示的に委譲する。

## 10. G9: 自身の`.spec/`

repositoryはSDD toolの設計文書を持つが`.spec/`を持たない。実装計画Phase 0の比較task 5件と
Phase 5の垂直スライスは、対象となるSPECを前提とする。

**方針**: Phase 1完了時点でbitz-core自身の`.spec/`を作り、以後の実装をSmall Flowで進める。
最初のREQはParserと結果契約に対するものとし、Coreが自分自身をcheck・verifyできる状態を
Phase 3の完了条件へ含める。これは最も安価な適合試験と実用性試験を兼ねる。

## 11. 実装計画への変更提案

[実装計画](12_Core-1.0実装計画.md)のPhase構成は妥当だが、次の2点を変更する。

### 11.1 Step 0を追加する

Phase 1の前に、コードを書かない仕様確定stepを置く。成果物は文書2件とADR 2件である。

| 成果物 | 対象 |
|---|---|
| `00_共通契約/03_Context Digest正規化仕様` | G1 |
| `00_共通契約/04_適合fixture仕様` | G2 |
| 既存文書の追補 | G3、G4、G6 |
| ADR: MCP面のscope | G5 |
| ADR: 実行環境と配布物 | G7 |

完了条件は、G1〜G7が規範文書だけを読んで一意に実装できることである。

### 11.2 実行順を「骨格優先」へ変える

現行計画はdoctorをPhase 3に置くが、doctorは設定読込み、workspace／catalog発見、結果・Diagnostic・
終了コードの配管という、他3操作が全て使う土台だけで成立する最小の操作である。ここを先に通すと、
以後の全phaseが同じ公開面から検証できる。

| Step | 内容 | 完了条件 |
|---|---|---|
| 0 | 仕様確定（§11.1） | G1〜G7が文書だけで一意 |
| 1 | fixture harness、共通結果・Diagnostic・終了コード、設定読込み、`doctor`（単一） | 終了コード0〜4を`SINGLE-*`で区別できる |
| 2 | 候補Scanner、Lexer、Parser、Semantic IR、文書モデル、索引 | 同一入力から同一IRとDiagnosticを再現する |
| 3 | 関係・閉包・Constraint Ledger・coverage・Context Digest・`context`、`check` | 固定fixtureのDigestが規定値と一致し、部分Contextを成功にしない |
| 4 | binding解決、`{tests}`展開、cwd、timeout、`targetResults[]`、`verify` | 成功・非0・起動失敗・signal・timeout・0件をfixtureで区別する |
| 5 | 連合catalog、修飾ID、所有境界、横断Context、`--all-workspaces` | `MONO-001`〜`024`が全て通過する |
| 6 | 自身の`.spec/`によるSDD垂直スライス | 通常Markdown条件との比較で改善を確認する |

Phase 0の実証条件（比較task 5件、基準fixture、測定手順）は現行計画のまま、Step 1と並行して固定する。
性能受入は現行計画 §6の数値と測定方法を変更しない。

## 12. 着手可否

- G1、G2を閉じるまでコード着手を保留する。両者は受入基準そのものであり、後から追加すると
  Phase 1〜4の成果物を作り直すことになる。
- G3〜G7はStep 0で同時に閉じる。いずれも既存の裁定に反さず、記述の追補で足りる。
- G8、G9はStep 1以降と並行して進めてよい。

Step 0の完了をもって実装着手gateをOpenとする。

## 13. 裁定結果（2026-09-03）

G1〜G8を全件採用し、正本へ反映した。G9は着手を妨げないため、実装計画のStep 6へ組み込み、
Step 2完了時点で自身の`.spec/`を作ることとした。

| ID | 裁定 | 反映先 |
|---|---|---|
| G1 | 採用 | [Context Digest正規化仕様](../03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md) |
| G2 | 採用 | [適合fixture仕様](../03.詳細設計/00_共通契約/04_適合fixture仕様.md)。`SINGLE-001`〜`080`を追加 |
| G3 | 採用 | [共通契約 §6.1](../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md)と4操作仕様。`EAI-CORE-ID-003`は予約済みとして明示 |
| G4 | 採用 | [共通契約 §3](../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md) |
| G5 | 採用 | [ADR-044](../02.設計書/10_決定記録/ADR-044_MCP面をCore-1.0のscope外とする.md)。詳細設計README、操作仕様README、`source.kind`、`SPEC-DOCTOR-CORE-002`を訂正 |
| G6 | 採用 | [共通契約 §7](../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md) |
| G7 | 採用 | [ADR-045](../02.設計書/10_決定記録/ADR-045_実行環境と配布物の確定.md)。doctor §3.1へ下限versionを明記 |
| G8 | 採用 | accepted ADR 8件のlinkを現構造へ訂正。`checks[]`語彙の所有をdoctorへ明示委譲 |
| G9 | 条件付き採用 | [実装計画 §9](12_Core-1.0実装計画.md)。着手gateには含めない |

実装計画は、Step 0（仕様確定）を追加し、実行順を骨格優先へ変更した。
これによりStep 0はClosedとなり、実装着手gateはOpenである。
