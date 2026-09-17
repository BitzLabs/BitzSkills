"""review済みの複合workspace corpusと参照計算A。

Step 0Bのfixture側の参照材料であり、Coreの実装ではない。root workspace 1件とmember 2件からなる
固定corpus、fixtureごとに独立にreviewしたDigest材料、単一workspaceと同じRFC 8785 serializerを持つ。
参照計算Bはmulti_crosscheckにあり、同じbyte列を入力treeから導出する。

corpusは、横断`refines`と横断coverageを持ち、2つのmemberが同じlocal ID `TECH-010`を使う。
そのため、修飾IDの解決、workspace境界を越えるedge、到達workspaceだけの設定射影を1つの入力で固定できる。
"""
from . import digest_reference

# --- 固定した複合workspaceのcorpus -------------------------------------------------

ROOT_ID = "platform"
MEMBERS = (("api", "services/api"), ("web", "apps/web"))
ROOT_CONFIG_PATH = ".spec/bitz.yaml"
ROOT_REQ_PATH = ".spec/requirements/REQ-001.md"
WEB_CONFIG_PATH = "apps/web/.spec/bitz.yaml"
WEB_TECH_PATH = "apps/web/.spec/technical/TECH-010.md"
API_CONFIG_PATH = "services/api/.spec/bitz.yaml"
API_TECH_PATH = "services/api/.spec/technical/TECH-010.md"

# catalogの列挙順はweb、apiとし、結果と材料のworkspace順がID辞書順であることを固定する。
ROOT_CONFIG = (
    'schemaVersion: "1.0"\n'
    "language: ja\n"
    'earsAi: "1.0"\n'
    "workspace:\n"
    "  id: platform\n"
    "multiWorkspace:\n"
    "  members:\n"
    "    - id: web\n"
    "      path: apps/web\n"
    "    - id: api\n"
    "      path: services/api\n"
)


def member_config(workspace_id, command):
    return (
        'schemaVersion: "1.0"\n'
        "language: ja\n"
        'earsAi: "1.0"\n'
        "workspace:\n"
        f"  id: {workspace_id}\n"
        "verify:\n"
        "  commands:\n"
        f"    {command}:\n"
        '      argv: ["/bin/true", "{tests}"]\n'
        "      cwd: .\n"
    )


WEB_CONFIG = member_config("web", "frontend")
API_CONFIG = member_config("api", "backend")

REQ_HEAD = "---\nid: REQ-001\ntitle: 認証Contextの基準\nstatus: approved\n---\n"
REQ_BODY = (
    "# REQ-001 認証Contextの基準\n"
    "\n"
    "## Intent\n"
    "\n"
    "複合workspaceのDigest goldenの固定要求を定義する。\n"
    "\n"
    "## Acceptance Criteria\n"
    "\n"
    "- [REQ-001:AC-01] [ACTOR:TargetSystem] [ALWAYS] [MUST] [CONSTRAINT] 秘密情報を出力しない。\n"
    "- [REQ-001:AC-02] [ACTOR:TargetSystem] [WHEN] 保存した場合 [SHOULD] [REASON] 確認のため [THEN] 結果を返す。\n"
    "\n"
    "## Verification\n"
    "\n"
    "apps/webとservices/apiのtestで確認する。\n"
)

WEB_TECH_HEAD = (
    "---\n"
    "id: TECH-010\n"
    "title: Web側の認証実装方針\n"
    "status: approved\n"
    "relations:\n"
    "  refines: [platform::REQ-001:AC-01]\n"
    "implements: [src/auth/login.py]\n"
    "tests:\n"
    "  - path: tests/auth/test_login.py\n"
    "    covers: [platform::REQ-001:AC-01]\n"
    "    command: frontend\n"
    "---\n"
)
WEB_TECH_BODY = (
    "# TECH-010 Web側の認証実装方針\n"
    "\n"
    "## Context\n"
    "\n"
    "root workspaceのMUSTをwebのlogin処理で実装する。\n"
)
API_TECH_HEAD = (
    "---\n"
    "id: TECH-010\n"
    "title: API側のsession実装方針\n"
    "status: approved\n"
    "relations:\n"
    "  refines: [platform::REQ-001:AC-02]\n"
    "implements: [src/session.py]\n"
    "tests:\n"
    "  - path: tests/test_session.py\n"
    "    covers: [platform::REQ-001:AC-02]\n"
    "    command: backend\n"
    "---\n"
)
API_TECH_BODY = (
    "# TECH-010 API側のsession実装方針\n"
    "\n"
    "## Context\n"
    "\n"
    "root workspaceのSHOULDをapiのsession処理で実装する。\n"
)
CODE_FILES = {
    "apps/web/src/auth/login.py": "def login():\n    return True\n",
    "apps/web/tests/auth/test_login.py": "def test_login():\n    assert True\n",
    "services/api/src/session.py": "def open_session():\n    return True\n",
    "services/api/tests/test_session.py": "def test_open_session():\n    assert True\n",
}


# 変種ごとに、webのTECH-010のFrontmatterだけを差し替える。1つのfixtureは1つの原因だけを持つ。
WEB_TECH_UNQUALIFIED = (
    "---\n"
    "id: TECH-010\n"
    "title: Web側の認証実装方針\n"
    "status: approved\n"
    "relations:\n"
    "  refines: [REQ-001]\n"
    "---\n"
)
WEB_TECH_MISSING_TARGET = WEB_TECH_HEAD.replace(
    "relations:\n  refines: [platform::REQ-001:AC-01]\n",
    "relations:\n  requires: [api::TECH-999]\n  refines: [platform::REQ-001:AC-01]\n", 1)
VARIANTS = {
    # 変種名: (webのTECH-010のFrontmatter, webのcode／testを置くか)
    "golden": (WEB_TECH_HEAD, True),
    "unqualified": (WEB_TECH_UNQUALIFIED, False),
    "missing-target": (WEB_TECH_MISSING_TARGET, True),
}


def reviewed_inputs(variant="golden"):
    """corpusの全入力file。fixtureごとにdirectoryを分けて同じbyte列を置く。"""
    head, web_code = VARIANTS[variant]
    files = {
        ROOT_CONFIG_PATH: ROOT_CONFIG.encode(),
        ROOT_REQ_PATH: (REQ_HEAD + "\n" + REQ_BODY).encode(),
        API_CONFIG_PATH: API_CONFIG.encode(),
        API_TECH_PATH: (API_TECH_HEAD + "\n" + API_TECH_BODY).encode(),
        WEB_CONFIG_PATH: WEB_CONFIG.encode(),
        WEB_TECH_PATH: (head + "\n" + WEB_TECH_BODY).encode(),
        **{path: text.encode() for path, text in CODE_FILES.items()},
    }
    if not web_code:
        for path in [p for p in files if p.startswith("apps/web/") and "/.spec/" not in p]:
            del files[path]
    return files


# --- review済みのDigest材料（参照計算A） -------------------------------------------

EMPTY_RELATIONS = digest_reference.EMPTY_RELATIONS
STATEMENTS = [
    {
        "id": "platform::REQ-001:AC-01",
        "actor": "TargetSystem",
        "activation": {"kind": "ALWAYS", "text": None},
        "modality": "MUST",
        "reason": None,
        "operation": {"kind": "CONSTRAINT", "text": "秘密情報を出力しない"},
        "extensions": [],
    },
    {
        "id": "platform::REQ-001:AC-02",
        "actor": "TargetSystem",
        "activation": {"kind": "WHEN", "text": "保存した場合"},
        "modality": "SHOULD",
        "reason": "確認のため",
        "operation": {"kind": "THEN", "text": "結果を返す"},
        "extensions": [],
    },
]


def _member_document(workspace_id, title, target, implements, test_path, command, body):
    return {
        "id": f"{workspace_id}::TECH-010",
        "workspaceId": workspace_id,
        "kind": "technical",
        "status": "approved",
        "applicability": "applicable",
        "frontmatter": {
            "id": f"{workspace_id}::TECH-010",
            "title": title,
            "status": "approved",
            "relations": {**EMPTY_RELATIONS, "refines": [target]},
            "implements": [implements],
            "tests": [{"path": test_path, "covers": [target], "command": command}],
            "verify": None,
            "changes": [],
        },
        "bodyText": body,
        "statements": [],
        "strongRelations": [{"relation": "refines", "target": target}],
    }


def reviewed_digest_input():
    """`context platform::REQ-001 --purpose verify`のreview済みDigest材料。"""
    return {
        "digestVersion": "1.0",
        "specSchemaVersion": "1.0",
        "earsAiVersion": "1.0",
        "resolverVersion": "1.0",
        "purpose": "verify",
        "requestWorkspaceId": "platform",
        "roots": ["platform::REQ-001"],
        # request workspaceが先頭、以降はID辞書順。catalogの列挙順（web、api）には従わない。
        "workspaces": [
            {"id": "platform", "path": "."},
            {"id": "api", "path": "services/api"},
            {"id": "web", "path": "apps/web"},
        ],
        "documents": [
            _member_document("api", "API側のsession実装方針", "platform::REQ-001:AC-02",
                             "src/session.py", "tests/test_session.py", "backend", API_TECH_BODY),
            {
                "id": "platform::REQ-001",
                "workspaceId": "platform",
                "kind": "requirement",
                "status": "approved",
                "applicability": "applicable",
                "frontmatter": {
                    "id": "platform::REQ-001",
                    "title": "認証Contextの基準",
                    "status": "approved",
                    "relations": dict(EMPTY_RELATIONS),
                    "implements": [],
                    "tests": [],
                    "verify": None,
                    "changes": [],
                },
                "bodyText": REQ_BODY,
                "statements": [dict(statement) for statement in STATEMENTS],
                "strongRelations": [],
            },
            _member_document("web", "Web側の認証実装方針", "platform::REQ-001:AC-01",
                             "src/auth/login.py", "tests/auth/test_login.py", "frontend", WEB_TECH_BODY),
        ],
        "crossWorkspaceEdges": [
            {"relation": "refines", "source": "api::TECH-010", "target": "platform::REQ-001:AC-02"},
            {"relation": "refines", "source": "web::TECH-010", "target": "platform::REQ-001:AC-01"},
        ],
        "settings": {
            "workspaces": [
                {"id": "api", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"},
                {"id": "platform", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"},
                {"id": "web", "schemaVersion": "1.0", "earsAi": "1.0", "language": "ja"},
            ],
            "context": {"maxDocuments": 20, "maxBytes": 131072},
            "verifyTimeouts": [
                {"workspaceId": "api", "timeoutSeconds": 300},
                {"workspaceId": "web", "timeoutSeconds": 300},
            ],
            "commands": [
                {"workspaceId": "api", "name": "backend", "argv": ["/bin/true", "{tests}"], "cwd": "."},
                {"workspaceId": "web", "name": "frontend", "argv": ["/bin/true", "{tests}"], "cwd": "."},
            ],
        },
    }


canonical_bytes = digest_reference.canonical_bytes
digest = digest_reference.digest
