"""`runner: package`の参照実装(ADR-046 Decision 5)。

Core実行体を起動せず、候補のsource tree、build成果物(wheel)、隔離環境への導入metadataだけを検査する。
harnessの参照実装であり、Coreの実装ではない(適合fixture仕様 3.5、ADR-049 Decision 5)。
"""
import re
from pathlib import Path
import tomllib
import zipfile

PEP503_NORMALIZE = re.compile(r"[-_.]+")
REQUIRES_PYTHON_CLAUSE = re.compile(
    r"(>=|<=|==|~=|>|<)\s*([0-9]+)(?:\.([0-9]+))?(?:\.([0-9]+))?(?:\.\*)?")


class PackageCheckError(Exception):
    """caseそのものを判定できないharness側のerror。fixture errorへ変換する。"""


def normalize_name(name):
    """PEP 503のpackage名正規化。"""
    return PEP503_NORMALIZE.sub("-", name).strip("-").lower()


def wheel_top_level_packages(wheel_path):
    with zipfile.ZipFile(wheel_path) as archive:
        namelist = archive.namelist()
    tops = set()
    for name in namelist:
        head = name.split("/", 1)[0]
        if head.endswith(".dist-info") or head.endswith(".data"):
            continue
        tops.add(head)
    return tops


def wheel_contains(wheel_path, member):
    with zipfile.ZipFile(wheel_path) as archive:
        return member in archive.namelist()


def requires_python_allows(specifier, major, minor):
    """`>=3.12`系の単純な比較だけを解釈する。空・解釈不能な指定は許可しない扱いにする。"""
    if not specifier or not specifier.strip():
        return False
    candidate = (major, minor)
    for clause in specifier.split(","):
        clause = clause.strip()
        match = re.fullmatch(REQUIRES_PYTHON_CLAUSE, clause)
        if not match:
            return False
        op, c_major, c_minor, _c_patch = match.groups()
        bound = (int(c_major), int(c_minor) if c_minor is not None else 0)
        if op == ">=":
            ok = candidate >= bound
        elif op == ">":
            ok = candidate > bound
        elif op == "<=":
            ok = candidate <= bound
        elif op == "<":
            ok = candidate < bound
        else:  # == と ~= は同じmajor.minorへの一致として扱う(単純な比較の範囲)。
            ok = candidate == bound
        if not ok:
            return False
    return True


def _venv_bin(venv_dir, name):
    return Path(venv_dir) / "bin" / name


def _venv_site_packages(venv_dir):
    lib = Path(venv_dir) / "lib"
    if not lib.is_dir():
        return None
    candidates = sorted(lib.glob("python3.*/site-packages"))
    return candidates[0] if candidates else None


def check_metadata(source_dir, wheel_path, venv_dir):
    reasons = []
    if source_dir is None:
        # source treeが無いと判定材料(pyproject.toml)自体が無く、要件を満たさない
        # (rejected)と検査できない(error)を区別できない。harness側のerrorとする。
        raise PackageCheckError("wheelのみが与えられており、source treeのpyproject.tomlを検査できません")
    pyproject_path = Path(source_dir) / "pyproject.toml"
    if not pyproject_path.is_file():
        raise PackageCheckError("source treeにpyproject.tomlがなく検査できません")
    project = tomllib.loads(pyproject_path.read_text(encoding="utf-8")).get("project", {})
    if project.get("name") != "bitz":
        reasons.append("project.nameがbitzではありません")
    if "bitz" not in project.get("scripts", {}):
        reasons.append("project.scriptsにbitzがありません")
    if not requires_python_allows(project.get("requires-python", ""), 3, 12):
        reasons.append("requires-pythonがCPython 3.12を許可しません")
    try:
        top_level = wheel_top_level_packages(wheel_path)
    except PackageCheckError as error:
        reasons.append(str(error))
        top_level = set()
    if "bitz" not in top_level or not wheel_contains(wheel_path, "bitz/__init__.py"):
        reasons.append("wheelにtop-level import package bitz(bitz/__init__.py)がありません")
    if not _venv_bin(venv_dir, "bitz").exists():
        reasons.append("導入済み環境にconsole script bin/bitzがありません")
    return ("accepted" if not reasons else "rejected"), reasons


def _lock_dependency_closure(lock_data, root_name):
    packages = {pkg["name"]: pkg for pkg in lock_data.get("package", [])}
    root = packages.get(root_name)
    if root is None:
        raise PackageCheckError(f"uv.lockに{root_name}パッケージがありません")
    seen = set()
    stack = [dep["name"] for dep in root.get("dependencies", [])]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        pkg = packages.get(name)
        if pkg is not None:
            stack.extend(dep["name"] for dep in pkg.get("dependencies", []))
    return seen, packages


def check_dependencies(source_dir, wheel_path, venv_dir):
    reasons = []
    if source_dir is None:
        raise PackageCheckError("wheelのみが与えられており、source treeのuv.lockを検査できません")
    pyproject_path = Path(source_dir) / "pyproject.toml"
    lock_path = Path(source_dir) / "uv.lock"
    if not pyproject_path.is_file() or not lock_path.is_file():
        raise PackageCheckError("source treeにpyproject.tomlまたはuv.lockがなく検査できません")
    dependencies = tomllib.loads(pyproject_path.read_text(encoding="utf-8")).get("project", {}).get("dependencies", [])
    if len(dependencies) != 1:
        return "rejected", [f"project.dependenciesがちょうど1件ではありません({len(dependencies)}件)"]
    match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s,;]+)", dependencies[0].strip())
    if not match:
        return "rejected", [f"依存がexact pinではありません: {dependencies[0]!r}"]
    dep_name, dep_version = match.group(1), match.group(2)
    if normalize_name(dep_name) not in {"pyyaml", "ruamel-yaml"}:
        return "rejected", [f"YAML libraryへのexact pinではありません: {dep_name!r}"]
    lock_data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    try:
        closure, packages = _lock_dependency_closure(lock_data, "bitz")
    except PackageCheckError as error:
        return "rejected", [str(error)]
    normalized_closure = {normalize_name(name) for name in closure}
    if normalized_closure != {normalize_name(dep_name)}:
        reasons.append(f"runtime依存の推移閉包がYAML library 1件だけではありません: {sorted(closure)}")
    resolved = next((packages[name] for name in packages if normalize_name(name) == normalize_name(dep_name)), None)
    if resolved is None or str(resolved.get("version")) != dep_version:
        reasons.append("uv.lockのversionがexact pinと一致しません")
    site_packages = _venv_site_packages(venv_dir)
    dist_info = sorted(p.name for p in site_packages.glob("*.dist-info")) if site_packages else []
    if len(dist_info) != 2:
        reasons.append(f"導入済み環境のdist-infoが2件ではありません: {dist_info}")
    return ("accepted" if not reasons else "rejected"), reasons


def check(case, source_dir, wheel_path, venv_dir):
    """argv[0](case)を判定する。戻り値は(outcome, reasons)。"""
    if case == "metadata":
        return check_metadata(source_dir, wheel_path, venv_dir)
    if case == "dependencies":
        return check_dependencies(source_dir, wheel_path, venv_dir)
    raise PackageCheckError(f"未知のpackage caseです: {case!r}")
