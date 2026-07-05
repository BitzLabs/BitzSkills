---
name: skill-packager
description: エージェントスキルのパッケージ管理を行う。ライブラリから実環境へのインストール（コピー/シンボリックリンク/プラグイン一括）、frontmatterのversion比較によるバージョンアップ、アンインストール、配布（zip化・skill-creatorプラグイン）を担当する。「スキルを配置して」「インストールして」「アップデートして」「アンインストールして」「配布用にまとめて」「プラグインとして入れたい」と言われた場合に使用する。スキルの作成・修正は行わない。
metadata:
  version: "0.3.0"
  author: br7.hide
  created: "2026-07-05"
  updated: "2026-07-05"
---

# skill-packager

## 目的

このリポジトリ（プラグインモノレポ）の `plugins/*/skills/` に置かれたスキルは、
そのままではどのエージェントにも認識されない。ライブラリのスキルを実環境へ
インストールし、以後のバージョンアップ・アンインストールまでを管理する。

インストール状態は配置先SKILL.mdのfrontmatter（`metadata.installed-at` /
`metadata.installed-from`）に記録し、**frontmatterだけで自己完結**させる。
台帳ファイルは使わない。手順の詳細とフィールド定義は
`references/lifecycle.md`、プラットフォーム別の配置パスは
`references/platform-paths.md` を参照。

## どの操作か（decision tree）

- 初めて使えるようにしたい
  - 特定のスキルだけ選んで入れたい → **インストール**（スキル単体の直接配置）
  - このライブラリの7スキルをまとめて入れたい → **プラグイン一括インストール**
    （手順は `references/platform-paths.md` の「プラグインとしての配布」）
- ライブラリ側を更新したので配置先も新しくしたい → **バージョンアップ**
- 使わなくなったので消したい → **アンインストール**
- 他者に渡したい → **配布**
- いま何が入っているか知りたい → **棚卸し**（配置先の各SKILL.mdの
  frontmatterを読み、name / version / installed-at / installed-from を一覧にする）

## インストール

1. 対象スキル・プラットフォーム・スコープ（ワークスペース/グローバル）を確認し、
   `references/platform-paths.md` から配置先を決める
2. ライブラリ側SKILL.mdに `metadata.version` があることを確認する。無ければ
   バージョン管理ができないため、先に `skill-validator` での検証と修正を提案する
3. 方式を確認する
   - **コピー（既定）**: 配置先にフォルダごとコピーし、配置先のfrontmatterに
     `installed-at` / `installed-from` を追記する（手順は lifecycle.md）
   - **シンボリックリンク**: ライブラリと同一ファイルになるためstampは行わない。
     開発中のスキル向け（更新が即反映、バージョンアップ操作も不要）
4. 配置先に同名スキルが既に存在する場合は**上書きせずに停止**し、既存の
   frontmatterを読んで報告する（自分が入れたものなら「バージョンアップ」へ、
   他所由来なら指示を仰ぐ）

## バージョンアップ

1. 配置先とライブラリ両方のSKILL.mdからfrontmatterを読み、
   `metadata.version` を比較する（semver比較の詳細は lifecycle.md）
2. 比較結果ごとの対応:
   - **ライブラリが新しい** → 変更点の要約を提示し、承諾を得てから配置先を
     入れ替えて再stampする
   - **同じ** → 最新である旨を報告して終了
   - **配置先が新しい／配置先に直接編集の形跡がある** → 上書きすると変更が
     失われるため停止し、ユーザーに判断を仰ぐ（lifecycle.mdの判定基準を参照）
3. シンボリックリンク配置の場合はこの操作は不要（その旨を伝える）

## アンインストール

1. 配置先のSKILL.mdのfrontmatterを読み、name / version / installed-from を
   ユーザーに提示する
2. `installed-from` がこのライブラリを指していない、またはstamp自体が無い場合は
   「このライブラリ管理外のスキル」であることを明示して、それでも削除するか
   確認する
3. **削除は必ずユーザーの承諾を得てから**行う。削除するのは配置先のフォルダ
   （またはシンボリックリンク）のみで、ライブラリ側には触れない

## プラグイン一括インストール

このリポジトリはモノレポで、`plugins/skill-creator/` が両プラットフォーム対応の
プラグインになっている（Claude Code: `plugins/skill-creator/.claude-plugin/plugin.json`、
Antigravity 2.0: `plugins/skill-creator/plugin.json`。どちらもプラグイン内 `skills/`
配下の7スキルを読む）。

1. プラットフォームを確認し、`references/platform-paths.md` の
   「プラグインとしての配布」のコマンドを案内・実行する
2. プラグイン導入分は `installed-at` / `installed-from` の stamp を**行わない**
   （バージョン管理はプラットフォーム側とプラグインマニフェストの `version` が担う）
3. 同じスキルが直接配置とプラグインの両方で入ると二重発動の恐れがあるため、
   棚卸しで重複がないか確認し、あれば直接配置側の削除を提案する

## 配布

1. スキルフォルダをそのままzip化する（スキルの親ディレクトリで
   `zip -r skill-name.zip skill-name/`。`zip` コマンドがない環境では
   `python3 -m zipfile -c skill-name.zip skill-name/` で代替）。
   テスト成果物は `evals/` としてリポジトリ直下にありスキルフォルダ外なので、
   除外処理は不要
2. zipを展開すると `skill-name/SKILL.md` の形になることを確認する
3. 生成物のパスと、受け取った側の展開先（platform-paths.mdの表）を報告する
4. 7スキル全部を渡したい場合はzipではなく、リポジトリごと共有して受け取り側で
   プラグインとしてインストールしてもらう方が管理しやすい（その旨を提案する）

## 完了報告

操作内容（インストール/バージョンアップ/アンインストール/配布）、対象パス、
配置先frontmatterの最終状態（version / installed-at / installed-from）を伝える。
