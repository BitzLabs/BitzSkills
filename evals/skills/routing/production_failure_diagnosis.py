"""公開調査の評価失敗を、保存した原記録に対して読取り専用で再検査する（ADR-068の原因調査用）。

取込み処理は拒否の型だけを残し、文言を保存しない。ここでは取込み後の検査を、調査を実行したときの
sourceのコードで、原記録の元の場所に対してもう一度実行し、どの検査が拒否したかを返す。

- 検査のコードは、実行時の作業ツリーの`evals/skills/routing`から読む。作業ツリーは調査のsourceCommitに
  変更なしで置く。このファイル自体は調査時のsourceにないので、空のディレクトリへ複写して実行する。
- 失敗の後に取込み処理が書いた停止の印（`capture-stop.json`）は、検査の間だけ原記録のディレクトリの一覧から除く。
- 主な書込みの経路をプロセス内で遮断し、原記録の変化は前後の属性とhashの照合で検出する。
- 出力は、例外の型、評価基盤の固定の文言、評価基盤のコード内の発生箇所だけであり、ケース本文・応答・
  原記録の内容は出さない。モデル起動・予約はしない。
"""
import sys
from pathlib import Path

# 検査のコードは作業ツリー（調査時のsourceCommit）から読む。複写したこのファイルの隣のモジュールは使わない。
CHECK_ROUTING = (Path.cwd()/'evals'/'skills'/'routing').resolve()
if CHECK_ROUTING.is_dir() and str(CHECK_ROUTING) not in sys.path:
    sys.path.insert(0, str(CHECK_ROUTING))

import argparse
import builtins
from contextlib import contextmanager
import io as stdio
import os
import posix
import re
import subprocess
import traceback

import production_ledger as io
import production_trace as trace

require = trace.require
VERSION = 'evaluation-failure-diagnosis-0.2.0'
OWN = Path(__file__).resolve()
STOP_MARKER = 'capture-stop.json'
GIT_VALUE_OPTIONS = frozenset({'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--exec-path', '--config-env'})
READ_GIT = frozenset({'show', 'rev-parse', 'ls-tree', 'cat-file', 'ls-files', 'status', 'diff', 'log', 'merge-base'})
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
BLOCKED_OS = ('mkdir', 'makedirs', 'rename', 'renames', 'replace', 'unlink', 'remove', 'rmdir', 'removedirs',
    'symlink', 'link', 'chmod', 'lchmod', 'fchmod', 'chown', 'lchown', 'fchown', 'utime', 'truncate', 'ftruncate',
    'mkfifo', 'mknod', 'setxattr', 'removexattr', 'system', 'posix_spawn', 'posix_spawnp')


class ReadOnlyViolation(PermissionError):
    pass


def _deny(name):
    def blocked(*args, **kwargs):
        raise ReadOnlyViolation(f'diagnosis is read-only: {name}')
    return blocked


def git_subcommand(arguments):
    """gitの大域オプション（値を取るものは値ごと）を飛ばして、最初の副コマンドを返す。"""
    values = iter(arguments)
    for word in values:
        if word in GIT_VALUE_OPTIONS:
            next(values, None)
        elif not word.startswith('-'):
            return word
    return None


@contextmanager
def read_only():
    """主な書込みの経路を遮断する。gitは読取りの副コマンドだけを、出力先の指定なしで通す。"""
    saved = {name: getattr(os, name) for name in BLOCKED_OS if hasattr(os, name)}
    original_open, original_os_open, original_popen = stdio.open, os.open, subprocess.Popen
    original_file_io, original_posix_open = stdio.FileIO, posix.open

    def guarded_open(file, mode='r', *args, **kwargs):
        if any(flag in mode for flag in 'wax+'):
            raise ReadOnlyViolation('diagnosis is read-only: open for writing')
        return original_open(file, mode, *args, **kwargs)

    def guarded_os_open(path, flags, *args, **kwargs):
        if flags & WRITE_FLAGS:
            raise ReadOnlyViolation('diagnosis is read-only: os.open for writing')
        return original_os_open(path, flags, *args, **kwargs)

    class GuardedFileIO(original_file_io):
        def __init__(self, file, mode='r', *args, **kwargs):
            if any(flag in mode for flag in 'wax+'):
                raise ReadOnlyViolation('diagnosis is read-only: FileIO for writing')
            super().__init__(file, mode, *args, **kwargs)

    class GuardedPopen(original_popen):
        def __init__(self, args, *rest, **kwargs):
            argv = [str(x) for x in args] if isinstance(args, (list, tuple)) else []
            if (not argv or kwargs.get('shell') or Path(argv[0]).name != 'git'
                    or git_subcommand(argv[1:]) not in READ_GIT
                    or any(word.startswith('--output') or word == '-o' for word in argv[1:])):
                raise ReadOnlyViolation('diagnosis is read-only: subprocess')
            super().__init__(args, *rest, **kwargs)

    for name in saved:
        setattr(os, name, _deny('os.'+name))
    # pathlibの書込みはio.openを通るので、builtins.openと両方を置き換える。
    builtins.open = stdio.open = guarded_open
    os.open = posix.open = guarded_os_open
    stdio.FileIO, subprocess.Popen = GuardedFileIO, GuardedPopen
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(os, name, value)
        builtins.open = stdio.open = original_open
        os.open, posix.open = original_os_open, original_posix_open
        stdio.FileIO, subprocess.Popen = original_file_io, original_popen


def _entry(path):
    value = os.lstat(path)
    entry = (value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_nlink)
    if os.path.islink(path):
        return entry + (os.readlink(path),)
    if os.path.isfile(path):
        # 作業用のディレクトリにはhardlinkがありうるので、単一linkは求めない。symlinkは辿らない。
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            return entry + (io.sha(stream.read()),)
    return entry


def fingerprint(root):
    """原記録の木（root自身を含む）の属性とhash。symlinkは辿らず、リンク先の文字列を記録する。"""
    root = Path(root)
    require(root.is_absolute() and root.is_dir(), 'diagnosis original attempt directory')
    result = {'.': _entry(root)}
    for directory, names, files in os.walk(root, followlinks=False):
        for name in sorted(names + files):
            path = Path(directory)/name
            result[path.relative_to(root).as_posix()] = _entry(path)
    return result


def _source_text(routing):
    return '\n'.join(path.read_text(encoding='utf-8') for path in sorted(Path(routing).glob('*.py')))


def summarize(error, *, sources=None, routing=None):
    """例外の型と、評価基盤のコードに文字列リテラルとして書かれた拒否の文言だけを返す。"""
    routing = Path(routing or CHECK_ROUTING).resolve()
    frames = traceback.extract_tb(error.__traceback__)
    own = [frame for frame in frames if Path(frame.filename).resolve().parent in {routing, OWN.parent}]
    raised_by_require = bool(frames) and Path(frames[-1].filename).name == 'production_trace.py' \
        and frames[-1].name == 'require'
    if isinstance(error, ReadOnlyViolation):
        message, shown = str(error), True
    else:
        message = str(error) if isinstance(error, ValueError) else None
        text = _source_text(routing) if sources is None else sources
        # 値を埋め込んだ文言は非公開の内容を含みうるので、固定の文字列リテラルと一致する場合だけ出す。
        shown = raised_by_require and message is not None and any(q+message+q in text for q in ("'", '"'))
    return dict(errorType=type(error).__name__, message=message if shown else None,
        messageWithheld=message is not None and not shown,
        frames=[dict(file=Path(f.filename).name, function=f.name, line=f.lineno) for f in own][-8:])


@contextmanager
def without_stop_marker(base):
    """失敗の後に書かれた停止の印を、原記録のディレクトリの一覧からだけ除く。

    停止の印の一覧から外すだけでは、未知の原の名前として拒否され、本来の拒否に届かない。
    一覧するディレクトリは名前ではなくinodeで照合し、他のディレクトリの一覧は変えない。
    """
    info = os.stat(base)
    identity, original = (info.st_dev, info.st_ino), os.listdir

    def listdir(path='.'):
        names = original(path)
        value = os.fstat(path) if isinstance(path, int) else os.stat(path)
        if (value.st_dev, value.st_ino) == identity:
            names = [name for name in names if name != STOP_MARKER]
        return names

    os.listdir = listdir
    try:
        yield
    finally:
        os.listdir = original


def recheck(base, check):
    """原記録の場所でcheckを読取り専用に実行し、前後で原記録が変わっていないことを確かめる。"""
    before = fingerprint(base)
    failure = None
    try:
        with read_only():
            check()
    except Exception as error:
        failure = summarize(error)
    require(fingerprint(base) == before, 'diagnosis changed the original attempt')
    return dict(status='reverified' if failure is None else 'rejected', failure=failure, originalsUnchanged=True)


def stop_summary(base):
    """取込み処理が保存した停止の印と受領記録のうち、内容を含まない項目だけを読む。"""
    result = {}
    for name, keys in [(STOP_MARKER, ('reason', 'errorType')),
            ('receipt.json', ('namespaceExitCode', 'timedOut', 'primaryModelTrajectories'))]:
        path = Path(base)/name
        if path.exists():
            value = trace.strict_json(io.read_regular(path))
            result[name] = {key: value.get(key) for key in keys if isinstance(value, dict)}
    guards = Path(base)/'resource-guards.json'
    if guards.exists():
        value = trace.strict_json(io.read_regular(guards))
        result['resourcesUnchangedDuringLaunch'] = isinstance(value, dict) and value.get('before') == value.get('after')
    return result


def check_source(repository, source_commit):
    """作業ツリーが調査時のsourceCommitにあり、検査のコードに変更がないことを確かめる。"""
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repository, capture_output=True, text=True).stdout.strip()
    require(head == source_commit, 'diagnosis requires the survey source commit checked out')
    changed = subprocess.run(['git', 'status', '--porcelain', '--', 'evals/skills/routing'], cwd=repository,
        capture_output=True, text=True).stdout
    require(changed == '', 'diagnosis requires an unchanged survey source tree')
    require(CHECK_ROUTING == (Path(repository)/'evals'/'skills'/'routing').resolve(),
        'diagnosis must run from the repository root')


def diagnose(repository, bundle, ordinal):
    """survey_run.runと同じ束縛で、取込み後の検査（原記録の読込みと照合）だけをやり直す。"""
    import production_matrix_capture as capture
    import production_matrix_survey_run as survey_run
    p = survey_run.p
    require(Path(capture.__file__).resolve().parent == CHECK_ROUTING, 'diagnosis check code location')
    require(bundle.is_relative_to(repository/'.venv') and '..' not in bundle.parts, 'diagnosis bundle boundary')
    raws = {name: io.read_regular(bundle/(name+'.input.json')) for name in p.matrix.inputs.INPUT_NAMES}
    bound = p.matrix.bind(io.read_regular(bundle/'execution.json'), io.read_regular(bundle/'input-contract.json'), **raws)
    source = bound.slot(ordinal)['sourceCommit']
    check_source(repository, source)
    d_raw = io.read_regular(bundle/'deployment.json')
    review_raw, code_raw = io.read_regular(bundle/'prelaunch-review.json'), io.read_regular(bundle/'code-review.json')
    artifact = io.common_ledger_path(repository).parent.parent
    schema_raw = p.decision_schema(p.guard.git(repository, 'show', source+':'+p.inventory.SCHEMA))
    context_raw = p.guard.git(repository, 'show', source+':'+p.inventory.CONTEXT)
    manifest_raw = io.read_regular(repository/p.deployment(bound, d_raw)['snapshotRelativePath']/'manifest.json')
    base = artifact/bound.contract['outputRelativeRoot']/f'attempt-{ordinal:04d}'

    def check():
        with without_stop_marker(base):
            context = capture.originals_reader.load_provider_capture(bound, ordinal, source_repository=repository,
                artifact_repository=artifact, manifest_raw=manifest_raw, schema_raw=schema_raw, context_raw=context_raw)
            capture.verify_launch(context, repository, artifact, review_raw, code_raw)

    return dict(version=VERSION, ordinal=ordinal, caseId=bound.slot(ordinal)['caseId'], sourceCommit=source,
        stop=stop_summary(base), **recheck(base, check), modelsExecuted=0, reservations=0)


def ordinals(text):
    match = re.fullmatch(r'([0-9]+)(?:-([0-9]+))?', text)
    require(match is not None, 'diagnosis ordinal range')
    first, last = int(match.group(1)), int(match.group(2) or match.group(1))
    require(1 <= first <= last <= 92, 'diagnosis ordinal range bounds')
    return range(first, last+1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True, help='survey_runに渡したbundleのディレクトリ')
    parser.add_argument('--ordinals', required=True, help='例: 58 または 58-92')
    args = parser.parse_args(argv)
    repository = Path.cwd()
    results = [diagnose(repository, args.bundle.absolute(), n) for n in ordinals(args.ordinals)]
    groups = {}
    for row in results:
        key = io.encoded(dict(status=row['status'], failure=row['failure'])).decode()
        groups.setdefault(key, []).append(row['ordinal'])
    summary = [dict(trace.strict_json(key), ordinals=value) for key, value in groups.items()]
    print(io.encoded(dict(version=VERSION, slots=results, groups=summary)).decode())


if __name__ == '__main__':
    main()
