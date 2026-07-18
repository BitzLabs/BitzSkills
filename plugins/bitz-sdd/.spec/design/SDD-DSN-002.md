---
id: SDD-DSN-002
title: "日本語6章docsレイアウトと安全な移行"
status: active
version: 1.0
updated: 2026-07-18
owner: codex
implements: SDD-FR-125, SDD-FR-126, SDD-FR-127, SDD-FR-128, SDD-FR-129
origin: SI-SDD-012
---

# SDD-DSN-002 日本語6章docsレイアウトと安全な移行

- **背景 / 課題**:
  - BasicPlanの文書標準は日本語6章を正とする一方、sdd-docsは英語8章を生成・検査・同期する。
    移管時に二重標準と手動パス変換が生じている。
  - 現行パスはSDD-FR-020/030/040/101と回帰テストに固定されているため、直接置換すると
    verified済み契約の履歴を破壊する。
- **設計判断**:
  1. 正規レイアウトは次の必須6章とする。`MASTER.md`、`_conventions.md`、`_scaling.md` は
     ルートの機械・運用文書として名称を維持する。

     | 章 | 機械area | 主な収容内容 |
     |---|---|---|
     | `00_はじめに` | context / governance | ビジョン、スコープ、指標、ペルソナ、用語、統制 |
     | `01_システム仕様` | system | 人間向け機能・非機能・制約の索引（契約SSOTは`.spec/requirements`） |
     | `02_ユースケース` | usecase | UC索引と個別ユースケース（詳細契約はSI-SDD-013） |
     | `03_設計仕様` | design / implementation | architecture、API、data、security、patterns、ADR |
     | `04_テスト仕様` | quality | テスト戦略、品質ゲート、検証方針 |
     | `05_リリース・運用` | operations / knowledge | release、SLO、runbook、postmortem、恒久的教訓 |

  2. `06_リファレンス` は既定生成せず、`MASTER.md` の `optional_chapters: reference` と
     実ディレクトリが一致するときだけ許容する。外部API、CLI/SDKリファレンス、移行ガイドが
     増えたプロジェクト向けの拡張とする。
  3. `excluded_paths` はdocsルート相対のカンマ区切りリテラルパスとし、`..`、絶対パス、
     必須/任意章自身の除外を拒否する。調査・アーカイブをsdd-docs管理外にできるが、
     MASTERレジストリの正式文書にはできない。
  4. 文書IDとfrontmatterキー/値は英語を維持する。旧IDのareaは移動後も安定させるため、
     章とareaは1対1ではなく許容集合で検査する。
  5. 同期マッピングは既存成果物だけを新パスへ移す。Discoveryの不足マッピング追加は
     SI-SDD-011、ユースケース生成はSI-SDD-013、本文とfrontmatterの意味的マージは
     SI-SDD-010の責務として本変更に混ぜない。
  6. 移行CLIはdry-run既定、全件preflight後にのみapplyする。既知ファイルと未知の章内文書を
     章単位で移動し、異内容の移行先があれば原子的に停止する。移動前後とMASTERリンク置換を
     manifestへ記録し、整合確認付きrollbackを提供する。manifestは最初の移動前に`applying`で
     永続化し、各成功操作とcontent hashを逐次記録して、実行時障害でもrollback可能にする。
     完了時だけ`applied`へ更新し、rollbackは移行後hashとの一致を確認してから逆順に戻す。
     旧章は移動完了後に空の場合だけ削除する。
  7. 旧パス固有要件は新要件がgreenになった時点で後継化する。SDD-FR-020→126、
     SDD-FR-030/101→127、SDD-FR-040→128。mtime制御自体のSDD-FR-100は意味を変えない。
- **契約境界**:
  - 変更する契約: docs標準パス、テンプレート、docs検査、同期先、初期化/移行手順。
  - 維持する契約: `.spec` SSOT、pull/push/diff CLI、mtime保護、機械frontmatter、
    project_type、旧文書本文、Discovery/UCの未採用issue境界。
- **代替案と却下理由**:
  - 英語8章を維持してBasicPlanだけ変換する案は、コードリポジトリごとに変換規則を残すため却下。
  - 必須7章としてreferenceを常設する案は、参照資料を持たない小規模appに空章を強制するため却下。
  - 調査報告を第7章へ収容する案は、正式ナラティブと検証済み調査アーカイブのライフサイクルが
    異なるため却下。
  - apply時に旧章を即削除する案はロールバック証跡を失うため、manifest付きmoveを採用する。
- **影響範囲・ロールバック**: sdd-docsテンプレート/2スクリプト/新移行CLI、同期先を記す
  sdd-core/discovery/design/data/ops、回帰テスト、要件とplugin versionを同一リリースで更新する。
  ロールバックは移行CLIのmanifestから利用者文書を旧位置へ戻した後、リリース全体をrevertする。
  docsパスの既定値を変更するため、pluginはsemver majorとしてリリースする。
- **実装順序**: 検査・移行の失敗系テスト → テンプレート → docs_inspect → sdd_sync → migrate_docs →
  スキル/要件/マニフェスト → 全pytest・strict template検査・release_check・spec inspect。
- **Design Gate裁定**: 2026-07-18、SDD-REV-002のPASS（4.62 / 5.00、critical/major 0）を
  根拠に、ユーザーの継続指示によりactive化。リリース済みspec_update.pyはdesignを探索対象に
  含まないため、statusと裁定根拠は本設計へ直接記録した。
