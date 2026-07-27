---
id: SI-CORE-034
raised_by: 2026-07-27 Codex 実行時に既定の ~/.claude/plugins だけを参照して解決不能となった実例
target: scripts/spec の Claude/Codex 横断プラグイン解決
proposed_change_type: bump
status: accepted
---
- **目的**: `scripts/spec` は `BITZSKILLS_PLUGINS_DIR` 未指定時に
  `~/.claude/plugins` だけを参照するため、Codexへ `bitz-sdd` が正常にインストールされていても
  `$CODEX_HOME/plugins` 配下を解決できない。2026-07-27 のCodex実行では
  `python3 scripts/spec status . --json` が exit 3 で失敗し、
  `BITZSKILLS_PLUGINS_DIR=~/.codex/plugins` を明示すると成功した。Claude Code / Codex CLIを
  正式な配布対象とする本リポで、同じ正規コマンドが実行プラットフォームに依存せず動作するよう
  `CORE-FR-011` の解決契約を拡張する。
- **提案する修正**:
  1. `BITZSKILLS_PLUGINS_DIR` の明示指定を最優先の決定的なoverrideとして維持する。
  2. override未指定時は、Codex CLIが利用可能なら `codex plugin list --json` から
     インストール済みかつ有効な `bitz-sdd@bitzskills` のversion・marketplaceを取得し、
     `${CODEX_HOME:-~/.codex}/plugins/cache` 内の同一versionを固定版として検証・解決する。
  3. CLIが利用不能な場合は `${CODEX_HOME:-~/.codex}/plugins/cache` と
     `~/.claude/plugins/cache` を既知ルートとして探索する。CLIが正常にdisabled /
     uninstalled / no-entryを返した場合は、利用者の無効化を尊重してCodex cacheを探索しない。
     Claude側の
     `installed_plugins.json` にprojectPath一致の固定版がある場合は、現行どおり固定版を優先する。
  4. 複数プラットフォームで固定版が競合する場合や、同一versionでも実体のfingerprintが
     異なる場合は黙って一方を選ばず非ゼロで失敗し、
     `BITZSKILLS_PLUGINS_DIR` による明示指定を案内する。解決不能時は探索したルートと
     暫定回避策をエラーへ含める。
  5. `CORE-FR-011` を1.1へ改版し、Codex-only / Claude-only / 両方存在 / custom
     `CODEX_HOME` / 固定版競合 / 明示overrideの回帰テストを追加する。単体テストは実ユーザーの
     キャッシュへ依存せず、CLI JSONとディレクトリ構造をfixtureで再現する。
- **対象ファイル**: `scripts/spec`、`tests/test_spec_wrapper.py`、
  `.spec/requirements/CORE-FR-011.md`、後続のtask・test-spec、必要に応じて
  `AGENTS.md` / `.spec/PROJECT.md` の正規コマンド説明。bitz-sddプラグイン本体や
  `sdd-doctor` の公開挙動まで変更する場合は、単一関心事を越えるため別の委託issueとして扱う。
- **確認観点**:
  - **既存要件との関係**: SI-CORE-022 / CORE-FR-011の目的と重複するが、既存issueはaccepted、
    要件はverified済みでClaude既定パスの実装として完了している。Codexを第3の配布対象にした
    SI-CORE-024以後に判明した契約不足であるため、既存issueの再利用ではなく要件bumpとして追跡する。
  - **公式契約と内部構造**: `CODEX_HOME` と `codex plugin list --json` を優先し、
    `$CODEX_HOME/plugins/cache` はCLI解決不能時の検証付きfallbackに限定する。
    バージョン番号や一時ディレクトリをハードコードしない。
  - **ガードレール**: 認証情報・トークンを読まず、プラグイン探索は読み取り専用とする。
    解決競合やversion不一致は安全側に停止する。
  - **影響分析**: `spec inspect --impact CORE-FR-011 --check-only` では
    `.spec/tasks/CORE-TSK-012.md`、`tests/test_spec_wrapper.py`、
    `plugins/bitz-sdd/.spec/specs/sdd-plan-issue/test-spec.md` が依存成果物として検出された。
  - **検証**: 新規回帰テスト、既存pytest、`python3 scripts/release_check.py`、
    `python3 scripts/spec inspect --workspace . plugins/* --check-only` をgreenにする。
  - **軽量レーン適否**: **不適**。正規CLIラッパーの公開挙動とverified要件の受入基準を変更するため、
    通常フロー + Design Gateを通す。
- **影響推定・ロールバック**: 影響はルートのSDDツール解決、回帰テスト、CORE-FR-011の
  トレーサビリティに限定する。既存の明示overrideとClaude解決を先に回帰テストで固定し、
  問題時はCodex discovery部分と要件1.1を同一PRでrevertして1.0挙動へ戻せる構成にする。
- **依存**: SI-CORE-022 / CORE-FR-011（既存ラッパー契約）、SI-CORE-024
  （Codexを第3の配布対象に追加）。SI-ENV-023はCodex向けガードレール・env-initの課題であり、
  本issueとは関心事が異なる。
- **裁定結果**: **accepted**（2026-07-27、三ツ井 秀和がチャット指示
  「コミット後に、SI-CORE-034の解決を進めましょう」で裁定）。Codexを正式サポートしながら正規のSDDコマンドが
  環境変数なしでは失敗する状態は、ドッグフーディングと3プラットフォーム契約の両方に反する。
  一方、内部キャッシュ配置だけに依存すると将来のCodex更新で再発するため、公式CLIによる解決を
  優先し、既知パス探索を検証付きfallbackに限定する。無効化の迂回、破損固定版への縮退、
  複数実体の曖昧選択を禁止する安全側停止方針を採用する。
- **実施**: CORE-FR-011 v1.1、DSN-004、ルートラッパー、回帰テスト、test-specへ反映。
  対象25件・全328件・release_check・環境変数なしのCodex実地statusはgreen。
  全workspace inspectは本変更の新規問題0件で、着手前からの既知baselineだけが残る。
