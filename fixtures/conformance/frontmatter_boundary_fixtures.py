"""decode後のFrontmatterの境界を固定するreview済みvector（YAML loaderもCoreもない）。

各fieldは、JSONの構文をYAMLのflow valueとして使って書く。個々の値をjson.loadsで読むことで、
corpusと値の組を独立に確認する。実際のYAML loaderと検査の挙動はStep 2の受入で扱う。
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
from jsonschema import Draft202012Validator, ValidationError
from .schemas import schema_path
from .document_fixtures import INTENT, AC, VERIFICATION
from .ears_fixtures import GOOD
from .initial_fixtures import CONFIGS, observe, compare_state
from .harness import git, setup

HERE = Path(__file__).resolve().parent
TITLE = 'Frontmatter境界'
TEST_PATH = 'tests/test_contract.py'
TEST = {'path': TEST_PATH, 'covers': ['REQ-001:AC-01'], 'command': 'default'}
# 118系だけが使う2件目の規範文。covers集合の比較に2要素が必要なため置く。
SECOND = GOOD.replace('AC-01', 'AC-02').replace('秘密情報を出力しない。', '認証情報を記録しない。')
TWO_STATEMENTS = ('REQ-001:AC-01', 'REQ-001:AC-02')
# 明示TASK checkで変更差分を与えるcode path。
CHANGED_PATH = 'src/app.py'
BASE = {'id': 'REQ-001', 'title': TITLE, 'status': 'approved'}
# ID -> decode後のfield, primaryのcode（None = 成功）, Diagnostic key, 説明
CASES = {}

def add(identifier, updates, code=None, key=None, description='', remove=()):
    fields = {**copy.deepcopy(BASE), **updates}
    for name in remove:
        fields.pop(name)
    CASES[identifier] = (fields, code, key, description)

add('SINGLE-114', {'tests': [TEST]}, description='REQのtests object配列を受理する')
add('SINGLE-115-01', {}, description='最小REQ Frontmatterを受理する')
add('SINGLE-115-02', {'id': 'TECH-001'}, description='最小TECH Frontmatterを受理する')
add('SINGLE-115-03', {'id': 'ADR-001', 'status': 'accepted'}, description='最小ADR Frontmatterを受理する')
add('SINGLE-115-04', {'id': 'TASK-001', 'status': 'open'}, description='changes省略の最小TASKを受理する')
for suffix, value in [('01', '界' * 120), ('02', '界' * 121), ('03', ''), ('04', ' \t '), ('05', '前\n後')]:
    add('SINGLE-116-' + suffix, {'title': value}, None if suffix == '01' else 'SPEC-FM-SCHEMA-001',
        None if suffix == '01' else 'title', 'titleの文字数・非空・単一行条件を検査する')
add('SINGLE-117-01', {}, 'SPEC-FM-REQUIRED-001', 'title', '必須titleの欠落を拒否する', remove=('title',))
add('SINGLE-117-02', {'title': None}, 'SPEC-FM-SCHEMA-001', 'title', 'Core fieldのnullを拒否する')
add('SINGLE-117-03', {'tests': [{**TEST, 'covers': []}]}, 'SPEC-FM-SCHEMA-001', 'tests[0].covers', '空coversを拒否する')
add('SINGLE-118-01', {'relations': {'related': ['REQ-001', 'REQ-001']}}, 'SPEC-FM-SCHEMA-001', 'relations.related', 'scalar配列の重複を拒否する')
add('SINGLE-118-02', {'tests': [{**TEST, 'covers': list(TWO_STATEMENTS)},
                                {**TEST, 'covers': list(reversed(TWO_STATEMENTS))}]},
    'SPEC-FM-SCHEMA-001', 'tests', 'covers順だけが異なるtest要素をkey tupleで重複とする')
add('SINGLE-118-03', {'tests': [TEST, {**TEST, 'command': 'other'}, {**TEST, 'covers': ['REQ-001:AC-02']}]},
    description='同じpathでcommandまたはcoversが異なるtest要素を受理する')
add('SINGLE-119-01', {'relations': {'future': []}}, 'SPEC-FM-SCHEMA-001', 'relations.future', 'relations内の未知keyを拒否する')
add('SINGLE-119-02', {'tests': [{**TEST, 'future': True}]}, 'SPEC-FM-SCHEMA-001', 'tests[0].future', 'tests内の未知keyを拒否する')
add('SINGLE-119-03', {'future': True}, 'SPEC-FM-UNKNOWN-001', 'future', 'top-level未知fieldをwarningにする')
add('SINGLE-119-04', {'x-reviewed': {'team': '品質', 'enabled': True}}, description='x拡張を保持しDiagnosticを出さない')
add('SINGLE-120-01', {'id': 'TASK-001', 'status': 'open', 'changes': []},
    description='changes: []のTASKは変更差分がなければ明示checkを通過する')
add('SINGLE-120-02', {'id': 'TASK-001', 'status': 'open'}, 'SPEC-TASK-BOUNDARY-001', None,
    'changes省略のTASKは変更差分を許可pathなしとして拒否する')
add('SINGLE-120-03', {'changes': ['src/ignored.py']}, 'SPEC-FM-UNAVAILABLE-001', 'changes', '正しい型のREQ changesは利用不能warningにする')
add('SINGLE-120-04', {'changes': 42}, 'SPEC-FM-SCHEMA-001', 'changes', 'changes型不正は利用不能warningより先に拒否する')
# 利用者へ示すDiagnosticのsummary。manifestのdescription（検査の論点）とは別に持つ。
# 同じ条件の既存fixtureと文面をそろえる（119-03はSINGLE-085、120-03はSINGLE-084）。
SUMMARIES = {
    **{'SINGLE-116-' + suffix: 'Frontmatter titleは改行を含まない1〜120文字で指定してください'
       for suffix in ('02', '03', '04', '05')},
    'SINGLE-117-01': 'Frontmatterの必須field titleがありません',
    'SINGLE-117-02': 'Frontmatter titleにnullは指定できません',
    'SINGLE-117-03': 'tests[].coversは1件以上指定してください',
    'SINGLE-118-01': 'relations.relatedに重複した値があります',
    'SINGLE-118-02': 'testsに重複した要素があります',
    'SINGLE-119-01': 'relationsに未知のkey futureがあります',
    'SINGLE-119-02': 'testsの要素に未知のkey futureがあります',
    'SINGLE-119-03': '未知のFrontmatter fieldを無視します',
    'SINGLE-120-03': 'REQではchangesを使用できません',
    'SINGLE-120-04': 'Frontmatter changesはstringの配列が必要です',
}
WARNINGS = {'SPEC-FM-UNKNOWN-001', 'SPEC-FM-UNAVAILABLE-001'}
# 文書をskipするFrontmatter診断。TASK境界違反は文書自体を受理したうえでのfailedである。
REJECTIONS = {'SPEC-FM-SCHEMA-001', 'SPEC-FM-REQUIRED-001'}
# 明示TASK checkを行うcase。120-02だけが作業treeに変更差分を持つ。
TASK_CHECKS = {'SINGLE-120-01': False, 'SINGLE-120-02': True}
KINDS = {'REQ': ('requirements', 'reqFrontmatter'), 'TECH': ('technical', 'techFrontmatter'),
         'ADR': ('decisions', 'adrFrontmatter'), 'TASK': ('tasks', 'taskFrontmatter')}
CODE_BEFORE = b'# base\n'
CODE_AFTER = b'# changed\n'


def status(identifier):
    code = CASES[identifier][1]
    return 'passed_with_warnings' if code in WARNINGS else 'failed' if code else 'passed'


def rejected(identifier):
    return CASES[identifier][1] in REJECTIONS


def spec_path(identifier):
    spec_id = CASES[identifier][0]['id']
    return f'.spec/{KINDS[spec_id.split("-")[0]][0]}/{spec_id}.md'


def statement_ids(identifier):
    return TWO_STATEMENTS if identifier in ('SINGLE-118-02', 'SINGLE-118-03') else TWO_STATEMENTS[:1]


def reviewed_inputs(identifier):
    """base commitへ入れるrepository入力。変更差分はchanges_inputsが別に持つ。"""
    fields, _, _, _ = CASES[identifier]
    prefix = fields['id'].split('-')[0]
    # 有効なtitleはH1と一致させ、title長以外の独立原因を混ぜない。
    heading = TITLE if rejected(identifier) else fields.get('title')
    criteria = AC.replace(GOOD, GOOD + '\n' + SECOND) if len(statement_ids(identifier)) == 2 else AC
    body = f'# {fields["id"]} {heading}\n\n'
    body += {'REQ': INTENT + criteria + VERIFICATION,
             'TECH': '## Context\n\n前提技術。\n',
             'ADR': '## Context\n\n背景。\n\n## Decision\n\n決定。\n\n## Consequences\n\n影響。\n',
             'TASK': '## Objective\n\n境界を確認する。\n\n## Completion Criteria\n\n検査が完了する。\n'}[prefix]
    header = ''.join(f'{key}: {json.dumps(value, ensure_ascii=False)}\n' for key, value in fields.items())
    inputs = {'.spec/bitz.yaml': CONFIGS['SINGLE-001'].encode(),
              spec_path(identifier): ('---\n' + header + '---\n\n' + body).encode()}
    if 'tests' in fields:
        inputs[TEST_PATH] = b'raise RuntimeError("check must not run test code")\n'
        inputs['.spec/bitz.yaml'] += b'verify:\n  commands:\n    default:\n      argv: ["/bin/true"]\n      cwd: .\n'
        if any(test.get('command') == 'other' for test in fields['tests']):
            inputs['.spec/bitz.yaml'] += b'    other:\n      argv: ["/bin/true"]\n      cwd: .\n'
    if identifier in TASK_CHECKS:
        inputs[CHANGED_PATH] = CODE_BEFORE
    return inputs


def changes_inputs(identifier):
    """setup operationで作業treeへ適用するfile。stageもcommitもしない。"""
    return {'changes/app.py': CODE_AFTER} if TASK_CHECKS.get(identifier) else {}


def current_tree(identifier):
    tree = reviewed_inputs(identifier)
    if TASK_CHECKS.get(identifier):
        tree[CHANGED_PATH] = CODE_AFTER
    return tree


def reviewed_manifest(identifier):
    current = status(identifier)
    operations = [{'op': 'update', 'path': CHANGED_PATH, 'source': 'changes/app.py'}] if TASK_CHECKS.get(identifier) else []
    targets = ['TASK-001'] if identifier in TASK_CHECKS else ['--full']
    return {'fixtureId': identifier, 'description': CASES[identifier][3],
            'setup': {'git': True, 'baseCommit': {'message': 'base', 'paths': ['.']}, 'operations': operations},
            'invocation': {'runner': 'bitz', 'cwd': '.', 'argv': ['check', *targets, '--base', 'HEAD', '--format', 'json'], 'env': {}},
            'expect': {'status': current, 'exitCode': 1 if current == 'failed' else 0, 'stdout': 'json',
                       'resultFile': 'expected/check.json', 'reportFileCount': 0}}


def reviewed_result(identifier):
    fields, code, key, description = CASES[identifier]
    current = status(identifier)
    accepted = not rejected(identifier)
    diagnostics = []
    if code == 'SPEC-TASK-BOUNDARY-001':
        # SINGLE-034と同じ文面・sourceの形。変更pathだけを指し、keyを付けない。
        diagnostics.append({'code': code, 'severity': 'error', 'resultStatus': current,
                            'summary': f'{CHANGED_PATH}はTASK-001の許可変更path外です',
                            'source': {'kind': 'file', 'workspaceId': 'root', 'path': CHANGED_PATH}})
    elif code is not None:
        diagnostics.append({'code': code, 'severity': 'warning' if code in WARNINGS else 'error',
                            'resultStatus': current, 'summary': SUMMARIES[identifier],
                            'source': {'kind': 'file', 'workspaceId': 'root', 'path': spec_path(identifier), 'key': key}})
    statements = len(statement_ids(identifier)) if accepted and fields['id'].startswith('REQ-') else 0
    return {'schemaVersion': '1.0', 'operation': 'check', 'status': current,
            'scope': 'selected' if identifier in TASK_CHECKS else 'full',
            'workspace': {'id': 'root', 'path': '.'},
            'revision': {'base': '0' * 40, 'commit': '0' * 40, 'dirty': bool(TASK_CHECKS.get(identifier))},
            'checkedDocumentCount': int(accepted), 'checkedStatementCount': statements,
            'durationMs': 0, 'diagnostics': diagnostics}


def duplicate_tests(fields):
    """tests要素を(path, commandの有無と値, covers集合)で独立に比較する。

    JSON Schemaの uniqueItems は配列順を区別するため、covers順だけが異なる重複を検出できない。
    """
    keys = [(test['path'], ('command' in test, test.get('command')), tuple(sorted(test['covers'])))
            for test in fields.get('tests', [])]
    return len(keys) != len(set(keys))


def check_git_states(identifier, repository):
    """HEADとindexはbase入力、作業treeは変更適用後と一致することをbyteで確認する。"""
    base = reviewed_inputs(identifier)
    if set(git(repository, 'ls-files', '-z').decode().split('\0')[:-1]) != set(base):
        raise ValueError('indexのpathが審査済みbaseと異なります')
    for path, content in base.items():
        if git(repository, 'show', 'HEAD:' + path) != content or git(repository, 'show', ':' + path) != content:
            raise ValueError('HEADまたはindexのbyte列が審査済みbaseと異なります')
    actual = {p.relative_to(repository).as_posix(): p.read_bytes() for p in repository.rglob('*')
              if p.is_file() and '.git' not in p.relative_to(repository).parts}
    if actual != current_tree(identifier):
        raise ValueError('作業treeが審査済みの変更と異なります')


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads(schema_path(root, name).read_text()))
                  for name in ('manifest', 'result', 'side-effects')}
    schema = json.loads(schema_path(root, "frontmatter").read_text())
    for identifier in CASES:
        if identifiers is not None and identifier not in identifiers:
            continue
        fixture = root / 'single' / identifier
        try:
            manifest = json.loads((fixture / 'manifest.json').read_text())
            result = json.loads((fixture / 'expected/check.json').read_text())
            effects = json.loads((fixture / 'side-effects.json').read_text())
            for name, value in (('manifest', manifest), ('result', result), ('side-effects', effects)):
                validators[name].validate(value)
            if manifest != reviewed_manifest(identifier) or result != reviewed_result(identifier):
                raise ValueError('manifestまたは結果が審査済みの単一条件と異なります')
            inputs = reviewed_inputs(identifier)
            expected = {**{'repo/' + name: content for name, content in inputs.items()}, **changes_inputs(identifier)}
            files = {p.relative_to(fixture).as_posix(): p for directory in ('repo', 'changes')
                     for p in (fixture / directory).rglob('*') if p.is_file() or p.is_symlink()}
            if set(files) != set(expected) or any(p.is_symlink() or p.read_bytes() != expected[name] or p.stat().st_mode & 0o111 for name, p in files.items()):
                raise ValueError('入力のbyte列またはfile modeが審査済みcorpusと異なります')
            fields = CASES[identifier][0]
            header = inputs[spec_path(identifier)].decode().split('---\n')[1]
            decoded = {key: json.loads(value) for key, value in (line.split(': ', 1) for line in header.splitlines())}
            if fields != decoded:
                raise ValueError('固定したYAMLのflow valueが独立にdecodeしたfieldと異なります')
            definition = KINDS[fields['id'].split('-')[0]][1]
            validator = Draft202012Validator({'$ref': '#/$defs/' + definition, '$defs': schema['$defs']})
            failures = list(validator.iter_errors(decoded))
            if (bool(failures) or duplicate_tests(decoded)) != rejected(identifier):
                raise ValueError('Frontmatter Schemaの判定が審査済みの受理と一致しません')
            if effects['policy'] != 'read-only' or effects['before'] != effects['after']:
                raise ValueError('Frontmatterの検査はfileを書いてはいけません')
            previous = None
            with tempfile.TemporaryDirectory(prefix='bitz-fm-boundary-') as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / 'repo')
                    check_git_states(identifier, repository)
                    external = {name: sandbox / name for name in ('home', 'cache', 'temporary')}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects['before'], actual) or (previous is not None and previous != actual):
                        raise ValueError('隔離setupが固定snapshotと異なります')
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f'{identifier}: {str(error).split(chr(10))[0]}')
    return {'prepared': prepared, 'setups_per_fixture': 2, 'core_execution': 'Not run',
            'status': 'Passed' if not errors else 'Failed', 'errors': errors}
