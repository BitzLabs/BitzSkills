# SDD評価器の原出力・中断保存（2026-10-06）

source `9c576c508219a757d496f25319b8a1d56e50c8b3`、sdd-execution-0.1.2で、
対象52件の独立検分と作業者の再検査を通過した。原failedと独立P2を保持して是正した。
**全194件はリポジトリ外の一時領域承認待ち**で、全件合格・実モデル適合・Skill Gateを認定しない。

## 問題と最終動作

原source `997299b34dfe6be537a74248a016e146baac674c`では、実モデルを固定Python子と合成例外へ
置き換えた回帰試験で、非UTF-8の通常出力喪失、native/後処理KeyboardInterruptの記録漏れ、
起動例外の文面をprovider stderrへ合成する動作を再現した。新規一次モデル評価は0。

最終sourceはstdout/stderrをbytesで取得して解釈より先に保存する。
取得できなかったstreamは可用性を明記し、空ファイルを取得済みの空出力と扱わない。
出力保存中の単発KeyboardInterrupt/OSErrorは各streamで捕捉し、もう一方の保存も試す。
未保存の原bytesをbase64へ退避し、実exit、最初の例外、各保存エラー、部分workspace差分を失敗記録へ残す。
not-measured/not-certifiedを保持し、既存出力からの無断再起動を拒否する。旧結果・予算は変更しない。

## 失敗を保持した是正経緯

| 条件 | 実出力・独立判定 |
|---|---|
| 原sourceの3回帰 | 3 tests、1 failure / 2 errors、exit 1 |
| 原sourceの後処理中断を含む4回帰 | 4 tests、1 failure / 3 errors、exit 1 |
| 初回是正時の補助試験 | 改行の期待値を誤り4 tests中1 failure。元失敗ログを保持して修正 |
| 初回是正source d659d1a | 親・独立とも5/32/13=50件はOK。ただし独立検分は保存中断のP2でfailed |
| P2の親再現 | 原7 tests中2 errors、failure.json不在、exit 1 |
| 最終source 9c576c5 | 親7/32/13=52件、独立52件、親検分後52件、全てOK・exit 0。追加P1/P2なし |

独立SOL検分は最初と是正後の別sourceで各最大1枠、計2枠を事前固定した。
同条件の自動再試行0、元failedの上書き0。新規一次モデル評価0、独立の使用量・実料金は不明。

## 最終sourceの検証

Pinned CPython 3.12.3と確定Core srcのPYTHONPATHで以下を個別に実行した。
一時データは本repoの`.venv/test-temp`へ固定し、外部へ書いていない。

```sh
python -B -W ignore::DeprecationWarning -m unittest discover -s tests/skills -p test_sdd_interruption.py
python -B -W ignore::DeprecationWarning -m unittest discover -s tests/skills -p test_sdd_skill_eval.py
python -B -W ignore::DeprecationWarning -m unittest discover -s tests/skills -p test_sdd_batch.py
```

独立実出力は7件/0.522秒、32件/17.389秒、13件/0.066秒で全てOK・exit 0。
作業者は同じ52件を再実行し、4ソースの実bytesと固定ref、独立ログhashと親再検査3ログhashを照合した。
旧品質証拠19点と、capacity終端を含む品質比較archiveのhashも不変。

## 全件検証の承認待ち

初回source d659d1aで全192件をrepo内TMPDIRへ固定して実行すると、保持ケース用の合成データを
公開repo内へ置けないという境界検査により、4試験が拒否された（2 failures / 2 errors、188件通過）。
これは合否境界を緩める理由にしない。最終sourceは回帰2件追加後の全194件をまだ実行していない。

AGENTS.mdの「リポジトリ外への書き込み・上書き・削除」は事前確認対象である。
`/tmp/bitzskills-tests-20261006/`以下へ今回の合成試験データを一時作成・試験後削除する確認を提示済み。
本記録時点でその領域には書き込んでいない。承認後、同sourceコードを全194件で実検証して別に結果を保存する。
この確認は実際の非公開保持評価や公開リリースの承認ではない。

## 保存監査

```sh
python3 -B evals/skills/results/2026-10-06-sdd-interruption/archive-audit.py evals/skills/results/2026-10-06-sdd-interruption/evidence.tar.gz
```

実出力はstatus=passed、errors=[]。35ファイル、325619 bytes、3確定refのsource snapshot11件を保存した。
archive SHA-256は `92551b18c1736a6b27a12d1467eeadb60e7a01ea85fbc358f5a8d897a29e5705`。
保存監査のpassedは全件検証や実モデル適合を意味しない。
失敗記録自体の保存不能、反復中断、subprocess.runが返さないpartial bytesの完全保存は保証外。
