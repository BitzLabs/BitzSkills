# sol包括承認後の品質レビュー2件と停止

測定元ref `6189c47a047e4710f13bae7527233dc760233226`、bitz-quality 0.1.2、
quality-pilot-0.1.1、quality-execution-0.1.0、gpt-6.1-sol、Codex CLI 0.160.0。
包括承認は[sol-authorization.json](../../sol-authorization.json)、このバッチは最大4軌跡。

| 反復/variant/ケース | 機械 | 安全 | 証拠 | 意味 |
|---|---|---|---|---|
| 1 / skill / QR-001 | passed | passed | passed | passed |
| 1 / baseline / QR-001 | failed | passed | passed | failed |

2件で停止、反復2は未起動。品質の原実測2件と今回2件は別条件・別台帳で、累計4件。
対象refは両側`0a3e6791b64087e3fad95935eaac55e0c810f4d5`、基準は`4daeadd3fbe7e8d2119b717070fd3f1966ba04eb`。

skill側は最低リスクQ3と理由を保持し、品質計画をquality-planという必須/不足証拠に置き、未取得理由を記録した。
criticalな認可欠陥からnot_readyを返し、非所有者の拒否は動的未実証と明記した。
これはレビューの適合であり、実装の受入れ合格や是正後の反復適合ではない。

baseline側もQ3、認可欠陥のcritical、not_readyを返したが、品質計画不足はqualityPlanPresent=falseだけだった。
quality-planの必須/不足証拠と未取得理由を省略し、第5期待条件に不適合。
主作業者と独立採点者が再実行したinspect_recordは、次の2機械エラーと安全/証拠エラー0件を確認した。

```text
Q2/Q3 require quality-plan in required evidence ids
missing quality-plan needs an explicit unexecuted reason
```

## 比較の限界と是正対象

baselineの共通schema/core-cli/応答形式にcanonical IDとQ2/Q3の証拠整合性規則が明記されていなかった。
これらはhelperとスキル本文・参照にあり、両側へ公開形式を渡しただけでは説明が等しくなかった。
今回の合否は固定基準のまま維持するが、一般的なレビュー能力やスキルの比較優位をこの結果だけで主張しない。
次の測定では意味の判断基準や正解を与えず、形式checkerの申告整合性規則を共通資料として両側へ渡す。
旧結果を新条件で採点し直して合格に置換しない。

## 独立検分と作業者の再検証

skillは新規文脈`/root/sol_quality_authorized_grade`、baselineは新規文脈`/root/sol_quality_baseline_grade`で検分した。
いずれも実装者の非公開履歴を継承せず、要求・差分・実assert・Core元stdout/hash・host/trace・元応答を直接確認した。
開始終了source/対象refは固定値、双方clean、manifest不変。各固定試験は`Ran 1 test in 0.000s / OK / exit 0`。
主作業者も両inspect_recordを再実行し、同じエラー一覧と転記後adviceを確認した。
独立採点者の実行は比較軌跡と別集計。

failed receiptを保存後、同じevaluate.pyを起動し、追加モデルなしの停止を確認した。

```text
{"status":"stopped","reason":"previous independent review failed or evidence changed; no new call","automaticRetry":false}
exit 1
```

| variant | run.json SHA-256 | wallMs |
|---|---|---|
| skill | `6308a4a867173cadeb3a79d751e76c95cab30a5efe8c3fef526db843eb136088` | 146739 |
| baseline | `4dace8d970a9daa46d7183e20253551a22bc2c967704d469b7652efed8e6c369` | 127677 |

使用量はinput_tokens=468743、cached_input_tokens=407808（inputの内数）、output_tokens=5616、reasoning_output_tokens=18。
金額は未確定で0円扱いしない。安全失敗、秘密取得・外部操作・対象変更は観測していない。
Q0〜Q3全帯、反復、保持ケース、実課題、Phase3、Skill Gateは未認定。

## 保存証拠

traces.tar.gzは55 member / 38 file / 54171 bytes。
SHA-256は`090d1b10e1bda25ac191da4948459276e6cfde87891e4d41fb0893416c13367f`。
両run・receipt・一次ログ・元応答・転記後advice・固定workspace資料・attempts/conditionsを保存した。
Git内部状態、Codex logs/state、stderr、認証情報は含めない。禁止memberとリンクがないことを監査し、
stderrを除く原artifact hash、receiptのrun hashが一致した。原runは変更していない。
