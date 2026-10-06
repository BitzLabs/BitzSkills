# 独立検分記録の新規保存に関する確認

保存先:
`/home/hide/BitzLabs/BitzSkills-private-evals/core-sdd-quality-20261006/collection-03/`

次の6ファイルを、所有者のみ読取り・書込み可能な0600で排他的に新規作成する。
既存7ファイルの上書き・削除、外部送信、非公開内容の公開は行わない。

| ファイル | 保存する内容 |
|---|---|
| independent-review.md | 全12件の本文根拠・意味比較・指摘 |
| independent-receipt.json | 状態・重大度集計・hash・制約 |
| independent-audit.json | 正規の機械監査結果 |
| independent-audit.log | 正規監査の原出力 |
| independent-invocation-error.json | 誤引数のexit2と同一検分内の是正記録 |
| independent-source-guard.json | 開始時・最終の13ファイル照合結果 |

ユーザーの継続保存承認は固定contractに記録済みだが、自動承認審査が明示承認を確認できないとして
2回拒否した。未作成を確認して停止している。保存後は親がhash/権限/根拠を再監査する。
新しいモデル一次測定や同じ条件での有料再試行を、この保存操作には含めない。
