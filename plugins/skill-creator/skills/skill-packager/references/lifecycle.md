# ライフサイクル管理リファレンス

`skill-packager` がインストール・バージョンアップ・アンインストールで使う
手順とフィールド定義の詳細。ライブラリ側のmetadata規約（version等）は
`skill-creator` の `references/spec.md` が正。

## frontmatterフィールド

### ライブラリ側（skill-creator/optimizerが管理。packagerは書き換えない）

```yaml
metadata:
  version: "1.2.0"      # semver。変更のたびにbumpされる
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-05"
```

### 配置先のみ（packagerがコピー配置時に追記する）

```yaml
metadata:
  # ...ライブラリ側のフィールドはそのまま維持...
  installed-at: "2026-07-05"                  # インストール（更新）日
  installed-from: /home/hide/Dev/BitzSkills   # ライブラリの絶対パス
```

- `installed-*` を**ライブラリ側のSKILL.mdに書いてはならない**
  （書いてあったら手動コピーの痕跡。validatorが検出する）
- シンボリックリンク配置ではstampしない（ライブラリと同一ファイルのため）

## stampの手順（コピー配置時）

1. フォルダごと配置先へコピーする
2. **配置先の** SKILL.mdのfrontmatterの `metadata:` マップに `installed-at` と
   `installed-from` の2行を追記する（YAMLのインデントは既存の
   `version` 等と同じ2スペースに揃える）
3. 追記後のfrontmatterがYAMLとしてパースできることを確認する

## semver比較の手順

1. 両方の `metadata.version` を `X.Y.Z` の3整数に分解する
2. major → minor → patch の順に数値として比較する（文字列比較しない。
   `0.10.0` は `0.9.0` より新しい）
3. どちらかのversionが欠落・不正形式の場合は比較不能。ユーザーに状態を示して
   判断を仰ぐ

## バージョンアップ時の安全判定

配置先を上書きしてよいのは、次の**すべて**を満たすときだけ。

| 確認項目 | 満たさない場合 |
| --- | --- |
| 配置先の `installed-from` がこのライブラリを指す | 他所由来。上書きせず報告 |
| 配置先version < ライブラリversion | 同じなら何もしない。配置先が新しいなら停止して報告 |
| 配置先に直接編集の形跡がない | 停止。差分を示し、ライブラリへ取り込むか破棄するか確認 |

「直接編集の形跡」の判定: 配置先の `version` と同じバージョンのライブラリ側
内容と本文が一致するかで判断する。過去バージョンが残っていない場合は、
`installed-at` 以降に配置先ファイルの更新日時が新しくなっていないか
（`ls -l` 等）を目安にし、確信が持てなければユーザーに確認する。

### 責務境界（プラグインの update マイグレーションとの関係）

本節の安全判定が規定するのは**スキルファイル自体の置き換え可否**のみ。置き換え後
（または置き換えに伴って）必要になる**配置先の状態・設定の形式変換**（frontmatter
スキーマ・`.spec` 系書式・`.claude/<plugin>.local.md` 等の移行）は、各プラグインの
`<plugin名>:update` が持つマイグレーション機構が担う（規約は plugin-creator の
`plugin-structure/references/migration-steps.md` が正。バージョン軸もスキル単位の
`metadata.version` ではなくプラグイン version で別管理）。packager 側では規定しない
（二重規定の禁止）。

## 操作チェックリスト

### インストール
- [ ] ライブラリ側に `metadata.version` がある
- [ ] 配置先に同名フォルダが存在しない（存在したら停止）
- [ ] コピー後にstamp、YAMLパース確認
- [ ] 配置先の `SKILL.md` が読めることを確認して報告

### バージョンアップ
- [ ] 両側のversionを読み、semver比較
- [ ] 安全判定3項目をすべて確認
- [ ] 変更点の要約を提示して承諾を得る
- [ ] 入れ替え後に再stamp（`installed-at` を当日に更新）

### アンインストール
- [ ] 配置先frontmatterの name / version / installed-from を提示
- [ ] ライブラリ管理外なら明示して再確認
- [ ] ユーザーの承諾を得てから配置先フォルダのみ削除
- [ ] ライブラリ側に影響がないことを報告
