# 実装計画：pnpm & tsx を用いた `skill-creator` の初期構築

本計画では、pnpm パッケージマネージャーと tsx 実行環境を使用して、`skill-creator` を開発するためのベース環境（srcフォルダ、パッケージ構成）を構築し、バリデーション機能付きインストーラー（install.ts）を実装します。

## ユーザーレビューが必要な事項

*   **インストーラー依存ライブラリの選定**:
    *   YAML解析のために `js-yaml`、ファイルコピーおよびディレクトリ同期のために `fs-extra` をインストールします。

---

## 提案される変更点

### 1. プロジェクト設定ファイルの作成

#### [NEW] [package.json](file:////wsl.localhost/Ubuntu/home/inoue332/Dev/BitzLabs/BitzSkills/package.json)
*   pnpmで使用するパッケージ定義。
*   `pnpm install-skills` コマンドで `install.ts` を実行できるようにします。
*   依存関係として `js-yaml` と `fs-extra`、開発依存関係として `typescript`, `tsx`, `@types/node`, `@types/js-yaml`, `@types/fs-extra` を定義。

#### [NEW] [tsconfig.json](file:////wsl.localhost/Ubuntu/home/inoue332/Dev/BitzLabs/BitzSkills/tsconfig.json)
*   Node.jsでの実行に適したTypeScriptの基本設定。

---

### 2. ソースファイルおよびテンプレートの作成

#### [NEW] [SKILL.md](file:////wsl.localhost/Ubuntu/home/inoue332/Dev/BitzLabs/BitzSkills/src/skills/skill-creator/SKILL.md)
*   `skill-creator` のメインの指示書。日本語で作成します。
*   Antigravity 2.0 に特化したスキル生成プロセス、500行制限ルール、段階的開示に関するガイドラインを記述します。

#### [NEW] [templates.md](file:////wsl.localhost/Ubuntu/home/inoue332/Dev/BitzLabs/BitzSkills/src/skills/skill-creator/references/templates.md)
*   新しくスキルを作成する際のテンプレート。
    *   最小限の構成テンプレート
    *   外部参照ドキュメント（references/）を含む構成テンプレート

#### [NEW] [step_by_step.md](file:////wsl.localhost/Ubuntu/home/inoue332/Dev/BitzLabs/BitzSkills/src/skills/skill-creator/examples/step_by_step.md)
*   スキルを作成する際の具体的な設計手順・対話の例を記載。

---

### 3. インストーラーの実装

#### [NEW] [install.ts](file:////wsl.localhost/Ubuntu/home/inoue332/Dev/BitzLabs/BitzSkills/install.ts)
*   `src/skills/` 以下のすべてのスキルフォルダを走査します。
*   以下の検証（バリデーション）を実施します：
    1.  `SKILL.md` の冒頭に正しいYAMLフロントマター（`name` と `description`）が存在すること。
    2.  フロントマターを除く本文が 500 行以内であること。
*   検証に合格したスキルを `.agents/skills/<skill_name>/` にコピーします。

---

## 検証計画

### 自動テスト / 動作確認コマンド
1.  **依存関係のインストール**:
    ```bash
    pnpm install
    ```
2.  **インストーラーの実行**:
    ```bash
    pnpm install-skills
    ```
3.  **インストールの結果確認**:
    *   `.agents/skills/skill-creator/` 配下にファイルが正しくコピーされていること。
    *   正しく動作すること（バリデーションでエラーが出ないこと）。
4.  **検証のテスト（エラー時）**:
    *   意図的に `src/skills/skill-creator/SKILL.md` の本文を500行以上に増やしたり、フロントマターを削除したりして、インストーラーが適切にエラーを吐くことを確認。
