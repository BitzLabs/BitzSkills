# Core 1.0実装前最終レビューと修正提案

- 状態: Open（裁定・正本反映待ち）
- 実施日: 2026-09-04
- 基準branch: `bitz_next`
- 基準commit: `f47d14704dd4352cc08af538bd3633f4a030573d`
- 対象: [02.設計書](../02.設計書/README.md)、[03.詳細設計](../03.詳細設計/README.md)
- 入力: [提案資料README](README.md)、提案01〜24、ADR-001〜045
- 目的: 仕様検討の最終段階として、実装着手gateを再検証し、残存する契約不足と修正案を確定する

## 1. 結論

Core 1.0の設計方針、責務境界、安全原則、単一workspaceとモノレポ連合の基本モデルは妥当であり、
全面的な再設計は必要ない。一方、現在の規範文書だけから互いに独立した2実装が同一の入力、結果、
Diagnostic、Digest、fixture判定を再現できる状態には達していない。

したがって、本レビュー時点の実装着手判定は**No-Go**とする。
[提案24](24_Core-1.0実装着手方針.md)でOpenとしたgateは、§8のStep 0Bを完了するまで再度閉じることを提案する。

ただし、次は先行してよい。

- repositoryとpackageの骨格
- lint、Schema検証、fixture harness、CIの準備
- 仕様から振る舞いを確定しない内部interfaceの雛形
- 本提案のP0を閉じるための試験入力と期待値の作成

Parser、Context Resolver、Diagnostic生成、Digest、check、verifyの公開挙動を固定する実装は、P0の裁定・反映後に開始する。

## 2. レビュー方法と判定基準

### 2.1 確認範囲

次の観点で`docs/04.提案資料`を検討履歴、`docs/02.設計書`を目的・境界、
`docs/03.詳細設計`を機械契約の正として横断した。

1. 提案の裁定と正本の反映状態
2. 文書間の規範所有、重複、矛盾
3. CLI入力、対象選択、結果Schema、Diagnostic、終了コード
4. EARS-AI構文、Frontmatter、関係、状態、coverage
5. Context Digestの決定性
6. fixtureの再現性と期待値比較
7. Git、path、process、cache、reportの安全境界
8. モノレポ連合、失敗分離、resource上限、性能受入
9. 相対link、見出しanchor、JSON例、ADR metadataの構造整合

### 2.2 Go判定基準

[詳細設計README](../03.詳細設計/README.md#1-規範性)と
[実装計画 Step 0](12_Core-1.0実装計画.md#2-step-0-仕様確定コードを書かない)に従い、
次をすべて満たす場合だけGoとする。

- ADRや提案資料を読まず、規範文書だけで公開挙動を一意に実装できる
- 規範上の各非成功条件がcode、severity、result status、source、優先順位へ一意に対応する
- 公開JSONとtextのfield、型、必須性、null、順序、既定値を完全比較できる
- fixtureの入力状態をmanifestから再現し、1つの正確な期待結果と比較できる
- 同一入力からContext Digestを独立実装間で一致させられる
- timeout、resource上限、path境界、read-only性を有限時間内に検証できる

## 3. Gate summary

| 領域 | 判定 | 概要 |
|---|---|---|
| 設計方針・scope | Pass | local/offline、明示操作、Core非変更、LLM非判定の境界は一貫 |
| 単一workspace・連合モデル | Pass with conditions | identity、所有境界、preflight、独立継続は妥当。対象展開に残件 |
| 公開機械契約 | Fail | 結果Schema、grammar、Frontmatter型、Diagnostic閉包が未確定 |
| 適合受入 | Fail | matrixとmanifestが自己矛盾し、期待成果物が未作成 |
| 決定性 | Fail | Digestと一部sortにtie、型外正規化、version値の未確定がある |
| 安全性 | Pass with conditions | 基本原則は妥当。cacheとprocess終了契約に残件 |
| 文書構造 | Pass with hygiene issues | 現行正本linkとJSON例は良好。accepted ADRに旧linkが残る |
| 総合gate | **No-Go** | P0 6件を閉じてから再判定 |

## 4. P0: 実装着手前に閉じる項目

### 4.1 `FIN-FIX-001`: 適合fixtureが再現可能な契約になっていない

#### 問題

[適合fixture仕様 §2](../03.詳細設計/00_共通契約/04_適合fixture仕様.md#2-配置)は
`fixtures/conformance/`配下のversion管理成果物を受入条件とするが、基準commitに`fixtures/`は存在しない。
実体は実装工程で作成できるものの、現在のmatrixとmanifestだけでは一意な実体を作れない。

特に次が競合する。

- §2は「1つのfixtureへ複数の独立原因を混ぜない」とするが、`SINGLE-012`、`SINGLE-017`は複数原因と複数codeを持つ。
- §3は1つの正確な終了コードとstatusを要求するが、`SINGLE-069`、`070`、`071`、`075`、`076`は`元statusと同じ`、
  `SINGLE-080`は`passed/0、failed/1`という複数期待を1 IDに持つ。
- `setup.baseCommit`と`setup.currentState`だけでは、base treeからcurrent treeへ加える変更、staging対象、rename、削除を表現できない。
- `SINGLE-042`を含め、固定入力に対する期待Context Digestの実値がない。
- text normalizerは「所要時間を含む行」を除外するため、所要時間を含む共通要約行からstatus、scope、件数まで除外する。

#### 影響

実装者ごとにfixture分割、Git setup、比較除外項目が変わる。matrix通過が同じ適合性を意味せず、
Step 1以降の完了条件を客観的に判定できない。

#### 修正案

1. 1 IDを1 invocation、1独立原因、1 exit code、1 statusへ分割する。
2. `setup`へ次のいずれかを規範化する。
   - `base/`と`current/`の2 tree
   - base commit後に適用する固定patchと`stagePaths[]`
   - `operations[]`によるcreate/update/delete/rename/stageの宣言
3. 各IDへ実際の`repo/`、`manifest.json`、`expected/*.json|txt`を追加する。
4. text normalizerは要約行全体ではなく`(<duration>ms)` tokenだけを置換する。
5. Digest fixtureへCanonical JSON byte列と期待`sha256:`値を置く。

#### 完了条件

- matrixの全行が単一のmanifestと期待fileへ対応する
- 選択肢、範囲、`元status`という期待表現が0件である
- clean、staged、worktree、rename、delete、unbornをmanifestだけから再現できる
- 同一fixtureを2回実行し、normalizer後の結果がbyte一致する

### 4.2 `FIN-DIAG-001`: Diagnostic表の閉包が成立していない

#### 問題

[共通契約 §6.1](../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#61-diagnostic表の閉包)は
各操作の固有codeを閉じた集合とする。しかし、次の規範条件はDiagnosticを発生させるにもかかわらず、
対応codeまたは優先順位が明示されていない。

- 既存BOMのwarning
- 利用できないCore fieldのwarning
- `x-`で始まらない未知Frontmatter fieldのwarning
- 未知設定keyと`profiles`のwarning
- Frontmatterの型不正、重複key、禁止YAML構文
- 単一workspaceのresource上限超過
- `SHOULD`に理由がない場合のwarning
- Git不在時の縮退で返すinfo/warningの一部

また、設定不正に対する共通`SPEC-CONFIG-SCHEMA-001`とdoctor固有
`SPEC-DOCTOR-CONFIG-001`の関係が一意でない。doctor仕様は後者が前者を置換しないとする一方、
全操作共通codeも適用すると記載するため、同一原因へ一方または両方を返す実装が成立する。

#### 修正案

1. 規範条件を行単位で列挙したDiagnostic registryを共通契約に追加する。
2. 各行へ`conditionId`、code、severity、result status、source kind、継続単位、primary優先順位を持たせる。
3. doctorの設定不正は次のいずれかへ統一する。
   - 共通codeだけをDiagnosticへ置き、doctor check itemがそれを参照する
   - doctor固有codeだけを返し、共通codeの適用対象からdoctorを除く
4. 1原因1primary Diagnosticをfixtureで検証する。

#### 完了条件

- 規範文書に現れる全`warning`、`failed`、`blocked`、`error`条件がregistryに存在する
- codeのない非成功規則が0件である
- 同一原因に対する重複Diagnosticの有無と優先順位がfixtureで固定される

### 4.3 `FIN-EAI-001`: EARS-AI grammarと候補Scannerが未完結

#### 問題

[言語・Semantic IR仕様 §3](../03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md#3-正規構文)は
`text`、`DQUOTE`、`qchar`、`escaped`を参照するが定義していない。記法もEBNFとABNFの
`%x`、`/`、`*`が混在する。

[同仕様 §5](../03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md#5-規範行候補)の
「文書IDらしいtoken」は字句規則になっておらず、短いID、未知prefix、3階層、ID欠落を
どこまで候補に含めるかが実装依存になる。複数backtick code span、quoted value、escape解除、
`SHOULD`理由、`EAI-CORE-LANG-001`の言語判定も決定手順が不足する。

#### 修正案

1. grammar記法をISO EBNF相当またはABNFのどちらか1つへ統一する。
2. UTF-8 code point単位のtoken、escape、quoted value、code spanを完全定義する。
3. 候補Scannerを有限状態機械または同等の擬似codeで定義する。
4. `SHOULD`理由を構文fieldにするか、理由なしwarning規則をCore 1.0から除く。
5. 言語不一致を判定するなら決定論的規則を定義し、できない場合は該当Diagnosticをscope外へ出す。
6. scanner、lexer、parser、validatorの各段階に正例・反例・境界値を追加する。

#### 完了条件

- grammarに未定義nonterminalがない
- 候補抽出、parse、Diagnostic位置をfixtureで完全比較できる
- 同一行へ返すprimary syntax codeが一意である

### 4.4 `FIN-OUT-001`: 公開結果Schemaとtext出力が完全ではない

#### 問題

[共通結果](../03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#2-共通結果)では
`scope`と`revision`の必須性が「操作依存」のままであり、4操作と単一／連合の完全なvariantが
machine-readable Schemaになっていない。

残件は次のとおりである。

- context例は16桁commit、fixture仕様は40桁小文字commitを要求する
- 各操作の既定`--format`がない
- Context `documents[]`の`full`、`normative`、`reference`別field、null、省略条件が完全でない
- `revision`のbase、commit、dirtyと`null`になる条件が操作別に閉じていない
- textの`targets=<n>`がcontext、check、doctor、連合で何を数えるか不明である
- 全体結果のtop-levelとmember Diagnosticを`diagnostics=<n>`へどう数えるか不明である
- verifyが保持するstdout/stderr抜粋の公開fieldがない

#### 修正案

1. JSON Schema Draft 2020-12等で共通定義と操作別`oneOf`をversion管理する。
2. 各fieldのrequired、nullable、enum、additionalProperties、配列順を文書とSchemaで一致させる。
3. Git commitは40桁小文字16進へ統一する。
4. 4操作の既定formatを明示する。
5. text件数をJSON上のどのfieldまたは導出式へ対応させるか定義する。
6. process抜粋を公開しないなら表示もしない。公開するならredacted excerpt Schemaを追加する。

#### 完了条件

- 単一／連合、成功／非成功の全期待JSONがSchema validationを通過する
- 例示JSONと規範Schemaの不一致が0件である
- text要約の全tokenをJSON結果から一意に導出できる

### 4.5 `FIN-TARGET-001`: target展開規則が操作間で一致していない

#### 問題

[関係・トレースモデル §8](../03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#8-coverage)は
REQ／規範文ありTECHのtarget statementを「所有statementとapplicable refinement」とする。
一方、[verify仕様 §3](../03.詳細設計/03_操作仕様/03_verify.md#3-対象)は
「所有statementとapplicable dependency/refinement」とし、dependencyが所有するstatementを
test対象へ含めるかが一致しない。

また、次が未確定である。

- `check`へ構文上有効だがcatalogに存在しない文書IDまたはstatement IDを渡した場合
- contextの一般的なSPEC ID表現に対するADR起点の可否
- TASKの`addresses`句と`requires`閉包で、依存文書のどのstatementをcoverage対象にするか
- 複数起点の同一statement、refinement、test bindingの重複排除時点

#### 修正案

1. `TargetExpansion(root, purpose)`を関係仕様に1つだけ定義し、各操作は参照する。
2. 出力を`rootDocuments`、`contextDocuments`、`targetStatements`、`adjacentStatements`へ分離する。
3. dependencyはContext材料かtest義務かをpurposeごとに明記する。
4. 明示target不存在を終了コード4または`CTX-ROOT-MISSING-001`のどちらかへ統一する。
5. ADRを起点にできる操作とpurposeを明記する。

#### 完了条件

- 同じroot/purposeに対するcontextとverifyのtarget statement集合が一致する
- root種別ごとの期待集合をfixtureで完全比較できる
- 不存在targetが操作、入力形式、workspaceによって揺れない

### 4.6 `FIN-FM-001`: Frontmatter型とYAML subsetが内部矛盾する

#### 問題

[文書・Frontmatter・状態仕様 §3](../03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md#3-共通field)は
`tests`を`object[]`とする。一方、[同仕様 §11](../03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md#11-yaml制約)は
scalar、scalar配列、通常mapだけを許可し、object配列を明示的に許可していない。
設定仕様ではobject配列を`monorepo.members`だけに限定しており、文書Frontmatterとの規則も揃っていない。

さらに、配列重複の同値条件、map内の未知key、nullと空値、titleの文字数単位、`TASKのみNo`という
必須性表記が実装可能な型制約になっていない。

#### 修正案

1. 文書Frontmatterの完全な構造Schemaを追加し、`tests` object配列を明示的に許可する。
2. 設定YAMLとFrontmatter YAMLの共通subsetと個別追加型を分離する。
3. duplicate判定を正規化後の構造等値またはkey tupleで定義する。
4. null、空string、空配列、省略の許否をfieldごとに定義する。
5. 文字数をUnicode code point等の測定単位で固定する。

#### 完了条件

- 全正例FrontmatterがSchemaを通過し、全禁止例が一意なDiagnosticで失敗する
- `tests`を含む規範例とYAML subsetが矛盾しない

## 5. P1: 該当componentの実装前に閉じる項目

### 5.1 `FIN-DIGEST-001`: Context Digestの残存非決定性

- `resolverVersion`のCore 1.0値を`"1.0"`等へ固定する。
- `tests`のsortを`(path, command, covers)`等の完全順序にするか、同一pathの複数要素を禁止する。
- extensionのsortへ`value`を加えるか、同一namespace/termの重複を禁止する。
- path separator変換は全stringではなくpath型fieldだけへ適用する。
- golden Canonical JSONとdigestを最低1件、単一と連合で固定する。

対象: [Context Digest正規化仕様](../03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md)

### 5.2 `FIN-IO-001`: read-onlyとcache writeの境界

`context`と`doctor`はfileを書かない、`check`は既定でread-onlyとする一方、共通契約とfixtureは
cacheを例外扱いできる。次のいずれかへ統一する。

1. Core 1.0の全適合試験でcache writeを既定無効にする
2. repository外の明示cache rootだけを書込み可能にする
3. 「fileを書かない」を「正本とworkspaceへ書かない」に変更し、cache副作用をSchema化する

対象: [安全な入出力 §2・§7](../03.詳細設計/00_共通契約/02_安全な入出力・互換性.md)

### 5.3 `FIN-PROC-001`: verify processの安全性とliveness

次をcommand実行契約へ追加する。

- argv要素の型、空文字、長さ、NUL、`argv[0]`のPATH解決
- 継承する環境変数、追加／除去する環境、locale、stdinの扱い
- timeout時のsignal、猶予時間、直接processの終了確認、pipeを閉じる条件
- 子孫processがstdout/stderr FDを保持した場合でも操作が有限時間で戻る条件
- `spawn_error`と「環境不足によるblocked」の境界
- 抜粋の切捨て、制御文字無害化、secret maskの決定規則

対象: [verify仕様 §5・§6](../03.詳細設計/03_操作仕様/03_verify.md#5-command実行)

### 5.4 `FIN-CLI-001`: CLI既定値とADR依存

- `context`、`check`、`verify`、`doctor`の既定formatを規範化する。
- `--timeout`の1〜3,600秒をADRだけでなくverify仕様へ記載する。
- duplicate option、空target列、`--report`のpathと排他、未知targetの処理を確定する。
- CPython/Git下限、配布物名、実行時依存、YAML loader条件をADR-045から詳細設計の規範節へ移す。
  ADR-045は判断理由を保持する。

[詳細設計README §1](../03.詳細設計/README.md#1-規範性)が
「ADRを読まなければ実装できない契約を残してはならない」と定めるため、
doctor仕様が値の所有者をADR-045とする現状は解消する。

### 5.5 `FIN-PERF-001`: 性能受入成果物が未作成

[品質属性と安全境界](../02.設計書/02_品質属性と安全境界.md#4-性能予算)が要求する
version管理済み基準fixture、環境manifest、比較task、成功基準を作成する。
[実装計画 Step 0-P](12_Core-1.0実装計画.md#3-step-0-p-実証条件)は「Step 1と並行」と
「実装前に固定」を同時に記載するため、少なくとも入力fixtureと測定基準はStep 1開始前に固定する。

## 6. P2: 文書衛生と実証上の残件

### 6.1 `FIN-DOC-001`: accepted ADRの旧link

現行の`docs/02.設計書`主要文書と`docs/03.詳細設計`では相対linkと見出しanchorの不整合を検出しなかった。
一方、accepted ADRではADR-001に2件、ADR-016に5件の旧相対linkが残る。

修正対象:

- [ADR-001](../02.設計書/10_決定記録/ADR-001_EARS-AI旧検討版の位置づけ.md)
- [ADR-016](../02.設計書/10_決定記録/ADR-016_Agent-Plugins準拠の複数プラグイン配布.md)

旧構造を記録するsuperseded ADRとClosed提案は時点snapshotとして維持し、accepted ADRだけを修正する。

### 6.2 `FIN-DOC-002`: 提案資料READMEの状態表示

提案資料README §22の見出しは「裁定待ち」のままだが、本文は提案24を採用・反映済み、gate Openとしている。
見出しを「裁定・反映済み」へ訂正し、本提案による再レビュー結果を次節へ追加する。

### 6.3 `FIN-SELF-001`: 自身の`.spec/`による実証

基準commitに`.spec/`は存在しない。これは提案24で着手gate外と裁定済みのためP0へ戻さないが、
Step 6まで遅らせず、grammar、Schema、checkが安定した時点で自身の仕様を作成する方がよい。
自己適用により、文書作成負荷、Context量、Diagnosticの実用性を性能試験より早く確認できる。

## 7. 確認できた強み

次の点は現在の設計を維持する。

1. `docs/03.詳細設計`を機械契約、`docs/02.設計書`を目的・境界、ADRを判断理由、
   提案資料を検討履歴とする所有階層は明確である。
2. Coreはlocal/offlineで動作し、LLMやtest出力の自然言語を合否判定へ使わない。
3. `context`、`doctor`、`check`、`verify`の責務分離と、暗黙のSPEC変更を行わない原則は妥当である。
4. モノレポの明示catalog、永続workspace ID、修飾ID、canonical所有境界、global preflightは整合している。
5. global preflight後に文書、target、binding単位で独立処理を継続する方針は、可用性と失敗分離を両立する。
6. verifyの`targetResults[] -> bindingRefs[] -> commands[]`証跡とreport明示保存は監査可能性が高い。
7. status 0〜3と引数不正exit 4を分ける基本モデルは明確である。
8. 現行正本の相対link・anchor、JSON例の構文、ADR 45件のID・status・H1・Revision Historyは概ね整合している。

## 8. 修正実行案: Step 0B

### 8.1 実行順

| 順序 | 作業 | 主対象 | 完了証拠 |
|---:|---|---|---|
| 1 | grammar、Frontmatter、公開結果、Diagnostic registryを閉じる | P0-2〜4、6 | Schema validation、parser vectors |
| 2 | target展開とDigestを確定する | P0-5、P1-1 | target集合fixture、golden digest |
| 3 | fixture manifestとmatrixを分割する | P0-1 | 全IDに実入力と単一期待値 |
| 4 | cache、process、CLI、実行環境を確定する | P1-2〜4 | 副作用・timeout・CLI fixture |
| 5 | 性能入力と基準環境を固定する | P1-5 | benchmark fixture、manifest |
| 6 | linkと状態表示を修正する | P2-1〜2 | link checker 0件 |
| 7 | 独立実装相当のcross-checkを行う | 全体 | 2系統のserializer/parser結果一致 |

### 8.2 正本への反映候補

| 反映先 | 主な修正 |
|---|---|
| `00_共通契約/01_結果・Diagnostic・終了コード.md` | 完全結果variant、件数定義、Diagnostic registry |
| `00_共通契約/02_安全な入出力・互換性.md` | cache write、process出力、redaction |
| `00_共通契約/03_Context-Digest正規化仕様.md` | version、完全sort、path型限定正規化、golden値 |
| `00_共通契約/04_適合fixture仕様.md` | 1 ID 1結果、Git setup、normalizer、実成果物対応 |
| `01_EARS-AI/01_言語・Semantic-IR仕様.md` | 完全grammar、Scanner、escape、SHOULD理由 |
| `02_SPECモデル/01_workspace・設定仕様.md` | argv、YAML subset、実行環境規範 |
| `02_SPECモデル/02_文書・Frontmatter・状態仕様.md` | 完全Frontmatter Schema、object配列、null・重複 |
| `02_SPECモデル/04_関係・トレースモデル.md` | `TargetExpansion`の単一所有 |
| `03_操作仕様/*.md` | 既定format、target不存在、process、結果variant参照 |
| `12_Core-1.0実装計画.md` | Step 0Bとgate再開条件 |

## 9. Gate再開条件

次を全件満たしたcommitに対して再レビューする。

- [ ] P0 6件に裁定があり、`docs/03.詳細設計`へ反映済み
- [ ] 公開JSON例がmachine-readable Schemaを全件通過
- [ ] 規範上の全非成功条件がDiagnostic registryへ対応
- [ ] grammarに未定義token/nonterminalがない
- [ ] target種別×purposeの期待集合fixtureが存在
- [ ] fixture matrixに選択的期待、複数原因、`元status`がない
- [ ] Git base/current/staged/worktree/unbornをmanifestから再現可能
- [ ] 単一と連合のgolden Context Digestが固定済み
- [ ] read-only、report、cacheの許可書込みが副作用fixtureと一致
- [ ] timeoutと子process/pipe保持時も規定時間内に終了
- [ ] 性能基準fixtureと環境manifestがversion管理済み
- [ ] 現行正本とaccepted ADRの相対link検査が0件
- [ ] 実装計画のStep 0BがClosed

## 10. 提案する裁定

| ID | 提案 |
|---|---|
| D1 | 現在の実装着手gate Openを撤回し、Step 0B完了までClosedとする |
| D2 | §4の6件をP0として全件採用する |
| D3 | §5の5件を該当component実装前のP1として採用する |
| D4 | fixtureは文書上のmatrixだけでなく、実入力・manifest・期待結果までversion管理する |
| D5 | 公開結果とFrontmatterへmachine-readable Schemaを追加する |
| D6 | Diagnostic registryと`TargetExpansion`を単一所有者へ集約する |
| D7 | ADR-045の現行規範値を詳細設計へ移し、ADRは理由の記録へ戻す |
| D8 | P0反映後、§9を満たす自動検査結果を添えてgateを再判定する |

本提案の採否と正本反映が完了するまでは、実装計画のStep 1完了条件を満たせない。
したがって、契約修正と検証基盤以外の機能実装を開始しない。
