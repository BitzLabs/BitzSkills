# SDD評価0.1.2の是正と独立再検分

2026-10-04。先行実評価0.1.1の2件停止を根拠に評価器とケース条件を是正した。
公開Core・スキル本文・規範・承認済み要求は変更していない。モデル再評価は未実施で、Phase 2完了・Skill Gate通過を主張しない。
元評価は[停止報告](2026-10-04-sdd-pilot/report.md)のFailed/not-certified、66件欠測のまま保持する。

## 是正

- `setup`時の合成workspaceの初期commitを`control.baseCommit`に固定する。公開contextが返した同じcommitはcheckの`--base`値位置だけで許可する。
  任意のhex、短縮commit、別の引数位置へ渡したcommit、重複baseを拒否する。HEAD移動後は明示HEADとbase省略も拒否し、初期commitを明示した比較だけを続ける。
- SP-001の狭い実装TASKと同時作成draft REQの条件を明確化した。REQ check通過と、最後の保存後のTASK check failed/SPEC-TASK-BOUNDARY-001、実差分の保持、実装・verifyへの停止を要求する。
  最終TASKのchangesは指定の`src/input.py`と`tests/test_input.py`に完全一致する必要がある。部分拡張も拒否する。
- 最終境界の解析は採点者が公開contextを読取り再実行する。yaml表記・順序の違いを許し、workspace、hostログ、モデルdecisionを変えない。
  採点者の操作をモデルのCore呼出しやcoreResultsへ加えない。資格情報を継承せず、timeout等の検査障害はケース失敗として残す。
- 評価集合は`sdd-0.1.2`。測定時は別の確定refと`.venv/sdd-evaluation-02`を使う。元runを新条件へ再利用・再分類しない。

SP-001の成功計画との区別は公開境界仕様と実再現に基づく。計画保存の成功は既存REQからTASKだけを作るSP-004で測る。
検査通過のためのTASK境界拡張、REQ削除、無許可commit、比較元変更は採用しない。

## 実検証と独立検分

最初の固定commit許可の回帰試験は元評価器で`Ran 1 test / FAILED (failures=1) / exit 1`を確認した。
初回是正ref `b4a0b18863450b9bacc035b84447112ce2c535bc`では24試験が通ったが、独立否定例でbase省略と部分境界拡張の漏れを確認した。
主作業者も同refに対して追加した2回帰試験で`Ran 2 tests / FAILED (failures=2) / exit 1`を再現した。

最終是正source refは`6a5b8b6168d20c759c39a7a0efffeaacfa522b6c`。開始時cleanで主作業者が実行した:

```text
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/home/hide/.codex/worktrees/b1e9/BitzSkills/.venv/sdd-plan-worktree/plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i \
python3 tests/skills/test_sdd_skill_eval.py
Ran 27 tests in 16.393s
OK
exit 0

python3 evals/skills/sdd/evaluate.py audit
{"status":"Passed","cases":17,"plannedCalls":68,"errors":[]}
exit 0

git diff --quiet 26f0a5feb6897287cc226739d097b69f45dca2ca HEAD -- plugins/bitz-core plugins/bitz-sdd fixtures
exit 0
```

独立検分者`/root/sol_sdd_pilot_review`は初回のfresh contextを継続し、主作業者の非公開実装履歴を継承していない。
最終refの開始・終了ともclean、27試験/16.359s/OK/exit 0とaudit Passedを自分で再実行した。
独自否定例でbase省略、明示HEAD、`HEAD^{commit}`、短縮commit、`--base=<commit>`を拒否し、保存した初期commitだけで公開checkが通ることを確認した。
部分境界拡張は期待の診断が残っていてもworkflow falseになることを確認した。
境界解析の前後でworkspace snapshot、hostログ、モデルdecisionが不変だった。検分範囲で追加の是正必須事項はないと判定した。
相対path順の`path + NUL + content + NUL`で測った評価5ファイルと試験1ファイルのSHA-256は、主作業者と一致した:
`f0859041f32314181a0bff3291ee277f8c22c04d7947ea432ea8c8a3d4ad1e6c`。

主作業者は元archiveのartifact hashも再照合し、元refのCore・SDD・評価sourceから再計算したhashが両runに一致することを確認した。
`score.json`は全68行、missing runは66行。新条件のモデル評価は未実行である。

## 次の確認点

モデル測定の再開は、新条件の先行4回と、通過後の全件68回を含む別測定として明示承認を得る。
この68回は今回実行した2回に追加される。自動再試行0、同時最大2、1回240秒、必須検査失敗時は新規投入を停止する。
今回の是正試験と独立再検分はモデル測定ではない。
発火Gate、保持ケース、複数モデル、実地パイロット、品質スキル接続、収束、配布・リリースは引き続き未認定である。
