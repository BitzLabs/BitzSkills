# 保持ケース単体試験の合成リポジトリ隔離

source `edaf5a0660d5952d65d6f20c08fb47030af291f0`。変更は
`tests/skills/test_skill_eval.py` のみ。製品validatorとrunnerは
基準ref `d31900c6` から変更していない。

実リポジトリ内の一時領域で保持ケースを作る従来の4試験は、製品の公開領域拒否により、
本来のmetadata・衝突・event・release検査へ到達しなかった。基準refの本文を直接実行した
27件の結果は `FAILED (failures=2, errors=2)` / exit 1。

単体fixtureに合成公開リポジトリとprivateの兄弟ディレクトリを作り、
公開入力・schema・runnerを実bytesのコピーで用意する。検査関数とresolve境界はmockしない。
4試験の検証条件を維持し、公開側へのsymlink拒否と実リポジトリ拒否の2試験を追加した。
属性patchとrunner cacheは正常・例外時とも復元する。

実出力:

- 作業者: `Ran 29 tests in 5.884s / OK`、exit 0。
- 全スキル単体: `Ran 196 tests in 53.229s / OK`、exit 0。
- SOL独立検分: `Ran 29 tests in 5.796s / OK`、exit 0、P1/P2指摘0。
- 検分後の作業者再実行: `Ran 29 tests in 5.957s / OK`、exit 0。

モデルはgpt-6.1-sol。新規一次軌跡0、事前固定した独立1枠を消費、自動再試行0。
独立検分は全196件を再実行せず、作業者の全件ログを直接点検した。
作業者は独立ログ・source bytes・基準refとの差分・全件ログのhashを再確認した。
一時データ・ログはリポジトリ内へ配置し、単体試験のための外部一時領域承認は不要になった。

[SDD中断是正の先行記録](../2026-10-06-sdd-interruption/report.md)に記載した
旧失敗・P2・全件未認定は当時の事実として保持する。本記録が単体試験の後続検証となる。
品質capacity通知、停止済み予算、原failed/unknownも変更しない。
実保持ケースの評価、実モデル比較、全Skill Gate、Core Gateの認定ではない。
合成privateは実保持領域として扱わず、実保持評価には公開リポジトリ外の領域が必要。

原ログ・固定ref再現driver・独立所見・予算・old/new sourceは
`evidence.tar.gz` に保存し、`manifest.json` と `archive-audit.py` で検査する。
