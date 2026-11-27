"""Exercise the R04 review boundary with synthetic inputs only (Linux, bubblewrap)."""
import errno
import hashlib
import itertools
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile


SKILLS = ("bitz-core", "sdd-plan", "sdd-implement", "sdd-converge",
          "quality-plan", "quality-review")


def write_private(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False)


def require(condition):
    if not condition:
        raise ValueError("preflight verification failed")


def inputs(directory):
    # Synthetic rule labels supply the oracle for transport testing.
    # They do not approximate the semantic judgment required for real inputs.
    conditions = [
        {"id": f"C{i}", "skill": skill, "polarity": polarity,
         "premise": f"synthetic condition {i}", "counterfactual": f"without rule {i}"}
        for i, (skill, polarity) in enumerate(itertools.product(SKILLS, ("positive", "negative")))
    ]
    public = [{"id": f"P{i}", "premise": f"public example {i}"} for i in range(50)]
    prior = [{"id": f"H{i}", "premise": f"historical example {i}"} for i in range(84)]
    public[-1]["premise"] = conditions[0]["premise"]
    prior[-1]["premise"] = conditions[1]["premise"]
    conditions[-1]["premise"] = conditions[-2]["premise"]
    packet = {"conditions": conditions, "public": public, "prior": prior}
    write_private(directory / "input.json", packet)
    return packet


def reviewer(mode):
    # This runs inside the test namespace. Only this script, system runtime,
    # synthetic inputs and a fresh private output directory have been mounted.
    src = Path("/inputs/input.json")
    packet = json.loads(src.read_bytes())
    require(not Path("/home/hide").exists())
    try:
        with src.open("ab"):
            pass
    except OSError as error:
        require(error.errno == errno.EROFS)
    else:
        raise ValueError("writable inputs")
    require({name for _, name in socket.if_nameindex()} <= {"lo"})
    if mode == "leak":
        print(packet["conditions"][0]["premise"], file=sys.stderr)
    def compare(left, right):
        equal = left["premise"] == right["premise"]
        return [left["id"], right["id"], equal,
                f'{left["premise"]} / {right["premise"]}']
    conditions = packet["conditions"]
    comparisons = [compare(c, ref) for c in conditions
                   for ref in packet["public"] + packet["prior"]]
    peers = [compare(a, b) for a, b in itertools.combinations(conditions, 2)]
    if mode == "incomplete":
        peers.pop()
    write_private(Path("/out/report.json"), {
        "inputSha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "comparisons": comparisons, "peers": peers,
    })


def summary(directory, packet, mode):
    out = directory / mode
    out.mkdir(mode=0o700)
    command = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
               "--clearenv", "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib"]
    if Path("/lib64").exists():
        command.extend(["--symlink", "usr/lib64", "/lib64"])
    command.extend(["--ro-bind", str(Path(__file__).resolve()), "/review.py",
                    "--ro-bind", str(directory / "inputs"), "/inputs",
                    "--bind", str(out), "/out", "--remount-ro", "/",
                    "/usr/bin/python3", "-IB", "/review.py", "--child", mode])
    # No child stream is forwarded, including errors and tracebacks.
    with tempfile.TemporaryFile(dir=directory) as streams:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=streams,
                                stderr=streams, timeout=30, check=False)
        require(result.returncode == 0)
        if streams.tell():
            return "unexpected_child_output", None
    path = out / "report.json"
    require(not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == 0o600)
    raw = path.read_bytes()
    report = json.loads(raw)
    require(report["inputSha256"] == hashlib.sha256(
        (directory / "inputs/input.json").read_bytes()).hexdigest())
    ids = [c["id"] for c in packet["conditions"]]
    refs = [r["id"] for r in packet["public"] + packet["prior"]]
    blocked = set()
    for name, expected in (("comparisons", itertools.product(ids, refs)),
                           ("peers", itertools.combinations(ids, 2))):
        rows = report[name]
        if [(r[0], r[1]) for r in rows] != list(expected):
            return "incomplete_coverage", None
        for left, right, duplicate, reason in rows:
            require(type(duplicate) is bool and isinstance(reason, str) and reason)
            if duplicate:
                blocked.add(left)
                if name == "peers":
                    blocked.add(right)
    # Only aggregate counts, an enumerated outcome and a local digest cross
    # the boundary. Never copy child-provided text to the public receipt.
    return "completed", {"status": "synthetic_completed", "conditions": len(ids),
            "externalComparisons": len(report["comparisons"]), "peerPairs": len(report["peers"]),
            "duplicateConditions": len(blocked), "reviewSha256": hashlib.sha256(raw).hexdigest()}


def main():
    os.umask(0o077)
    if sys.argv[1:] in (["--child", "normal"], ["--child", "leak"], ["--child", "incomplete"]):
        reviewer(sys.argv[2])
        return
    require(len(sys.argv) == 1)
    with tempfile.TemporaryDirectory(prefix="r04-synthetic-") as tmp:
        directory = Path(tmp)
        src = directory / "inputs"
        src.mkdir(mode=0o700)
        packet = inputs(src)
        status, receipt = summary(directory, packet, "normal")
        require(status == "completed" and receipt["duplicateConditions"] == 4)
        require(summary(directory, packet, "leak") == ("unexpected_child_output", None))
        require(summary(directory, packet, "incomplete") == ("incomplete_coverage", None))
        print(json.dumps(receipt))


if __name__ == "__main__":
    main()
