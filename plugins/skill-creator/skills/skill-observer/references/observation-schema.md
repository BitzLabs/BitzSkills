# 観察ログスキーマ

`skill-observer` が書き、`skill-improver` が読む観察ログの正式な書式。
このファイルが書式の正典。変更する場合は observer / improver の両方の
整合を確認し、version を bump すること。

## 保存先

```
<プロジェクトルート>/evals/observations/observations.jsonl
```

- 1行 = 1観察の JSON（JSONL形式）。整形（複数行JSON）は禁止
- 追記のみ。既存行の書き換えは `skill-improver` の status 更新だけに限る
- 主な収集場所は BitzSkills リポジトリでの開発作業。他プロジェクトで
  記録された observations.jsonl は、`skill-improver` の Ingest 時に
  BitzSkills 側へ行単位で連結（cat >>）して統合できる

## フィールド定義

| フィールド | 必須 | 値 | 説明 |
| --- | --- | --- | --- |
| `ts` | ✅ | ISO 8601 文字列 | 観察日時（例: `"2026-07-07T14:30:00+09:00"`） |
| `skill` | ✅ | スキル名 | 観察対象スキルの `name`（例: `"skill-tester"`） |
| `project` | ✅ | 文字列 | 実行していたプロジェクト名（リポジトリ名。なければディレクトリ名） |
| `outcome` | ✅ | `"partial"` \| `"fail"` | success は記録しないため、この2値のみ |
| `severity` | ✅ | `"critical"` \| `"high"` \| `"medium"` \| `"low"` | 下の基準を参照 |
| `step` | ✅ | 文字列 | 問題が起きたステップ（SKILL.md の見出し名。例: `"3. 観察ログへの追記"`。特定できなければ `"(全体)"`） |
| `observation` | ✅ | 文字列 | 起きた事実。解釈・言い訳を書かない |
| `suggested_fix` | ✅ | 文字列 | スキル名・ステップ・変更内容まで特定した具体的な修正案 |
| `status` | ✅ | `"open"` \| `"resolved"` \| `"wontfix"` | observer は常に `"open"` で記録。更新は improver のみが行う |
| `resolved_by` | 任意 | 文字列 | improver が status 更新時に記入（日付と対応の要旨） |

## severity 基準

- **critical**: スキルの指示に従うと誤った結果・破壊的な操作につながる
- **high**: 主要な成果物が作れない、またはワークフローが進行不能になる
- **medium**: 回避策で完了できたが、手戻り・迷い・ユーザーの訂正が発生した
- **low**: 完了に支障はないが、記述の不明瞭さ・改善余地に気づいた

## 記入例

```jsonl
{"ts":"2026-07-07T14:30:00+09:00","skill":"skill-tester","project":"BitzSkills","outcome":"partial","severity":"medium","step":"3. 実行","observation":"ベースライン実行の保存先が cases.md からは読み取れず、runs/ 直下とrun番号付きのどちらか迷った","suggested_fix":"skill-tester の Step 3 に「ベースラインも runs/<n>/ に1実行1ディレクトリで保存する」と明記する","status":"open"}
{"ts":"2026-07-07T15:02:00+09:00","skill":"skill-packager","project":"my-app","outcome":"fail","severity":"high","step":"インストール","observation":"Antigravity のワークスペース配置パスが実環境と異なりコピーが失敗した","suggested_fix":"skill-packager の platform-paths.md の Antigravity ワークスペース行を実測パスに修正する","status":"open"}
```

## 書き方の注意

- **observation は事実のみ**: 「〜だった」で終わる記述にする。
  悪い例: 「仕様が分かりにくいと思う」／良い例: 「Step 2 の『対象を特定』が
  ファイルパス指定かスキル名指定か判別できず、ユーザーに聞き直した」
- **suggested_fix は1観察1提案**: 複数の修正案があるなら観察を分けて複数行にする
- **JSON エスケープ**: observation / suggested_fix に `"` や改行を含めない
  （改行は「。」で区切った1行の文にする）
- **シェルからの追記例**:

```bash
mkdir -p evals/observations
cat >> evals/observations/observations.jsonl << 'EOF'
{"ts":"...","skill":"...","project":"...","outcome":"partial","severity":"medium","step":"...","observation":"...","suggested_fix":"...","status":"open"}
EOF
```
