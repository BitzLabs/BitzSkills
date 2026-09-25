# Diagnostic意味網羅review

実施日: 2026-09-07。更新日: 2026-09-08。状態: **review完了（実装受入は別工程）**。

`diagnostic-coverage.json`はregistryの各conditionIdを規範の根拠文書と判断理由へ対応付けるreview台帳である。
codeの文字列一致を意味網羅の証明とはしない。validatorは対応の欠落・重複・未知ID、根拠文書とregistryの変更を
検出する。文書が変わった場合は意味を再確認してから台帳のhashを更新する。自動実行でhashを更新しない。
registryから派生する対応表はreview記録であり、独立した動作oracleではない。

## 修正した不整合

| 論点 | 根拠 | 修正 |
|---|---|---|
| implementの未tested MUST | 関係・トレースモデル §8、context §9 | warning行を追加 |
| context purpose=verifyの未tested MUST | 関係・トレースモデル §8、context §9 | blocked行のoperationへcontextを追加、purposeを限定 |
| 未tested SHOULD | 関係・トレースモデル §8 | purposeをimplement/verifyへ限定し、verify索引にもwarningを明記 |
| 複合workspace依存遮断の継続単位 | 複合workspace仕様 §8、verify §10、doctor §3 | skip-workspaceからtarget/check別へ分割。checkは具体的relation診断を使用 |
| YAML禁止構文の列挙 | workspace設定 §8、CLI基盤 §3 | 複雑key・複数documentをregistryへ補完 |
| statement ID重複 | 言語仕様、registry §4 | 関係モデル索引をEAI-CORE-ID-002へ訂正 |

## 非成功条件の裁定

### DG-OPEN-001: command設定のGit管理要件

安全な入出力 §3はcommandをGit管理されたbitz.yamlからだけ取得すると規定する一方、§8はGit不在でも
test実行を継続すると規定する。Git不在時の信頼確認方法、未追跡設定を検出したときのcode・status・source・継続単位は
registryにない。Git不在の扱いと、Gitが使える場合の未追跡設定拒否を分けて裁定する必要がある。
裁定: Git利用可能時はindexでの追跡を要求し、未追跡設定は`VERIFY-CONFIG-UNTRACKED`へ対応付けた。
codeは既存の`SPEC-VERIFY-BLOCKED-001`、error／blocked、file、skip-bindingとする。追跡済み設定のworking tree変更は
許可する。Git不在の単一workspaceは既存のverify継続契約を優先し、現在設定を使うが追跡保証をしない。
複合workspaceはGit不在事前検査で遮断する。新しいCLI flagや暗黙command取得元は追加しない。

### DG-OPEN-002: test pathがcommand cwd配下にない場合

workspace設定 §6はtest pathをcwd配下に限定するが、双方が存在し同一workspace内にある場合の
違反について、設定Schema不正、trace path不正、verify binding遮断のどれを返すかが未確定である。
VERIFY-CWD-UNAVAILABLEはcwd不在、MULTI-OWNERSHIPは所有境界越えであり、そのまま同じ原因に当てはめられない。
裁定: 所有境界・存在検査後にverifyだけが包含検査を行い、`VERIFY-TEST-OUTSIDE-CWD`へ対応付ける。
codeは`SPEC-VERIFY-BLOCKED-001`、error／blocked、file、skip-bindingとする。sourceはtest対応の宣言SPEC。
check/doctorの責務をtarget別binding解決へ拡張しない。`{tests}`なしでも同じ条件を適用する。

### DG-OPEN-003: 別repository/worktreeへのmember path

複合workspace仕様 §5.1・§11は既知の別repository/worktreeへのmember pathをSPEC-MULTI-PATH-001／failedとするが、
§10は同じ解決結果をSPEC-MULTI-GIT-001／blockedにも含めている。既知の不適合と境界確定不能を
区別する方針を採用した。既知の別repository/worktreeはPATH／failed、境界を確定できない場合はGIT／blockedとし、
§10を§5.1と整合させた。同じ原因へ両codeを返さない。

## Diagnosticを生成しない条件

- CLI構文、option、対象種別、未知workspace、明示base解決不能: 終了コード4。操作結果・reportなし。
- 起動済みtestの通常非0終了: command結果からfailedを集約。Diagnosticなし。
- 単一workspaceのcontext/verifyでGit差分保証を要求しない呼出し: Git不在だけではDiagnosticなし。
- process出力の不正UTF-8・制御文字・秘密値・保持上限: 置換、redaction、truncated表示で処理。自然言語で合否判定しない。
- cacheの内容、IDの全履歴再利用、自然言語判定、style推奨、Profile: Core 1.0の検査対象外。未知entry等の別規則は維持。
- adapterの書込み可否、配布物の構築要件、consumerの互換性拒否: Core操作Diagnosticを新設する条件ではない。

## 検証と完了条件

`uv run fixtures/validate_conformance.py`は台帳の整合性と変更検出を実行する。回帰検査は対応欠落、未知ID、
根拠改変、未裁定条件が残る場合の非完了を確認する。修正した条件に対する期待operation/status/continuationも固定する。
上記3件の裁定を規範・registry・台帳へ反映した。119条件を14論点群・17根拠文書へ対応付け、未裁定事項は0件とする。
判定は人手で確認した規範対応のreview結果であり、自然言語の意味をvalidatorが自動証明するものではない。
適合fixtureによるCore実装の実証は別工程であり、本reviewでは代替しない。

## 2026-09-14の再review（関係・トレースモデル §6.3）

`verify`の起点TASKについて、`addresses`先と当該先を所有する文書を`contextDocuments`へ含めることを明文化した。
既存の裁定を変更せず、verify仕様 §3が要求する「TASKは自身の`addresses`先を対象にする」を実行可能にするだけの
記述整合であるため、新規ADRは起こさない。

- 新規のDiagnostic条件は生じない。`addresses`はstrong relationであり、解決不能な先は既存の
  `SPEC-RELATION-MISSING-001`（strong target不在）が担う。119条件・14論点群の対応に変更はない。
- target展開の期待集合25 caseは、参照計算が以前からこの読みを実装しており、期待値の変更は0件である。
  変更は文書側の欠落を埋めるものであり、reviewされた期待に文書を合わせた。
- 上記を確認したうえで、台帳と`targets/cases.json`が固定する根拠文書hashを更新した。

## 2026-09-17の再review（report directoryのsymlink）

SINGLE-125-06の発生条件を確定するため、結果・Diagnostic・終了コード §8に「`.spec`または`.spec/reports`が
symlinkなら解決せず保存失敗とする」ことを、workspace・設定仕様 §3に「`.spec/reports`はentry種別にかかわらず
既知entryとし探索しない」ことを追記した。registryの`REPORT-WRITE`行には、directory以外またはsymlinkの場合を
含むことを注記した。

- 新規のDiagnostic条件は生じない。既存の`REPORT-WRITE`（`SPEC-REPORT-WRITE-001`、error／error、file、
  `stop-operation`）が担い、119条件・14論点群の対応に変更はない。
- `.spec/reports`が通常fileの場合（SINGLE-072）と同じ扱いに揃えるもので、未知entry warningを追加しない。
- 上記を確認したうえで、台帳が固定する3文書のhashを更新した。

## 2026-09-17の再review（argv template全体の上限）

workspace・設定仕様 §6へ、単一設定fileの64 KiB上限によりtemplate全体1 MiB上限を超える設定は先に
`SPEC-INPUT-LIMIT-001`となること、template全体の上限は防御上の上限として保持し適合matrixでは個別に検査しないことを
追記した。これに伴いmatrixからSINGLE-126-06を削除した。

- 新規のDiagnostic条件は生じず、既存条件の意味も変わらない。119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳が固定するworkspace・設定仕様のhashを更新した。

## 2026-09-17の再review（role割当、draft refinement、verifyの起点TASK）

残りの適合fixtureを作成する過程で、期待値を一意に決められない規範の欠落3件と矛盾1件を確認し、次のとおり裁定した。
いずれも既存の決定を変えず規範の欠落を埋めるもので、新規ADRは起こさない。

- 関係・トレースモデル §7へrole割当表を追加した。`requires`または`addresses`で到達したREQは`requirement`、
  TECHとaccepted ADRは`constraint`、起点以外のTASKは`work`とする。複数に該当する文書は表の上から最初のroleとする。
- 関係・トレースモデル §6.1へ、interpretでは閉包内の文書を`refines`する`draft`文書をadvisoryとして含め、
  その先を辿らないことを追記した。文書・Frontmatter・状態仕様 §7の「`draft`は`interpret`でadvisory」を
  閉包規則へ接続するもので、implementとverifyの閉包は変わらない。
- context仕様 §4・§5へ、`statementRefs[]`は所有する全規範文、Constraint Ledgerとcoverageの各modalityは
  対象statementだけ、`coverage.adjacent`は`adjacentStatements`と同じ内容・順序であることを追記した。
- verifyの起点TASKについて、§6.3本文（`requires`閉包を含めない）とmatrix `SINGLE-110`行・target vector
  `TASK-REQUIRES-NOT-TARGET`（先行TASKをContextへ含める）が矛盾していた。§6.3を正とし、matrix行、vectorの
  期待値、参照計算を修正した。2026-09-14の再reviewで「期待値の変更は0件」としたのは誤りで、参照計算は
  起点TASKの`requires`もverifyで辿っていた。今回の修正で変わった期待集合はこの1 caseだけである。

新規のDiagnostic条件は生じない。119条件・14論点群の対応に変更はない。
上記を確認したうえで、台帳と`targets/cases.json`が固定する根拠文書hashを更新した。

## 2026-09-17の再review（Git版の取得方法）

ADR-046に従い、Core実行環境・CLI基盤契約 §4へ、Gitの版を`git --version`の出力1行目から解析し、非0終了や
解析できない出力を実行不能として扱うことを追記した。下限未満・PATH解決不能・実行不能をGit不在とする既存の
縮退契約へ入力を1つ明示しただけで、単一workspaceの`SPEC-DOCTOR-GIT-001`／warning、複合workspaceの
`SPEC-MULTI-GIT-001`／blockedの条件と継続単位は変わらない。

- 新規のDiagnostic条件は生じない。119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳が固定するCore実行環境・CLI基盤契約のhashを更新した。

## 2026-09-17の再review（複合workspaceの識別子の改名）

ADR-047に従い、設定key `monorepo`を`multiWorkspace`、Capability `monorepo.v1`を`multiWorkspace.v1`、
結果field `federation`を`multiWorkspace`、Diagnostic code `SPEC-MONOREPO-*`を`SPEC-MULTI-*`、condition ID
`MONO-*`を`MULTI-*`、継続単位`stop-federation`を`stop-multi-workspace`へ改名した。

- 条件の意味、severity、status、source、継続単位、優先順位は変えていない。14件のcondition IDは同じ条件のまま
  名前だけを改めた。119条件・14論点群の対応に変更はない。論点群ID `federation`は`multiWorkspace`へ改めた。
- 改名はCore 1.0の公開前に限る一回だけの例外であり、旧ID `MONO-*`を別の条件へ再利用しない。
- 上記を確認したうえで、台帳が固定する根拠文書のhashを更新した。

## 2026-09-17の再review（file名の改名）

用語集 §7に従い78件のfile名を改名し、根拠文書に含まれるlink pathを新しいfile名へ直した。
根拠文書`05_モノレポSPEC連合仕様.md`は`05_複合workspace仕様.md`、`03_文書種別・本文テンプレート.md`は
`03_文書種別・本文template.md`へ改名し、台帳の根拠文書keyも直した。

- 文言統一のみで、規範の変更はない。119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳とtarget vectorが固定する根拠文書のhashを更新した。

## 2026-09-17の再review（詳細設計の文言統一）

用語集に従い、詳細設計の本文のカタカナ語、英語の一般語、複合workspaceの呼び方、送り仮名を統一した。
Schema表の型名、code block、inline code、Diagnostic code、condition IDは変えていない。

- 文言統一のみで、規範の変更はない。119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳とtarget vectorが固定する根拠文書のhashを更新した。

## 2026-09-18の再review（federationの残りの言換え）

用語集 §4.7に従い、結果契約の表の種別名（`workspace-local`、`workspace-federated`、`workspace`、`federation`）を
単一workspace、複合workspace内、workspace単独、複合workspace全体へ改め、複合workspace仕様の構成図の注記と、
`multiWorkspace.id`の説明に残っていた「federation ID」をroot workspace IDへ直した。

- 文言統一のみで、規範の変更はない。119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳が固定する根拠文書のhashを更新した。

## 2026-09-18の再review（上限の同時超過）

`verifyBindingCount`はbindingが必ずcommand定義の部分集合になるため、`commandDefinitionCount`と同時にしか
超過できない。複合workspace仕様 §10へ、複数のdimensionが同時に超過する場合はverify実行計画のdimensionを
優先して報告する規則を1文加えた。

- `SPEC-MULTI-LIMIT-001`の条件、severity、status、source、継続単位は変えていない。119条件・14論点群の対応に変更はない。
- 適合fixture `MULTI-021-08`はこの規則に従い、`evidence.dimension`を`verifyBindingCount`とする。
- 上記を確認したうえで、台帳が固定する根拠文書のhashを更新した。

## 2026-09-24の再review（契約Schemaの正本の移動）

[ADR-050](../../docs/02.設計書/10_決定記録/ADR-050_契約Schemaの正本を詳細設計へ置く.md)に従い、公開結果とFrontmatterの
Schemaの正本を`docs/03.詳細設計/schemas/`へ移した。結果契約 §1とFrontmatter仕様 §2のlinkを移転先へ直し、
Frontmatter仕様 §2の「定義を選んで検証する」を、定義と同じ判定で検証し、Schema fileを実行時に読むことは
要求しない、という意味に明確化した。

- Schemaの内容と、拒否する構造は変えていない。Frontmatterの判定の対象と結果は同じであり、実装方法だけを明確にした。
- 119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳が固定する根拠文書のhashを更新した。

## 2026-09-24の再review（CPythonの下限の引上げ）

[ADR-053](../../docs/02.設計書/10_決定記録/ADR-053_CPythonの下限を3.12へ引き上げる.md)に従い、
Core実行環境・CLI基盤契約 §2とdoctor仕様 §3.1のCPythonの下限を3.11から3.12へ改め、実行環境契約の判断理由に
ADR-053を加えた。

- `DOCTOR-RUNTIME-VERSION`（`SPEC-DOCTOR-CORE-001`）は下限の値だけが変わり、条件、severity、status、source、
  継続単位は変えていない。下限未満を入力にするfixtureは従来どおりmatrixに持たない。
- 119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳が固定する根拠文書のhashを更新した。

## 2026-09-26の再review（規範文IDの文書部分の不一致とcoveredのevidence明文化）

2026-09-25に管理者が承認した方針を反映したcommitで、Diagnostic registryへ条件行
`EAI-ID-DOCUMENT-MISMATCH`（`EAI-CORE-ID-001`、error／failed、file、`skip-document`、draftでもerror）を
追加した。規範文IDの文書部分がFrontmatter `id`と一致しない場合を、既存の`EAI-ID-FORMAT`（規範文ID形式不正）と
区別する新条件である。同じcommitで、共通結果契約 §4とregistry §2へ、relation edgeまたは`covers`要素を単位とする
Diagnostic（`SPEC-RELATION-MISSING-001`、`SPEC-RELATION-ADVISORY-MISSING-001`、`CTX-RELATION-TYPE-001`、
`SPEC-MULTI-REF-001`、`SPEC-TEST-COVERAGE-001`）の`evidence`規則も明文化されたが、これは既存条件の
`evidence`fieldの記法を定めるものであり、新規condition IDではない。

- `EAI-ID-DOCUMENT-MISMATCH`を論点群`language`（`docs/03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md`、
  `docs/03.詳細設計/02_SPECモデル/03_文書種別・本文template.md`）へ対応付けた。rationaleへ、draftでもerrorとする旨を追記した。
- 120条件・14論点群の対応となった（119条件から1件増）。未裁定事項は0件のまま。
- 上記を確認したうえで、台帳が固定する次の根拠文書のhashを更新した: `05_Diagnostic-registry.md`、
  `01_結果・Diagnostic・終了コード.md`、`01_workspace・設定仕様.md`、`02_文書・Frontmatter・状態仕様.md`、
  `04_関係・トレースモデル.md`、`05_複合workspace仕様.md`、`01_context.md`、`02_check.md`、`03_verify.md`、
  `01_言語・Semantic-IR仕様.md`。
- 同日、結果契約 §7のDiagnostic sort規則へ、sort keyがすべて同じDiagnosticを生成元の宣言の出現順とする1文を足した
  （`SINGLE-133`の同じkeyの参照切れ2件の順序を規範文で決めるため）。条件の対応は変えず、同文書のhashを再度更新した。
