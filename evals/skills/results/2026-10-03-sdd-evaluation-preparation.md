# SDD実モデル接続評価の準備と採点是正

- 対象ref: `0e536d18fceac45ea7bceafa00aaf5448786afe3`
- 採点是正ref: `a441855babb5b52b075268ea93504deac5bc4aec`
- 初版ref: `d36684fcba995bcb1dd373d4be96a2d8c072dcaa`
- ブランチ: `codex/sdd-plan-japanese`
- 評価集合: sdd-0.1.1、17ケース、skill／baseline各2反復、最大68回
- モデル予定: gpt-6.1-solのみ。Astraは使用しない
- 状態: 準備のローカル試験・独立是正検分まで。実モデル評価未実行、Phase 2 In progress

## 目的と境界

配布したsdd-planとsdd-implementについて、計画→実装→Core検査・実テスト→人手レビュー待ちの接続を測る。
4入口の計画、草案保存と計画のみ、無許可の意味変更、本文偽装、境界内実装、precheck失敗、
草案要求、先行TASK、完全フローの承認／設計レビュー不足、危険なverify、古いcontext、
レビュー省略、テスト障害を17件に固定した。
Q2／Q3は停止判断だけを測り、その実変更を実施しない。

評価専用stdio MCPと固定合成workspaceで実操作を記録する。製品のMCP API、独自のCore判定器は追加していない。
Coreのsource・適合fixture・承認済み製品REQ／TECHの意味は変更していない。
Core評価ブランチの未統合コードを取り込まず、今回の評価器はSDDの対象・書込み・実テストに限定した。

実行ホストは読取り可能なファイルと変更可能なパスを固定し、範囲外パスとsymlinkを拒否する。
入力関数はASTで副作用のない比較・分岐・リストのreturnへ限定し、固定Pythonテストのhashを検査してから実行する。
一般のPythonプログラムの安全化を保証する仕組みではない。
モデルのshell・直接編集・web・apps/plugins等を無効化し、追加ツールの試行とホストが拒否した操作も失敗にする。
Codex CLIのモデル認証値を読まず、Coreのsubprocessには資格情報の環境変数を渡さない。

## 主作業者の実検査

確定refのcleanな状態で、CPython 3.12.3、ruamel.yaml 0.19.1を使用した。
試験内のモデル応答traceは、評価器の欠陥を検査するための合成データであり、実モデルの成果ではない。

```text
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i \
  python3 tests/skills/test_sdd_skill_eval.py -v
Ran 19 tests in 13.332s
OK / exit 0

python3 evals/skills/sdd/evaluate.py audit
{"status":"Passed","cases":17,"plannedCalls":68,"errors":[]}
exit 0
```

既存の計画2件と公開CLI接続7件も初版refで再実行し、2 tests / 0.975s / OKと7 tests / 3.705s / OK、exit 0だった。
git diff --checkは出力なし / exit 0。
CLIのローカル表示はcodex-cli 0.160.0。read-only環境でPATH aliasesを作れない警告が出たが、バージョン表示はexit 0だった。
実モデル起動の動作はこの表示では検証していない。
codex exec --helpもexit 0で、使用予定のJSON・ephemeral・ignore-user-config・ignore-rules・sandbox・cd・model・
output-schema・output-last-messageの各オプションが掲載されていることをローカルで確認した。

未実行の出力先をscoreすると、各条件・反復を0/17、全68件をmissingとして返した。
実出力の集計は `Failed / not-certified / missing 68`。欠測を成功として埋めていない。

対象refの評価器5ファイル＋単体試験1ファイルをリポジトリ相対pathでソートし、
各 `path + NUL + content + NUL` を連結したSHA-256は
`4f362326c337a7df7fac1652874484b457b49238e12816427aa67ca1092c5c42`。
cases.jsonのSHA-256は `2df534037e876923132d3fdf91f247c398ed8602a72078bb97e25d86867cfeac`、
protocol.jsonは `8fdf50b2d9d6a345e8210a11837a04267ccb7ab6f7faa8f1832d49fb3e9a980c`。

## 独立検分と是正

新しいfork_turns=noneの `/root/sol_sdd_evaluation_host_review` が初版を独立検分した。
主作業者の非公開履歴や意図した結論は渡していない。指摘の再現には/tmp合成データと実Coreだけを使い、
モデルCLI・外部サービスは起動しなかった。

初版は11単体試験が通過していたが、独立検分で次の欠陥が直接再現された。

1. 実verifyの成功後にコードを再変更しても、過去の成功だけで採点が通過する。最終状態の実テストはfailedだった。
2. sol／lunaや版の異なる記録を一つの比較へ集計できる。
3. 不正な最終応答JSONにより集計が例外終了し、固定分母の失敗記録を返せない。
4. MCP traceを逆順にしてもホスト順序と照合できない。

主作業者も1を実Coreの回帰試験で再現し、修正前は `Ran 1 test / FAILED (failures=1) / exit 1`だった。
最終書込み→後check→verifyの順序、条件の一致、破損証拠のケース失敗化、trace順序を是正した。
異なる条件の記録を成功として混ぜず、拒否や欠測を後段の点数で相殺しない。

SI-010の固定テストはコードで解消できないself.failを含む。テスト変更の権限もないため、
事前にテストを読み取って実装前に停止する正しい経路も認め、集合版をsdd-0.1.1へ上げた。
モデル測定による失敗に合わせた期待値変更ではなく、測定開始前のケース明確化である。
baselineのselectedEntryはスキルの導入有無ではなく処理した工程名として記録することを明示した。

独立再検分は同じ検分者の文脈を継続し、新しい確定refを直接読み直した。
主作業者が初版検分の終了前に回帰試験を保存したため、初版の終了直前にはその試験の変更が見えた。
検分者は変更前に11試験と再現を実行し、自身ではソースとGitを変更していない。
是正refでの再検分は開始・終了とも対象HEAD、treeはcleanだった。

```text
独立再検分: a441855babb5b52b075268ea93504deac5bc4aec
Ran 17 tests in 13.114s
OK / exit 0
audit: Passed / cases 17 / plannedCalls 68 / errors [] / exit 0
```

検分者は独自の合成再現でも、未検証の最終変更・混在条件・逆順trace・不正JSONが拒否されることを確認した。
一致する完走記録のresumeは再利用、版変更とdecision欠測はモデル呼出し前に拒否した。
SI-010の開始前停止はCore呼出し0で通過し、未実行を実テストの成功・失敗として捏造しなかった。
理由の意味は機械採点で判定しないため、実モデルの結果にも独立した意味検分を必要とする。
その後、モデル呼出しまたは必須検査が失敗したら新しいケースの投入を止める処理を追加した。
すでに実行中の最大jobs件だけ証拠を回収し、未着手ケースを固定分母のmissingとして残す。
終了コード1で返し、失敗の後に自動で全件実行へ進まない。

独立追加検分は対象ref `0e536d18fceac45ea7bceafa00aaf5448786afe3` で、19 tests / 13.344s / OK、audit Passedだった。
独自のモデルなし並列検査でもA/Bだけを開始し、Aの例外とBの完了後に1を返してC/Dを開始しなかった。
開始・終了treeはclean、評価source6ファイルのhashは主作業者の確定ref測定と一致した。
主作業者も上記の19件を同じ確定refのclean状態で再実行した。
[独立検分記録](2026-10-03-sdd-evaluation-preparation.independent-review.json)へ対象refと未実施を保存する。

## 次に実行する測定

費用と時間を伴う新しいモデル測定の開始前に、以下の具体的な実行計画を提示する。
計画は17ケース×2条件×2反復の最大68呼出し、gpt-6.1-solだけ、並列最大2、
1呼出しのタイムアウト240秒、自動再試行0である。
先行した重点ケースの完走記録は、同じ対象ref・入力・版・モデル条件でだけresumeする。
欠測・条件不一致・安全失敗があれば記録を残して止め、別条件の新実行へ自動で拡張しない。

実行の例は[評価README](../sdd/README.md)にある。出力はリポジトリ内の専用未追跡ディレクトリへ分離する。
モデルのプロバイダー固定版は確認できず、aliasの表示ラベルとして扱う。
認証情報を読んで料金を推定せず、実消費tokenと壁時計時間は測定後の実記録へ残す。

現在は実モデル結果0件で、評価環境の設定が実際のモデルに対して有効であることも未実証である。
発火の各区分分母、保持ケース、2モデル系統、実地パイロット、Skill Gate、品質スキルとの接続、配布・リリース受入れは残る。
68件の接続測定を通過しても、公開・隔離評価をSkill Gateや出荷認定へ読み替えない。
