---
id: SDD-DSN-003
title: "frontmatter境界を保持する本文同期レンダリング"
status: active
version: 1.0
updated: 2026-07-19
owner: codex
implements: SDD-FR-135
origin: SI-SDD-010
---

# SDD-DSN-003 frontmatter境界を保持する本文同期レンダリング

## 背景 / 課題

`.spec` 成果物と `docs` 文書は同じ Markdown でも別の機械契約を持つ。現行の
`sdd_sync.py` は `shutil.copy2` でファイル全体をコピーするため、pull 後の docs 文書に
`CORE-DSC-*` 等の spec ID、`draft`、`1.0` が流入し、`docs_inspect.py --strict` が
`DOC-*`、docs status、SemVer、`changeImpact`、`project_type` の不一致を報告する。
push では逆に docs 固有 frontmatter が `.spec` へ流入し得る。

SI-SDD-012 の日本語6章移行は完了しており、同期先は SDD-FR-126 / 128 で確定済みである。
本設計はパスや検査契約を再変更せず、同期単位を「ファイル全体」から「本文」へ狭める。

## 設計判断

### 1. 文書を frontmatter と本文に分離する

`sdd_sync.py` に、先頭の `---` から閉じ `---` までを frontmatter ブロックとして
抽出し、残りを本文として返す小さなパーサを置く。YAML値の解釈は行わず、保持対象の
frontmatter ブロックはバイト列として扱う。先頭が `---` なのに閉じ delimiter が無い文書は
不正入力として同期前に拒否する。同期元はpull/pushとも有効なfrontmatterを必須とし、
欠如または破損時は同期先を変更しない。

### 2. pull は docs frontmatter を所有し、spec 本文だけを受け取る

- 既存docs文書に有効なfrontmatterがある場合は、そのブロックを無変更で再利用する。
- 同期先が存在しない、またはfrontmatterが無い場合は、スキル同梱の
  `assets/docs-templates/<docs相対パス>` からfrontmatterを取得する。
- 生成frontmatterの `project_type` は `docs/MASTER.md` の有効値
  （`app` / `library` / `both`）へ置換し、MASTERと一致させる。
- MASTERの`project_type`が欠如または統制語彙外なら、strict PASSを保証できないため生成前にエラーにする。
- テンプレートが無い場合は不完全なdocs文書を生成せずエラーにする。
- 出力本文は同期元 `.spec` のfrontmatterを除いた本文とする。

テンプレートをdocsメタデータの正にすることで、`DEFAULT_MAPPING` にID・status・version等を
重複保持しない。同期元の追跡は `DEFAULT_MAPPING` の spec path → docs path 対応を正とし、
現時点では `derived_from` 等の新しいdocs frontmatterキーを追加しない。

### 3. push は spec frontmatter を所有し、docs 本文だけを受け取る

- 既存 `.spec` 文書の有効なfrontmatterを無変更で再利用する。
- 出力本文はdocs frontmatterを除いた本文とする。
- `.spec` 同期先が存在しない、frontmatterが無い、または壊れている場合は、プロジェクト固有IDを
  推測して生成せずエラーにする。これにより `DOC-*` の `.spec` 逆流を防ぐ。

### 4. mtime 契約を維持する

本文レンダリング後、同期先mtimeを同期元mtimeと同値に設定する。これにより、pull直後のpushや
push直後のpullを新しい手動変更と誤認しない。新旧判定そのものはSDD-FR-100の
「新しい側だけを反映し、同値なら更新しない」を維持する。

### 5. 失敗は対象ファイルを変更する前に確定する

同期元・同期先・テンプレートの解析と出力内容の構築を完了してから、同期先と同じディレクトリの
一時ファイルへ書き、`os.replace` でファイル単位に原子的置換する。
frontmatter不正やテンプレート欠如では対象ファイルを変更せず、標準エラーへ理由を出して
プロセスを非0終了させる。他マッピングの成功を隠さないよう成功件数と失敗件数を集計する。

### 6. テスト先行の契約固定

`tests/test_sdd_sync.py` に `SDD-FR-135` を含むテスト名で次を固定する。

1. pullで既存docs frontmatterが保持され、spec本文だけが反映される
2. pullの同期先欠如時に同梱テンプレートfrontmatterが生成され、MASTERのproject_typeと整合する
3. pull後に日本語6章テンプレート全体がstrict PASSする
4. pushでspec frontmatterが保持され、docs本文だけが反映される
5. pull/pushの同期元不正、push先欠如・不正frontmatter、およびpull先の壊れたfrontmatterが無変更で失敗する
6. pull/push完了後のmtimeが同期元と一致する
7. docs側が新しい場合のpull抑止、spec側が新しい場合のpush抑止が維持される

## 代替案と却下理由

- **docs_inspectを緩和してDSC/DSN frontmatterを許容**: docs契約が二重化し、
  日本語6章テンプレートの機械検査価値を失うため却下。
- **specとdocsで共通frontmatterへ統一**: 既存ワークスペースの移行と公開契約変更が大きく、
  SI-SDD-010の表示・同期境界を超えるため却下。
- **マッピング内にdocs frontmatter値を直書き**: テンプレートとの二重定義になるため却下。
- **push先が無い場合にspec IDを自動推定**: プロジェクト固有prefixを安全に決定できず、
  幽霊・重複IDを作り得るため却下。

## 影響範囲・ロールバック

- 実装: `skills/sdd-docs/scripts/sdd_sync.py`
- 回帰テスト: `tests/test_sdd_sync.py`
- 利用手順: `skills/sdd-docs/SKILL.md`
- 仕様証跡: SDD-FR-135、SDD-DSN-003、テスト仕様、タスク、STATE、SI-SDD-010実施記録
- 版管理: sdd-docsスキルのsemverとbitz-sddプラグインのpatch/minorを規約どおり更新

永続DB・ネットワーク・認証情報は扱わない。ロールバックはレンダリング関数と対応テスト・仕様を
同一PRでrevertし、旧raw copyへ戻せる。ただし旧挙動ではstrict不整合が再発することを明記する。
