"""Reviewed Context Digest vectors and reference computation A.

This is fixture-side reference material for Step 0B, not a Core implementation.
It holds the fixed input corpus, the independently reviewed digest input for each
fixture, and one RFC 8785 serializer. Reference B lives in digest_crosscheck and
derives the same bytes from the input tree, so agreement is evidence rather than a
restatement of one construction.
"""
import hashlib

# --- fixed single-workspace corpus -------------------------------------------------

CONFIG_PATH = ".spec/bitz.yaml"
REQ_PATH = ".spec/requirements/REQ-001.md"
TECH_PATH = ".spec/technical/TECH-001.md"
ADR_PATH = ".spec/decisions/ADR-001.md"

CONFIG = (
    'schemaVersion: "1.0"\n'
    "language: ja\n"
    'earsAi: "1.0"\n'
    "verify:\n"
    "  commands:\n"
    "    default:\n"
    '      argv: ["/bin/true", "{tests}"]\n'
    "      cwd: .\n"
)

REQ_HEAD = "---\nid: REQ-001\ntitle: 認証Contextの基準\nstatus: approved\n---\n"
REQ_BODY = (
    "# REQ-001 認証Contextの基準\n"
    "\n"
    "## Intent\n"
    "\n"
    "Digest goldenの固定要求を定義する。\n"
    "\n"
    "## Acceptance Criteria\n"
    "\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
    "- [REQ-001:AC-02] [ACTOR:TargetSystem] [WHEN] 保存した場合 [SHOULD] [REASON] 確認のため [THEN] 結果を返す。\n"
    "\n"
    "## Verification\n"
    "\n"
    "tests/test_auth.pyとtests/test_session.pyで確認する。\n"
)
# Only the blank-line count differs; every other byte of the body is identical.
REQ_BODY_BLANK_LINES = REQ_BODY.replace(
    "\n\n## Acceptance Criteria\n", "\n\n\n## Acceptance Criteria\n", 1)

TECH_HEAD_FIELDS = (
    "id: TECH-001\n"
    "title: 認証の実装方針\n"
    "status: approved\n"
    "relations:\n"
    "  refines: [REQ-001]\n"
    "  related: [ADR-001]\n"
    "implements: [src/auth.py, src/session.py]\n"
    "tests:\n"
    "  - path: tests/test_auth.py\n"
    "    covers: [REQ-001:AC-01]\n"
    "    command: default\n"
    "  - path: tests/test_session.py\n"
    "    covers: [REQ-001:AC-02]\n"
    "    command: default\n"
)
TECH_BODY = (
    "# TECH-001 認証の実装方針\n"
    "\n"
    "## Context\n"
    "\n"
    "規範文を持たない実装方針。\n"
    "\n"
    "| 項目 | 値 |\n"
    "|---|---|\n"
    "| 方式 | token |\n"
)
# Only the table padding differs; cell text and row order are identical.
TECH_BODY_TABLE_PADDING = TECH_BODY.replace(
    "| 項目 | 値 |\n|---|---|\n| 方式 | token |\n",
    "| 項目 | 値    |\n| ---- | ----- |\n| 方式 | token |\n", 1)

ADR_DOCUMENT = (
    "---\nid: ADR-001\ntitle: 認証方式の選定\nstatus: accepted\n---\n"
    "\n# ADR-001 認証方式の選定\n"
    "\n## Context\n\n判断の背景。\n"
    "\n## Decision\n\ntoken方式を採用する。\n"
    "\n## Consequences\n\n規範契約はREQへ置く。\n"
)
CODE_FILES = {
    "src/auth.py": "def authenticate():\n    return True\n",
    "src/session.py": "def open_session():\n    return True\n",
    "tests/test_auth.py": "def test_authenticate():\n    assert True\n",
    "tests/test_session.py": "def test_open_session():\n    assert True\n",
}

# fixture id -> (argv tail after the root, REQ body, TECH body, x-owners value)
CASES = {
    "SINGLE-042": ([], REQ_BODY, TECH_BODY, "team-auth"),
    "SINGLE-043-01": (["--detail", "full"], REQ_BODY, TECH_BODY, "team-auth"),
    "SINGLE-043-02": (["--expand", "TECH-001"], REQ_BODY, TECH_BODY, "team-auth"),
    "SINGLE-044-01": ([], REQ_BODY_BLANK_LINES, TECH_BODY, "team-auth"),
    "SINGLE-044-02": ([], REQ_BODY, TECH_BODY_TABLE_PADDING, "team-auth"),
    "SINGLE-045": ([], REQ_BODY, TECH_BODY, "team-platform"),
    "SINGLE-127-03": (["--expand", "TECH-001", "--expand", "REQ-001"], REQ_BODY, TECH_BODY, "team-auth"),
    "SINGLE-127-04": (["--expand", "TECH-001", "--expand", "TECH-001"], REQ_BODY, TECH_BODY, "team-auth"),
}
DESCRIPTIONS = {
    "SINGLE-042": "固定入力の完全解決に対する単一workspace golden Digest",
    "SINGLE-043-01": "detailの変更がDigestとresolutionを変えない",
    "SINGLE-043-02": "expandの変更がDigestとresolutionを変えない",
    "SINGLE-044-01": "本文の空行数変更がDigestを変える",
    "SINGLE-044-02": "表の桁揃え変更がDigestを変える",
    "SINGLE-045": "x-拡張fieldの変更がDigestを変えない",
    "SINGLE-127-03": "異なるexpand値を反復し、入力順に依存せず正規ID辞書順で返す",
    "SINGLE-127-04": "同じexpand値を反復し、1件へ重複排除する",
}
# Escaped text is reviewed as literal input and literal semantic value separately.
ESCAPED_TEXT = r'記号 \[ \] \\ \` \" を保持する'
DECODED_TEXT = '記号 [ ] \\ ` " を保持する'
ESCAPED_BODY = REQ_BODY.replace("秘密情報を出力しない", ESCAPED_TEXT)
CASES["SINGLE-097-01"] = ([], ESCAPED_BODY, TECH_BODY, "team-auth")
DESCRIPTIONS["SINGLE-097-01"] = "textの5種類の既知escapeを各1 code pointへ解除する"

# These matrix dimensions deliberately reuse the golden corpus: its second
# statement has a non-null SHOULD reason, and its full documents exercise the
# projection schema without changing semantic resolution.
for identifier, tail, description in (
    ("SINGLE-101-01", [], "理由付きSHOULDのreasonと完全Digest材料を比較する"),
    ("SINGLE-106-01", ["--detail", "full"], "full projectionの必須fieldと禁止fieldを検証する"),
    ("SINGLE-121", [], "固定Digest入力のdigestVersionとresolverVersionを検証する"),
):
    CASES[identifier] = (tail, REQ_BODY, TECH_BODY, "team-auth")
    DESCRIPTIONS[identifier] = description

# A distance-two refinement exercises normative presentation without adding
# statements, paths, commands or another independent condition.
NORMATIVE_PATH = ".spec/technical/TECH-002.md"
NORMATIVE_BODY = "# TECH-002 間接の具体化\n\n## Context\n\n直接の実装方針をさらに具体化する。\n"
NORMATIVE_HEAD = "---\nid: TECH-002\ntitle: 間接の具体化\nstatus: approved\nrelations:\n  refines: [TECH-001]\n---\n\n"
CASES["SINGLE-106-02"] = ([], REQ_BODY, TECH_BODY, "team-auth")
DESCRIPTIONS["SINGLE-106-02"] = "距離2のrefinementをnormativeで提示し禁止fieldを省略する"

# Fixtures whose digest input is byte-identical to the golden.
SAME_AS_GOLDEN = ("SINGLE-042", "SINGLE-043-01", "SINGLE-043-02", "SINGLE-045", "SINGLE-127-03", "SINGLE-127-04", "SINGLE-101-01", "SINGLE-106-01", "SINGLE-121")


def reviewed_inputs(identifier):
    _, req_body, tech_body, owners = CASES[identifier]
    tech = "---\n" + TECH_HEAD_FIELDS + f"x-owners: [{owners}]\n---\n\n" + tech_body
    return {
        **({NORMATIVE_PATH: (NORMATIVE_HEAD + NORMATIVE_BODY).encode()}
           if identifier == "SINGLE-106-02" else {}),
        CONFIG_PATH: CONFIG.encode(),
        REQ_PATH: (REQ_HEAD + "\n" + req_body).encode(),
        TECH_PATH: tech.encode(),
        ADR_PATH: ADR_DOCUMENT.encode(),
        **{path: text.encode() for path, text in CODE_FILES.items()},
    }


# --- reviewed digest input (reference A) -------------------------------------------

STATEMENTS = [
    {
        "id": "REQ-001:AC-01",
        "actor": "TargetSystem",
        "activation": {"kind": "ALWAYS", "text": None},
        "modality": "MUST",
        "reason": None,
        "operation": {"kind": "CONSTRAINT", "text": "秘密情報を出力しない"},
        "extensions": [],
    },
    {
        "id": "REQ-001:AC-02",
        "actor": "TargetSystem",
        "activation": {"kind": "WHEN", "text": "保存した場合"},
        "modality": "SHOULD",
        "reason": "確認のため",
        "operation": {"kind": "THEN", "text": "結果を返す"},
        "extensions": [],
    },
]
EMPTY_RELATIONS = {"requires": [], "refines": [], "addresses": [], "supersedes": [], "related": []}


def reviewed_digest_input(identifier):
    _, req_body, tech_body, _ = CASES[identifier]
    statements = [dict(statement) for statement in STATEMENTS]
    if identifier == "SINGLE-097-01":
        statements[0] = {**statements[0], "operation": {"kind": "CONSTRAINT", "text": DECODED_TEXT}}
    result = {
        "digestVersion": "1.0",
        "specSchemaVersion": "1.0",
        "earsAiVersion": "1.0",
        "resolverVersion": "1.0",
        "purpose": "verify",
        "requestWorkspaceId": "root",
        "roots": ["REQ-001"],
        "workspaces": [{"id": "root", "path": "."}],
        "documents": [
            {
                "id": "REQ-001",
                "workspaceId": "root",
                "kind": "requirement",
                "status": "approved",
                "applicability": "applicable",
                "frontmatter": {
                    "id": "REQ-001",
                    "title": "認証Contextの基準",
                    "status": "approved",
                    "relations": dict(EMPTY_RELATIONS),
                    "implements": [],
                    "tests": [],
                    "verify": None,
                    "changes": [],
                },
                "bodyText": req_body,
                "statements": statements,
                "strongRelations": [],
            },
            {
                "id": "TECH-001",
                "workspaceId": "root",
                "kind": "technical",
                "status": "approved",
                "applicability": "applicable",
                "frontmatter": {
                    "id": "TECH-001",
                    "title": "認証の実装方針",
                    "status": "approved",
                    "relations": {**EMPTY_RELATIONS, "refines": ["REQ-001"], "related": ["ADR-001"]},
                    "implements": ["src/auth.py", "src/session.py"],
                    "tests": [
                        {"path": "tests/test_auth.py", "covers": ["REQ-001:AC-01"], "command": "default"},
                        {"path": "tests/test_session.py", "covers": ["REQ-001:AC-02"], "command": "default"},
                    ],
                    "verify": None,
                    "changes": [],
                },
                "bodyText": tech_body,
                "statements": [],
                "strongRelations": [{"relation": "refines", "target": "REQ-001"}],
            },
        ],
        "crossWorkspaceEdges": [],
        "settings": {
            "workspaces": [{"id": "root", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"}],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [{"workspaceId": "root", "timeoutSeconds": 300}],
            "commands": [
                {"workspaceId": "root", "name": "default", "argv": ["/bin/true", "{tests}"], "cwd": "."}
            ],
        },
    }

    if identifier == "SINGLE-106-02":
        result["documents"].append({
            "id": "TECH-002", "workspaceId": "root", "kind": "technical", "status": "approved",
            "applicability": "applicable",
            "frontmatter": {"id": "TECH-002", "title": "間接の具体化", "status": "approved",
                            "relations": {**EMPTY_RELATIONS, "refines": ["TECH-001"]},
                            "implements": [], "tests": [], "verify": None, "changes": []},
            "bodyText": NORMATIVE_BODY, "statements": [],
            "strongRelations": [{"relation": "refines", "target": "TECH-001"}],
        })
    return result


# --- RFC 8785 serializer (reference A) ---------------------------------------------

ESCAPES = {0x08: "\\b", 0x09: "\\t", 0x0A: "\\n", 0x0C: "\\f", 0x0D: "\\r",
           0x22: '\\"', 0x5C: "\\\\"}


def _string(value):
    out = ['"']
    for character in value:
        point = ord(character)
        if point in ESCAPES:
            out.append(ESCAPES[point])
        elif point < 0x20:
            out.append(f"\\u{point:04x}")
        else:
            out.append(character)
    out.append('"')
    return "".join(out)


def _serialize(value):
    if value is None:
        return "null"
    if value is True or value is False:
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if isinstance(value, dict):
        # RFC 8785 orders members by their UTF-16 code unit sequence; comparing
        # UTF-16BE bytes is the same ordering for every well-formed key.
        keys = sorted(value, key=lambda key: key.encode("utf-16-be"))
        return "{" + ",".join(_string(key) + ":" + _serialize(value[key]) for key in keys) + "}"
    raise TypeError(f"digest input holds an unsupported value: {type(value).__name__}")


def canonical_bytes(value):
    return _serialize(value).encode("utf-8")


def digest(canonical):
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
