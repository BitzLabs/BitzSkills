# 品質スキル試作の局所検証

対象はbitz-qualityの日本語quality-plan / quality-review、advisory文書形式、申告整合性チェッカーである。
Phase 3、Skill Gate、配布、モデル行動は未認定。新規品質モデル実測は0件。

## 確定した対象と独立検分

- 初版: `33659be1ca89bd2d777c842c6a2423c5e48ec21f`、bitz-quality 0.1.0。
- 是正: `1baae6e36ed09c471ec5bec7ef65c050ea52c331`、bitz-quality 0.1.1。
- 作業者: `/root`。独立検分: 新規文脈の`/root/sol_quality_prototype_review`、gpt-6.1-sol。
- 作業者の非公開会話は継承せず、一次資料、対象ref、検査手順を渡した。再検分では前回指摘も渡した。
- 初回・再検分とも開始/終了refが一致し、`git status --porcelain`は空だった。

初回は現在のCore failedを追加してもreadyが通る矛盾と、計画側でCore元結果・警告・未実行を格納できない形式を指摘された。
0.1.1で共通観測形式を設け、元JSONとstderr・argv・cwd・対象ref・取得先/hashを保持する。
今回の判定に使うcurrent_gateと、理由付きhistorical / expected_negativeを区別する。
現在のfailedはnot_ready、blocked/error/終了4・必須Core取得不足・dirty・不完全解決はunknownとなる。
既知重大事項を優先し、過去・期待負例を現在の通過証拠へ代用しない。
未再実行と証拠ID・取得可否を結び付け、未取得と取得済みの矛盾を拒否する。

独立再検分は前回の必須2点と未再実行・証拠対応の是正を確認し、対象範囲で新しい必須是正事項なしと報告した。
独自の過去成功のみ、期待負例のみ、check欠落、dirty、完全解決情報欠落の入力でもreadyを拒否した。

## 実出力

作業者が実行したコマンド:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/hide/BitzLabs/BitzSkills/.venv/quality-plan-worktree/plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i python3 -B tests/skills/test_quality_contracts.py
Ran 29 tests in 0.382s
OK
exit 0

python3 -B /home/hide/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/bitz-quality/skills/quality-plan
Skill is valid!
exit 0

python3 -B /home/hide/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/bitz-quality/skills/quality-review
Skill is valid!
exit 0

git diff --check
（出力なし）
exit 0
```

独立検分の再実行は`Ran 29 tests in 0.386s / OK / exit 0`、両quick_validateも各`Skill is valid! / exit 0`。
追加合成検査は`Independent synthetic probes: OK / exit 0`。
実Core接続試験は合成workspaceの公開CLI context/checkを読み取り実行し、passedだけでは必須実テスト証拠を補えないことを確認した。
登録された製品verify・外部モデル比較・依存導入・実課題評価は実行していない。

## 限界と次工程

形式チェッカーは元JSONのCore適合性、参照先の実在、hashの実内容、用途分類や独立性の真実性を証明しない。
対象・所有workspace・要求・実assert・リスク根拠を一次資料で別に検分する必要がある。
Q0〜Q3全帯、発火、敵対、安全、保持ケース、別モデル、導入/版不整合、SDD連携の総合測定は未完了。
本記録は局所是正の確認であり、Phase 3完了や出荷可能の宣言ではない。

SDD比較は機械不適合で停止したまま。SDD実測累計59件/承認上限70件で、残り11件は品質測定へ流用しない。
次は固定した小規模ケースの隔離事前検査と、品質向け追加モデル実測の範囲・費用承認を分けて準備する。
