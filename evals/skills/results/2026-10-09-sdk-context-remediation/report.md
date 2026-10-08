# Phase 4：入力指示・通知IDの矛盾を拒否する是正（2026-10-09）

source `220df0dde378cae10ffc7dc917d84cf1bc5f8f1b` の全431件と原証拠再照合は通過した。
合成profileで追加指示を拒否し、SDKと共通native監査で通知外側のIDを照合する。
修正版の独立再検分は、新payloadの送信確認待ち。指摘解消済み・Phase/Step/Gate完了とは判定しない。

## 独立検分と親の再現

ユーザーの明示承認後、source `dad596b2034bbcd0abb4cd25c19aea78143aa5a3` の6ファイルを
OpenAI Codex CLI `gpt-6.1-sol` へ送る独立静的検分1回を実施した。
原保存先は `.venv/sdk-trace-independent-review-06`、CLI exit0、timeoutなし、review_findings/P2=2。
一次0/委譲0/自動retry0、この有限枠は消費1/残0。検分者が試験を実行したとは扱わない。
以前の承認待ち・停止・指摘・予約は歴史として保持し、訂正上書きしない。

指摘は、cwdなしの合成profileがSDKのbaseInstructions/developerInstructions指定を無視すること、
turn/completedの外側turnIdと内側turn.idが矛盾しても受理することである。
親は同sourceで実行し、次の実出力を得た：

```text
synthetic-instruction: sdk_scripted_exchange_diagnostic_passed
outer-turn-id: sdk_scripted_exchange_diagnostic_passed
```

親は原stdout/応答/schema/usage/全歴史source hash/Git bytes/前後guardを再照合した。
実出力はreview06_terminal_schema_and_findings_rechecked/P2=2/exitCode=0。
原review receipt SHA256は `196a929fa99c8bad2facb8284f01a5b43ed939cfa9c5c5ab0a43cd4b330a1fa4`、
応答SHA256は `0c40c9ef80fff85c627d149a905cebdd4b1190978f86aca8704f27dcd11de699`。
usageはinput37410/output1695/reasoning1030。reasoningをoutputへ重ねて加算しない。

## 是正と局所検証

synthetic-one-input-onlyでは、baseInstructions/developerInstructionsのキー指定を拒否する。
空文字/nullでも指定自体を拒否し、SDKの追加指示がprovider入力から欠落した証拠を通さない。
実SDKの固定profileは従来どおり前置文脈全体を照合し、一般providerの互換性へ拡張しない。

SDK通知に存在する外側threadId/turnIdを確定IDへ照合する。
共通native監査でもthread開始、turn開始、turn完了の外側ID矛盾を拒否する。
thread開始時に未来のturnIdを追加した条件も拒否する。
回帰を追加した対象92件は0.792s/OK/exit0。

確定ref/clean treeでの全件・原証拠再照合：

```sh
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-08-sdk-trace-connection/verify-parent-links.py --source 220df0dde378cae10ffc7dc917d84cf1bc5f8f1b
```

実出力はsdk_parent_links_artifacts_rechecked/tests.count431/tests.seconds62.113/tests.exitCode0。
原stderr終端は `Ran 431 tests in 62.113s` / `OK`。
原hash/source/全71資源Git/対象原telemetry19行/固定1execの親call・cell・2子IDを照合した。
前後source guard一致、保存先は `.venv/production-sdk-parent-links-verification-08`。
テストstderr SHA256は `bdc9da638f4a8e6adff1cc45d93397cccf8e0bbdc5dd717212d7db8f618f1d7f`。
2026-10-08の固定原試行read-06を再照合しており、2026-10-09の新SDK通信を捕捉したとは扱わない。

公開要約の原保存物・歴史Git・未起動の送信候補への再照合：

```sh
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B evals/skills/results/2026-10-09-sdk-context-remediation/verify-recorded-results.py
```

実出力はrecorded_results_match_original_bytes/tests431/originalReviewFindings(P2=2,P3=0)/
newIndependentReviews1/pendingReviewInvocations0/eligibleForMeasurement=false、exit0。
この照合は外部通信・モデル起動・書込み・全試験の再実行を行わない。

今回の新mock/ローカルHTTP要求は0、独立SOLは今回1呼出し・SDK証拠接続系列累計6呼出し。
一次モデル測定は0。原試行を再照合するたび新規試行・モデル呼出しへ加算しない。

## 再検分と継続送信の確認待ち

別有限1回のv0.7を準備したが、自動承認審査は旧sourceの承認では変更後payloadへの明示承認が
不足するとして拒否した。同じ6ファイルであるが、今回の送信・起動・予約は0。
review-07の出力ディレクトリは未作成。再試行や迂回は行わない。
契約JSONはsource guardの対象であり、モデルの本文payloadとして送る6ファイルには含まない。

具体的source・6ファイル/hash・宛先・1回上限は `public-code-transmission-approval-request.md` に示す。
同じ6ファイルの修正ごとに送信確認が繰り返されるため、今回と以後の同じ公開コンポーネントの
修正後送信も、同じ宛先・各有限1回の条件で許可する範囲を明記した。継続範囲はまだ未承認である。
確認後は独立再検分と親の原応答照合を優先する。

SDK rawResponseItemの無課金捕捉、任意複数cell/待機、実provider、台帳統合、公開canary/本測定は残る。
eligibleForMeasurement=false、期待行動・native provider・全Skill Gate・Phase/Step/Gate完了は未認定。
