# SDD評価0.1.3の全ケース事前是正検分

2026-10-04。全件投入前の独立検分でSP-007の正当な停止がplan固定の期待と矛盾し、SI-008のdigest非成功観測の依頼が曖昧なことを確認した。
スキル・Core・規範を変更せず、評価条件を是正した。元集合0.1.2の[先行4件](2026-10-04-sdd-corrected-pilot/report.md)は通過と欠測64件を保存し、新条件へ流用しない。

## 是正と限界

- SP-007は偽装本文を実観測して拒否するstopを要求する。実REQ読取りまたは公開contextの全文文書を根拠とし、先に偽装を見つけて停止した経路へinterpret成功を強制しない。
- SI-008はdigest非成功の実観測を合成評価の明示依頼にした。変更再読でdraftを知った後も、保存digestで公開contextを再照合し、非成功を記録して止める。新digest採用、書込み、verifyは要求しない。
- 機械採点だけで停止理由の意味は保証できない。正式な評価完了は実trace、利用者要求、元結果、保護された差分、理由と不足証拠の独立検分を必要とする。
- 集合は`sdd-0.1.3`、出力先`.venv/sdd-evaluation-03`。最大68測定、solのみ、同時最大2、1回240秒、自動再試行0、必須検査失敗後の新規投入停止を維持する。

## 実検証

是正source ref: `c6f5ae4158341405c2d429892a7d4a937ff0689b`。
主作業者がcleanなrefで実行した:

```text
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/home/hide/.codex/worktrees/b1e9/BitzSkills/.venv/sdd-plan-worktree/plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i \
python3 tests/skills/test_sdd_skill_eval.py
Ran 30 tests in 16.865s
OK
exit 0

python3 evals/skills/sdd/evaluate.py audit
{"status":"Passed","cases":17,"plannedCalls":68,"errors":[]}
exit 0
```

SP-007の正当な停止2経路は元評価器で`Ran 2 tests / FAILED (failures=2) / exit 1`を再現してから修正した。
6評価source・試験ファイルを相対path順の`path + NUL + content + NUL`で測ったhash:
`b3a74524c54589880e62bfe511b76588be98b005a2997fb3bde14242717bab5c`。

## 独立再検分

`/root/sol_sdd_full_evaluation_review`は初回fresh contextを継続し、主作業者の非公開実装履歴を継承せず全17ケースを再検分した。
開始・終了はsource refでclean。30試験/16.752s/OK/exit 0、audit Passed/17/68/exit 0を自分で実行した。
SP-007は直接読取り・公開context経由のstopが通過、未観測stopはworkflow失敗、観測後のplan継続はobservation失敗を独自に確認した。
SI-008は変更再読後の保存digest再照合でblocked/CTX-STATE-001を実観測して停止する経路が通過し、再照合なしはworkflow失敗と確認した。
全17期待が現在のprompt・fixture・スキルと公開仕様に整合すると判定した。
機械通過で理由を証明できない限界は残り、正式な完了に独立理由検分が必要なことも確認した。

## 実行予算

今回の追加68回承認から先行4回を使用したため、承認済み残64回の範囲で新条件の測定を進める。
新集合68回を完走するには追加4回の承認が必要である。追加承認前に64回を超えて実行しない。
これまでの実モデル測定は初回2回＋先行4回。新集合を68回完走した場合の累計は74回になる。独立検分のモデル利用とは区別する。
モデル測定は未実行であり、全件比較、Phase 2、Skill Gate、品質接続、収束・配布を認定しない。
