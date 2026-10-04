# 品質JSONの申告整合性

Schemaに加えてvalidate_quality.pyが検査する公開形式規則。スキルの有無によらず同じ資料を使う。
形式検査は一次資料からのリスク分類・所見・証拠・独立性の真実性を証明しない。
この資料はケースの正解、対象のリスク帯、重大度、判定、取得すべき個別証拠を指定しない。

## 共通

Core観測は元operation/status/revisionを保持する。statusとexitはpassed/passed_with_warnings=0、
failed=1、blocked=2、error=3。引数不正のexit 4はstatus/rawResult=nullでstderrが必要。
current_gateの対象refは文書のsubjectCommitと一致し、元revisionも観測のsubjectCommitと一致する。
評価用のCore転記アダプタはcore-cli.mdの通り、モデルはcoreResultsを空にして全観測IDを順に返す。

## plan

evidencePlanのevidenceIdは一意、priority=requiredを1件以上含める。
notRun.evidenceIdsは計画したIDだけを参照する。
現在のCore非成功や、全体/観点の未知riskがある場合、planningStatus=proposedにしない。
Q0<Q1<Q2<Q3で、既知の観点最低帯を全体帯が下回る場合は人間の降格承認記録が必要。
Q2/Q3ならindependentReviewPlanned=true、flowはfullまたはspike。

## review

collectedEvidenceのIDは一意で、subjectCommitは文書の対象refと一致する。
missingEvidenceIdsはrequiredEvidenceIdsからcollectedEvidenceのIDを引いた集合と正確に一致する。
notRerun.evidenceIdsは必須または収集済みIDだけを参照し、evidenceAvailable=falseのIDを収集済みにしない。
independent=trueなら実装と検分のrun IDを別にし、Schemaの新規文脈・履歴非継承・直接検分条件も満たす。
riskAssessment.minimumBandが既知ならriskBandはnullやそれより低い帯にしない。

riskBandがQ2/Q3なら、品質計画のcanonical IDはquality-planで、requiredEvidenceIdsへ必ず含める。
qualityPlanPresentはcollectedEvidenceにquality-planがあることと一致させる。
未取得ならmissingEvidenceIdsにもquality-planを入れ、notRerunへ同じIDとevidenceAvailable=false、未取得理由を記録する。
品質計画不足はdecision=not_readyでも省略しない。提供有無、対象帯の選択、根拠の十分性は一次資料から判断する。

decisionは申告した事実から次の順に照合する。

1. 未解決critical/majorまたは現在のCore failedがあればnot_ready。
2. それ以外で必須不足、独立性不成立、subjectCommit/riskBand未確定、Q2/Q3の計画不足、
   現在のCore blocked/error/引数不正、context/checkの欠落があればunknown。
   現在のcontext/check/verifyの元revisionが対象refと違う・dirtyがfalseでない、contextが完全解決でない・digestなしも不足。
3. それ以外でconditionsがあればready_with_conditions、なければready。
4. 未解決minorがあってreadyの場合は不整合。重大でない明示条件を残す。

これらは申告値同士の検査であり、形式を通すために事実や未取得証拠を作らない。
