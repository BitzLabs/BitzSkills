# R02 原artifact・固定入力・共有予約の照合記録

2026-10-11。対象ブランチはcodex/core-sdd-quality-integration。
[計画と進捗](../../../../docs/04.提案資料/31_スキル統合残件の開発計画と進捗.md)のR02に従う。

## 実装範囲

原artifactの固定名・有限rollout構造と、内容を読む前のNOFOLLOW/regular/single-link境界を検査する。認証・cache・state内の一覧と内容を読まない。固定Git契約、manifest/全公開本文、case/catalog/instructions/environment、入力/Schema、source guard、runtime config/namespace argv、共有campaign/予約/先行独立記録へ束縛する。

成功でもeligibleForMeasurement/行動/Skill Gate/独立採点/台帳確定はfalse。この部品は原RPC/host/native final/rollout/client/usageの意味相関をまだ行わない。

## 原独立判定と是正

初回確定ref `b0ba6ba9c3e5354f1251525818c882c2a8825020` の別文脈検分はP2=2。
禁止した実rollout group名を降下前に検査できない点と、共有ledgerのhardlinkがsingle-link境界を通らない点を、公開合成データのみで確認した。canary関連40件、ledger関連30件は通過したが、コンポーネントの是正済み判定には使わない。元の所見を保持する。

親も検知patchを用いた回帰で再現し、禁止列挙/読取りを抑止した。実認証情報は使用しない。group名の検査を降下前へ移し、全共有記録の読取りをledger.read_regular/read_ownedのNOFOLLOW・regular/nlink1・owner/mode検査へ統一した。

是正ref `d22c4cb8fe8cd414163d8c1964f51e4e2db981a4` は検証用detached Worktreeだけに保存。元の対象ブランチHEAD64aed6ccは保持し、実装・文書は対象Worktreeに保存している。pushは行っていない。

## 検証と原記録

clean b0ba6ba9の全件初回はPYTHONPATH不足による44エラーで停止。同refでCIに合わせてPYTHONPATHを設定し、全587件が通過（68.546秒、exit0）。初回と再実行の原出力は、それぞれ検証用Worktreeの `.venv/r02-fixed-evidence-full/` と `.venv/r02-fixed-evidence-full-restored-env/` に保持する。

是正後の全件試験・独立検分は進行中。結果は同refを自分で照合して追記する。

## 残件

原RPC/host/finalの一次profile接続、rollout/client/usageの相関、独立意味採点のSchema/有限実行器、親確定レシートと台帳接続。R02全体・一次モデル行動・Phase・Gateは未認定。今回の一次/独立モデル起動は0。

## 有限値の追加指摘

clean d22c4cbの全590試験（68.295秒）は通過したが、独立検分でP2=1が残った。JSON数値1e999はstrict_jsonでinfへ変換され、経過時間として受理された。元P2=2は同refで是正確認済みだが、追加所見は保持し、完了判定にしない。

親も公開合成receiptで再現し、floatのmath.isfinite検査と指数オーバーフロー回帰を追加した。最終是正refは `b64772aa1993b4be992ba47275d620f5c7585c30`。全件試験・独立検分結果を後続に追記する。CLI timeout300後の照合時間を含む301.5秒の正例は維持する。

## 最終是正検分結果

cleanな確定ref `b64772aa1993b4be992ba47275d620f5c7585c30` で全591試験が通過（68.365秒、exit0）。stderr SHA256は `0a91229f812c08ecbce31d6b42b9e5ce3fabf39526aa39851a425c4c2369ba21`。検証用Worktreeの `.venv/r02-fixed-evidence-final-full/` にcommand/environment/stdout/stderr/summaryを保持した。親が原stderrの件数・終端、hash、確定ref、前後cleanと対象Worktreeの4ファイル一致を自分で確認した。

同clean refの独立是正検分はcanary44件（1.238秒）・ledger30件（0.337秒）、いずれもOK/exit0。先の3指摘の是正を確認し、検分範囲の追加阻害指摘0。対象4ファイルhashとclean前後も一致した。元b0ba6ba9のP2=2とd22c4cbのP2=1は履歴として保持し、元判定を成功へ置換しない。

全件コマンドは以下。環境はPYTHONPATH=$PWD/plugins/bitz-core/src、PYTHONDONTWRITEBYTECODE=1、TMPDIR=$PWD/.venv/test-temp。

```sh
uv --cache-dir .venv/uv-cache run --offline --project plugins/bitz-core --with jsonschema==4.23.0 python -B -m unittest discover -s tests/skills -p 'test_*.py'
```

当該コンポーネントの検分済みに限る。R02全体は進行中、一次/独立採点0件、Gate/Phase認定なし。次は原RPC/host/native finalの一次profile接続、続いてrollout/client/usageを束縛する。
