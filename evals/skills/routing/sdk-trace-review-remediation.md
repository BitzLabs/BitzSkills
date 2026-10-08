# Phase 4：SDK診断の指摘と是正候補

初版静的検分source `2ce51de64a7721ab08f4c7a431563c477f4382a4` の別SOL応答はP2=2/P3=1だった。
CLIの2つの起動エラー通知（廃止featureとCode Modeの意図的無効化）を受入れ器が拒否したため、
原receiptのreview_stoppedを保持し、通過と訂正しない。原最終JSONの3指摘は親が同じsourceで実行して再現した。
旧有限枠は消費1/残0。原receipt・応答・stdioを変更しない。

- P2：前後provider prefixが同じでも、SDKとは別のユーザー本文で診断が通る。
  修正候補は最初のprovider要求の最終user messageをSDKのturn/start原入力へ一致させる。
- P2：結果イベントに矛盾するcell/runtime/turn/sourceを足しても親子ID診断が通る。
  修正候補はresult/result_ready内の追加識別フィールドを受領済みの識別へ照合する。
- P3：final item IDとdelta item IDの両方を欠落させてもNone同士で一致する。
  修正候補は非空IDを必須化し、provider final IDとnative final IDも照合する。

3条件を回帰へ追加した。修正確認は別の独立SOL有限1回の静的検分と親の原証拠照合で行う。
静的検分者は試験を実行せず、親が入力送信前のsourceを照合して確定bytesを送る。
Code Mode無効化の既知エラーはturn開始前の完全一致1通知だけを原hash付きで保持する。
未知エラー・turn開始後のエラー・tool実行・複数turnは引き続き停止させる。
これは任意の実行、実provider、一次採点、全Skill Gate、Phase完了の認定ではない。

## 2回目の静的検分からの是正候補

source `55bd64eb55baaf00d0ba8b366b5fbc7fd7cec0e7` の別SOLはP2=4。
旧3指摘の修正後にも、同じprefixへの追加user message、dispatchの操作識別矛盾、
子操作同士の逆順、選択ログが原stderrの部分列でしかない条件を親が実行して再現した。
原receiptのreview_findings、応答、消費1/残0を保持する。

是正候補は、SDK原入力だけでなく前置メッセージも固定すること、dispatchの操作識別を照合すること、
逐次list→readをnative/telemetry両方で要求すること、全対象ログを原stderrから完全抽出して照合すること。
検証済みのSDK0.160.1/局所mock provider/2026-10-08の自動文脈は、明示形と資源hashに束縛する。
試験用の合成入力は単一user messageだけの別profileとし、文脈を補完・推定して受理しない。
一般のprovider/別日/複数cellへの互換性を今回認定しない。
