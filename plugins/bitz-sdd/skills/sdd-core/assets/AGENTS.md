# AGENTS.md（BitzSDD v1.0 準拠）
1. **読み込みプロトコル**: 起動時 PROJECT.md → 担当タスク → implements が指す要件のみ。docs/ 全読み禁止
2. **権限**: requirements/ と docs/ への書き込み禁止（提案は spec-issues/ へ）。実装は担当タスクの boundary 内のみ
3. **失敗時**: code-bug はリトライ2回まで / spec-bug はリトライ禁止・spec-issue 起票 / env は再実行1回
4. **採番**: 実装中の採番禁止。仮番号 SI-<branch>-<n> で起票
5. **検証**: 通すために仕様・テスト・閾値を緩めない。判定は spec_inspect.py と CI に従う
6. **ツールアダプタ**: CLAUDE.md / rules.md / .cursorrules は本ファイルへの参照のみ（内容複製禁止）
