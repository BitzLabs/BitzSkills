# 独立CLI準備の停止と初期化修正

2026-10-07のユーザー承認を受け、非公開評価資料をSOL提供先へ送信する独立CLI準備を起動した。
旧source `e49304314469a260362f0b10f29c25ea7497f351` の準備枠を起動前に1回予約したが、
実exit1・5280msで停止した。stdoutは0 bytes、stderrは197 bytesで、thread.started/turn.completedはなかった。
原bytes・台帳・実行receiptをowner-onlyで保持し、準備の通過や費用0を推定しない。
usage/費用はunknownである。作成・集合検分・一次はまだ0。

## 切分けと修正

stderrを復号・表示せず既知のbyte列だけを照合し、内部app-server初期化とEROFSを分類した。
ネットワークを`bwrap --unshare-net`で分離したローカル診断6条件を実施した。
hostの実homeを読取専用にしたままでは初期化が停止し、tmpだけの仮想隔離でも開始しなかった。
config.toml/installation_id/tmpを新scratchへ仮想隔離し、既存の他の子要素をROへ戻した条件では、
thread.startedが得られ、初期化のEROFSは検出されなかった。

新実行source `4736737b25b8e0b190e3863b508e56589e952f1e` は13ファイルを固定する。
実homeを上書きせず、HOME/CODEX_HOMEも変更しない。新しいCLI初期化状態は今回phase内の新codex-homeへ置く。
旧source7、collection source15、旧停止receipt/原出力も開始・終了で照合する。
旧枠を返却せず、新しい台帳02・各役割1回を別契約で予約する。
追加準備の明示承認記録をsourceへ束縛し、それがない場合はCLI起動・枠予約より前に拒否する。

修正版のnamespace全体でも、ネットワーク遮断下でthread.startedを確認した。
診断は12秒でtimeout終了（実exit-15）し、モデルの正常終了や準備通過は主張しない。
提供先へ通信できないローカル診断であり、有料モデル検分の代替にはしない。
実行した補助コードの公開コピーは[offline-bootstrap.py](offline-bootstrap.py)。
実コード/診断集計のhashはsummary.jsonへ記録した。

## 実検証

固定Python3.12.3/jsonschema4.23.0/ruamel.yaml0.19.1を用いた。
親の実出力と実exitは以下のとおり。各logはrepo内`.venv/held-out-single-replacement-05/`に保持する。

```text
旧実行器16件: Ran 16 tests in 0.658s / OK / exit 0
収集監査14件: Ran 14 tests in 2.745s / OK / exit 0
修正版9件: Ran 9 tests in 0.102s / OK / exit 0
全体: Ran 285 tests in 61.414s / OK / exit 0

native_actor_v02.verify(4736737b25b8e0b190e3863b508e56589e952f1e)
new source13/old source7/collection15/candidate/old stop bytes matched / exit 0

native_actor_v02.py --source 4736737b25b8e0b190e3863b508e56589e952f1e --role preparation
status blocked / errorType FileNotFoundError / automaticRetry false / exit 1
（追加承認記録なしの起動拒否。モデル起動・枠予約は0）
```

新試験の合成fixtureは初回にpublic storage拒否を起こしたため、fixtureのrepo境界をmockへ合わせて訂正した。
また、旧停止領域を残す終了時チェックと新版promptの参照先を確定前に修正した。
初回試験logを保持し、訂正後の9件/285件を採用する。有料再試行は行っていない。

親の[verify-parent-artifacts.py](verify-parent-artifacts.py)もexit0だった。
非公開原成果物7件のhash/0600、旧停止receipt、新source13/旧source7/collection source15、
候補71資源の実Git blob一致、285件の原log、診断集計と実行コードhashを再照合した。
承認なしの新台帳/新CLI領域が未作成で、cases/evidenceが0であることも確認した。

これは親のコード検証とオフライン初期化検証である。修正版の独立SOL検分は未実施。
旧collection0.4のP2停止とcollection0.5準備だけの通過を保持し、cases/evidenceは未作成。
追加確認の具体的な上限は[budget-approval-request.md](budget-approval-request.md)に記録した。
