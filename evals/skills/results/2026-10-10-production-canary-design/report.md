# Phase 4：公開canary統合設計の準備結果

source `747c4988536fa61af1e91f9e30853e4ad4de58e6` でdraft設計、有限静的検分v0.24、起動しない局所検証を用意した。
初回案は2ケース×2反復、一次4/独立一次検分4。設計静的検分は別の1枠であり、今回は未起動。
provider retry/要求上限、隔離差分、完全初期入力の証明方法は一次起動前の未解決事項。
正本の採点条件、REQ/TECHの意味、既存固定診断の範囲は変更していない。

## 実検証

最初の直接起動は必要なPYTHONPATHを指定し忘れ、505件/43.919s/44 errors/exit1。ホストの実終端出力で確認した。
この失敗のstdout/stderrファイルは保存しておらず、原bytesの保存済み証拠として扱わない。
修正後はクリーンな確定refで `check_canary_design_preparation.py --source 747c4988536fa61af1e91f9e30853e4ad4de58e6` を実行。
全505件/61.853s/OK/exit0。原stdout/stderr、起動前後guard、公開6本文hash、前回原結果pinを私的出力に保存した。
今回の公開6本文は89,977 bytes。原結果summary hashは `a9fbe189a4fd0084d9f8351aa507244d1de7fc0daf92838f848a8012f3e00e9e`。

## 停止と次の作業

新6パスの静的SOL送信は自動承認レビューがprocess作成前に拒否した。送信・モデル予約・起動・消費0。
理由は、SOL評価全般の許可では今回の具体的6ファイルとOpenAIへの送信承認を満たさないこと。
本人へ確認する具体的範囲は `public-code-transmission-approval-request.md` に記載する。
許可後は有限v0.24の静的検分と原応答の親照合、指摘対応を進める。
実provider接続・一次台帳統合の実装・本canary起動・測定適格性・Phase/Step/Gateは未認定。
