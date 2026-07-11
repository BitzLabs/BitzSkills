# 推奨 permissions セット（env-init が生成する settings.json の根拠）

生成対象は「無害で普遍的な最小集合」に限定する。プロジェクト固有の
allow（スクリプトのパス等）はユーザーと相談して追加する。

## deny（機械ブロック）

| ルール | 根拠 |
| --- | --- |
| `Bash(rm -rf:*)` | 再帰強制削除。復元不能 |
| `Bash(sudo:*)` | 特権昇格。エージェントに不要 |
| `Bash(git push --force:*)` / `Bash(git push -f:*)` | リモート履歴の破壊 |
| `Bash(git reset --hard:*)` | 作業内容の破棄 |
| `Bash(git clean -f:*)` | 未追跡ファイルの削除 |
| `Read(~/.claude/.credentials.json)` | 認証情報の読み取り禁止 |
| `Read(.env)` / `Read(.env.*)` | シークレットの読み取り禁止 |

## ask（要ユーザー承認）

| ルール | 根拠 |
| --- | --- |
| `Bash(git push:*)` | 外部公開はユーザー判断 |

## allow（読み取り系の既定）

`git status/diff/log/branch`、`ls`、`find`、`grep`、`wc` の読み取り系を許可し、
承認プロンプトのノイズを減らす。

## 生成テンプレート

```json
{
  "permissions": {
    "deny": [
      "Bash(rm -rf:*)",
      "Bash(sudo:*)",
      "Bash(git push --force:*)",
      "Bash(git push -f:*)",
      "Bash(git reset --hard:*)",
      "Bash(git clean -f:*)",
      "Read(~/.claude/.credentials.json)",
      "Read(.env)",
      "Read(.env.*)"
    ],
    "ask": [
      "Bash(git push:*)"
    ],
    "allow": [
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git branch:*)",
      "Bash(ls:*)",
      "Bash(find:*)",
      "Bash(grep:*)",
      "Bash(wc:*)"
    ]
  }
}
```

## マージの指針（既存 settings.json がある場合）

- 既存の deny/ask/allow は**削除しない**（緩和はユーザーの明示判断のみ）
- 上記テンプレートとの和集合を提案し、diff を提示して承認を得る
- プラグイン同梱フック（env_guard.py）と重複するのは意図的な二重化
  （permissions はプラグイン無効時も効く恒久層、フックは導入直後から効く即効層）
