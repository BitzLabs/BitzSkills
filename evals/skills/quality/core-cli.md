# 評価workspaceの公開Core操作

run_bitzはbitz-core 1.0.0の公開CLIを呼ぶ読取りアダプタである。
operation=contextなら`python3 -B -m bitz.cli context <指定起点> --purpose interpret --format json`、
operation=checkなら`python3 -B -m bitz.cli check <指定起点> --format json`を実行する。
指定起点と所有workspaceはlist_filesのメタデータで確認する。
任意argv、verify、設定変更、外部操作、秘密取得は提供しない。

状態と終了コードはpassed/passed_with_warnings=0、failed=1、blocked=2、error=3。
引数不正は終了4、Core結果とstatusを作らず、stderrに理由を残す。
公開元結果の対象、revision、完全解決、contextDigest、診断と警告を保持する。
Coreの結果は仕様構造の検査やコンテキスト取得であり、実assertの範囲や製品品質を保証しない。

run_bitzは観測IDと元結果を返し、一次stdoutとhashはモデル外のhost.jsonlに保存する。
最終応答のcoreObservationIdsは実際の全Core観測IDを呼出し順で列挙する。
documentJsonは品質schemaのJSONを文字列として返すが、coreResultsだけは空配列にする。
取得した元JSONの複写ミスを避けるため、評価器は指定されたIDから元結果を変えず挿入する。
全ID一致、status/exitCode/source/hash/元JSONの同一性を検査し、元応答と挿入後文書を別に保存する。
これは両variantに同じ条件で提供する転記アダプタであり、助言や証拠取得を自動で生成しない。

read_fileは一覧にある固定ファイルだけを読む。read_diffは確定した基準/対象refの差分を返す。
run_fixture_testが提供される場合、固定test_fixture.pyの本文と副作用を先に読み、安全を確認してから起動する。
各ツールは取得先・hash・対象refを返す。collectedEvidenceには直接取得した証拠だけを使い、未取得の予定を載せない。
最終応答のreasonとdocumentJsonは日本語で記述する。
