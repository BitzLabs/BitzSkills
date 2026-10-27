# 新規1件と再利用11件の収集監査

集合0.5は、0.4のP2対象1件だけを置換する別契約である。
0.4の原記録と消費済み予算を保持し、候補11件をcaseId以外の全fieldsを変えず再利用する。
次の集合は全12件を再度独立検分する。

```text
python evals/skills/routing/audit_single_replacement.py \
  --source <確定した40桁の契約source> \
  --cases <承認済み非公開root>/collection-05/cases.json
```

契約はそのsourceの `held-out-collection-v0.5.json` から読む。
HEAD自体は条件ではなく、source15ファイル/input7ファイルと候補6スキル/71資源の実bytesを照合する。
caseIdsは1200〜1211、12件の分母・区分・機能別件数と再利用例外を先に固定する。
非公開retentionは旧04ケース/独立receipt/独立報告のhashへ束縛する。
旧固定報告の12経路見出しとP2見出し1件の対応を検査するが、本文の意味を自動採点しない。

evidenceは12件のrouting/lineage、公開全46件と旧0.1/0.3/0.4各全12件の比較網羅、
新規1件のnoveltyComparisonsを含む。新規同士の組数は0なのでnewCasePairsは空配列とする。
新規と再利用11件との比較は、旧0.4全12件への直接意味比較にも含める。

新規のcounterfactualには変更条件・理由・測定判断種別に加え、
beforeDecision/afterDecision（ケースexpectedと同じ5fields）と固定本文sourceのpath/hash/実在anchorを記録する。
beforeは実ケースexpectedと一致し、afterは変更条件を近い旧条件へ戻したときの予測判断を表す。
選択経路/outcome/採点対象eventに差がなければ拒否する。event順序の違いだけでは通過しない。
question/stopの差を主張する場合は、それに対応するoutcomeも必要となる。
scopeの差を主張する場合も、採点対象のoutcomeまたはeventへ結び付ける。
これは採用前の作成根拠で、モデル軌跡や実操作の観測結果ではない。

機械通過は全6スキルの宣言整合・hash・来歴・比較網羅・観測可能な差の構造を検査する。
変更条件が実際に本文判断へ効くか、既存ケースとの意味上の差が十分かは別の独立SOL検分で判断する。
細部の言い換え・対象ラベルだけの変更を新規性として許容しない。
P1/P2があればその有限契約を停止し、一次測定へは進まない。
作成/独立の必要な内部直接読取りは許可し、公開成果物には保持本文や期待値、個別比較を含めない。
