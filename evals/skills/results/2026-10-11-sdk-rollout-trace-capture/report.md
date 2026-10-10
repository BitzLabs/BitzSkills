# Phase 4：SDKの推論要求traceの無課金捕捉

公式CLI0.160.1の固定上流ref `d27764b82f7118f674371e6d6e76271d9d606edb` に、
`CODEX_ROLLOUT_TRACE_ROOT`で要求本文をローカル保存する経路を確認した。
thread.rsの環境変数入口、inference.rsのrecord_started、client.rsのHTTP要求直前の記録を参照した。
通常SDKのraw通知で欠落していた初期入力を、認証内容を読むproxyなしで取得する候補として検証した。

有限v0.11/source0d3f281のsequential-readを1回だけ実行。ネットワーク隔離・認証なし・有料0。
CLI/SDK版とSDK tree hash、候補6スキル・71資源を起動前に固定し、source guardの前後一致も確認した。
模擬HTTP3要求、host2呼出し、SDK raw item8件、namespace/runtime exit0、SDKエラーなし。
原イベント33件、原artifact26ファイル、inference開始/完了各3件を私的出力に保存した。
全3要求のtrace JSONは、模擬サーバーが受信・保存した原HTTP要求JSONと型を含めて一致した。
初期inputはdeveloper3件/user2件。通常SDK通知で欠落していた2件を含む5件の要求入力を局所で観測した。

比較器は要求投影だけを扱い、元artifactのhashをcallerが照合してから使う。
追加指示、boolean/数値の差替え、参照欠落・パス逃避、別thread/turn、seq改変、開始/完了の欠落やID差替え、
追加・終端後の推論を拒否する合成4試験は0.002s/OK/exit0。捕捉入口39試験は0.111s/OK/exit0。
verify-recorded-results.pyで原receipt hash・全artifact・Git refのsource・SDK turn・要求値を再照合する。

この捕捉と新比較器の独立検分は未実施。上流HTTP/SSE bytes、応答全payload、全traceの意味、
実providerの完全入力・実効要求上限、発火/行動/実地/Skill Gate/Phase完了は認定しない。
JSON値一致をwire bytes一致へ拡張しない。原応答traceはprotocol投影であり、final itemのstatusやannotationsに
元SSEとの差異があることを保持する。要求側の一致から応答の完全性を推定しない。
原bundle/RPC/SDK通知/host/HTTP/SSEは私的出力のまま保持し、公開記録はref・件数・hash・実exitのみ。
