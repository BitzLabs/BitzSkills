# SDD評価の中断保存とログ保存失敗の是正

SI-010はnative app-server初期化で中断し、元refには終了コード・実条件・前後差分をまとめる失敗記録がなかった。
元中断の証拠と意味適合未測定の判断は`../2026-10-05-sdd-implement-safety-03/`に保存しており、変更していない。
起動環境のRead-only file systemの原因解消とは分け、失敗時の保存処理を補強した。

## 原不足と是正

最初の保存補強ref `a63dbd2c24bf53537d5c80ebf8e805043573b531`では、
非zero exit・timeout・OSError・最終応答欠如をfailure.jsonへ保存する試験31件が通過した。
しかし独立検分で、trace保存だけにOSError(28)を注入すると保存関数に到達しないP2を再現した。

```text
invocationCount: 1
failureJsonExists: false
runJsonExists: false
stderrExists: false
```

この不適合は`independent-review-original.json`へfailedのまま保存した。
SHA-256 `90d1f8590de49f6296d735a3361ac7a4fea8afd3b6bbfc3d3648be4cec1bf977`。
最初の検分は31件/18.500sと台帳13件/0.070sがOKでも、反例発見で停止している。

是正ref `644603a569f65d9fad89a9504731890beaac9b1c`では、原stdout/stderrをbytesのまま個別保存する。
一方が失敗しても他方を保存し、保存失敗のパス・errnoと未保存の原bytesをbase64でfailure.jsonへ残す。
非UTF-8のtimeout部分出力でもdecode例外で記録を失わない。
failure.jsonには固定identity、argv、cwd、timeout、state/logの場所、実wallMs、終了コード、前後snapshot、
実changedPaths、保存済みartifact hashを記録する。適合run.jsonや意味合格へ変換しない。
再実行は既存出力として拒否し、原ログ・失敗記録を上書きしない。
provider usage/costの欠測はnullを保持する。

## 独立再検分と作業者の再実行

私的履歴を引き継がない別SOL文脈で、32件/19.050sと台帳13件/0.074sのOKを確認した。
原P2を含む独立8条件で固定identity、変更済みworkspace、原bytes、retry拒否、非上書きを直接再実証した。
元refから品質scopeの証拠2ファイルを保存するHEAD変更があったが、対象評価器・2試験ファイルのblobは一致した。
再検分結果は`independent-review-corrected.json`に別記録として保存した。
SHA-256 `b7a60be42fbb18194b1d23fac322eacbd98e94fe67683c4ef53fb6ec8b465e03`。
最初の成果物は指定worktreeへ保存されておらず、作業者のnative cpがexit 1を返した。
検分者がnative apply_patchで保存し直し、作業者も原保存物からのコピーとhashを確認した。試験retryはない。

作業者の全スキル検査は固定Core src/ruamel.yamlの絶対PYTHONPATHとjsonschema 4.23のPythonで実行した。

```text
python -B -W ignore::DeprecationWarning -m unittest discover -s tests/skills -p 'test_*.py'
Ran 156 tests in 45.719s
OK
```

再検分後も作業者が実コマンドを再実行した。

```text
python3 -B tests/skills/test_sdd_skill_eval.py \
  SddEvaluationTests.test_native_invocation_failures_preserve_conditions_partial_changes_and_raw_output \
  SddEvaluationTests.test_timeout_keeps_non_utf8_partial_output_and_log_write_failure_fallback -v
Ran 2 tests in 0.543s / OK
python3 -B tests/skills/test_sdd_batch.py
Ran 13 tests in 0.069s / OK
```

すべてexit 0。2試験は8条件でnative呼出し1回、実条件と原bytesの保存、差分保持、成功非主張、再実行拒否を確認する。
追加モデル測定・Codex起動は行っていない。
元SDD評価refからCoreと適合fixtureはgit diff exit 0で不変のため、Core Gateの再認定はしていない。

## 限界と次工程

保存先全体やfailure.json自体を書けないファイルシステムの障害には保存を保証できない。
native app-serverの具体的なreadonly失敗パスと実効環境は未確定であり、SI-010は未測定のまま。
補強後にモデル送信なしでローカルapp-serverのinitializeだけを比較した。
通常sandboxではexit 1/Read-only file system、外側制限解除ではinitialize結果を取得しexit 0だった。
具体的な失敗パスは未特定だが、外側のfilesystem制限を変更すると初期化が成功することを実証した。
thread/turnは送らず、返信はキー名だけを保存し、秘密は読取り・出力していない。
実出力と条件は`native-initialization.json`に保存した。モデル処理の成功はこの診断では主張しない。
次は実行器の失敗保存の是正と外側の実行条件を変更し、別ref・別出力・新しい有限台帳で
SI-010だけを1回測定する。同条件の自動retryやモデルの任意操作の許可に拡張しない。
独立検分usage・provider費用は欠測で、0扱いしない。Skill GateとPhaseは未認定。
