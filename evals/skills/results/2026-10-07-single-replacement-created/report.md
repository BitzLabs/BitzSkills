# collection 0.5 作成と独立検分の準備

2026-10-07。12件中11件を保持し、1件を差し替えた。作成CLIの正常終了と親の機械監査を確認した。
全12件の意味・新規性を判定する別SOLの起動は自動承認レビューに拒否され、未実施である。
集合採用、Skill Gate、実操作、リリースは認定しない。

## 前回停止の保持と今回の変更

旧実行source `4736737b25b8e0b190e3863b508e56589e952f1e` の準備SOL1回は、CLI exit0・正常turn終端だった。
モデルの最終結果は `stopped` で、実shellの起動失敗によりtool実行0・試験0・準備報告/receiptなしだった。
記録上のP1/P2=0は未検分を意味し、準備通過と扱わない。原bytesと消費済みの予約を保持した。

無モデルの診断をCLI開始記録から実 `command/exec` へ広げ、外側RO namespace内で内側shellを起動した。
空の `.agents`・`.codex`・`.aws` が存在しないと、内側sandboxのmkdirがROエラーになることを再現した。
既存設定/認証データを読まず、RO化の前に空の0700ディレクトリを存在させる。
また、旧権限fixtureのmkdir指定はumask077では0700となった。新しい版だけexplicit chmod755で不正権限を作るよう訂正した。
旧版のsource/試験/失敗は変更していない。

実行器0.3をsource `33c89531d29d87b6d470a1e61b76d8d2a9a722c5` の19ファイルに固定した。
集合仕様はsource `879101449c93df2545bb6c5dcab07664b6d5cdd2` の15ファイルを維持した。
CLIは0.160.1、モデルは `gpt-6.1-sol`。
無モデルの事前検証はnetwork namespaceを遮断し、initializeと `command/exec` だけを使う。
thread/turn要求とモデル呼出しは0。実39試験/command exit0を確認してから意図的にserverを終了した（server exit-15）。
CLIの当該protocolは[公式定義](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/src/protocol/v2/command_exec.rs)に従う。
この診断を独立検分の代替とはしない。

直前に承認された今後最大3呼出しのうち、旧0.2準備1回を消費済みとして保持した。
残る作成1回の冒頭で、実装者と独立した文脈による準備検分を行った。追加準備モデル呼出しは0。
その準備が通過した同じturnでケースを作成し、集合の意味は別SOL1回で検分する手順に固定した。
作成者による集合の自己レビューで採用を認定しない。同条件の有料再試行0、一次測定0。

## 実結果と親の確認

- 独立準備：実16+9+14=39試験は各exit0。報告/receiptにP1=0/P2=0を保存した。
- 作成CLI：exit0、422607ms、thread開始1・turn正常終端1、最終応答とraw traceが一致した。
  実command完了19件はすべてexit0。準備試験の実command出力もnative traceで確認した。
- 機械監査：実12件・保持11件・新1件、全12routing assessment、意味新規性は独立検分待ち。
  source15、public除外46、旧private除外12+12+12、保持whole-field、新1件の比較/反実仮想、証拠schemaを再照合しexit0。
- 親の再実行：39試験は `Ran 39 tests in 3.458s` / `OK` / exit0。
  実行器固定前の全単体試験は `Ran 294 tests in 62.580s` / `OK` / exit0。
- 固定source19/旧13/旧7/集合15と既存停止原bytes、準備14束縛ファイル、作成物hash・0600/0700を再照合した。
  候補6スキル/71資源のGit blobも一致した。

親の証拠照合は以下の実出力でexit0となった（私的保存物とローカルログが必要）。

```text
{"status": "parent_artifacts_verified", "sourceFiles": 19, "collectionSourceFiles": 15, "caseCount": 12, "newCaseCount": 1, "retainedCaseCount": 11, "candidateResourcesGitMatched": 71, "preparationP1": 0, "preparationP2": 0, "creatorCommandCount": 19, "reviewerReserved": false, "semanticIndependentReviewPending": true, "certifiesCaseSet": false, "certifiesSkillGate": false}
```

再照合スクリプトは `verify-parent-artifacts.py`。固定ref/原bytesを検証し、現HEADを実験条件にはしない。
これは作成直後・独立検分前の段階用スクリプトで、後続の検分開始後はその段階の証拠を用いる。
件数・hash・集計だけを公開し、ケース本文/期待値/個別比較/私的報告/raw traceは公開していない。
provider stderrは復号・表示していない。無モデルの試験結果と単体試験stderrは実出力として限定集計した。
usageはCLIの実値をsummaryに記録し、金額は算出していない。

## 起動拒否と次工程

別SOL reviewer1回の起動前に、自動承認レビューが次の理由で拒否した。

> 全SOL評価の承認はあるものの、非公開ケース本文・証拠・raw traceをCodex提供先へ送信する具体的なペイロードと宛先への承認は、信頼できるユーザー発言で確認できないため。

別経路で起動していない。reviewerの予約/結果/私的phase/独立receiptは存在せず、枠は未消費。
送信内容と宛先を明記した確認は `private-transmission-approval-request.md`。
承認後は同じ固定source19/集合15で別SOL1回を起動し、親が意味判定receipt、全12件coverage、原bytes/機械監査を再検証する。
P1/P2が残れば集合を停止のまま保持する。通過後の製品一次測定は別工程で、現在は0件。

確認待ちの間に、結果・検証器・正本計画・残件計画を記録した。Core実装と適合fixtureは変更していない。
