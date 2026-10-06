# 保持集合0.3の収集と独立検分の停止

保持集合 `production-routing-held-out-0.3.0` の12件を新規保存した。親の実監査は
`mechanical_checks_passed` / exit0、確定source13ファイルの再照合は
`fixed_source_matches` / exit0。ケースhashは
`3d34e4ab071e5d6e984b7f6adc12129b96576e6c490190c6d16907e0e9407cd9`。
6機能、正例6件/負例・停止6件、公開46件/旧12件に対する比較記録12件を確認した。
作成receiptの6成果物hash、開始時/保存直前の照合と確定refを親も再確認した。
非公開7ファイルは0600、ディレクトリは0700。内容は公開側へ複写しない。

## 独立検分の不通過と証拠保存待ち

独立SOL1枠は全12件の検分後にP1=3/P2=3、影響3件を報告し、集合を停止した。
mandatory12件の集合として通過を主張しない。
この件数は独立agentの申告で、詳細報告/永続receiptの保存と親の原証拠再監査は未完了。
9件についても全体の合格や意味新規性を認定しない。

独立側は監査CLIの `--collection` に誤った形式を渡してexit2となり、
原失敗を保持して同じ有料検分内で正規の `--collection fixed-ref` を1回実行した。
正規監査/最終source guardのexit0は独立側の申告で、親は別に同じ固定source/集合で
両CLIを実行しexit0を確認した。誤引数と是正の永続記録も保存待ち。

詳細記録6ファイルの非公開領域への新規保存は、自動承認審査が2回拒否した。
理由はリポジトリ外書込みの明示的なユーザー承認を確認できないこと。
固定contractには対象root/scope/ongoingとユーザー発言「OK、以後も許可します」があるが、
再審査でも拒否された。予定6ファイルは未作成で、別領域への迂回保存は行わない。
保存対象と条件は `storage-approval-request.md` に具体化した。

## 実検証

`audit_held_out.py --collection fixed-ref --cases <承認済み非公開領域>/collection-03/cases.json`:
exit0、`mechanical_checks_passed`。

`source_guard.py --source 5ff330a73de281be8708cba4083e1235c2ad8fca`:
exit0、`fixed_source_matches`、対象13ファイル。
HEADは結果コミットへ移動しているが、固定sourceの内容は変わっていない。

同じ確定sourceの準備工程で記録した親の全スキル試験は
`Ran 230 tests in 56.820s` / `OK` / exit0。
独立検分後の親のsource guard4件/保持監査11件も `OK` / exit0。
詳細とログは `../2026-10-06-held-out-fixed-ref-preparation/` の固定ref archiveに保存する。

## 消費枠と次工程

集合0.3の準備独立SOL1・作成SOL1・ケース独立SOL1を消費した。
一次モデル軌跡0・自動再試行0。使用量/費用はunknown。
旧集合0.1の意味重複、準備0.2のP2、集合0.2のHEAD拘束停止を保持する。
Skill Gate、発火実測、Core操作の実証は未認定。

まず拒否された詳細記録の保存を解決し、親が永続証拠を再監査する。
是正する場合は原集合を上書きせず、新しいsource/条件/有限枠を固定する。
製品一次発火実行器の接続案は公開の計画文書に記録した。新しい一次起動は行っていない。
