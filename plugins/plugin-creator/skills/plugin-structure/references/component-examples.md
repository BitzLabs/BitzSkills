# コンポーネント配置のコード例

## skills/ のフォルダ構成例

```
skills/
└── api-testing/
    ├── SKILL.md
    ├── scripts/test-runner.py
    └── references/api-spec.md
```

## hooks/hooks.json の例

```json
{
  "PreToolUse": [{
    "matcher": "Write|Edit",
    "hooks": [{
      "type": "command",
      "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate.sh",
      "timeout": 30
    }]
  }]
}
```
