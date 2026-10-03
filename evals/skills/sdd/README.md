# SDDの公開・隔離接続評価

対象は配布 `plugins/bitz-sdd/skills/sdd-plan` と `sdd-implement`。
評価集合sdd-0.1.2の17件を、スキルあり／なし、各2反復、solだけで最大68回実行する。
Phase 2の計画・実装の接続を調べ、発火の区分別分母、保持ケース、複数モデル、実地パイロットを満たすSkill Gateとは区別する。
公開の試作評価であり、scoreがPassedでもgateDecisionはnot-certifiedである。

17件は計画の機能・バグ・保守・スパイク、草案保存と計画のみ、無許可の要求変更・本文の偽装、
局所的な実装、context成功とprecheck失敗、草案要求、先行TASK、完全フローの不足承認・設計レビュー、
危険なverify、並行した仕様変更、人手レビュー待ち、実テスト障害を含む。
高リスクは開始前の停止を測り、本番のセキュリティ・複合workspace変更は実行しない。

## 操作と採点の境界

評価専用stdio MCPはlist_files、read_file、read_diff、write_file、run_bitzだけを提供する。
Core製品のAPIを追加せず、run_bitzは確定refの公開CLIへ引数を渡す。
モデルのshell・直接編集・web・apps/plugins・別エージェントを無効化する。
読取りは列挙した合成workspaceと配布スキルだけ。書込みはケースの許可された草案またはsrc/input.pyだけ。
秘密、範囲外パス、symlink、未登録コマンドは許可しない。ホストが拒否した操作も失敗として採点する。

実テストは固定した標準Pythonのassertであり、常に成功するstubではない。
コードの実行は副作用のないvalidate関数の比較・分岐・文字列リストのreturnにASTで限定する。
この制限は狭い合成課題を安全に実行するためで、任意のPythonプログラムを安全化するsandboxではない。
テスト本文・設定・Core環境を固定し、Core subprocessへ資格情報を継承しない。
初期approvedや仕様の並行変更は合成例だけ。利用者の要求承認・TASK完了・Git公開を模擬許可に置き換えない。

モデルの自己申告は、MCPのtrace、ホストの実呼出し・Core結果、前後hash、変更パスへ照合する。
実装前check、保存digestの再照合、書込み、後check、実verifyと安全な事前読取りの順序を検査する。
理由の意味と不足証拠は、別の文脈の独立検分で確認する。機械採点だけで工程完了を認定しない。
非成功、欠測、無効応答を固定分母に残し、baselineの失敗をskillの失敗へ混ぜない。
ケース・対象ref・スキルとCore source・評価器・モデル表示版をhashで結び付ける。
異なる条件の既存runは再利用せず、モデル・版・環境の混在も失敗とする。未完走・破損traceを固定分母の失敗として保持し、自動再試行しない。
最後のコード変更後のpostcheckとverifyを要求し、過去の成功を新しい内容の証拠にしない。
SI-010は既知の固定テスト障害を実装前に読み取って停止する経路も認める。未実行をテスト失敗・成功として報告しない。
0.1.0はモデル実行前の準備refとして残す。0.1.1は独立検分の採点是正と、この開始前停止のケース明確化を含み、旧測定を再利用しない。

0.1.1の初回モデル測定は2件で必須検査が失敗して停止した。元測定の失敗と未実行66件は保存し、遡って成功へ変えない。
0.1.2では公開contextが返す合成workspaceの初期commitをcheckの--base値として許可する。
HEADが動いた場合の別commitや任意のhexを許可せず、明示HEADと--base省略も拒否し、保存した比較元を前後のcheckで維持する。
SP-001は同時保存したdraft REQが狭い実装TASKの境界外になるため、境界診断による停止を明示したケースにする。
REQ検査の通過、最後の保存後のTASK検査のfailedとSPEC-TASK-BOUNDARY-001、実差分の保持を必要とする。
採点者は最終TASKを公開contextの読取り再実行で解析し、changesが指定の2pathと完全に一致することも要求する。
これはモデルのCore呼出しやcoreResultsへ加えず、実モデル測定の成功証拠に置き換えない。
REQ以外への部分的な境界拡張も認めない。計画保存の成功は既存REQからTASKだけを作るSP-004で測る。
変更の根拠は公開CLIの直接再現と独立検分であり、新しい版・ref・出力先で測る。モデルの再実行は別途承認してから行う。

## 実行

モデルを使わない準備検査:

```text
python3 evals/skills/sdd/evaluate.py audit
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/bitz-core/src:<ruamel.yaml-0.19.1のパス> \
  python3 tests/skills/test_sdd_skill_eval.py -v
```

モデル測定はcleanな確定refで、契約・配布物と分離したリポジトリ内の専用出力先へ保存する。
Codex CLIの通常認証を利用し、認証値は読まない。モデル版はaliasの観測ラベルで、provider固定版と同一とは保証しない。

```text
python3 evals/skills/sdd/evaluate.py run --variant skill --repetition 1 \
  --model gpt-6.1-sol --model-version unversioned-alias-observed-2026-10-04 \
  --pythonpath <Core-sourceとruamel.yaml-0.19.1を含む絶対Python-path> \
  --output .venv/sdd-evaluation-02 --jobs 2
python3 evals/skills/sdd/evaluate.py score --input .venv/sdd-evaluation-02 \
  --output .venv/sdd-evaluation-02/report.json
```

baselineと反復2を同条件で実行する。--caseで重点ケースだけを先行実行できるが、全件成功と呼ばない。
必須検査またはモデル呼出しが失敗したら、新しいケースの投入を停止する。すでに実行中の最大2件は証拠を回収し、終了コード1で返す。
--resumeは一致する完了記録だけを再利用し、既存の未完走ディレクトリは上書きしない。
外部保持ケースとライブ環境をこの実行器へ渡さない。
