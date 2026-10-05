# 品質評価のSOL承認照合の補強

旧ref `fb295c9bf87c2df2ebb2bfabd25eef28f48449de`では、承認者がuserでない、
目的が別プロジェクト、modelsが辞書でもSOLキーを含むという3反例が起動前照合を通った。
作業者はpreflight.gitを例外mockにして再現し、3件ともworkspaceアクセス直前へ到達した。
出力・台帳・モデル呼出しは生成しない反例であり、承認記録そのものは変更していない。

修正ref `b11de631a5dac3d53d1758cbc223b27552bb0261`では承認状態approved、承認者user、
既存の固定目的、`models == ["gpt-6.1-sol"]`をworkspace・出力・台帳・モデル起動より前に照合する。
モデル・評価版・承認パス・protocol hashと有限予算の既存照合は維持する。
3反例と追加モデル混在を対応試験へ追加した。

## 実検証

絶対Core srcとruamel.yamlのPYTHONPATH、固定jsonschema 4.23のPythonで実行した。

```text
python -B -W ignore::DeprecationWarning tests/skills/test_quality_evaluation.py
作業者: Ran 24 tests in 6.498s / OK / exit 0
独立検分: Ran 24 tests in 6.444s / OK / exit 0
```

別文脈のSOLコード検分は確定refと親差分を直接読み、旧条件をメモリ内復元した3反例について、
旧条件はmockされたpreflightへ進み、新条件はsol authorizationのValueErrorで先に停止することを再現した。
台帳・subprocessは呼ばれず、出力未作成を確認した。追加モデル実測はない。
作業者も独立記録を原保存物と同一バイトで照合し、変更した起動前停止試験を再実行した。

```text
python3 -B tests/skills/test_quality_evaluation.py \
  QualityEvaluationTests.test_model_version_and_sol_scope_mismatch_stop_before_any_output_or_ledger -v
Ran 1 test in 0.006s / OK / exit 0
```

1試験の10反例でworkspace・出力・台帳・モデル到達前の拒否を確認している。
独立記録のSHA-256は`0b9f5f91f79c43e401967fdcd3f9c501812e8b5d9e706db0a8f50bc454e6bdb4`。
検分者は補助報告の生成時に`python`が未導入でexit 127となり、apply_patchで記録した。
本試験の実行は指定した絶対Pythonで1回、評価retryはない。

## 限界と次工程

型と目的の照合は、承認記録の改ざん耐性や人間承認の外部真正性を証明しない。
この是正は起動前の拒否の実証であり、品質レビューの追加モデルケースやQ0〜Q3全帯の認定ではない。
既存の停止済み評価、4件の限定比較、予算消費を維持している。
独立検分usageと費用は欠測で、0 token・0円としない。
次は別条件で固定したunknown・供給網・攻撃ケースの準備と独立検分を行い、
その後に新しい有限予算を固定して測定する。
