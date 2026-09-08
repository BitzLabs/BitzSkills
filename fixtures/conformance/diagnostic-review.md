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
VERIFY-CWD-UNAVAILABLEはcwd不在、MONO-OWNERSHIPは所有境界越えであり、そのまま同じ原因に当てはめられない。
裁定: 所有境界・存在検査後にverifyだけが包含検査を行い、`VERIFY-TEST-OUTSIDE-CWD`へ対応付ける。
codeは`SPEC-VERIFY-BLOCKED-001`、error／blocked、file、skip-bindingとする。sourceはtest対応の宣言SPEC。
check/doctorの責務をtarget別binding解決へ拡張しない。`{tests}`なしでも同じ条件を適用する。

### DG-OPEN-003: 別repository/worktreeへのmember path

連合仕様 §5.1・§11は既知の別repository/worktreeへのmember pathをSPEC-MONOREPO-PATH-001／failedとするが、
§10は同じ解決結果をSPEC-MONOREPO-GIT-001／blockedにも含めている。既知の不適合と境界確定不能を
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
