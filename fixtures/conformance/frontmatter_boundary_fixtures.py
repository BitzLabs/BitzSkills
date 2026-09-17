"""Reviewed decoded-Frontmatter boundary vectors; no YAML loader or Core.

Each field is serialized using JSON syntax as a YAML flow value. Reading these
individual values with json.loads independently verifies the corpus/value pair.
The actual YAML loader and check behavior remain Step 2 acceptance work.
"""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
from jsonschema import Draft202012Validator, ValidationError
from .document_fixtures import INTENT, AC, VERIFICATION
from .initial_fixtures import CONFIGS, observe, compare_state
from .harness import setup

HERE = Path(__file__).resolve().parent
TITLE = 'Frontmatter境界'
TEST_PATH = 'tests/test_contract.py'
TEST = {'path': TEST_PATH, 'covers': ['REQ-001:AC-01'], 'command': 'default'}
BASE = {'id': 'REQ-001', 'title': TITLE, 'status': 'approved'}
# ID -> decoded fields, primary code (None = success), diagnostic key, description.
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
add('SINGLE-119-01', {'relations': {'future': []}}, 'SPEC-FM-SCHEMA-001', 'relations.future', 'relations内の未知keyを拒否する')
add('SINGLE-119-02', {'tests': [{**TEST, 'future': True}]}, 'SPEC-FM-SCHEMA-001', 'tests[0].future', 'tests内の未知keyを拒否する')
add('SINGLE-119-03', {'future': True}, 'SPEC-FM-UNKNOWN-001', 'future', 'top-level未知fieldをwarningにする')
add('SINGLE-119-04', {'x-reviewed': {'team': '品質', 'enabled': True}}, description='x拡張を保持しDiagnosticを出さない')
add('SINGLE-120-03', {'changes': ['src/ignored.py']}, 'SPEC-FM-UNAVAILABLE-001', 'changes', '正しい型のREQ changesは利用不能warningにする')
add('SINGLE-120-04', {'changes': 42}, 'SPEC-FM-SCHEMA-001', 'changes', 'changes型不正は利用不能warningより先に拒否する')
WARNINGS = {'SPEC-FM-UNKNOWN-001', 'SPEC-FM-UNAVAILABLE-001'}
KINDS = {'REQ': ('requirements', 'reqFrontmatter'), 'TECH': ('technical', 'techFrontmatter'),
         'ADR': ('decisions', 'adrFrontmatter'), 'TASK': ('tasks', 'taskFrontmatter')}


def status(identifier):
    code = CASES[identifier][1]
    return 'passed_with_warnings' if code in WARNINGS else 'failed' if code else 'passed'


def spec_path(identifier):
    spec_id = CASES[identifier][0]['id']
    return f'.spec/{KINDS[spec_id.split("-")[0]][0]}/{spec_id}.md'


def reviewed_inputs(identifier):
    fields, _, _, _ = CASES[identifier]
    prefix = fields['id'].split('-')[0]
    # Match valid titles in H1 so title length is the only independent condition.
    heading = fields.get('title') if status(identifier) != 'failed' else TITLE
    body = f'# {fields["id"]} {heading}\n\n'
    body += {'REQ': INTENT + AC + VERIFICATION,
             'TECH': '## Context\n\n前提技術。\n',
             'ADR': '## Context\n\n背景。\n\n## Decision\n\n決定。\n\n## Consequences\n\n影響。\n',
             'TASK': '## Objective\n\n境界を確認する。\n\n## Completion Criteria\n\n検査が完了する。\n'}[prefix]
    header = ''.join(f'{key}: {json.dumps(value, ensure_ascii=False)}\n' for key, value in fields.items())
    inputs = {'.spec/bitz.yaml': CONFIGS['SINGLE-001'].encode(),
              spec_path(identifier): ('---\n' + header + '---\n\n' + body).encode()}
    if 'tests' in fields:
        inputs[TEST_PATH] = b'raise RuntimeError("check must not run test code")\n'
        inputs['.spec/bitz.yaml'] += b'verify:\n  commands:\n    default:\n      argv: ["/bin/true"]\n      cwd: .\n'
    return inputs


def reviewed_manifest(identifier):
    current = status(identifier)
    return {'fixtureId': identifier, 'description': CASES[identifier][3],
            'setup': {'git': True, 'baseCommit': {'message': 'base', 'paths': ['.']}, 'operations': []},
            'invocation': {'runner': 'bitz', 'cwd': '.', 'argv': ['check', '--full', '--base', 'HEAD', '--format', 'json'], 'env': {}},
            'expect': {'status': current, 'exitCode': 1 if current == 'failed' else 0, 'stdout': 'json',
                       'resultFile': 'expected/check.json', 'reportFileCount': 0}}


def reviewed_result(identifier):
    fields, code, key, description = CASES[identifier]
    current = status(identifier)
    accepted = current != 'failed'
    return {'schemaVersion': '1.0', 'operation': 'check', 'status': current, 'scope': 'full',
            'workspace': {'id': 'root', 'path': '.'},
            'revision': {'base': '0' * 40, 'commit': '0' * 40, 'dirty': False},
            'checkedDocumentCount': int(accepted),
            'checkedStatementCount': int(accepted and fields['id'].startswith('REQ-')),
            'durationMs': 0, 'diagnostics': [] if code is None else [
                {'code': code, 'severity': 'warning' if code in WARNINGS else 'error',
                 'resultStatus': current, 'summary': description,
                 'source': {'kind': 'file', 'workspaceId': 'root', 'path': spec_path(identifier), 'key': key}}]}


def validate(root=HERE, identifiers=None):
    errors, prepared = [], []
    validators = {name: Draft202012Validator(json.loads((root / f'{name}.schema.json').read_text()))
                  for name in ('manifest', 'result', 'side-effects')}
    schema = json.loads((root / 'frontmatter.schema.json').read_text())
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
                raise ValueError('manifest or result differs from reviewed single condition')
            inputs = reviewed_inputs(identifier)
            files = {p.relative_to(fixture / 'repo').as_posix(): p for p in (fixture / 'repo').rglob('*') if p.is_file() or p.is_symlink()}
            if set(files) != set(inputs) or any(p.is_symlink() or p.read_bytes() != inputs[name] or p.stat().st_mode & 0o111 for name, p in files.items()):
                raise ValueError('input bytes or file modes differ from reviewed corpus')
            fields = CASES[identifier][0]
            header = inputs[spec_path(identifier)].decode().split('---\n')[1]
            decoded = {key: json.loads(value) for key, value in (line.split(': ', 1) for line in header.splitlines())}
            if fields != decoded:
                raise ValueError('fixed YAML flow values differ from independently decoded fields')
            definition = KINDS[fields['id'].split('-')[0]][1]
            validator = Draft202012Validator({'$ref': '#/$defs/' + definition, '$defs': schema['$defs']})
            failures = list(validator.iter_errors(decoded))
            if bool(failures) != (status(identifier) == 'failed'):
                raise ValueError('Frontmatter Schema disagrees with reviewed acceptance')
            if effects['policy'] != 'read-only' or effects['before'] != effects['after']:
                raise ValueError('Frontmatter check must not write files')
            previous = None
            with tempfile.TemporaryDirectory(prefix='bitz-fm-boundary-') as temporary:
                for run in range(2):
                    sandbox = Path(temporary) / str(run)
                    sandbox.mkdir()
                    repository = setup(fixture, manifest, sandbox / 'repo')
                    external = {name: sandbox / name for name in ('home', 'cache', 'temporary')}
                    for path in external.values():
                        path.mkdir()
                    actual = observe(repository, external)
                    if compare_state(effects['before'], actual) or (previous is not None and previous != actual):
                        raise ValueError('isolated setup differs from fixed snapshot')
                    previous = actual
            prepared.append(identifier)
        except (OSError, ValueError, KeyError, TypeError, ValidationError, subprocess.SubprocessError) as error:
            errors.append(f'{identifier}: {str(error).split(chr(10))[0]}')
    return {'prepared': prepared, 'setups_per_fixture': 2, 'core_execution': 'Not run',
            'status': 'Passed' if not errors else 'Failed', 'errors': errors}
