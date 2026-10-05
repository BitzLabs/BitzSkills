# 品質評価器の中断保存の是正（2026-10-06）

品質評価器の後処理で原trace/stderrを失う欠陥を、原コミットの不合格を保持して是正した。
対象は評価器の故障時保存であり、実モデルの品質比較・Skill Gate・Phase全体の認定ではない。

原sourceは `e515544660dcf115a5d8e523ec5228fa1705f780`、是正sourceは
`6bfaa73245a731c3eeccc9abb3faccc502cd4af7`。SOLの独立文脈は各refにつき1回、
新規一次測定0・自動再試行0の別の有限条件で固定した。
元の利用上限による独立起動中断1件と、自動承認レビューが利用上限で完了せずPUSH未実行となった記録も保持する。
今回の独立2起動の使用量・料金は不明であり、0として扱わない。

原refの独立検分はfailed、Spyによる8経路で次の3件を確認した。

- P1: 起動成功後の `OSError` が保存済みtrace/stderrを空出力と例外文で上書きする。
- P2: `text=True` の復号失敗で非UTF-8原bytesを取得前に失う。
- P2: `KeyboardInterrupt` で中断記録を保存しない。

作業者の初回統合9試験も `FAILED (failures=3, errors=1)`、exit 1。
是正後の11試験を原評価器へ再接続すると `FAILED (failures=4, errors=1)`、exit 1。
この追加分には中断receipt拒否と起動失敗の確認を含む。原helper試験2件だけの通過を統合経路の通過と扱わない。

是正版 `quality-execution-0.1.3` は起動と後処理の例外経路を分離し、原bytesを保存してから復号する。
保存失敗は両ログを個別に試し、未保存bytesをbase64で退避する。非0終了・後処理失敗には実exit codeを保存する。
手動中断で `subprocess.run` が返さないpartial outputは未取得、provider使用量は不明と記録する。
中断記録がある軌跡はreceiptがあっても追加起動を拒否する。旧実測の版・台帳・判定は変更しない。

検証はCPython 3.12.3の既存固定環境で実行した。全てモデル起動を伴わない合成試験である。
共通の実行接頭辞は次のとおり。

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$PWD/plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i" \
/home/hide/.cache/uv/environments-v2/run-conformance-3a9acb64608185bd/bin/python \
-B -W ignore::DeprecationWarning -m unittest discover -s tests/skills -p '<pattern>'
```

| 文脈 | pattern | 実出力 | exit |
|---|---|---|---|
| 作業者・是正時 | test_quality_interruption.py | Ran 11 tests in 0.087s / OK | 0 |
| 作業者・全スキル | test_*.py | Ran 182 tests in 49.499s / OK | 0 |
| 新しいSOL独立文脈 | test_quality_interruption.py | Ran 11 tests in 0.091s / OK | 0 |
| 新しいSOL独立文脈 | test_quality_evaluation.py | Ran 24 tests in 6.206s / OK | 0 |
| 作業者・独立検分後 | test_quality_interruption.py | Ran 11 tests in 0.092s / OK | 0 |
| 作業者・独立検分後 | test_quality_evaluation.py | Ran 24 tests in 6.213s / OK | 0 |

是正refの独立判定はpassed・指摘0件。作業者が再実行した35試験と、独立検分の4ソース/4ログの
確定ref・原bytes・SHA256一致を別々に確認した。正常記録、timeoutのbytes/text、起動失敗、
非0終了と実workspace差分、片側/両側の保存失敗、再起動拒否、共有形式の旧新版互換を検査した。

保存証拠は `evidence.tar.gz` の25ファイル・180714 bytes。hashは
`4af6bc663085c8481dd5b41cac0b4d67f4043846f13cf07d6900e28363fc9a20`。
原failedレビュー、是正passedレビュー、別有限scope、模擬プローブ、原・是正のソース、
回帰試験の失敗/成功ログ、作業者の再検査・照合を含む。
`manifest.json` と保存監査は次のコマンドで再確認できる。

```sh
python3 -B evals/skills/results/2026-10-06-quality-interruption/archive-audit.py \
  evals/skills/results/2026-10-06-quality-interruption/evidence.tar.gz
```

実出力は `status: passed`、`files: 25`、`bytes: 180714`、`errors: []`、exit 0。
保存監査はarchiveを展開せず、各原bytes・hash・原/是正判定・有限条件・ソースsnapshotを確認する。

中断記録自体も書けない全面ストレージ故障では、全証拠を保存できるとは判定していない。
手動中断の未取得partial outputを完全保存したとも判定しない。Core実装と適合fixtureは今回変更しておらず、
CoreのGate A/B再認定は行っていない。
残る攻撃経路、発火・保持ケース・実地パイロット、複数モデル、配布・復旧・最終認定は未完了。
