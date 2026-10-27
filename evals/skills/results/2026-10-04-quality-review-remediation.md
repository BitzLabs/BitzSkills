# 品質レビューの局所是正と承認待ちの4件比較

局所検証対象: `f61eac44fb240e47c13660506491a8e0146cb42e`、bitz-quality 0.1.2。
是正候補の追加モデル実測は0件。原実測は[停止記録](2026-10-04-quality-pilot-stop/report.md)の2件で停止し、
QP-001適合、QR-001意味不適合の一次証拠とfailed receiptを維持している。

## 変更と保証範囲

品質レビューは、計画にリスク帯の指定がなくても、要求・差分・実装から最低リスクを独立に導く。
確認した最低帯と理由をriskAssessmentへ記録し、暫定riskBandで既知の重大観点を下げない。
Q2/Q3で品質計画がなければ、not_readyでもquality-planを必須/不足証拠と未取得理由へ残す。
計画があるという申告も、同じ証拠IDの取得先・hash・対象refと照合する。

Schemaとvalidate_quality.pyは宣言の整合性を検査する。一次資料からの正しい分類、所見やhashの真実性、
モデルが改訂指示に従うことはこの検査だけでは実証しない。実Coreや承認済みREQ/TECHの意味は変更していない。
quality-plan本文は0.1.1のまま、quality-review本文と配布候補を0.1.2とした。

実行器は固定した原/是正用のprotocolとapprovalだけを選択でき、候補の実版と分母を起動前に照合する。
原承認の台帳・出力・failed receiptは再利用も初期化もせず、新承認は別台帳と出力に結び付ける。
これは停止した原候補の成績を書き換える操作ではない。

## 作業者の実出力

cleanな対象refで、次の環境を付けて局所試験を実行した。

```text
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=/home/hide/BitzLabs/BitzSkills/.venv/quality-plan-worktree/plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i
python3 -B tests/skills/test_quality_contracts.py
Ran 32 tests in 0.411s
OK
exit 0
python3 -B tests/skills/test_quality_evaluation.py
Ran 21 tests in 5.540s
OK
exit 0
```

契約試験は既知最低帯の不明化/降格、critical時の計画必須不足の省略、取得済み証拠のない計画申告を拒否した。
実行器試験は承認待ちの起動拒否、原ケース保持、原承認による別版の起動拒否、別承認台帳の出力固定を検査した。
合成試験で台帳分離を検査した結果を、実評価の承認やモデル適合と数えない。

system skill-creatorのquick_validate.pyをquality-plan/reviewへ実行し、それぞれ`Skill is valid!`・exit 0。
`git diff --check`もexit 0。Core実装と規範fixtureは変更しておらず、Gate認定を行っていない。

新提案の承認待ち停止:

```text
python3 -B evals/skills/quality/evaluate.py --protocol evals/skills/quality/remediation-protocol.json --approval evals/skills/quality/remediation-approval.json --output /home/hide/BitzLabs/BitzSkills/.venv/quality-plan-worktree/.venv/quality-review-remediated
{"status":"stopped","reason":"measurement authorization or fixed protocol mismatch","automaticRetry":false}
exit 1
```

原評価の停止を同じ実行器で再確認した:

```text
python3 -B evals/skills/quality/evaluate.py --output /home/hide/BitzLabs/BitzSkills/.venv/quality-plan-worktree/.venv/quality-model-pilot
{"status":"stopped","reason":"previous independent review failed or evidence changed; no new call","automaticRetry":false}
exit 1
```

両操作後も原attempts/台帳は2件、新出力は存在せず、新承認台帳は0件。新規モデル起動はなかった。
原保存archiveは60 member / 40 file / 70151 bytes、SHA-256
`049bc102be3f09ac3aea91e68c4ffaf7861aadfede8710a52460b492fe6f2d1f`で不変。

## 独立検分

`/root/sol_quality_prototype_review`が同じ確定refを独立に検分した。開始/終了HEADは対象ref、
両時点のstatusは空。32契約試験は`Ran 32 tests in 0.388s / OK / exit 0`、
21実行器試験は`Ran 21 tests in 5.585s / OK / exit 0`、両quick_validateも各exit 0。
原archiveは`archive independent audit: OK / exit 0`で、両runのhash・各7artifact（stderr除外）・receiptを照合した。
保存reportの失敗理由・ref・使用量・実時間も一次結果と一致した。
今回の局所是正と承認待ちの範囲に必須是正事項はなかった。

検分者は以前の独立準備検分からの別文脈を継続し、実装者の非公開履歴は継承していない。
是正内容と原失敗箇所は検分課題として伝えた。新規モデルに結論を与えない実測とは区別する。
helperが根拠からの導出自体の誤りや実証拠の真実性を証明できない点も確認した。
モデル是正効果は未実証であり、Gate完了を意味しない。[検分記録](2026-10-04-quality-review-remediation.independent-review.json)を参照する。

## 承認を求める具体的範囲

[固定protocol](../quality/remediation-protocol.json)はquality-pilot-0.1.1、bitz-quality 0.1.2、gpt-6.1-solのみ。
原QR-001のprompt・fixture・期待条件をそのまま使い、skill/baseline各2反復、最大4軌跡、直列、再試行なし。
スキル有無の両側へ同じ公開形式と固定資料を渡す。是正による形式・候補版の変更を別条件として記録する。
期待値や隠した動的反例は実測モデルへ提供しない。
機械・安全・意味・起動/利用・証拠破損・条件混在のどの不適合でも停止し、baselineの意味失敗も続行しない。

[承認記録](../quality/remediation-approval.json)はpending。protocol SHA-256は
`c617450008e09760e8490974c79561c7821c387578d0f7a6c4e642fbec7650e1`。
新しい承認があった場合だけ、この提案をapprovedへ記録し、確定したclean refから別出力に実測する。
原上限8件の未使用6件やSDD上限の未使用11件を流用しない。独立準備検分/採点者の実行は比較軌跡と別集計。
使用量・実時間を保存し、未確定の金額を0円扱いしない。

4件が全て適合しても、QPの反復比較、Q0〜Q3全帯、保持ケース、実課題、発火・安全全件、SDD連携は未認定。
Phase 3・Skill Gate・配布完了は宣言しない。
