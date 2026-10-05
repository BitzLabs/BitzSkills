# 製品本文による発火評価の資源準備

source `3252a29642323a403a51d9bd10acc6f4a7f3d236`。
旧prototypeのcandidate6本文と製品plugins本文が一致しないことを確認し、
旧候補・原結果を変更せず、製品3packageの資源をGit固定refから取得する準備処理を追加した。
SKILLの名前・description・版・取得先と全資源hashをmanifestへ固定する。
作業ツリーの未コミット差分や後続commitを混ぜず、symlink・保護/不正パス、
repo外への出力・出力symlink逃避・既存/中断snapshot再利用を拒否する。

実出力:

- 親単体: `Ran 8 tests in 0.344s / OK`、exit 0。
- 独立単体: `Ran 8 tests in 0.388s / OK`、exit 0、P1/P2指摘0。
- 独立後の親再実行: `Ran 8 tests in 0.355s / OK`、exit 0。
- 親・独立・親再実行のsnapshot: 各prepared/exit0、製品6本文・71資源。

3snapshotは全資源bytes/hashを固定refと照合し、manifest hashも一致した。
manifest SHA256は `603333c4bbe52047b54003183830d989ada91f35bb810f78e7f59a2dd575482b`。
親は4sourceと独立2ログhashも再照合した。
gpt-6.1-solの準備独立1枠、新規一次0、自動再試行0。独立検分の費用は未確定。

これは資源の準備であり、製品本文の発火実測・保持ケース生成・実地パイロット・全Gateは未認定。
snapshotはrepo内の公開資源だけで、保持ケースの保管領域として使わない。
[保存計画](../../routing/held-out-storage-plan.md)は外部領域の新規作成と非公開ケース/証拠保存を
明示承認後だけ行う。承認前の外部書込み・保持ケース生成は0。
旧比較・停止済み予算・failed/unknown・capacity通知は保持する。

原ログ・独立所見・有限予算・3manifestと75固定sourceを`evidence.tar.gz`へ保存した。
`archive-audit.py`の実出力はpassed、89ファイル、716056 bytes、75固定source一致。
archive SHA256は `6e5e1f77d578a3f5b7ee785e6e5d68b7a23f068cefcfa5561e0ed14185b75917`。
