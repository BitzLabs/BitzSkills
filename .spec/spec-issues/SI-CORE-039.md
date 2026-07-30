---
id: SI-CORE-039
raised_by: ROADMAP 順序10 の検証中に実測（2026-07-30）
target: .github/workflows/ci.yml の検証ステップ
proposed_change_type: modify
status: open
---
- **目的**: `AGENTS.md` は「仕様（.spec）検証の正規コマンド」を
  `python3 scripts/spec inspect --workspace . plugins/*` と定めているが、
  **CI はこれを実行していない**。`.github/workflows/ci.yml` の検証ステップは
  `pytest tests/ -v` と `python3 scripts/release_check.py` の2つだけである。

  この欠落により、canonical inspect が FAIL したままの変更が main へマージされた。
  実測（2026-07-30）では PR #146（`ba8bb5a`）以降、ルートと bitz-sdd の2ワークスペースが
  幽霊参照3件で FAIL していたが、CI は緑のままであり、後続の PR #147〜#150 も
  同じ状態のまま通過した。検出は人手のレビュー時に偶然行われた。

  加えて、判定はワークスペースごとに出力されるため、`tail` で末尾だけを見ると
  先行ワークスペースの FAIL を見落とす。人間・エージェントの双方が同じ誤りを起こしうる。

- **提案する修正**:
  1. `.github/workflows/ci.yml` に canonical inspect のステップを追加する。
     コマンドは `AGENTS.md` と同一の
     `python3 scripts/spec inspect --workspace . plugins/*` とし、コマンド文字列を
     CI とドキュメントで二重定義しない方法（スクリプト化またはマーカー照合）を検討する。
  2. CI は作業ツリーを検査する側であるため、`AGENTS.md` の呼び出し規約に従い
     ラッパー `scripts/spec`（固定版のプラグインキャッシュへ委譲する）ではなく
     **リポジトリ内の実体を直接指す**か、ラッパーが作業ツリーを見る保証を確認する。
     ここを誤ると、CI が固定版を検査して作業ツリーの退行を見逃す。
  3. inspect は `.spec/inspection-report.md` を書き換えるため、CI では
     `--check-only` を使うか、生成物の差分を許容する運用を選ぶ。どちらを正とするか裁定する。
  4. 全ワークスペースの判定を集約し、1つでも FAIL なら非ゼロ終了することを確認する
     （現状の終了コードで満たされているかを実測する）。

- **対象ファイル**: `.github/workflows/ci.yml`、`AGENTS.md`（検証義務の節）、
  必要なら `scripts/release_check.py`（inspect を取り込む場合）。

- **確認観点**:
  - 重複: `SI-CORE-023` は canonical コマンドの**引数**（`--workspace . plugins/*` を使う理由）
    を定めた issue であり、CI で実行するかどうかは扱っていない。本 issue は実行箇所の追加。
  - 既存要件との関係: `CORE-FR-011`（ラッパーの解決規約）と衝突しないよう、
    CI からの呼び出しがラッパー経由か実体直接かを明示する。
  - ガードレール: 既存ワークスペースが FAIL する状態で CI へ追加すると、
    無関係な PR まで赤になる。**本 issue の実装前に main を緑へ戻すこと**を前提条件とする。
  - 検証: 意図的に幽霊参照を作った状態で CI が赤くなること、
    緑の状態で通ること、レポート生成物の扱いが決めたとおりであることを確認する。
  - 軽量レーン適否: **可**。CI 設定の追加であり公開契約の変更を伴わない。
    ただし判定の扱い（提案3）は運用に影響するため、裁定を経る。

- **影響推定・ロールバック**: 変更は CI 設定に閉じ、単独 revert できる。
  導入直後に想定外の FAIL が出る場合は、`continue-on-error` での観測期間を挟む選択肢がある。

- **依存**: main の canonical inspect が緑であること（幽霊参照3件の修正）。

- **予備判定（推薦）**: **accept 推奨**。正規と定めた検証が CI に無いことは、
  規約と機械強制の乖離そのものであり、実際に4つの PR が赤い main の上で緑と表示された。
  提案3（レポート生成物の扱い）だけは実測してから決めるのが安全である。
