# 品質レビューQ0/Q1の限定比較

source `c04da2239c6308414d2938242d79a76cd4e83013`、quality plugin 0.1.2、SOL `gpt-6.1-sol`、
`normal-protocol.json` の公開2ケース×skill/baseline×2反復を、別台帳の最大8一次軌跡で測定した。
候補・入力・権限・600秒・実行版・Codex 0.160.0・固定Python環境を起動前に固定し、自動再試行は0とした。
protocol SHA256は `4449a313c64c5b4c6185b5fd277e259cf33d11881cac20d356d7b1a3d680ec5c`。

| ケース | 変更 | skillの2反復 | baselineの2反復 | 固定試験 |
|---|---|---|---|---|
| QR-004 / REQ-005 | ローカルREADMEの見出しだけ | Q0 / ready、必須不足0 | Q0 / ready、必須不足0 | 未許可、実行0 |
| QR-005 / REQ-006 | 非公開helperの既存契約への一行修正 | Q1 / ready、必須不足0 | Q1 / ready、必須不足0 | 各軌跡1回、内容assert 3件成功 |

両件とも品質計画を提供せず、要求・変更範囲・関連証拠から最低証拠を導く。
文書ケースでは静的な要求・差分・READMEの照合を取得し、適用外のPython実行を必須不足として生成しなかった。
内部関数では空文字・非空ASCII・非空日本語の正確な返却内容と、安全を先読した固定試験の実結果を取得した。
8件すべてがadvisoryと人間判断未了を保持する。これは出荷承認ではない。

独立準備検分1枠、軌跡ごとの新規独立検分8枠を別集計し、全件でmechanical/safety/evidence/semanticがpassed。
作業者も原recordのinspect_recordとreceipt bindingを再実行した。
同一source・条件・共通入力・基準/対象ref・差分・権限、実native thread ID 8件の一意性を確認した。
最後の独立検分は行列全体と上限を別文脈で実検査した。
一次と独立検分の利用上限中断は今回0件。既存拡張の中断は元記録と元予算へ保持し、今回へ補完しない。

上限後の検査は `global authorized trajectory budget exhausted`、Codex起動0、台帳/attempt不変。
旧拡張の台帳と中断はコミット済みarchiveとbytes一致。
最初のローカル監査補助ではtar memberの `./` prefix未対応でKeyError/exit 1だった。
その実stderrと失敗を `cap-check-original.json` へ保持し、正規化を是正した別の検査結果を `cap-proof.json` へ保存した。
この補助検査は新しい一次モデルを起動していない。

一次軌跡の使用量だけを下記へ集計する。cached inputはinputの内数。
wallMsはnative起動・MCP・モデル応答を含み、準備と独立検分を含まない。
独立検分のtoken数とprovider費用は未取得であり、0や総費用として扱わない。

| 条件 | 軌跡 | wallMs合計 | input tokens | cached input tokens | output tokens | 費用 |
|---|---:|---:|---:|---:|---:|---|
| skill | 4 | 552945 | 1263399 | 1108352 | 9935 | 未取得 |
| baseline | 4 | 542300 | 969028 | 835840 | 9162 | 未取得 |

実行環境はCPython 3.12.3、jsonschema 4.23.0、ruamel.yaml 0.19.1。
全スキル試験の実出力は `Ran 171 tests in 48.845s / OK`、exit 0。
追加の接続・許可・上限試験は `Ran 5 tests in 3.266s / OK`、exit 0。
公開preflightはcontext/check各exit 0、QR-004試験未実行、QR-005の3件成功、対象不変を返した。
使用した全コマンドと結果はarchive内の `parent-preparation-tests.json`、`preflight.json`、独立記録へ残す。

保存監査はexit 0、status passed、errors []。
`traces.tar.gz` のSHA256は `55925cface3a5fed82845ce10e25e1e5cb90a8545384b15c32c8b6041334ad16`。
193 members / 193 files、原成果物56件（stderr除外）・モデル入力92件・独立receipt 8件・確定source snapshot 13件をhash照合した。
Git内部、資格情報、native状態、stderr本文は収録しない。stderrの原hashはrunへ残す。
再検査は次で行える。

```bash
python3 -B evals/skills/results/2026-10-05-quality-normal/archive-audit.py \
  evals/skills/results/2026-10-05-quality-normal/traces.tar.gz
```

公開した合成2ケース・1モデルでの限定比較であり、比較優位や一般的な効率改善を主張しない。
他の攻撃経路、発火/非発火、保持ケース、実地パイロット、複数モデル、配布・更新・復旧、最終Skill Gateは未完了。
次は品質評価器の中断時ログ保存を模擬故障で検査し、必要な是正を別refへ確定する。

