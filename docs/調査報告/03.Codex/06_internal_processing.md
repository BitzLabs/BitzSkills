# 6. 内部処理とアーキテクチャ詳細 (Internal Processing)

本章は、OpenAI Codex CLI / SDK の内部動作を、2026年7月時点の公式ドキュメント（developers.openai.com/codex、openai/codex GitHub、OpenAI Blog）で裏取りした内容に基づいて解説します。過去の資料に混在していた誤解や旧称を整理し、Codex の実際の動作に直結する構造に絞って説明します。

---

## 6.1 AGENTS.md の探索・マージ・再読込アルゴリズム

Codex は起動ごと（TUI では通常セッション開始ごと）に指示チェーンを再構築します。

1. **グローバル**: `$CODEX_HOME`（既定 `~/.codex`）直下に `AGENTS.override.md` があればそれを、なければ `AGENTS.md` を読む（1階層につき1ファイルのみ）。
2. **プロジェクト**: Git ルートから現在の作業ディレクトリまで各階層を下りながら、`AGENTS.override.md` → `AGENTS.md` → `project_doc_fallback_filenames` の順で1ファイルを採用。
3. **マージ**: ルートから近い方へ空行区切りで連結。**現在ディレクトリに近いファイルほど後方に配置され、実質的に優先される**（「上書き」ではなく「プロンプト内の後方配置による優先」）。
4. `project_doc_max_bytes`（既定 **32KiB**）に達すると以降のファイル追加を打ち切る。カスタムファイル名（例 `TEAM_GUIDE.md`）は `project_doc_fallback_filenames` に登録すれば認識される。
5. キャッシュは存在せず、再起動のたびに再構築される。監査は `~/.codex/log/codex-tui.log` または `session-*.jsonl` で可能。

なお、既存4章が述べた「`PostCompact` 時に AGENTS.md の重要指示が自動再注入される」という個別動作は一次情報で確認できませんでした（要確認）。ただし `PostCompact` は Hooks の対応イベントとして実在するため、フック経由でのコンテキスト補完は可能です。

---

## 6.2 コンテキスト管理・コンパクション

`model_auto_compact_token_limit`（未設定時はモデル既定値）でトークン閾値に達すると自動コンパクションが走ります。`compact_prompt` / `experimental_compact_prompt_file` でコンパクション用プロンプトを上書きできます。AGENTS.md はセッション開始時に一度構築されシステムプロンプト相当の位置に固定されるため、コンパクションによって失われにくい設計です。

---

## 6.3 サブエージェントと context rot 対策

OpenAI が Subagents の導入理由として明示するのは、"context pollution"（有用な情報がノイズに埋もれる）と "context rot"（会話が長くなるほど性能が劣化する現象）への対策です。設計原則は次のとおりです。

メインスレッドは要件・意思決定・最終成果物に集中させ、探索・テスト実行・ログ解析などノイズの多い作業をサブエージェントに逃がし、**要約のみ**をメインに持ち帰らせます。読み取り主体（探索・テスト・トリアージ）の並列化は推奨される一方、書き込み主体の並列化は競合リスクがあるため慎重に、と公式が明記しています。

> [!IMPORTANT]
> 既存4章の「エージェントが自律的に複雑と判断してサブエージェントを起動する」という説明、および内部ツール名 `delegate_to_subagent` は**いずれも不正確**です。正しくは、`features.multi_agent`（既定有効）が公開する実ツールは **`spawn_agent` / `send_input` / `resume_agent` / `wait_agent` / `close_agent`** であり、Codex はサブエージェントを**自動起動せず**、ユーザーが明示的に並列実行を要求した場合にのみ動作します。設定は `agents.max_depth`（既定1）、`agents.max_threads`（既定6）、`agents.job_max_runtime_seconds`（既定1800秒）。

---

## 6.4 サンドボックス承認フローと Auto-review

既存章に無い機能として **`approvals_reviewer`**（`user` | `auto_review`）が存在します。`auto_review` を指定すると、承認プロンプトを人間ではなく **レビュアー・サブエージェント** が自動判定します（サンドボックスエスケープ要求・ネットワークブロック・破壊的ツール呼び出し等が対象、サンドボックス内で既に許可されている操作には介入しません）。`auto_review.policy` で Markdown によるローカルポリシーを注入できます。

さらに `codex execpolicy check --rules <file>` という実験的コマンドで、コマンドプレフィックス単位に allow/prompt/deny を機械的に判定できます。AGENTS.md の「お願いベース」の指示とは別レイヤーの、確実性の高い制御手段です。

---

## 6.5 ネットワーク制御の実態

サンドボックス下のネットワークは `features.network_proxy` サブシステムで制御されます。`domains` マップで `example.com`（完全一致）/ `*.example.com`（サブドメインのみ）/ `**.example.com`（親＋サブ）/ `*`（全許可、非推奨）のワイルドカードを allow/deny 指定でき、**deny が常に allow より優先**されます。SOCKS5・アップストリームプロキシ連鎖等も設定可能です。既定ではネットワークは未設定＝**外部宛先は一切許可されません**。
