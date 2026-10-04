# 日本語sdd-implementと公開CLIの接続

- 対象ref: `36567d4463fad3cdd0da3d3522be201038b608c5`
- 初版ref: `a85eab068f7cfc5ae4f02bc652641abeb1015db1`（独立検分後に是正）
- ブランチ: `codex/sdd-plan-japanese`
- プラグイン／スキル: bitz-sdd 0.2.0 / sdd-plan 0.1.0 / sdd-implement 0.1.0
- 状態: Phase 2 In progress。実装本文と合成workspaceの接続試験を追加。モデル行動・Skill Gateは未認定

## 実装と検査範囲

実装スキルは承認済み起点から、フローとリスク、完全なimplement context、設計レビュー、
実装前check、書込み直前の--expect-digest、境界内のコード・テスト変更、後check、
安全なverify、人手レビュー、TASK最終checkと許可されたGit記録を案内する。
完全フローの要求承認、Q2／Q3の品質計画と独立レビュー、複合作業、失敗と戻り先を参照へ分けた。
人手レビュー待ちや未収集証拠を不足として返し、Core成功をreadyやリリース許可へ変換しない。

Coreの実装・適合fixture・承認済み製品REQ／TECHの意味は変更していない。
CLIラッパー、独自の判定器、内部API、1系の規則・スクリプトは追加していない。
Coreスキル評価のブランチから未統合コードを取り込まず、既存の公開CLIと引渡しSchemaを使った。

cleanな対象refで配布10ファイルをリポジトリ相対パスでソートし、
各 `path + NUL + content + NUL` を連結して測ったSHA-256は
`4dee0fd64d9afe9a01098a35f0ef06e0e980c74d73133ad0c35b74a858d30364`。
接続試験ファイルのSHA-256は `40b89d40335a1fdf7f0a9501bf00a3a3764c24f4b66dacf91802163a397c7e8e`。

## 主作業者のローカル再実行

CPython 3.12.3、ruamel.yaml 0.19.1で、確定refのcleanな状態から実行した。
Core操作は公開CLIだけで、実装スキルによるモデル応答を評価する試験ではない。

```text
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i \
  python3 tests/skills/test_sdd_plan_examples.py -v
Ran 2 tests in 1.177s
OK / exit 0

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i \
  python3 tests/skills/test_sdd_implement_connection.py -v
Ran 7 tests in 4.065s
OK / exit 0

python3 /home/hide/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  plugins/bitz-sdd/skills/sdd-implement
Skill is valid! / exit 0
```

既存sdd-planのquick_validateもSkill is valid! / exit 0、git diff --checkは出力なし / exit 0だった。

| 接続試験 | 実際に検査した条件 |
|---|---|
| 実装前check | contextが完全通過しても利用者の境界外差分でcheckがfailed。差分とコードを保護 |
| digest再照合 | SPEC本文の変更後、保存digestを要求するとblocked / CTX-STALE-001。コード変更へ進まない |
| コード差分 | コード内容の変更ではdigestが一致する。差分と実行安全性の確認を別途要求する根拠 |
| コマンド設定 | 登録argv変更ではimplement digestが一致する一方、verify digestの再照合はblocked / CTX-STALE-001 |
| 先行TASK | requiresのopen TASKによりimplement contextがblocked / CTX-TASK-DEPENDENCY-001 |
| 必須テスト対応 | MUSTの対応欠落ではverifyがblocked / CTX-COVERAGE-TEST-001、commandsは空 |
| 実テストと不足証拠 | check通過でもPythonのassert失敗でverifyがfailed / exit 1。境界内修正後にexit 0。人手レビュー未実施を保持 |

合成例はsdd-planの配布REQ/TASKを/tmpへコピーする。人間の承認後の状態を合成例だけで模擬し、
単純な入力関数の実テストを標準Pythonの-I・-Bで実行する。通信、秘密の読取り、外部サービスは使わない。
CLIの前後でworkspaceファイルのhashを照合し、暗黙の書込みがないことも検査する。

最後の試験では合成例をコミットして対象refを固定し、cleanなrefでcheck・verifyを再実行する。
実在する結果JSONのhashを型付き引渡しへ結び付け、人手レビューはmissingEvidence／not-run、TASKはopenのままとする。
Schema検査と実ファイルのhash照合は通過し、必須missingEvidenceの削除はSchema違反になることを確認する。
ここでの合成コミットは試験用/tmpだけで、製品TASKを完了したり利用者の要求を承認したりする処理ではない。

初回試験では診断をトップレベルだけから読むテスト側の想定が誤っていた。
公開結果の対象別診断を直接確認し、targetResults[].diagnosticsを検査するよう修正した。
Coreの結果や診断、合否を変更せずに試験を再実行した。

## 独立検分で見つかった説明の是正

初版の独立検分で、digest保証範囲の説明と、実装スキル単独のリスク分類の不足が指摘された。
初版でも配布例2件・接続6件とquick_validateは通過しており、静的検分が機械試験の限界を補った。

- implement用digestが登録argvテンプレートを含むように読めたが、context仕様§6ではこの材料は目的verifyだけ。
  独立検分者は合成workspaceでargv変更後もimplement digestが不変／passedと再現した。
  主作業者も7番目の接続試験でimplementの一致とverifyのCTX-STALE-001を直接再現した。
  説明を目的別に限定し、登録コマンドをimplement digest以外の差分確認で検査する必要を入口にも示した。
- Q帯の目安・重大観点の引上げ・降格時の人間の承認・Q3の専門観点／復旧や攻撃の証拠が不足していた。
  既存sdd-planと提案30にある要点を実行参照へ追加し、リスク確定時に読むリンクを付けた。

テストをスキルの誤説明に合わせず、正本と公開CLIの実結果を根拠に是正した。
初版配布hashは `ec14f18d6153d2e4cc31f60e57272e9dca2d679cf8c742d95159b760de537d13` である。
是正後の主作業者再実行は上記の確定refから実施した。

検分は新しいfork_turns=noneの文脈 `/root/sol_sdd_implement_review` で開始し、主作業者の非公開履歴や意図した結論を渡さなかった。
初版を検分した後、同じ独立検分者へ新しい確定refの再検分を依頼した。再検分時は前回の検分文脈を継続している。
是正の解消判定では初版からの3ファイルの差分と正本を読み直し、試験を再実行した。

```text
独立再検分: 36567d4463fad3cdd0da3d3522be201038b608c5
test_sdd_implement_connection.py -v: Ran 7 tests in 3.917s / OK / exit 0
test_sdd_plan_examples.py -v: Ran 2 tests in 1.072s / OK / exit 0
quick_validate.py: Skill is valid! / exit 0
開始・終了HEADは対象ref、git status --porcelainは空
```

配布10ファイルのsourcehashと接続試験hashは主作業者の確定ref測定と一致した。
今回確認した範囲では2指摘の解消が確認され、新たな指摘はなかった。
根拠と未再実行事項は[独立検分記録](2026-10-03-sdd-implement-connection.independent-review.json)に残す。
公開の独立検分Schemaと実装／検分実行IDの相違を直接検査する。Schemaは独立性の事実を自動証明するものではない。

```python
import json
from pathlib import Path
from jsonschema import Draft202012Validator
record = json.loads(Path('evals/skills/results/2026-10-03-sdd-implement-connection.independent-review.json').read_text())
schema = json.loads(Path('evals/skills/schemas/independent-review.schema.json').read_text())
errors = [e.message for e in Draft202012Validator(schema).iter_errors(record)]
if record['independent'] and record['implementationRunId'] == record['reviewRunId']:
    errors.append('実装と検分の実行IDが同一です')
print(json.dumps({'status': 'Failed' if errors else 'Passed', 'errors': errors}, ensure_ascii=False))
raise SystemExit(bool(errors))
```

主作業者の実検査はこれに確定refの配布hash再測定を加え、実出力は
`Passed / errors [] / files 10 / sourcehash 4dee0fd64d9afe9a01098a35f0ef06e0e980c74d73133ad0c35b74a858d30364 / exit 0`だった。

## 未実施と次工程

モデルによる発火・実装行動、完全フローの承認／設計レビュー欠落に対する実応答、
危険な検証・偽装入力・複合workspace・高リスクの一連のモデル評価は未実施。
追加の比較ベンチマークや評価用モデルCLIは実行していない。
今回の独立検分も静的判断とローカルCLI検査であり、Skill Gateや製品要求の実証・出荷を認定しない。

次はQ0／Q1のSDDモデル行動・接続評価を準備し、完全フローの不足承認と設計レビュー、
実装前check失敗、未信頼入力、危険なverify、証拠なし成功の停止を確認する。
保持ケース、実地評価、sdd-converge、品質スキルとの接続、人間のリリース受入れは残る。
