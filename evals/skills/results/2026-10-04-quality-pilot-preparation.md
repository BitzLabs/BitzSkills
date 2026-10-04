# 品質先行比較の準備と追加実測の判断材料

固定対象: `2faa9fb687e381d3ba883dff7b87a46c91884f45`。
評価集合: quality-pilot-0.1.0、bitz-quality 0.1.1、対象モデル案はgpt-6.1-solのみ。
protocol SHA-256: `972e93a0519b7386cce7331dcaed8f1d78091c1871628019d4de3e5fea19ee48`。

## 提案する実測範囲

| ケース | 実施する工程 | 主な検分対象 |
|---|---|---|
| QP-001 | 品質計画 | 件数だけのassertを型・内容の実証にせず、変更リスクと必要証拠を計画する |
| QR-001 | 独立品質レビュー | 既存試験が通る認可欠陥を直接検分し、既知重大事項と証拠不足を別に扱う |

2ケース×スキル有無×2反復で最大8軌跡。直列、新規文脈、再試行なし。
期待値はモデルworkspaceへ渡さず、一次資料・公開形式・安全条件を両variantで共有する。
スキル本文とreferencesだけをskill側へ渡し、baselineへの形式・許可の不利を作らない。
機械、安全、意味、起動/利用上限、証拠破損、比較条件混在のいずれでも新規起動を止める。
SDD比較のbaseline意味不適合続行例外と残11件の予算は使わない。

実行器・隔離workspaceの実作成・操作ログ・共有資源配布・停止制御は、実測前に別途検査する必要がある。
既存発火用run_model.pyを実操作測定の代わりに起動しない。必要な実操作経路を用意できなければ未実行で停止する。
本提案は上記最大8軌跡の追加費用・新しい品質評価範囲を承認するための材料であり、認定や自動実行の許可を意味しない。
費用の金額は未確定。使用量を記録し、不明な費用を0円と扱わない。
新規品質実測は0件。準備の独立検分実行はモデル比較軌跡とは別集計である。

## 作業者の実検証

cleanな対象refで次を実行した:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/hide/BitzLabs/BitzSkills/.venv/quality-plan-worktree/plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i python3 -B evals/skills/quality/preflight.py
exit 0
status: passed
scope: synthetic-input-preflight
certifiesQuality: false
newModelTrajectories: 0
```

QP-001/QR-001とも公開context/checkはpassed・exit 0。
ローカル試験はそれぞれ`Ran 1 test in 0.000s / OK / exit 0`、`unchanged=true`。
QR-001の別事前検査は他所有者に`{"status":200,"body":"synthetic document"}`を返し、認可欠陥を保持することを確認した。
元Core stdout4件のSHA-256は保存されたcoreResultsと一致した。
生stdout、解析済み元結果、テスト出力、基準/対象ref、入力ファイルhash、差分は[事前検査JSON](2026-10-04-quality-preflight.json)へ保存した。
一時workspaceは検査後に除去されるため、保存JSONの一次出力を参照する。実測のモデルへこのJSONは渡さない。

共通評価契約の監査:

```text
python3 -B evals/skills/validate.py audit
status: Passed
evaluationSetVersion: 0.7.1
cases: 46
schemas: 7
errors: []
exit 0
```

これは共通契約の監査であり、新しい先行2ケースのモデル成績ではない。

## 独立検分

`/root/sol_quality_prototype_review`が固定refの一次資料とpreflightを自分で検分・再実行した。
始点と終点は同じref、両時点の`git status --porcelain`は空。
preflightはexit 0・passed・新規モデル0件。両ケースのCoreと試験・非変更は作業者の結果と一致した。
生stdout4件のhash、解析JSON、対象ref、dirty=falseの追加照合は`Independent preflight artifact checks: OK`。
コピー対象はfixtureだけで、protocol期待値・認可反例・review-base.pyはモデルworkspaceにコピーされないことを確認した。
準備範囲で必須是正事項は見つからなかった。将来の実行器の隔離・公平性・ログ・停止は未検証。

## 未認定の範囲

先行8件が通っても試作分母、発火/負例/競合/敵対、安全全件、Q0〜Q3、保持ケース、実地・別モデル比較は満たさない。
Phase 3、Skill Gate、配布完了を宣言しない。
品質スキルの局所是正は[試作検証記録](2026-10-04-quality-prototype.md)を参照する。
