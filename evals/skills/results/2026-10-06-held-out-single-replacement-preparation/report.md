# 1件差替・11件再利用の準備結果

collection0.5の監査・schema・有限契約をsource `879101449c93df2545bb6c5dcab07664b6d5cdd2` に固定した。
旧0.4の独立報告で不適格となった1件と、再利用候補11件の全フィールドを来歴hashへ束縛した。
新規1件には公開46件と旧0.1/0.3/0.4各12件の除外比較を要求し、
条件を戻した際の期待経路・outcome・eventsの観測可能な変化と本文根拠を機械監査する。
反実仮想は作者の判断予測であり、一次モデルの実測値ではない。

独立SOLによる収集準備検分はP1=0/P2=0だった。親も14試験とsource guardを再実行し、
source15・入力7・公開46件・候補6スキル71資源・旧3集合・来歴を再照合した。
これは準備の合格である。collection0.5のcases/evidenceは未作成で、集合の意味合格は未認定。
旧0.4のP2=1と消費済み枠、旧停止記録を保持する。

## 実行器と実検証

協調ツールで作成者の新規起動と既存作成者の再開がスレッド上限で拒否された。
両方ともモデル未起動だったため、collection0.5の作成・集合検分枠は未消費である。
代替の独立CLI実行器7ファイルをsource `e49304314469a260362f0b10f29c25ea7497f351` に固定した。
役割を起動前の共通台帳で1回だけ予約し、bubblewrapでhostと既存成果物を読取専用にする。
原stdout/stderrはfile-backedで保持し、中断・非zero・保存失敗・終了イベント不足を成功扱いしない。
source7とcollection source15を開始・終了で照合する。HEADの移動自体は条件にしない。

固定Python3.12.3/jsonschema4.23.0/ruamel.yaml0.19.1で得た実出力は以下のとおり。
`python` は準備と同じ固定環境を表す。各log/hashはsummary.jsonに記録した。

```text
独立: python -m unittest discover -s tests/skills -p test_single_replacement.py
Ran 14 tests in 2.735s / OK / exit 0

親の再実行: python -m unittest discover -s tests/skills -p test_single_replacement.py
Ran 14 tests in 2.768s / OK / exit 0

親: python -m unittest discover -s tests/skills -p test_native_actor.py
Ran 16 tests in 0.646s / OK / exit 0

親: python -m unittest discover -s tests/skills -p 'test_*.py'
Ran 276 tests in 60.194s / OK / exit 0

親: native_actor.verify(e49304314469a260362f0b10f29c25ea7497f351)
source7/collection15/inputs/candidate/retention matched; primary=0 / exit 0
```

ログ・独立準備JSON・guard原出力はrepo内の`.venv/held-out-single-replacement-05/`に保持する。
非公開collection0.5は0700で来歴1ファイルだけを保持し、case/evidence/CLI実行領域は存在しない。
CLI実行の共通台帳も未作成である。今回の準備SOL1消費、CLI準備/作成/集合検分/一次/retryは0。

## 確認待ち

独立CLI準備の実行要求は、非公開リポジトリ内容をSOL提供先へ送信し得ることへの
具体的な承認が不足しているとして自動承認レビューに拒否された。
プロセス・モデルは起動していない。拒否を迂回しない。
送信対象と上限を[transmission-approval-request.md](transmission-approval-request.md)へ具体化した。
ユーザー確認後に固定sourceのCLI準備1回を実行し、P1/P2なしと親の再監査を条件に
新規1件の作成1回、全12件の独立検分1回を順に進める。
本結果で製品発火・行動・Skill Gate・完成は認定しない。
