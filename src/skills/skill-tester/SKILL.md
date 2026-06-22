---
name: skill-tester
description: Antigravityスキル用のテストケースを作成し、単一の機能チェックを実行します。ユーザーがスキルのテストプロンプトを作成したり、evals.jsonファイルを設定したり、スキルがエラーなく正しくトリガーされるかどうかの簡単な動作確認を行いたい場合に、必ずこのスキルを使用してください。
---

# Skill Tester

あなたは`skill-tester`です。あなたの仕事は、ユーザーがAntigravityスキルのテストケースを定義し、簡単な機能チェックを実行するのを支援することです。

## フェーズ 1: テストケース設計
1. ユーザーにどのスキルをテストしたいか尋ねます。
2. スキルをトリガーするはずの現実的なテストプロンプトを2〜3個議論して作成します。また、それぞれのテストに対して`expected_output`（期待される結果の説明）と客観的に検証可能な`expectations`（期待項目のリスト）をユーザーと確認します。
3. これらのプロンプトをターゲットスキルのディレクトリ内にある`evals.json`ファイル（例：`.agents/skills/<skill_name>/evals/evals.json`）に保存します。
   - `evals.json`のフォーマット：
     ```json
     {
       "skill_name": "<skill_name>",
       "evals": [
         {
           "id": 1,
           "prompt": "ここにテストプロンプトを記述",
           "expected_output": "期待される結果の説明",
           "files": [],
           "expectations": ["客観的に検証可能な文1", "文2"]
         }
       ]
     }
     ```

## フェーズ 2: 機能チェック (ドライラン)
1. テストプロンプトの1つを選択します。
2. そのテストのためのディレクトリ（例：`.agents/skills/<skill_name>/evals/eval-<id>/`）を作成し、そこに`eval_metadata.json`ファイルを書き込みます。
   - `eval_metadata.json`のフォーマット：
     ```json
     {
       "eval_id": 1,
       "eval_name": "basic-functional-test",
       "prompt": "ここにテストプロンプトを記述",
       "assertions": []
     }
     ```
3. `invoke_subagent`ツールを使用して、単一の`self`サブエージェント（Workspace: 'branch', Role: 'Tester'）を生成（spawn）します。
   - プロンプト: "Execute the following task: <test_prompt>. Note: Make sure to use the <skill_name> skill."
4. サブエージェントからの応答を確認し、スキルがトリガーされたこと、およびクラッシュしなかったことを検証します。
5. A/Bテストや品質評価は**実行しないでください**。
6. テストに合格した場合は、包括的なA/Bテストや品質分析のために`skill-evaluator`を使用するようユーザーに伝えます。
