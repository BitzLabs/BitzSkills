# collection 0.5 独立意味検分と親の再照合

2026-10-07。全12件のrouting意味と新規1件の意味新規性は、作成者と別文脈のSOLで通過した。
P1=0/P2=0、経路通過12/12、新規性通過1/1。親の機械監査・原bytes/receipt/全件coverage再照合もexit0。
この集合を製品評価の測定準備用に採用する。一次モデル軌跡は0で、実操作・Skill Gate・製品完了・リリースを認定しない。

## 承認と固定条件

自動承認レビューが前段の起動を拒否した後、非公開本文/期待値/証拠/過去報告/原実行traceの具体的な
送信内容とOpenAIのCodex CLI `gpt-6.1-sol` という宛先、未消費の独立検分1回、owner-only保存先を明記した。
その確認へのユーザーの「OK」を得て再申請し、承認された1回だけを実行した。拒否の迂回は行っていない。
条件は前段の `../2026-10-07-single-replacement-created/private-transmission-approval-request.md` に記録している。

- CLI0.160.1、モデル `gpt-6.1-sol`、実行器source19 `33c89531d29d87b6d470a1e61b76d8d2a9a722c5`。
- 集合仕様source15 `879101449c93df2545bb6c5dcab07664b6d5cdd2`。
- 作成時の公開結果ref `1a1212a2ad274a281bd86af214f07d74dd4ed251` と私的作成物hashを束縛した。
- 集合0.5、保持11件/新1件、全12件。候補6スキル/71資源を変更していない。
- 残りreviewer1回を消費。追加準備モデル0、一次測定0、自動有料再試行0。現契約の残枠は0。

## 独立検分の実結果

起動前の無モデルpreflightはnetwork遮断/モデル呼出し0/thread・turn要求0、実39試験/command exit0。
意図的にserverを終了したexit-15は診断終了で、モデルの正常終了とは区別した。
有料検分CLIは実exit0、257605ms、正常turn終端1、raw traceの最終応答とresponse原bytesが一致した。

独立検分は全12件の個別経路・来歴を私的報告の12節に記録した。
差し替え1件を公開46件/過去非公開3集合/保持11件と比較し、反実仮想の5判断と因果性を意味で確認した。
構造監査だけで新規性を認定せず、P1=0/P2=0/affected0/経路12/新規1のreceiptを保存した。
開始/保存前/終了guardは各exit0、既存8ファイルのhashは前後一致、既存ファイル不変と記録した。
独立16+9+14試験は各exit0、native auditもexit0だった。

native command完了19件中18件はexit0、1件は補助誤りでexit1だった。
誤りの原記録を消さず `independent-invocation-error.json` に保存し、既定の同じ検分内で1回訂正した。
訂正後のguard/監査/保存を確認した。有料呼出しの追加や自動retryは行っていない。
raw traceとprovider stderrは承認した私的領域に保持し、stderr本文は復号・表示していない。

## 親の再確認

- `Ran 39 tests in 3.732s` / `OK` / exit0で独立結果に関連する試験を再実行した。
- source19/旧13/旧7/集合15と旧停止原bytes、作成時refに束縛したケース/証拠/receipt、準備14ファイルを再照合した。
- 別SOLのreceipt/報告/監査/guard/実エラー5ファイルをhash・0600/0700に照合した。
  私的報告は全12IDを網羅し12ケース節を含む。個別内容を公開へ転記していない。
- native終端/最終応答/usage/commandの実exit、実39試験のtool出力、補助訂正1回の原記録を照合した。
- 機械監査を再実行し12件・保持11件・新1件・全12routing assessmentを確認した。
  候補71資源のGit blobもすべて一致した。

`verify-parent-artifacts.py` の実出力は以下、exit0だった。私的保存物とローカル試験ログが必要。

```text
{"status": "parent_review_artifacts_verified", "sourceFiles": 19, "collectionSourceFiles": 15, "caseCount": 12, "routingSemanticsPassedCount": 12, "novelNewCaseCount": 1, "independentP1": 0, "independentP2": 0, "reportCaseCoverage": 12, "parentTests": 39, "candidateResourcesGitMatched": 71, "nativeAuxiliaryCorrections": 1, "caseSetAcceptedForMeasurementPreparation": true, "primaryModelTrajectories": 0, "certifiesBehavior": false, "certifiesSkillGate": false}
```

公開は版・件数・hash・集計と検証コードのみ。私的本文/期待値/個別比較/報告本文/raw traceは含めない。
usageはCLIの実値をsummaryへ記録し、金額は推定していない。旧0.1/0.3/0.4の停止と古いraw byte欠落は保持した。
独立意味検分の通過を、過去停止の取消や欠落原bytesの復元成功として扱わない。

## 次工程

`evals/skills/routing/production-evaluation-plan.md` に従い、製品6本文を実際に読む一次実行器を実装する。
先にモデルへ渡す入力を分離し、読取りhostだけの接続、選択本文の実読取りhash、host/native/finalの対応、
有限予算の起動前予約・独立receiptゲート・停止時の原bytes保存を検証する。
公開正例/負例の小さいcanaryを別contractへ固定してから起動する。今回の採用集合を即座にモデルへ投入しない。
canaryが通ってから公開/保持の分母を広げる。同一条件のスキルなし比較・行動評価・異なるモデル系統・実地5種類・配布と最終承認は残件。
