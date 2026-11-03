# 公開92枠の連続した評価失敗の調査

対象は、公開評価の campaign `public-matrix-survey-20261016-01`（source `b00589bac9bd9dc1f96a9e8b9f71654cad4af5e3`、
condition `45a9d8195897afea589364566e2cfcfd4471b88cf3b412398d65522f76f1360e`）の最終記録である。
新しいモデル実行、予約、非公開原記録の読取りは行っていない。公開済みの集計と archive だけを読んだ。
以下の仮説と事実は2026-10-27時点の調査である。2026-11-04に原記録を再検査した結果を末尾へ追記した。
今回の再検査は過去の成績を書き換えるものではなく、Skill Gateの認定ではない。

## 読んだ資料

- `evals/skills/results/2026-10-11-development-plan/r04-survey-progress92-20261016.json`
- `evals/skills/results/2026-10-11-development-plan/evidence-r04-survey-progress92-20261016.tar.gz`
  の `actual-slot-0021.json`〜`actual-slot-0092.json`、`observation.json`、`report.json`、`quota.json`
- 提案31 §5 の 2026-10-15〜2026-10-21 の進捗履歴と、同期間のコミット

集計は次で再現できる。

```text
uv run --project plugins/bitz-core --with jsonschema==4.23.0 python \
  evals/skills/routing/production_failure_streak.py \
  evals/skills/results/2026-10-11-development-plan/evidence-r04-survey-progress92-20261016.tar.gz
```

出力の要点は、新規72枠のうち`evaluation_failed` 35、連続の範囲が58〜92（同じsignature
`["primary","primary_capture_stopped","ValueError",false]`）、測定のないケースが SE-030〜SE-046 の17件である。

## 事実

| 区分 | 枠 | 正解 | 不正解 | 評価失敗 |
|---|---|---:|---:|---:|
| 持越し | 1〜20 | 16 | 2（7、8: SE-004） | 2（18: SE-009、20: SE-010） |
| 新規 | 21〜57 | 36 | 1（46: SE-023） | 0 |
| 新規 | 58〜92 | 0 | 0 | **35** |

- 58〜92 の35枠は、すべて一次の段階で `primary_capture_stopped`、`errorType: ValueError`、`timedOut: false` だった。
  型が1種類だけで、途中に成功がない。
- 対象は SE-029 の2回目から SE-046 までである。**SE-030〜SE-046 の17ケース（46ケースの37%）は、
  この campaign で有効な測定が1件もない**。公開の正解52／不正解3は、SE-001〜SE-029 だけの値である。
- 失敗は3回の実行区間（58〜60、61〜76、77〜92）に分かれ、その間に約4.3時間（15443秒）と
  約5.5時間（19910秒）の待機がある。待機は利用枠の回復を待つためだった（コミット `224822b1`、`2360e50c`）。
  失敗は**2回の利用枠の回復をまたいで続いた**。
- 失敗した枠でも名前空間の起動は1回ずつ記録されている（`actualNamespaceInvocations: 1`）。
  最終の利用枠は5時間枠97%、週枠76%だった（`quota.json`、`rateLimitReachedType: null`）。
- 運用者は1枠ずつ、60秒の間隔で起動を続けた。連続失敗で起動を止める規則はなく、
  原因分析は「全件評価の後」とする方針（提案31 §5 2026-10-15、2026-10-16）で後回しにした。

## 原因の仮説

最も可能性が高いのは、**評価環境の外部の変化を、評価基盤が取得失敗として拒否し続けた**ことである。

- 同じ型が35回続き、利用枠の回復でも変わらなかった。利用枠の枯渇だけでは説明できない。
- 利用枠が97%まで減っているので、モデル自体は動いて利用枠を消費し、その後の取込み検査で拒否された可能性が高い。
- 4日後の保持評価の最初の停止（2026-10-20）は、同じ CLI の構成で、SDK と名前空間が正常終了した後に
  原監査で拒否された。独立した原因調査で、CLI が配信元から受け取るモデル一覧（catalog）の変化による
  補足コンテキストの不一致と、未対応の通知 `turn/moderationMetadata` が見つかっている
  （提案31 §5 2026-10-20〜2026-10-21、コミット `8b3c718e`、`c062f9b3`）。
  公開評価の58枠目以降も、同じ外部の変化で始まった可能性がある。

確認できていないこと:

- 35枠の `ValueError` の文言と、拒否した検査の名前（非公開の原記録にあり、公開 archive には含まれない）
- 58枠目の直前に catalog または通知が変わった時刻

## 原記録を持つ環境での確認方法

取込み処理は拒否の型だけを残し、文言を保存していない。`production_failure_diagnosis.py` は、取込み後の検査を、
調査を実行したときのsource（`b00589ba`）のコードで原記録に対してやり直し、拒否した検査の固定の文言と発生箇所を
枠ごとにまとめる。このファイルはそのsourceにないので、空のディレクトリへ複写してから、作業ツリーを切り替えて実行する。
`--bundle` には、公開調査で `production_matrix_survey_run.py` に渡した bundle のディレクトリを指定する。

```text
mkdir -p ~/diagnosis && cp evals/skills/routing/production_failure_diagnosis.py ~/diagnosis/
git switch --detach b00589ba
uv run --project plugins/bitz-core --with jsonschema==4.23.0 python \
  ~/diagnosis/production_failure_diagnosis.py --bundle .venv/<公開調査のbundle> --ordinals 58-92
git switch -
```

- 作業ツリーが調査のsourceCommitにあり、検査のコードに変更がないことを確かめてから実行する。いまのコードは
  `turn/moderationMetadata` を受け入れるので、いまのコードで検査すると当時の拒否が見えなくなる。
- 失敗の後に取込み処理が書いた停止の印（`capture-stop.json`）は、検査の間だけ原記録のディレクトリの一覧から除く。
  除かないと、全枠が同じ `primary stop marker` で拒否され、本来の拒否に届かない。
- 主な書込みの経路（ファイルの作成・変更・削除、git の書込み系の副コマンドと出力先の指定、git 以外の子プロセス）は
  プロセス内で遮断し、原記録の変化は前後の属性と hash の照合で検出する。
- 出力は、例外の型、評価基盤のコードに文字列リテラルとして書かれた拒否の文言、評価基盤のコード内の発生箇所だけである。
  値を埋め込んだ文言、ケース本文、応答、原記録の内容は出さない。
- 結果の `groups` が1種類にまとまり、その文言が 2026-10-20 の保持評価の停止と同じ検査なら、原因は同じと判断できる。

## 判断と今後の扱い

- 35枠は**スキルの発火を測っていない**。Skill Gate 1 の判断材料に使わない。分母から除くのではなく、
  「評価基盤による取得失敗」として区別して残す。
- 原記録を持つ環境で、58枠目の `ValueError` の検査名を確かめる。10/20 の停止と同じ原因なら、
  固定 catalog 接続（`c062f9b3` 以降）の source で、SE-029 の2回目〜SE-046 を**別の campaign として測り直す**。
  元の35枠の記録は書き換えない。
- 同じ型の失敗が連続したら、次の枠を起動する前に止める（ADR-068 D4、`production_failure_streak.py`）。
- 保持評価の残り21枠は、上の確認が済むまで始めない。同じ原因が残っていれば、同じ結果になる可能性が高い。

## 2026-11-04: 原記録による原因の再検査

診断の確定ソースは`c7e5ec6d`、診断版は`evaluation-failure-diagnosis-0.2.1`。
当時の検査コード`b00589bac9bd9dc1f96a9e8b9f71654cad4af5e3`と、元の場所に保存された58〜92枠の原記録を照合した。
元のworktreeには別作業の変更があるため、別の診断用worktreeの当時のソースを、診断プロセスにだけ元のパスへ読み取り専用で提示した。
実行データのディレクトリはファイル記述子で固定した。`bwrap`でルートを読取り専用にし、ネットワークを分離した。

既存の診断は木全体のハッシュ値を計算する際に認証情報も読むため、そのままでは実行しなかった。
版0.2.1は`auth.json`、資格情報ファイル、`.env`類の内容を読まず属性だけを確認し、検査コードからの読取りも拒否する。
合成ファイルの回帰試験でこの条件を確認した。元の認証情報、台帳、原記録、他worktreeの変更は書き換えていない。

### 確認結果

| 対象 | 当時のコードでの拒否 | 確認した原因 | 現行コードでの限定した確認 |
|---|---|---|---|
| 58〜82、84〜92の34枠 | `production_trace.completed_items`の`native action not allowed` | 全枠に`turn/moderationMetadata`通知があり、当時のコードにはこの通知の受理規則がない | 元のRPC値を変更せず、現行の投影・SDK通知検査は34枠すべて通過 |
| 83枠目 | `production_canary_evidence.artifact_names`の`primary stop marker` | `host-stop.json`あり。ホストの2回目の`read_resource`呼出しが、必須の`path`ではなく`uri`を渡し、`accepted: false`・`ValueError`で拒否された | 原RPCは正常な完了を持たず、現行の検査も`raw native turn lifecycle`で拒否。停止を保持 |

34枠について、当時のスタックは原記録の読取り→provider検査→完全性検査→native検査→SDK通知の正規化→`completed_items`→`require`だった。
全35枠で、診断前後の原記録の属性・認証情報以外の内容のハッシュ値は一致した。
モデル起動0、予約0、ネットワーク通信なし。RPC本文、metadata本文、認証情報の内容は報告へ出していない。

補助通知への対応は、既存コミット`8b3c718eb85a286056b53186f004e444cbc4dfe5`に実装済みである。
同一thread・進行中turn・正確なフィールド集合を要求し、metadataを操作許可や得点へ使わない。
この既存修正を再実装する必要はない。83枠目のホストの引数検査も緩めない。
同じ引数不適合を資源本文の読取り前に拒否する回帰入力を、既存のホスト試験へ追加した。

診断環境の準備では、`/dev/null`の権限、データのマウント先、uvの一時的なPython実行パスで停止した。
通常の`/dev`・`/proc`、ディレクトリFDによる読取り専用マウント、既存の固定依存を持つPythonで解決した。
いずれも診断の起動前の問題で、モデルや予約を消費していない。

### 再開条件

1. この再検査と34枠・1枠の区分を独立した文脈で検分し、今回の原因調査を確認する。
2. 通知対応`8b3c718e`、catalog固定接続`c062f9b3`、ADR-068の停止・後継台帳の処理を含む現行の確定refを候補にする。
3. 原公開92枠の正解52・不正解3・評価失敗37と、保持評価の旧停止・消費を維持する。今回通過したのはSDK通知の検査だけで、34枠の独立採点・親照合・有効測定への昇格は行わない。
4. 新しい公開評価の少数枠で、資源一覧→正しい`path`による資源読取り→一次取得→独立採点→親確認を完走する。83枠目の失敗を踏まえ、呼出し引数と停止の有無も確認する。
5. 起動前にref、ケース、分母、有限予算、出力先、停止条件と必要な検分を固定する。同型失敗2枠で追加予約を止める。少数枠が完走した後に、未測定の範囲へ進む。

保持評価の後継台帳への移行と追加評価は、上記の検分と現行候補の起動前確認を済ませてから行う。

### 検証と独立検分

- `c7e5ec6d`で診断の関連11試験が`OK`。
- 対象`9dd983127ccb01117efade6b96db5e1980528f7b`で、`PYTHONPATH=plugins/bitz-core/src`とリポジトリ内の一時領域を使い、`uv run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -m unittest discover -s tests/skills -p 'test_*.py'`を実行。`Ran 1176 tests in 188.348s`、`OK`、終了コード0。
- 評価契約の監査は`Passed`、`errors: []`、終了コード0。変更した文書の相対リンクと見出し、`git diff --check`を確認した。
- 利用者の明示指示により、実装の履歴を継承しない別文脈の`/root/r04_independent_review`が検分した。[独立検分記録](independent-review-20261104.json)に、直接確認した内容と未追試の範囲を記録した。
- 検分者は関連113試験と、原RPC・ホスト記録からの独立した集計を実行し、34件と1件の区分を再現した。阻害指摘なし。親も原記録の再検査と全スキル試験を自分で実行している。
- 当時のソース全体のマウント、過去の実行前後の全原記録一致、当時のネットワーク分離自体は独立再現していない。限定した原因の検分を超える認定には使わない。

### 次の評価候補と継続の制約

公開の少数枠に向け、既存の`prepare.py`で確定ref`9dd98312`の製品6スキル・73資源を
`.venv/matrix-routing-preparation-recovery-20261104-01/snapshot`へ固定した。
manifestのSHA-256は`f34a7bd1dc61e53a95487ad0df04541e4775b50e4f707b38c32960437eed54cd`。
これは資源の準備であり、当日の校正、実行契約・配置・開始前検分の束縛はまだ行っていない。

保持評価の前の台帳は、既存の`predecessor --kind continuation-0.2.0`で読取り専用に確認した。
14eventから正解2、中断1、一次予約済み3、次の新規枠4、再試行候補1を再計算した。
未完了の実行は0で、旧中断1を保持する。後継の印は未作成（`sealed: false`）、追加予約とモデル起動は0。

保持評価の現行契約は、製品資源を旧source`b00589ba`の72資源・同一バイト列へ固定している。
候補`9dd98312`は73資源（`activews.py`の追加、既存16資源の内容変更）であり、旧保持台帳の条件へ単純に継ぎ足せない。
この確認はGitの確定ref同士で行った。保持の旧結果を現行製品の結果へ読み替えず、当面は公開の少数枠の起動前準備を先に進める。
保持側の候補・条件を更新する場合は、先行台帳の消費と旧停止を保全したうえで、評価条件の変更として別に扱う。検査を緩めて通過させない。


## 2026-11-04: 当日校正・起動前検分と公開少数枠の停止

### 固定した条件と検証

mainを`6506f66a`へ更新し、当日の局所校正を束縛した候補
`9a85b9098af7b19316d518978f82eaac790fcfc0`を確定した。6スキル・73資源のsnapshotは
`.venv/matrix-routing-preparation-public-recovery-20261104-01/snapshot`、manifestのSHA-256は
`f77ac641408efedd9c0b75e2c67dc50f0dddd2d3207e59a909965453fdacd6c8`である。
旧候補の測定をこの候補の成績へ合算しない。

- 校正原は`.venv/matrix-local-isolation-calibration-recovery-20261104-02`。
  `local_calibration_verified`、namespace終了0、外部モデル・課金・予約0。校正のmanifestは
  `99fdd1dac2991919780fd73b3b0dfd1c5082eb8032234f6f91d6ffb4364ea72e`、受領記録は
  `0999833e26eb0ab77df962b3499311704f6b34b0ff3892692c1a7b997d77eeb9`。
  通常の局所隔離検査も`local_isolation_verified`（local HTTP 1、raw通知5、外部モデル・予約0）。
- 最初の局所校正`...-01`はsandboxでの`NETLINK_ROUTE`拒否で停止した。停止原を保持し、実評価に数えない。
  過去の校正原12ファイルはworktree整理時の退避先から、歴史manifestの全hash一致を確認して元の固定パスへ復元した。
  退避原を変更せず、認証情報は読んでいない。
- 確定候補で全スキル試験を実行し、`Ran 1176 tests in 184.022s`、`OK`、終了0。
  コマンドは`PYTHONPATH=plugins/bitz-core/src UV_CACHE_DIR=$PWD/.venv/uv-cache PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/.venv uv run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -m unittest discover -s tests/skills -p 'test_*.py'`。
  `uv run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python evals/skills/validate.py audit`は`Passed`、`errors: []`。
- 別文脈の検分者は関連392試験（matrix 191、trace 164、関連37）を終了0で実行した。
  独立worktreeは検分前後ともclean。snapshot、SDK、runtime、9世代の校正chain、復元12ファイル、通常局所原と
  最終pinを再検証し、阻害指摘なし。[コード検分](public-prelaunch-code-review-20261104.json)と
  [具体条件の検分](public-operational-review-20261104.json)に範囲・制限を残した。

公開の`SE-001`（「bitz doctorをJSON形式で実行し、結果を説明して」）を2反復する条件を固定した。
SOLの一次最大2・独立最大2、再試行0・委譲0、起動間隔60秒、任意の評価失敗でこのバッチを停止する。
既存92枠の実行契約を縮小したとは扱わず、親が単枠ごとに検査して、この2枠以外を起動しない運用条件である。
外部送信・実評価は自動承認レビューで一度拒否された後、この入力と範囲への利用者の明示承認を得た。

束は`.venv/matrix-public-recovery-bound-20261104-01`、条件のSHA-256は
`b702b946cdfc6b25f370950e581e0b10a31186f4dd30f3be54f3e00a38bc92d7`。
実行契約のSHA-256は`4340249b1d7093389537b55fdb9ff908500a0c77ded952b95b931ffc66c92faa`、
開始前検分のSHA-256は`126eb92af63cb2e4610eed32dcd66bebbb6c4db90b1ac4b69539a3fc8b58dd3f`である。

### 実評価と停止

`production_matrix_survey_run.run(root, bundle, 1)`で1枠目だけを実行した。
一次は1回、独立採点は0回、測定完了は0件。`evaluation_failed`、段階`primary`で閉じ、2枠目は未予約・未起動。
同条件を再試行せず、停止原・一次予約の消費を維持する。
停止後の独立診断を終えた後、このバッチの台帳へ`stop.json`をEXCL追記し、同じ入口からの追加予約も拒否する。
既存`summary()`の再集計は`status: stopped`、`primaryReserved: 1`、`independentReserved: 0`、
`evaluationFailed: 1`、`pendingSlots: 0`である。

CLIは19.210537秒で終了0、timeoutなし、SDK errorなし、資源の前後照合一致。
`list_resources`と`read_resource`はいずれも受理され、host停止はない。
ただし原rolloutと校正の照合は`production_canary_rollout.initial_context`の
`fixed caller and SDK supplement`で拒否された。既存の`production_failure_diagnosis.py --bundle ... --ordinals 1`で
読取り専用に再現し、`originalsUnchanged: true`、追加モデル・予約0を確認した。

校正と実評価のdeveloper補助指示は、Default modeで仮定を置いて実行を優先するという1段落だけ異なる。
校正の補助ブロックのSHA-256は`50b5bc7aa05dca239d92bb79cf72e3b65e1d0da62ff988af6eb5db443913f92d`、
実評価は`cad0a82ec499c65eee6cfd73d82d5d1d56da8a4cfcc00c81e7980de2db7b35d0`。
通知不対応や`uri`引数の旧原因と混同しない。`primary.native`の限定検査は通過し`bitz-core`選択を観測したが、
完全な証拠照合と独立採点がないため、正解や有効測定へ昇格しない。

SDKのnative観測使用量は入力19,712・出力332・合計20,044 token（入力cache 10,112）。
推論APIは3回で、一次軌跡1回とは区別する。これは観測値であり、未完了の全原照合や課金額の認定ではない。
金額は未確認で、0円とは扱わない。

### 次の是正の範囲

補助指示の不一致を独立に再検査し、公開の実起動と局所校正でモデル情報の条件を固定する接続を確認する。
保持側には既存のcatalog固定があるが、公開側の`config_for`には接続されていない。
[停止後の独立検分](public-poststop-review-20261104.json)も同じ拒否と補助指示の差分、raw RPCとrolloutの一致を再現した。
固定runtimeのcatalogには追加段落がないが、実通信のmodels応答本文は取得していない。
外部のモデル情報の更新が原因という説明は推定であり、catalog固定による是正の効果はまだ実証していない。
校正のhashを実評価からコピーしたり検査を緩めたりせず、必要な是正は別の確定候補・条件で検分する。
今回の停止と消費、旧公開92枠・保持の停止は維持する。R04全体・Skill Gate・リリースは未完了である。


## 2026-11-04: 公開一次と局所校正のモデル情報を固定する是正

修正は`e23ec42d`、旧版読取り入口の是正と新校正の束縛まで含む検証対象は
`02328a5619419d0ebbf5ea01bcfc33c0ba33a4ae`である。公開一次・当日校正・通常局所プローブに、
既存の固定CLI内蔵catalogの抽出処理を共通して接続した。catalogはSOL 1モデル、65,209 bytes、
SHA-256は`529c2b0d2e898ac64e6bfedf750818a94cc5cba7c0e3fac950c2c81211675db9`。
受け取った実評価の補助文を校正profileへコピーする変更や、補助指示の一致検査を緩める変更は行っていない。

- 新しい原には`public-model-catalog.json`を保存し、固定runtimeから導出したbytesと親子で照合する。
  `config.model_catalog_json`の固定パスも検査する。catalog helperは確定sourceの照合・namespaceのmountに含む。
- 校正manifestは新版`matrix-client-calibration-originals-0.2.0`（24原）、provider receiptは
  新版`public-matrix-original-binding-0.1.2`とした。旧校正0.1.0・旧provider 0.1.1は、当時のGitにある宣言から
  旧inventory・config・mount順序・source proofで再検証する。新版のcatalog欠落、改変、設定解除、版の偽装は拒否する。
- 独立検分で旧providerを読む入口の版条件の見落としを1件指摘され、入口を是正した。
  実際の`load_provider_capture`へ旧原を渡し、受領記録不変・catalogを追加しないことを確認する回帰試験を追加した。

新校正原は`.venv/matrix-local-isolation-calibration-catalog-20261104-01`、producerは`e23ec42d`。
`local_calibration_verified`、namespace終了0、manifestは
`e20ff69b401600fc798d4508415392e68b13e22298e39407e0797949b4a38ca1`、受領記録は
`c1ac29747b8e32f83425dae78529d8d5fd42e9a1cc9b48a0d568b59a048c51cd`。
新版manifestから全原・当時Git・profileを再検証し、`original_local_calibration_matches`を確認した。
補助指示のhashは従来の校正と同じ`50b5bc7aa05dca239d92bb79cf72e3b65e1d0da62ff988af6eb5db443913f92d`である。

`02328a56`の通常原は`.venv/matrix-local-isolation-catalog-20261104-01`。
`local_isolation_verified`、namespace終了0、local HTTP 1・raw通知5。
6スキル・73資源のsnapshotは`.venv/matrix-routing-preparation-catalog-20261104-02/snapshot`、manifestは
`b29de030340dc1572d4c48f7fbe8ad55d10e7badbcf6232eb9fc94842b83ede8`へ固定した。

親は同refで次を実行した。

- `PYTHONPATH=plugins/bitz-core/src UV_CACHE_DIR=$PWD/.venv/uv-cache PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/.venv uv run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -m unittest discover -s tests/skills -p 'test_*.py'`
  — `Ran 1183 tests in 192.827s`、`OK`、終了0。
- `uv run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python evals/skills/validate.py audit`
  — `Passed`、`errors: []`、終了0。
- 旧停止9a85b909の原を新版readerから読取り専用で再検査し、従来どおり
  `fixed caller and SDK supplement`で拒否すること、`originalsUnchanged: true`・`ledgerUnchanged: true`を確認した。

[独立検分記録](public-catalog-independent-review-20261104.json)には、初回209試験、是正後の関連33試験、
新校正24原・通常23原の再照合、旧校正chainと旧停止原の再検査、阻害1件の是正と残存阻害なしを記録した。
同じ試験の追試を別々の測定件数として加算しない。

今回の作業の外部モデル呼出し・課金・予約は0。旧バッチは`stopped`、一次予約1・独立0を維持し、追記していない。
公開側の実providerでこの是正の効果を確認する新測定はまだ行っていない。
次はこの新候補に対する少数枠の実行条件と開始前検分を固定する。R04全体やSkill Gateの完了とは判定しない。
