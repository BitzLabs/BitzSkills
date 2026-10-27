# 日本語sdd-planの本文と配布例

- 対象ref: `d68a1a194acc2dacb99b0a260b83f32712b1e183`
- ブランチ: `codex/sdd-plan-japanese`（origin/mainから作成、Core評価ブランチとは別）
- プラグイン／スキル: bitz-sdd 0.1.0 / sdd-plan 0.1.0、BitzSkills 2系の試作版
- 状態: Phase 2 In progress。本文とローカル検査を実装、モデル行動・Skill Gateは未認定

## 実装

機能、バグ修正、保守、スパイクの4入口から既存契約を検索し、解釈用contextを確認して計画へ整理する。
計画のみの依頼は会話へ返し、文書作成も依頼された場合だけ必要なdraft草案を保存する。
小さな保守に新規REQを強制せず、TASKのaddresses・requires・changesで対象・前提・境界を分ける。
承認済み要求の意味変更、Core不在・非成功、所有者不明、未信頼入力、高リスクの準備不足では停止条件を示す。
要求承認、コード実装、verify、実装後の品質レビューとは分離した担当工程である。

配布物はplugin.json、README、SKILL.md、planning参照、REQ/TASKの草案例の6ファイル。
CLI内部API、独自の判定器、ラッパーは追加していない。1系のルール・スクリプトも持ち込んでいない。
Core依存は公開CLI 1.0.0と公開結果契約のみ。Core実行体は別途導入する。
新しい配布例はfixtures/ではなくplugins/配下に置き、Core実装・適合fixture・承認済REQ/TECHは変更していない。

配布6ファイルのsourcehashは `3b43dd45a095b19693fb990a9c5cb1d1d4e4eb6f4419aba56e299e69a7a76d98`。
cleanな対象refで測り、リポジトリ相対パスでソートした各 `path + NUL + content + NUL` を連結してSHA-256とした。
rootの再計算と独立検分の値は一致した。

## ローカル検査

CPython 3.12.3、ruamel.yaml 0.19.1で合成workspaceを使い、公開CLIだけを呼んだ。
テスト本文や外部サービスを起動せず、暗黙のファイル変更も前後hashで検査した。

```text
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=plugins/bitz-core/src:/home/hide/.cache/uv/archive-v0/Ug0C44_7vEo9wg_i \
  python3 tests/skills/test_sdd_plan_examples.py -v
Ran 2 tests in 0.922s
OK / exit 0

python3 /home/hide/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  plugins/bitz-sdd/skills/sdd-plan
Skill is valid! / exit 0
```

第1試験は配布REQ/TASKの静的検査、draftの解釈、draftをaddressesするTASKの実装遮断を検査する。
第2試験は合成REQの承認後を模擬し、TASK境界内の差分が通過、境界外が不合格になることを検査する。
この模擬承認は/tmpの合成fixtureだけで、利用者や製品のREQを承認する処理ではない。

rootも掲載例を公開CLIへ直接入力し、次の実結果を確認した。

| 操作 | status | exit | 結果 |
|---|---|---:|---|
| check REQ-001 | passed | 0 | diagnosticsなし |
| check TASK-001 | passed | 0 | diagnosticsなし |
| context REQ-001 --purpose interpret | passed | 0 | complete true、digestあり |
| context TASK-001 --purpose implement | blocked | 2 | complete false、CTX-STATE-001 |

## 独立検分

新しい文脈の `/root/sdd_plan_review` が確定refの配布物・試験と、SDDフロー、SPECモデル、EARS-AI、
ADR-060、実装計画を直接照合した。主作業者の非公開履歴や意図した結論は渡していない。
4入口・草案状態・権限・承認・高リスク・Core非成功・所有者・未信頼入力・引渡しを静的に検分し、
重大な規範矛盾・欠落は指摘されなかった。

独立実行IDは `sdd-plan-static-ed9ca3e9-66fb-45ef-b261-e04b7cf04d6f`。
試験を自分で再実行して2 tests / 0.921s / OK、quick_validateもSkill is valid!、ともにexit 0だった。
最初のpython実行はコマンド不在でexit 127だったため、python3で再実行した。
元の実装refと配布hashを[独立検分記録](2026-10-03-sdd-plan-implementation.independent-review.json)へ結び付けた。

このブランチの評価器にはreviewサブコマンドがなく、最初の呼出しは引数不正（exit 2）だった。
別ブランチの未統合コードを取り込まず、次のSchema検査と実行IDの相違を直接確認した。

```python
import json
from pathlib import Path
from jsonschema import Draft202012Validator
record = json.loads(Path('evals/skills/results/2026-10-03-sdd-plan-implementation.independent-review.json').read_text())
schema = json.loads(Path('evals/skills/schemas/independent-review.schema.json').read_text())
errors = [e.message for e in Draft202012Validator(schema).iter_errors(record)]
if record['independent'] and record['implementationRunId'] == record['reviewRunId']:
    errors.append('実装と検分の実行IDが同一です')
print(json.dumps({'status': 'Failed' if errors else 'Passed', 'errors': errors}, ensure_ascii=False))
raise SystemExit(bool(errors))
```

実出力: `Passed / errors [] / exit 0`。

Schema検査は記録の整合性を調べるもので、モデル行動やGateの自動認定ではない。
Core不在、複合workspace、偽装依頼等のモデルによる実応答は未測定である。

## 残件

追加の評価用モデル呼出しは行っていない。sdd-implement、接続の実動作評価、保持ケース、
発火・行動・安全・実地のSkill Gate、配布・人間のリリース受入れは残る。
今回は本文の具体化と公開CLI検査の範囲であり、Phase 2完了や出荷許可とは扱わない。
