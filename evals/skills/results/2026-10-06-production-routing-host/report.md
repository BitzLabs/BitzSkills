# 製品発火評価の固定資源ホスト

source `fe794c66` / production-routing-host-0.1.0で、製品6スキルの資源だけを
stdio MCPで提供するホストを追加した。確定manifestと全71資源を照合し、
読取り時にもhash・相対パス・package・symlinkを検査する。
公開toolはlist_resourcesとread_resourceだけで、操作・試験・shell・変更の入口を持たない。
未登録のcase/期待値/controlを渡さず、manifestの追加情報を一覧へ転送しない。
各実結果・hashと拒否を新規0600ログへ記録し、既存ログを再利用しない。

有限contractはhost-preparation.json、独立SOL1・一次0・retry0。
独立検分 `sol_production_routing_host_review_01` はP1/P2各0件で通過した。
作業者は4sourceと確定ref、独立実ログとreceipt、固定manifest・全資源のhashを照合した。
単体実出力は親 `Ran 215 tests in 55.429s` / `OK`、
独立 `Ran 9 tests in 0.074s` / `OK`、検分後の親 `Ran 9 tests in 0.080s` / `OK`、各exit0。
独立native stdioは承認2/拒否1、親再接続は承認4/拒否2、各exit0。
親はCore/SDD/品質の実本文読取りhashと、操作tool・case読取り拒否を実確認した。
全71資源は再接続の前後で不変だった。実モデルは起動していない。

成果物・固定source snapshotの保存監査はarchive-audit.jsonに記録する。
usageと費用は不明で0扱いしない。本結果は発火実測・Core操作・動作実証・Skill Gateを認定しない。
不正JSONへの耐障害性と並行した悪意あるファイル置換への原子的防御は保証しない。
モデル機能の無効化・非公開出力保存・有限台帳・独立検分待ちは後続runnerで固定する。
原保持集合の意味重複によるP2停止を、本ホストの成功へ置換しない。
