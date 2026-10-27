# Phase 4：公開カナリアの一次実行器

公開正例SE-001と負例SE-016を各2反復、起動前の共通台帳で一次4枠・独立SOL4枠に束縛する実行器を追加した。
現時点の一次起動・一次独立採点は0。有限ホストは一覧1・選択SKILL.md本文1のみ、制御はexec/wait計2回。
SDK1 turn、壁時計300秒、通常/stream retry0、WebSocket/無制限retry/proxy fallback無効。
モデルAPI3・モデル一覧2は応答ログの観測閾値であり、送信前hard cap・認証復旧ゼロは保証しない。
`capture`は原取得であり、親の原相関と独立採点が終わる前に次を予約しない。

source `533f0f11b91bcf025a6592d049f8d1838ae87e99`の全560試験は56.069秒、26 errors、exit1。
一般名hostのimportが既存の品質評価ホストと衝突した。失敗原出力を保持し、固有名の動的読込みへ是正した。
source `dcdfd4f21831ff17a21a2a237366263e55060fc7`の全561試験は62.516秒、OK、exit0。
固定71資源・公開Git本文・SDK依存・入力投影の無課金事前検査も通過した。

SOL v39は固定入力の完全一致是正に追加指摘せず、監視スレッド例外の停止への伝播と、拒否後の本文読取りについてP2=2を指摘した。
型検査・全relayの例外/未完了をcaptureIntegrity=falseへ伝える処理・停止後の不可逆拒否・一覧成功状態を追加した。
模擬CLIをexit0にした監視例外の実subprocess回帰でもcaptureIntegrity=falseとAttributeError原記録を確認する。
この是正の独立再確認は残件。過去の原指摘・消費を消さず、全wire/行動/実地/Gate/Phaseの成功に静的検分を代用しない。
