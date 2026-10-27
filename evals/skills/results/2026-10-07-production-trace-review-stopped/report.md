# Phase 4：製品入力・証拠監査コンポーネントの独立検分停止

公開コンポーネントのsource8 `7c556166d7552dc2faed8502b5dddfdc6de94b53` を別SOLで検分し、P1=0/P2=3で停止した。
確定ref/clean treeの親315試験と独立21/315試験は通過したが、次の偽装条件を通す問題があった。

1. `commentary` のagentMessageだけで最終応答と扱う。phase欠如/未知値/開始完了のphase変更も拒否しない。
2. 最終応答の開始後に本文を読む、または進行中の読取りを完了しても、判断時点の本文読取り証拠にできる。
3. 実hostが拒否するscope/schemaVersionのmanifestと、それに合わせたdiscovery/resultを通す。

原報告・receipt・予約は `.venv/production-trace-review-01/` に残し、hashをsummaryへ記録した。
原receiptは数値をフィールド名末尾へ付けたキーを含む。原ファイルを訂正せず、その制限も保持する。
後続receiptは明示的なschemaでキー/値を固定する。
この経路はcollaborationのtool記録と実ローカルコマンドを証拠とする。provider原通信bytesは取得できず、
native CLI接続/一次モデル測定/行動/Skill Gateの証拠へ拡張しない。私的評価資料は検分に使っていない。

是正では各攻撃を回帰にして、明示的 `final_answer` の一意性とphaseの前後一致、
最終応答開始前の全tool完了と以降のtool拒否、実hostと同じscope/schemaVersionを要求する。
phase欠如/null/未知値は互換推定せず停止し、`commentary` は最終応答前の進捗だけに使える。
親の局所試験が通っても是正完了を認定しない。修正版の別確定sourceと有限独立SOL1回を先に固定する。
旧停止と消費1枠を保持し、旧契約残枠0/一次0/有料自動retry0。
