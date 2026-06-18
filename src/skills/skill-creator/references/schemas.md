# JSON スキーマ定義 (JSON Schemas)

本ドキュメントでは、`skill-creator` で使用される JSON ファイルのスキーマ定義について説明します。

---

## 1. evals.json

スキルの評価テストケース（評価用の問題と期待値）を定義します。対象スキルのディレクトリ内の `evals/evals.json` に配置されます。

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "ユーザーのサンプルプロンプト",
      "expected_output": "期待される結果の説明（人間用）",
      "files": ["evals/files/sample1.pdf"],
      "expectations": [
        "出力に X が含まれていること",
        "スキルがスクリプト Y を使用したこと"
      ]
    }
  ]
}
```

### フィールド説明:
- `skill_name`: スキル定義のフロントマターにある `name` と一致する名前。
- `evals[].id`: ユニークな整数識別子（ID）。
- `evals[].prompt`: 実行させるタスクのプロンプト。
- `evals[].expected_output`: 成功条件に関する人間が読める説明文。
- `evals[].files`: （任意）入力ファイルのパス一覧（スキルルートからの相対パス）。
- `evals[].expectations`: 検証可能なアサーション（合格条件）のリスト。

---

## 2. history.json

改善モードにおけるスキルのバージョン変遷や、各バージョンの評価推移を記録します。ワークスペースルートに配置されます。

```json
{
  "started_at": "2026-01-15T10:30:00Z",
  "skill_name": "pdf",
  "current_best": "v2",
  "iterations": [
    {
      "version": "v0",
      "parent": null,
      "expectation_pass_rate": 0.65,
      "grading_result": "baseline",
      "is_current_best": false
    },
    {
      "version": "v1",
      "parent": "v0",
      "expectation_pass_rate": 0.75,
      "grading_result": "won",
      "is_current_best": false
    },
    {
      "version": "v2",
      "parent": "v1",
      "expectation_pass_rate": 0.85,
      "grading_result": "won",
      "is_current_best": true
    }
  ]
}
```

### フィールド説明:
- `started_at`: 改善処理を開始した時点の ISO タイムスタンプ。
- `skill_name`: 改善対象スキルの名前。
- `current_best`: 最もパフォーマンスが優れていたバージョンの識別子。
- `iterations[].version`: バージョン識別子 (`v0`, `v1`, `v2`, ...)。
- `iterations[].parent`: 派生元となった親バージョン。
- `iterations[].expectation_pass_rate`: アサーション（期待値）の合格率。
- `iterations[].grading_result`: 採点結果のステータス（`"baseline"`, `"won"`, `"lost"`, `"tie"`）。
- `iterations[].is_current_best`: このバージョンが現在のベストバージョンであるかどうか。

---

## 3. grading.json

採点用（グレーダー）エージェントが出力する詳細な評価結果です。各テストケースの実行ディレクトリ `<run-dir>/grading.json` に配置されます。

```json
{
  "expectations": [
    {
      "text": "出力に '田中太郎' という名前が含まれていること",
      "passed": true,
      "evidence": "実行ログのステップ 3 内で検出: '抽出された名前: 田中太郎、佐藤花子'"
    },
    {
      "text": "スプレッドシートのセル B10 に SUM 式があること",
      "passed": false,
      "evidence": "スプレッドシートは生成されませんでした。出力はテキストファイルでした。"
    }
  ],
  "summary": {
    "passed": 2,
    "failed": 1,
    "total": 3,
    "pass_rate": 0.67
  },
  "execution_metrics": {
    "tool_calls": {
      "Read": 5,
      "Write": 2,
      "Bash": 8
    },
    "total_tool_calls": 15,
    "total_steps": 6,
    "errors_encountered": 0,
    "output_chars": 12450,
    "transcript_chars": 3200
  },
  "timing": {
    "executor_duration_seconds": 165.0,
    "grader_duration_seconds": 26.0,
    "total_duration_seconds": 191.0
  },
  "claims": [
    {
      "claim": "フォームには 12 個の入力フィールドが存在する",
      "type": "factual",
      "verified": true,
      "evidence": "field_info.json で 12 個のフィールドを確認"
    }
  ],
  "user_notes_summary": {
    "uncertainties": ["2023年のデータが使用されており、古い可能性があります"],
    "needs_review": [],
    "workarounds": ["入力できないフィールドに対してテキストオーバーレイで代替しました"]
  },
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "出力に '田中太郎' という名前が含まれていること",
        "reason": "名前を捏造して含んだだけの不正なドキュメントでも合格してしまう懸念があります"
      }
    ],
    "overall": "アサーションは存在チェックしか行っておらず、正確性の検証が不十分です。"
  }
}
```

### フィールド説明:
- `expectations[]`: 各アサーションの採点結果（合否判定）と根拠（エビデンス）。
- `summary`: 合格・不合格・総数の集計値。
- `execution_metrics`: ツール呼び出し回数や出力文字数などの実行メトリクス（エグゼキューターの metrics.json から取得）。
- `timing`: 実行にかかった実時間情報（timing.json から取得）。
- `claims`: 出力から抽出および検証された事実主張（事実検証）。
- `user_notes_summary`: 実行中に検出された懸念事項やワークアラウンド。
- `eval_feedback`: （任意）今後のテストケースや評価を改善するためのフィードバック提案。
