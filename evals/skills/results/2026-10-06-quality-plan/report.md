# 品質計画QP-001の公開比較

source `cbd6700fb6f205f50eafe3dcd4b155da2b3508df`、
bitz-quality 0.1.3、quality-plan 0.1.1、quality-execution-0.1.5。
原pilotのQP skill1件とQR失敗停止・残枠不使用を保持し、別条件・別予算で測定した。
原QPのfixture・prompt・期待条件は維持し、試験実行不許可を明示した。
プロトコルSHA256は `c8dea00482517a5d2669f160db798ba61984fca07bc3c93ad444bc11fe01968e`。

最大4一次軌跡（skill/baseline各2反復）を完走した。各件の機械・安全・証拠・意味の
独立4検査と親再監査はpassed。準備独立1枠、軌跡独立4枠、自動再試行0。
モデル設定名はgpt-6.1-sol。内部provider版と料金、独立検分の使用量は未確定。

| 条件 | Q帯 | 計画状態 | 試験実行 | 独立4検査 |
|---|---|---|---:|---|
| skill反復1 | Q2 | needs_information | 0 | passed |
| baseline反復1 | Q2 | needs_information | 0 | passed |
| skill反復2 | Q2 | needs_information | 0 | passed |
| baseline反復2 | Q1 | needs_information | 0 | passed |

既存assertは空入力のエラー件数1だけを検査する。両条件は型・内容・通常入力を
実証済みとせず、追加試験・独立レビューを予定へ分け、未決事項と停止条件を残した。
Q2は具体的な互換性の懸念に基づく保守的上位として、事前固定したinterpretation内で許容した。
Q帯の相違だけを優劣へ変換しない。advisoryと人間判断待ちを維持している。
実装前なのでbase==target・空diffは適法。Core context/checkの成功は挙動実証を意味しない。

準備実出力は親 `Ran 89 tests in 15.687s / OK`、独立
`Ran 89 tests in 15.733s / OK`、検分後の親
`Ran 13 tests in 0.106s / OK`、各exit 0。親・独立・検分後のpreflightもexit 0、
context/check各passed/exit0、試験未実行・対象非変更だった。
11sourceと独立2ログhashを親が照合した。

4軌跡のsource/protocol/plugin/環境、fixture bytes、共通配布資料、安全権限、ref・空diffは一致した。
相違は該当SKILLとreferencesの有無。native threadと独立review IDは各4件で重複しない。
未検分時と上限後の実measure拒否を、Codex backend spyで追加起動0・台帳bytes不変と確認した。
補助probeの誤mockとarchive helperの誤ファイル名による失敗は、原helper・実出力ごと保持して是正した。
これらはモデルの再試行ではない。

| 一次測定条件 | 軌跡数 | wall ms | input tokens | cached input tokens | output tokens |
|---|---:|---:|---:|---:|---:|
| skill | 2 | 276850 | 534954 | 475904 | 9312 |
| baseline | 2 | 200019 | 415577 | 373248 | 6358 |

cached inputはinputの内数。費用不明を0円扱いせず、独立5枠の費用を上表に混ぜない。
両条件が同じ公開合成計画に限定適合した結果であり、比較優位・実保持ケース・実課題・
全Skill Gate・製品品質・Core Gateを認定しない。共通転記アダプタは元Core JSONを保持するが、
モデル自身による大きなJSONの転記精度を測ったとは主張しない。

一次成果物・原trace/host返却・独立receipt・親再監査・有限予算・31固定sourceを
`evidence.tar.gz`に保存した。provider原stderrはローカルに保持してhashを検査し、本文は公開しない。
`archive-audit.py`の実出力はpassed、152ファイル、817796 bytes、31固定source一致。
archive SHA256は `48e843712c0cc8b05326177121188b3b4fca2edf11090da78a6c34cdbdb5b63c`。
次は旧prototype候補と異なる製品本文の発火条件を、別の有限契約へ固定する。
