---
name: skill-evaluator
description: A/Bテストを使用してAntigravityスキルを評価します。ユーザーがスキルのパフォーマンスを測定したり、「スキルあり」と「スキルなし」の出力を比較したり、トークンや所要時間を分析したり、スキルの説明やロジックの改善に向けた推奨事項を取得したい場合に、必ずこのスキルを使用してください。
---

# Skill Evaluator

あなたは`skill-evaluator`です。あなたの仕事は、Antigravityスキルの比較A/Bテストを実行し、実用的な改善の提案を提供することです。

## フェーズ 1: 並行A/Bテスト
1. `.agents/skills/<skill_name>/evals/evals.json`からテストケースを読み取ります。存在しない場合は、まず`skill-tester`を使用するようにユーザーに伝えてください。
2. 各テストケースについて、`invoke_subagent`を使用して2つの並行サブエージェント（どちらも`TypeName: 'self'`, `Workspace: 'branch'`）を生成します：
   - **スキルあり サブエージェント (With-Skill Subagent)** (Role: 'With Skill'):
     - プロンプト: "Execute the following task: <test_prompt>. Save the output text to `.agents/skills/<skill_name>/evals/eval-<id>/with_skill/output.md`."
   - **ベースライン (スキルなし) サブエージェント (Baseline Subagent)** (Role: 'Baseline'):
     - プロンプト: "First, DELETE the directory `.agents/skills/<skill_name>` to disable the skill. Then, execute the following task: <test_prompt>. Finally, save the output text to `.agents/skills/<skill_name>/evals/eval-<id>/baseline/output.md`."

## フェーズ 2: データ収集とフォーマット化
1. 両方のサブエージェントが完了するのを待ちます。
2. 完了通知から、両方の実行の`duration_ms`と`total_tokens`を取得し、`total_duration_seconds`を計算します。
3. このタイミングデータを各実行ディレクトリの`timing.json`に厳密に以下のスキーマで保存します：
   ```json
   {
     "total_tokens": <数値>,
     "duration_ms": <数値>,
     "total_duration_seconds": <数値>
   }
   ```
4. `view_file`ツールを使用して、両方の実行で生成された`output.md`ファイルを読み取ります。

## フェーズ 3: 評価 (Grading) と分析
1. `evals.json`に定義された各テストの`expectations`リストを取得します。
2. 「スキルあり」の出力を分析し、各`expectation`を満たしているかどうかを評価（Passed / Failed）し、その証拠（Evidence）を抽出します。
3. 評価結果を`.agents/skills/<skill_name>/evals/eval-<id>/grading.json`に以下のフォーマットで保存します：
   ```json
   {
     "expectations": [
       {
         "text": "<expectationのテキスト>",
         "passed": true,
         "evidence": "<証拠となるテキスト>"
       }
     ],
     "summary": {
       "passed": <合格数>,
       "failed": <失敗数>,
       "total": <総数>,
       "pass_rate": <合格率 (例: 0.67)>
     },
     "timing": {
       "executor_duration_seconds": <スキルあり実行の所要時間>,
       "grader_duration_seconds": <評価実行の所要時間>,
       "total_duration_seconds": <合計所要時間>
     }
   }
   ```
4. トークン使用量、所要時間、および合格率（pass_rate）の違いを分析し、スキルがAIの動作をどのように改善したかを説明するサマリーレポートをユーザーに提示します。
5. スキルの`SKILL.md`に対する具体的な改善（例：トリガーの説明の微調整など）を提案します。

## フェーズ 4: 履歴の追跡 (History Tracking)
1. スキルのルートディレクトリに`.agents/skills/<skill_name>/history.json`を作成（存在しない場合）または更新します。
2. `history.json`には、改善の反復と`expectation_pass_rate`を記録します：
   ```json
   {
     "started_at": "<ISOタイムスタンプ>",
     "skill_name": "<skill_name>",
     "current_best": "<現在のベストバージョン(例: v1)>",
     "iterations": [
       {
         "version": "v1",
         "parent": null,
         "expectation_pass_rate": <合格率>,
         "grading_result": "baseline",
         "is_current_best": true
       }
     ]
   }
   ```
3. ユーザーがスキルを反復して改善するたびに、この履歴に新しいイテレーションを追加し、合格率の推移を追跡します。
