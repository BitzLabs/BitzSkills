# Phase 4：固定2exec/2cellの親セル相関監査（2026-10-10）

専用audit_sequential_parent_linksはprobe-call/exec→probe-read/exec、cell1→2、一覧→読取りの2 native子に限定する。
各親の開始/子受理/dispatch/result/ready/host timing/親完了と、3つのAPI要求の前後関係を検査する。
別turn、親/セルの取り違え・交換・使い回し、子IDやセル内runtime IDの重複、欠落・順序矛盾を拒否する。
旧1exec監査と固定exec/wait監査は追加exec/複数cellを未知として停止する。原証拠を変更しない。

最初の原捕捉再適用はruntime IDの全体一意条件で停止した。原セル1/2に同名tool-1が属することを確認し、
セルIDとruntime IDの組へ照合を是正した。局所正常回帰も異なるセルでの同名再利用を含む。
局所88件/0.814s/OK/exit0。旧yield親記録の再照合もexit0。
source `1d72e209691a06c81c3e53cc82468165f7fe2f81` のclean全501件/62.274s/OK/exit0。
原試験stderr SHA256 `032638639c1152c2560d9aa385f75fb44c3beb32ff75af419b0ee8cb44024d37`、
原検証summary SHA256 `30ddd7e47df49cab8fa974c1976879db2d75a66496514d0279952b1eaaa550a0`。
原captured ref27c3994/receipt SHA256 `b390a1791cdf06fdce9759f4d56b90cab66e2ce28022f902fd8dff347befb77b`へ再適用し、
全target24行/2 native子/2親/cell1/2で適合した。原telemetry値SHA256 `02d32fbfd3029e7324c8c978892a7651130dfb00cd93950cc7b191d979d4937e`。
wire/SSE/SDK配送値/host本文/候補71資源の検査はcallerの原保存物照合で行い、新親監査自身の本文認定とは扱わない。

同sourceの同6公開パス本文202879 bytesを有限v0.22で初回1回送信し、独立SOL22はstatic_review_passed/指摘0/CLIexit0。
入力63602/cached0/出力1302/推論1241 tokens。
原receipt SHA256 `f3ab4a6301b554c6c92612fa76e040ba5c5dbdc379da7d6b23216cbbe94439a2`、
原response SHA256 `19fddee8d9bdb2965bb3fb3390dd7fc5bf8c8e76f8c124b944275daa80a0f72c`。
親が原stdio/schema/最終JSON/usage/hash、確定Git、前後guard、有限予約を再照合した。
公開記録照合もrecorded_sequential_parent_matches_original_bytes/tests501/nativeChildren2/traceRows24/cellIds1,2/exit0。
当区切りSOL1/SDK静的系列累計22、新模擬/HTTP/一次/委譲/自動retry0。
固定2セルの局所相関と当該静的検分だけが通過した。新照合器全文は6パス送信に含めていない。
任意複数/並列/未知pending・全3交換SDK文脈/raw監査・実provider・一次台帳統合・canary・Phase/Step/Gate全体は未認定。
eligibleForMeasurement=falseを維持する。
