# Antigravity Skill Development Rules

When generating or editing skills for Antigravity, you MUST adhere to the following rules:

1. **Length Constraint**: `SKILL.md` must be kept concise and strictly under 500 lines. If the logic exceeds this, you must extract detailed instructions into `references/<topic>.md` and reference them from the main `SKILL.md`.
2. **Pushy Descriptions**: The `description` field in the YAML frontmatter is the primary trigger mechanism. It must explicitly state *what* the skill does and *when* to use it. Be slightly "pushy" to ensure the model uses it when appropriate. (e.g. "Make sure to use this skill whenever the user mentions X, even if they don't explicitly ask for Y.")
3. **Progressive Disclosure**: Antigravity uses a three-level loading system:
   - Level 1: Metadata (`name` and `description`) - always in context.
   - Level 2: `SKILL.md` body - loaded when triggered.
   - Level 3: Bundled resources (`scripts/`, `references/`) - read explicitly via tools when needed.
4. **Imperative Tone**: Use imperative verbs for instructions (e.g., "Do X", "Create Y").
5. **No Harmful Content**: Skills must not contain malware, exploit code, or any content that could compromise security.
6. **Default Location**: Newly created skills should default to the workspace root (`.agents/skills/<skill_name>/`) unless the user explicitly requests global placement.
