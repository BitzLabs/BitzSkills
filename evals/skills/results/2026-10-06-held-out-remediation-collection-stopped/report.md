# 保持集合0.4の収集と独立検分（P2で停止）

固定source `f760649f44a3d7bb2bd723181e3ab155b81d4140` の契約に従い、
既存9件をcaseId以外の全フィールドを変えず再利用し、新規3件を作成した。
SOLによる全12件の独立意味検分はP1=0・P2=1、影響1件だった。
全12件の全体経路と再利用9件の来歴は整合したが、新規性は3件中2件だけが適格だった。
集合は `stopped_on_p2` とし、一次発火測定を開始しない。

機械監査のexit0は、適用根拠や意味新規性の合格を表さない。
今回の意味判定は、固定された6スキル本体・証拠・比較集合を直接読んだ独立検分者の
永続報告/receiptを採用したもの。親は保存・対応範囲・hash・sourceを別途再監査した。
個別ケース、期待値、比較根拠、報告本文は非公開領域へ保持し、公開側は集計/hashだけを記録する。

## 親の実検証

検証時のPythonは3.12.3、jsonschemaは4.23.0、ruamel.yamlは0.19.1。
下記の `python` は準備検証と同じ固定環境を用いた。

```text
python evals/skills/routing/audit_remediated_held_out.py \
  --source f760649f44a3d7bb2bd723181e3ab155b81d4140 \
  --cases <承認済み非公開領域>/collection-04/cases.json
exit 0
status: mechanical_checks_passed
caseCount: 12 / newCaseCount: 3 / retainedCaseCount: 9
routingAssessmentCount: 12 / noveltyComparisonCount: 3
publicExclusionCount: 46 / privateExclusionCounts: [12, 12]
semanticNovelty: requires_independent_review
routingSemantics: requires_independent_review

python .venv/held-out-remediation-04/verify-source.py \
  f760649f44a3d7bb2bd723181e3ab155b81d4140
exit 0
status: fixed_source_matches
headIsCondition: false

python .venv/held-out-remediation-04/verify-final-artifacts.py
exit 0（投影パスの訂正後。初回失敗は保持）
status: artifact_source_bindings_verified
sourceFileCount: 12 / inputFileCount: 7 / candidateResourceCount: 71
privateArtifactsVerified: 14 / creatorFilesUnchanged: 8
oldCollectionArtifactBindingsVerified: 13 / reportCaseCoverage: 12
semanticStatus: stopped_on_p2
```

開始/保存直前/終了のguard、全出力のhash/0600・ディレクトリ0700、ケースと証拠と来歴の束縛を確認した。
親はsource12と候補71資源をそれぞれの確定Git blobおよび実bytesへ直接照合した。
旧集合0.1/0.3の入力hash、旧0.3の13成果物も不変だった。
独立native監査JSONは親の実再実行と一致した。
親の実出力は本ディレクトリの3つの `parent-*.json` に収録した。
検証補助の実コードは `verify-parent-artifacts.py` に保存した。

実行ソースは準備検分時から変更していない。準備時の実出力は次のとおりで、
今回の意味検分を単体試験の成功へ置き換えない。

```text
親: Ran 246 tests in 61.335s / OK / exit 0
親の回帰16件: Ran 16 tests in 2.964s / OK / exit 0
独立準備の回帰16件: Ran 16 tests in 2.722s / OK / exit 0
```

固定sourceと製品資源の公開可能な保存一式は、準備結果
`../2026-10-06-held-out-remediation-preparation/artifacts.tar.gz`
（SHA-256 `ad182dd11aff78b0f7b8c2b79018d1d4ab561c9b37f0e41609cef9f278201995`）に含まれる。
非公開の今回ケース/比較/独立報告をこのarchiveへ追加していない。

## 消費枠と失敗の保持

当該契約の準備独立SOL1・作成SOL1・集合独立SOL1を消費した。
一次0・追加委譲0・有料retry0。使用量/費用の確定値はunknown。
作成者のnative読取り補助TypeErrorと、独立検分者の実行体参照失敗exit127は保持し、
それぞれ同じ有料ターン内で1回訂正した。追加の有料呼出しではない。
親の集計補助2件の状態名/型の誤認と、Git資源投影パスの誤認も訂正した。
投影パス訂正前の失敗JSONは作業領域に残し、訂正後のnative照合exit0を採用した。

旧0.3のP1=3/P2=3・以前の停止/保存拒否・元native bytes欠落は保持する。
以前の保存継続SOL1を今回の準備枠へ付け替えず、元bytesの復元や検証成功は主張しない。

## 次の工程

残る1件だけを差し替え、今回指摘のなかった11件は再利用候補にする。
集合0.4を上書きせず、11件の全フィールドと1件の差替対象を非公開来歴へ固定する。
新しい集合/ID/source/監査/分母/停止条件/有限枠を別契約に先に確定する。
新規候補は公開46件、旧0.1/0.3/0.4の全件を除外比較し、
条件差を採点対象の選択経路・範囲・質問・停止判断へ結び付ける。
採点で観測しない付随情報の差や、ラベルの差では採用しない。
再利用11件も次集合の全件独立検分の対象とし、既存合格集合の扱いにはしない。

この後続契約はまだ確定/起動していない。当該0.4の消費済み枠を再利用しない。
P1/P2なしの永続receiptと親の再監査が揃うまで、製品本文の一次発火評価へ進まない。
行動評価・Skill Gate・製品完成は未認定である。
