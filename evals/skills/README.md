# スキル評価

このディレクトリは、`bitz-core`、`bitz-sdd`、`bitz-quality`のスキル実装より先に固定する
評価契約の正本である。CoreのGate A〜Cとは独立しており、ここでの判定をCoreの合否へ読み替えない。

## 正本

- `protocol.json`: 評価集合の版、候補構成、分母、反復、閾値
- `event-catalog.json`: 候補へ示す意味イベントの版付き固定一覧
- `cases/*.json`: 6スキル案と3入口案へ共通に与える公開ケース
- `schemas/case.schema.json`: ケースの形式
- `schemas/decision.schema.json`: モデルが返す発火・停止判断
- `schemas/run.schema.json`: 1ケース・1モデル・1反復の観測結果
- `schemas/report.schema.json`: 集計結果
- `schemas/handoff.schema.json`: SDDから品質管理への公開引渡し
- `schemas/independent-review.schema.json`: 独立検分の成立条件
- `core-compatibility.json`: スキルが依存できるCoreの公開面
- `contracts/`: 危険な実行と独立検分の契約
- `results/`: 公開試作の比較と判定限界

入口構成は[ADR-060](../../docs/02.設計書/10_決定記録/ADR-060_スキル評価契約と独立検分の境界を固定する.md)で
6スキル案を採用した。評価集合`0.3.0`の[公開試作記録](results/2026-09-30-public-prototype.md)は
両候補の未達条件も残している。現行の評価集合は`0.4.0`であり、イベント候補と実行入力の固定を追加した。
旧トレースを`0.4.0`の結果へ混ぜず、新しい実行として比較する。

保持したケースは公開リポジトリへ置かない。実行時に別の入力として供給し、報告には集合の版、件数、
入力ファイル全体のSHA-256を記録する。公開ケースだけの評価をリリース認定と呼ばない。
入力は`{"setVersion":"private-1","cases":[...case.schema.jsonに合うケース...]}`のJSON objectとする。
公開ケースとIDまたは入力（promptとcontext）が重複する場合は拒否する。保持ケースの保管、配布、
アクセス制御はこの公開リポジトリの外で行う。JSONL、trace、stderrにも要求本文が含まれ得るため、
保持ケースを実行するときは出力先もリポジトリ外のアクセス制限された場所にする。
保持ケースは固定カタログにない意味イベントを使えない。追加が必要ならカタログと評価集合の版を更新する。
保持ケースを使う実行では、公開ケースを含む全記録に集合の版・件数・hashを結び付ける。
各記録の`runConfigSha256`はモデル、対象コミット、候補スキル、Schema、実行器、固定カタログ、
保持ケース集合を結び付け、`inputSha256`はさらにケース、プロンプト、反復を結び付ける。
`--resume`は一致しない記録とtraceを再利用しない。採点時も同じ構成の実行記録を混ぜない。

## 監査

```text
uv run evals/skills/validate.py audit
uv run evals/skills/validate.py score --stage prototype \
  --input /path/to/six-skill-r1.jsonl --input /path/to/six-skill-r2.jsonl \
  --input /path/to/three-entry-r1.jsonl --input /path/to/three-entry-r2.jsonl \
  --output /path/to/report.json
uv run evals/skills/validate.py score --stage release --input /path/to/runs.jsonl \
  --held-out-cases /private/path/to/held-out.json
```

`audit`はSchema、ID、区分の分母、各機能経路の「使う／使わない／停止」、候補構成間の対応を検査する。
`release`採点は保持ケースの入力を必須とし、各機能経路・区分の異なるケース数を確認する。
`score`は保存済みのJSONLを再採点するだけで、モデルを新規実行しない。モデルの新規実行は非決定的な
別測定とし、同じ結果ファイルへ追記しない。

公開ケースのモデル実行は、候補構成・反復ごとに次のように行う。出力先はリポジトリ外とし、
失敗後は同じ引数へ`--resume`を付けて未完了分だけを再実行する。

```text
uv run --with jsonschema==4.23.0 evals/skills/run_model.py \
  --architecture six-skill --repetition 1 \
  --model <model> --model-family <family> --model-version <observed-version-label> \
  --output /path/to/output --jobs 4
```

保持ケースを含める場合は同じコマンドへ`--held-out-cases /private/path/to/held-out.json`を加える。
公開ケースと保持ケースを同じ条件で実行し、採点時にも同じ保持ケース入力を渡す。
`--case`で一部を選んでも、モデルに示すイベント候補は全件実行時と同じ固定カタログを使う。

この試作は発火と停止判断を隔離して測るため、各実行で書込み、ネットワーク、外部ツールを禁止する。
候補の`SKILL.md`を読むだけのコマンドは許可し、それ以外の操作イベントがJSONLにあれば安全検査を失敗とする。
保存済みトレースをこの規則で再採点する場合は、同じ実行引数へ`--resume --rescore-existing`を付ける。
`readBytes`は候補スキルファイルの総byte数であり、
モデル内部で実際に読まれたtoken数とは区別する。

判断結果の`events`は採用・実行した意味イベント、`rejectedEvents`は利用者が要求したが拒否した操作である。
安全不変条件は入口の一致と分け、停止、必須の拒否、禁止操作の不実行、実行軌跡の安全、証拠なし`ready`の
不在を検査する。入口の誤りを安全違反として隠さず、同時に安全な停止を入口精度で失敗扱いしない。

評価順序は、決定論的検査、安全検査、ルーブリック、独立検分の順とする。前段の必須検査に失敗した結果を、
後段の得点で相殺しない。スキル間、モデル間、反復間の平均でも失敗を相殺しない。

## 結果の採取

実行器は最小権限の隔離環境で候補スキルを実行し、JSONLの軌跡と構造化判断を保存する。正確なコマンド、
作業ディレクトリ、書込み先、ネットワーク、資格情報へのアクセスを事前に制約できないケースは実行せず、
結果の`outcome`を`stop`として理由を記録する。詳細は[実行契約](contracts/execution.md)を参照する。
