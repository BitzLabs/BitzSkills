#!/bin/bash
# SessionStart フックの例: プロジェクトコンテキストの読み込み
# プロジェクト種別を検出して環境変数を設定する

set -euo pipefail

# プロジェクトディレクトリへ移動
cd "$CLAUDE_PROJECT_DIR" || exit 1

echo "プロジェクトコンテキストを読み込み中..."

# プロジェクト種別を検出して環境変数を設定
if [ -f "package.json" ]; then
  echo "📦 Node.js プロジェクトを検出"
  echo "export PROJECT_TYPE=nodejs" >> "$CLAUDE_ENV_FILE"

  # TypeScript かどうか確認
  if [ -f "tsconfig.json" ]; then
    echo "export USES_TYPESCRIPT=true" >> "$CLAUDE_ENV_FILE"
  fi

elif [ -f "Cargo.toml" ]; then
  echo "🦀 Rust プロジェクトを検出"
  echo "export PROJECT_TYPE=rust" >> "$CLAUDE_ENV_FILE"

elif [ -f "go.mod" ]; then
  echo "🐹 Go プロジェクトを検出"
  echo "export PROJECT_TYPE=go" >> "$CLAUDE_ENV_FILE"

elif [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
  echo "🐍 Python プロジェクトを検出"
  echo "export PROJECT_TYPE=python" >> "$CLAUDE_ENV_FILE"

elif [ -f "pom.xml" ]; then
  echo "☕ Java (Maven) プロジェクトを検出"
  echo "export PROJECT_TYPE=java" >> "$CLAUDE_ENV_FILE"
  echo "export BUILD_SYSTEM=maven" >> "$CLAUDE_ENV_FILE"

elif [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then
  echo "☕ Java/Kotlin (Gradle) プロジェクトを検出"
  echo "export PROJECT_TYPE=java" >> "$CLAUDE_ENV_FILE"
  echo "export BUILD_SYSTEM=gradle" >> "$CLAUDE_ENV_FILE"

else
  echo "❓ 不明なプロジェクト種別"
  echo "export PROJECT_TYPE=unknown" >> "$CLAUDE_ENV_FILE"
fi

# CI設定の有無を確認
if [ -f ".github/workflows" ] || [ -f ".gitlab-ci.yml" ] || [ -f ".circleci/config.yml" ]; then
  echo "export HAS_CI=true" >> "$CLAUDE_ENV_FILE"
fi

echo "プロジェクトコンテキストの読み込みが完了しました"
exit 0
