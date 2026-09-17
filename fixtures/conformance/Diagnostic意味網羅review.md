# Diagnostic意味網羅レビュー

実施日: 2026-09-07。更新日: 2026-09-08。状態: **レビュー完了（実装受入は別工程）**。

`diagnostic-coverage.json`はregistryの各conditionIdを規範の根拠文書と判断理由へ対応付けるレビュー台帳である。
コードの文字列一致を意味網羅の証明とはしない。validatorは対応の欠落・重複・未知ID、根拠文書とregistryの変更を
検出する。文書が変わった場合は意味を再確認してから台帳のhashを更新する。自動実行でhashを更新しない。
registryから派生する対応表はレビュー記録であり、独立した動作oracleではない。

## 修正した不整合

| 論点 | 根拠 | 修正 |
|---|---|---|
| implementの未tested MUST | 関係・トレースモデル §8、context §9 | warning行を追加 |
| context purpose=verifyの未tested MUST | 関係・トレースモデル §8、context §9 | blocked行のoperationへcontextを追加、purposeを限定 |
| 未tested SHOULD | 関係・トレースモデル §8 | purposeをimplement/verifyへ限定し、verify索引にもwarningを明記 |
| 連合依存遮断の継続単位 | 連合仕様 §8、verify §10、doctor §3 | skip-workspaceからtarget/check別へ分割。checkは具体的relation診断を使用 |
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
連合はGit不在preflightで遮断する。新しいCLI flagや暗黙command取得元は追加しない。

### DG-OPEN-002: test pathがcommand cwd配下にない場合

workspace設定 §6はtest pathをcwd配下に限定するが、双方が存在し同一workspace内にある場合の
違反について、設定Schema不正、trace path不正、verify binding遮断のどれを返すかが未確定である。
VERIFY-CWD-UNAVAILABLEはcwd不在、MULTI-OWNERSHIPは所有境界越えであり、そのまま同じ原因に当てはめられない。
裁定: 所有境界・存在検査後にverifyだけが包含検査を行い、`VERIFY-TEST-OUTSIDE-CWD`へ対応付ける。
codeは`SPEC-VERIFY-BLOCKED-001`、error／blocked、file、skip-bindingとする。sourceはtest対応の宣言SPEC。
check/doctorの責務をtarget別binding解決へ拡張しない。`{tests}`なしでも同じ条件を適用する。

### DG-OPEN-003: 別repository/worktreeへのmember path

連合仕様 §5.1・§11は既知の別repository/worktreeへのmember pathをSPEC-MULTI-PATH-001／failedとするが、
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

`uv run fixtures/validate_step0b.py`は台帳の整合性と変更検出を実行する。回帰検査は対応欠落、未知ID、
根拠改変、未裁定条件が残る場合の非完了を確認する。修正した条件に対する期待operation/status/continuationも固定する。
上記3件の裁定を規範・registry・台帳へ反映した。119条件を14論点群・17根拠文書へ対応付け、未裁定事項は0件とする。
判定は人手で確認した規範対応のレビュー結果であり、自然言語の意味をvalidatorが自動証明するものではない。
適合fixtureによるCore実装の実証は別工程であり、本レビューでは代替しない。

## 2026-09-14の再レビュー（関係・トレースモデル §6.3）

`verify`の起点TASKについて、`addresses`先と当該先を所有する文書を`contextDocuments`へ含めることを明文化した。
既存の裁定を変更せず、verify仕様 §3が要求する「TASKは自身の`addresses`先を対象にする」を実行可能にするだけの
記述整合であるため、新規ADRは起こさない。

- 新規のDiagnostic条件は生じない。`addresses`はstrong relationであり、解決不能な先は既存の
  `SPEC-RELATION-MISSING-001`（strong target不在）が担う。119条件・14論点群の対応に変更はない。
- target展開の期待集合25ケースは、参照計算が以前からこの読みを実装しており、期待値の変更は0件である。
  変更は文書側の欠落を埋めるものであり、reviewされた期待に文書を合わせた。
- 上記を確認したうえで、台帳と`targets/cases.json`が固定する根拠文書hashを更新した。

## 2026-09-17の再レビュー（report directoryのsymlink）

SINGLE-125-06の発生条件を確定するため、結果・Diagnostic・終了コード §8に「`.spec`または`.spec/reports`が
symlinkなら解決せず保存失敗とする」ことを、workspace・設定仕様 §3に「`.spec/reports`はentry種別にかかわらず
既知entryとし探索しない」ことを追記した。registryの`REPORT-WRITE`行には、directory以外またはsymlinkの場合を
含むことを注記した。

- 新規のDiagnostic条件は生じない。既存の`REPORT-WRITE`（`SPEC-REPORT-WRITE-001`、error／error、file、
  `stop-operation`）が担い、119条件・14論点群の対応に変更はない。
- `.spec/reports`が通常fileの場合（SINGLE-072）と同じ扱いに揃えるもので、未知entry warningを追加しない。
- 上記を確認したうえで、台帳が固定する3文書のhashを更新した。

## 2026-09-17の再レビュー（argv template全体の上限）

workspace・設定仕様 §6へ、単一設定fileの64 KiB上限によりtemplate全体1 MiB上限を超える設定は先に
`SPEC-INPUT-LIMIT-001`となること、template全体の上限は防御上の上限として保持し適合matrixでは個別に検査しないことを
追記した。これに伴いmatrixからSINGLE-126-06を削除した。

- 新規のDiagnostic条件は生じず、既存条件の意味も変わらない。119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳が固定するworkspace・設定仕様のhashを更新した。

## 2026-09-17の再レビュー（role割当、draft refinement、verifyの起点TASK）

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
  期待値、参照計算を修正した。2026-09-14の再レビューで「期待値の変更は0件」としたのは誤りで、参照計算は
  起点TASKの`requires`もverifyで辿っていた。今回の修正で変わった期待集合はこの1ケースだけである。

新規のDiagnostic条件は生じない。119条件・14論点群の対応に変更はない。
上記を確認したうえで、台帳と`targets/cases.json`が固定する根拠文書hashを更新した。

## 2026-09-17の再レビュー（Git版の取得方法）

ADR-046に従い、Core実行環境・CLI基盤契約 §4へ、Gitの版を`git --version`の出力1行目から解析し、非0終了や
解析できない出力を実行不能として扱うことを追記した。下限未満・PATH解決不能・実行不能をGit不在とする既存の
縮退契約へ入力を1つ明示しただけで、単一workspaceの`SPEC-DOCTOR-GIT-001`／warning、連合の
`SPEC-MULTI-GIT-001`／blockedの条件と継続単位は変わらない。

- 新規のDiagnostic条件は生じない。119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳が固定するCore実行環境・CLI基盤契約のhashを更新した。

## 2026-09-17の再レビュー（複合workspaceの識別子の改名）

ADR-047に従い、設定key `monorepo`を`multiWorkspace`、Capability `monorepo.v1`を`multiWorkspace.v1`、
結果field `federation`を`multiWorkspace`、Diagnostic code `SPEC-MONOREPO-*`を`SPEC-MULTI-*`、condition ID
`MONO-*`を`MULTI-*`、継続単位`stop-federation`を`stop-multi-workspace`へ改名した。

- 条件の意味、severity、status、source、継続単位、優先順位は変えていない。14件のcondition IDは同じ条件のまま
  名前だけを改めた。119条件・14論点群の対応に変更はない。論点群ID `federation`は`multiWorkspace`へ改めた。
- 改名はCore 1.0の公開前に限る一回だけの例外であり、旧ID `MONO-*`を別の条件へ再利用しない。
- 上記を確認したうえで、台帳が固定する根拠文書のhashを更新した。

## 2026-09-17の再レビュー（file名の改名）

用語集 §7に従い78件のfile名を改名し、根拠文書に含まれるlink pathを新しいfile名へ直した。
根拠文書`05_モノレポSPEC連合仕様.md`は`05_複合workspace仕様.md`、`03_文書種別・本文テンプレート.md`は
`03_文書種別・本文template.md`へ改名し、台帳の根拠文書keyも直した。

- 文言統一のみで、規範の変更はない。119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳とtarget vectorが固定する根拠文書のhashを更新した。

## 2026-09-17の再レビュー（詳細設計の文言統一）

用語集に従い、詳細設計の本文のカタカナ語、英語の一般語、連合の呼び方、送り仮名を統一した。
Schema表の型名、code block、インラインコード、Diagnostic code、condition IDは変えていない。

- 文言統一のみで、規範の変更はない。119条件・14論点群の対応に変更はない。
- 上記を確認したうえで、台帳とtarget vectorが固定する根拠文書のhashを更新した。
