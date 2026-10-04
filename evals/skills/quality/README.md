# 品質スキルの先行2ケース

原0.1.1評価は2軌跡で意味不適合が出て停止した。原approval/protocolとfailed結果は保持する。
2026-10-04の「SOLでの評価は、すべて許可します。」を[包括承認](../sol-authorization.json)へ記録した。
是正候補0.1.2はremediation-protocol.jsonのQR-001×skill/baseline×2反復、最大4軌跡を
remediation-approval.jsonに基づき別出力・別台帳で測定する。失敗停止と独立検分は維持する。
以後のsol評価も、起動前に有限のバッチ条件を固定し、是正・証拠保存後の新測定ごとに再承認を求めない。

0.1.2の最初のレビュー比較も2軌跡で停止した。skillは適合、baselineは品質計画不足の保持に不適合。
両側の資料にはhelperのcanonical ID/整合性条件が十分明記されていなかったため、一般的な比較優位は主張しない。
advice-format.mdを共通配布し、実際の読取りを検査する実行器quality-execution-0.1.1で新測定する。
shared-format-protocol.jsonとshared-format-approval.jsonは包括承認に基づく別4件で、ケース/期待条件/スキル版は保持する。
この新条件は471d360から4件完走し、各runの独立判定は全項目passed。
詳細と未認定の範囲は[限定適合の記録](../results/2026-10-04-quality-shared-format/report.md)を参照する。

比較の準備版。2026-10-04の利用者承認はapproval.jsonに記録した。実行開始前の時点ではモデル実測は未実行。
bitz-quality 0.1.1の局所試作から始める。
両ケースは公開された合成入力で、保持ケースや実課題ではない。
評価の期待値はこのディレクトリのprotocol.jsonに置き、実測時のモデルworkspaceへ渡さない。

QP-001は局所・可逆な変更の証拠計画、QR-001は実装後の一次資料から行う独立検分である。
fixtureのテストが通ることと、規範文を十分検査することを区別する。
QR-001の脆弱な実装は合成データだけを返す。ネットワーク、秘密、認証情報、本番、依存導入を使わない。

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<worktree絶対パス>/plugins/bitz-core/src:<ruamel.yaml-0.19.1のパス> \
  python3 -B evals/skills/quality/preflight.py
```

preflightはリポジトリ内の.venvに一時workspaceを作り、fixtureをコピーする。
指定2ファイル等だけをGitへ追加し、合成の基準/対象refを作る。remoteは設定せず、フックは無効化する。
公開CLI context/checkと、本文を固定したローカルtest_fixture.pyだけを実行する。verifyは起動しない。
元結果、終了コード、sha256、実assertの範囲、対象の非変更を取得し、既存試験が認可境界を落としていることを別の事前検査で確認する。
この検査は品質やモデル行動の認定ではなく、実測入力の整合性確認である。

提案実測はgpt-6.1-solだけで2ケース×スキル有無×2反復、最大8軌跡。独立検分用実行は別集計とする。
baselineにも公開結果形式・安全条件・同じ一次資料を渡し、スキル本文/referencesだけを除く。
スキルだけに正解や安全な実行権限を渡して比較しない。新規・隔離文脈で直列に実行する。
実行対象ref、pluginとfixture/protocolのhash、モデル名/版、制限、入力/出力・操作ログ・使用量を固定/記録する。
未知の費用を0円扱いしない。追加や再試行は自動で行わない。

保存済み結果の形式/成果物、権限/安全、説明の実証範囲、独立文脈の直接検分の順で判定する。
機械不適合、安全失敗、意味不適合、起動/利用上限、破損や比較条件混在で新規起動を止める。
SDDで認められたbaseline意味不適合の続行例外は、この品質実測へ適用しない。
先行8件が通っても提案30の試作分母・発火/負例/敵対評価・Q0〜Q3・Skill Gateは満たさない。

approvalはこの8軌跡の費用・新しい評価範囲に限る。既存のSDD残予算へ流用しない。
この事前検査はモデル実行器を持たず、既存の発火用run_model.pyも実操作比較の代わりに起動しない。
実操作用evaluate.pyと読取り専用host.pyは、固定の公開Core/テスト操作と操作ログを提供する。
ネイティブシェル・書込み・他MCP・アプリ・プラグイン・検索を無効化し、自己完結したfixtureと公開形式を両variantへ渡す。
各軌跡の後はindependent-receipt.json（status=passed、independent=true、確定run.jsonのhash一致）が必要。
意味・安全・一次成果物を別文脈で検分し、証拠を再検査した後だけ次の1軌跡を起動できる。起動前に予算へ算入し、中断を自動再試行しない。
返却はresponse.schema.jsonの転記用包みに品質JSONを文字列で載せる。Core元JSONは実呼出しの全観測IDから変更せず挿入する。
モデルの元応答と挿入後advice.jsonを分けて保存し、全ID・生stdout/hash・trace/hostログ一致を検査する。
この転記アダプタは両条件で同じで、Core成功や品質判断・未取得証拠を生成しない。大きな元結果の転記精度を本測定で保証したとも主張しない。
実行はclean treeで、同じ確定source ref・protocol・plugin・モデル・実行環境を固定する。

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<worktree絶対パス>/plugins/bitz-core/src:<ruamel.yaml-0.19.1のパス> \
  python3 -B evals/skills/quality/evaluate.py --output <worktree絶対パス>/.venv/quality-model-pilot
```

1回のコマンドで1軌跡だけ起動する。順序は反復1→2、各反復のskill→baseline、各variantのQP→QR。
最大8件という承認を上限とし、最初の失敗・中断・独立検分待ちで止める。記録済みの条件を変えて同じ出力へ再開しない。
