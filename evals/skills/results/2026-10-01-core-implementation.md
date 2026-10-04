# Phase 0の完了確認と日本語Coreスキルの本実装

対象は確定ref `e7d1e5d5d3e7f3d539d089fd555dce54a180fd89`。
以下の最終再実行はこのrefのcleanな作業ツリーで行った。
評価器の是正は`296612f`、Coreスキルの追加は`e7d1e5d`に分けた。

## Phase 0の既存完了条件

| 条件 | 確認結果 |
|---|---|
| 正本との矛盾の分離、意味変更の決定記録化 | 計画の非規範境界とADR-060の採用判断を確認 |
| 全スキルの使う／使わない／停止 | 監査で全6能力の3区分を確認 |
| 空の試作スキルで失敗する | 空・空白・先頭情報のみ・説明中の区切り・終端欠落の負対照を追加し、本文読取り検査で拒否 |
| 3入口／6スキルの採否理由 | 公開比較とADR-060に発火、安全、読取り量、token数、時間、費用不明を記録 |
| 危険コマンド停止、独立性の機械点検 | 実行契約・安全ケースを確認。Schemaに加え`review`コマンドで同一実行IDを拒否 |

独立した`/root/phase0_review`は初回に空本文の負対照と同一ID拒否の欠落を指摘した。
是正後に、説明内の`---`が空本文拒否をすり抜ける問題も指摘したため、行単位の区切りへ修正した。
最終再検分は同じ直接プローブが`False`となること、監査と27試験の通過を直接確認し、
既存5条件を満たすと判定した。[独立検分記録](2026-10-01-phase0-independent-review.json)を参照する。

この負対照は決定論的な本文読取り検査の失敗を確認する。空スキルを使ったモデルの意味判断、
スキルなしとの効果比較、リリース合格を実証する測定ではない。
費用の実測、保持ケース、公開試作の未達、実動作の評価は後続へ引き継ぐ。
公開試作の全件合格を、新しいPhase 0の完了条件へ追加していない。

## Phase 1で追加したもの

- 配布用の日本語`plugins/bitz-core/skills/bitz-core/SKILL.md`（77行、本文版0.1.0）
- 操作、結果、安全の3参照、README、プラグインの説明
- 掲載した8操作例を公開CLIで実行する試験

Coreの公開面だけに依存し、実装用コンテキスト取得、検査、検証、診断の選択、対象範囲、
成功・警告・失敗・遮断・エラー、単一／複合ワークスペース、結果の欠落・不整合、
危険な検証の停止、利用者への報告を具体化した。
最小試作の`candidates/`は変更していない。試作の測定値を本実装の測定値として使わない。

独立した`/root/core_skill_review`が公開規範と照合し、発生元の3種別の説明と、
単独／全体結果の識別フィールドの排他確認を指摘した。是正後の再検分で両指摘の解消と、
Skill Gate 0の契約に重大な不足がないことを確認した。
[独立検分記録](2026-10-01-core-independent-review.json)を参照する。

## ローカル検証の実出力

`uv run evals/skills/validate.py audit`は依存取得時にDNSエラーでexit 2となった。
この試行では`UV_CACHE_DIR="$PWD/.venv/uv-cache" UV_PYTHON_DOWNLOADS=never`を指定し、
リポジトリ外へのキャッシュ書込みとPython取得を避けた。
以降はCPython 3.12.3の既存環境で同じ入口を直接実行した。評価器の依存をuvの固定版で
解決した結果ではないため、固定依存環境での再実行は残す。
Core試験は既存キャッシュにある指定版`ruamel.yaml==0.19.1`を読取り専用で利用した。
試験用`/tmp`ファイルの作成・終了時削除は利用者の明示承認を得た。

```text
PYTHONDONTWRITEBYTECODE=1 python3 evals/skills/validate.py audit
status: Passed
evaluationSetVersion: 0.7.2
schemas: 7
cases: 46
errors: []
exit: 0

TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 tests/skills/test_skill_eval.py
Ran 27 tests in 5.175s
OK
exit: 0

PYTHONPATH="$PWD/plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i" \
  TMPDIR=/tmp PYTHONDONTWRITEBYTECODE=1 python3 tests/skills/test_core_skill_commands.py
Ran 1 test in 1.152s
OK
exit: 0
```

掲載例試験は既存fixture `SINGLE-113`を一時ワークスペースへコピーし、設定とテストをGit管理下へ置く。
実行する登録コマンドは`/bin/true {tests}`のみで、検証結果の`passed`、対象と実行コマンド、
全例のJSONと終了コード、全操作前後のファイル内容の一致を確認する。
これは公開CLI例の検査であり、モデルがスキルに従うことを実証する行動試験ではない。
構造検査ではYAML、名前とフォルダの一致、説明、metadata、行数、全参照リンク、plugin JSONを確認した。
独立検分の2記録も`python3 evals/skills/validate.py review --input <記録>`で検査し、
いずれも`status: Passed`、`errors: []`、exit 0だった。`git diff --check`もexit 0だった。

## 認定範囲と次の検証

Phase 0は既存完了条件を満たす。Phase 1は`In progress`とする。
Skill Gate 0の契約は定義・独立検分済み。Skill Gate 1〜3、Phase 1全体、リリースは未認定。

Coreの公開回帰ケースは`SE-001`（明示）、`SE-006`（暗黙）、`SE-015`（文脈）、
`SE-016`・`SE-022`（負例）、`SE-028`（競合）、`SE-041`（行動）、`SE-036`（安全）を引き継ぐ。
日本語試作0.7.0で残った`SE-025`の不適用時の入口矛盾と、`SE-028`の意味イベント欠落も引き継ぐ。
SDDと品質管理に残った`SE-011`・`SE-029`は各担当Phaseへ渡す。

次は、配布本文と参照を対象として固定し、読取り・hash・判断・実操作を記録できる評価入力を用意する。
既存の試作実行器は`candidates/`本文の読取りに限定されているため、そのまま本実装の評価器とは呼ばない。
スキル別・モデル別・反復別の発火、単一／複合、各状態、危険コマンド、未信頼入力、
依頼外書込みの停止を検証し、保持ケースと独立検分を含めてSkill Gate 1〜3を判定する。
