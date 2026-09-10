#!/usr/bin/env python3
"""Pre-upload preflight for the AI Chessathon submission.

Builds a zip from ``git show HEAD:<file>`` into a staging directory -- never from the
working tree, per HANDOFF's "Verification checklist before any upload" -- then asserts
against the *unzipped* archive. Every check is designed so that it can fail; a check
that is true by construction is not a check (HANDOFF house rule 3).

Run:

    ~/Desktop/AIChessHackathon/pyenv/bin/python tools/preflight.py
    ~/Desktop/AIChessHackathon/pyenv/bin/python tools/preflight.py --full

``--full`` runs the long smoke game at the real time control. The default run is sized
to finish in a couple of minutes so that people actually run it.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Limits.
#
# Fetched from the live docs on 2026-09-09:
#   https://aichessathon.com/docs/agent-contract.md
#   https://aichessathon.com/docs/rules.md
#
# These are hard-coded on purpose: the preflight must not need the network, and
# the platform has none anyway. CLAUDE.md / AGENTS.md and harness/rules.py quote
# STALE numbers (60 s init, 6 uploads, 300-ply adjudication). The live docs say
# 90 s init, 10 uploads, and "a game still running at 600 plies is drawn".
# Re-fetch both URLs and bump DOCS_VERIFIED_ON when this warning fires.
# ---------------------------------------------------------------------------
DOCS_VERIFIED_ON = dt.date(2026, 9, 9)
DOCS_STALE_AFTER_DAYS = 3

INIT_BUDGET_S = 90.0  # agent-contract.md: "90s init budget"
BASE_MS = 120_000  # rules.md: "120s plus 0.5s per move, per side"
INCREMENT_MS = 500
MEMORY_LIMIT_BYTES = 2 * 1024 * 1024 * 1024  # agent-contract.md: "2 GB RAM"
MAX_UNZIPPED_BYTES = 50_000_000  # agent-contract.md: "total <= 50 MB unzipped"
MOVE_REPLY_CAP_BYTES = 4096  # agent-contract.md: "move payload over 4 KB"
PLY_DRAW_CAP = 600  # rules.md: "A game still running at 600 plies is drawn"
UPLOADS_PER_DAY = 10  # rules.md: "10 uploads per team per day"
PLATFORM_PYTHON = (3, 12)

# Judge-measured reference points for v10 (HANDOFF).
JUDGE_IMPORT_S_V10 = 28.4
LOCAL_IMPORT_S_V10 = 11.0
JUDGE_PEAK_RSS_MB_V10 = 632.0

# agent-contract.md: torch, numpy, python-chess, onnxruntime, numba. Nothing else.
PERMITTED_PACKAGES = {"torch", "numpy", "chess", "onnxruntime", "numba"}

# The five files HANDOFF's checklist names as the submission. Missing one is fatal.
REQUIRED_ROOT_PY = {"agent.py", "search.py", "evaluation.py", "nsearch.py", "bitboard.py"}
# In-progress modules that tools/check_root.py allows at the root and that
# harness/package.py therefore globs into the zip. They are dead weight in the
# archive; tolerated, but reported.
TOLERATED_ROOT_PY = {"nnue.py", "nsearch_nnue.py"}
EXPECTED_ROOT_PY = REQUIRED_ROOT_PY | TOLERATED_ROOT_PY

# Extensions that are always a native binary. ".bin" is deliberately absent: a
# Polyglot opening book is a .bin and the rules permit it ("Opening books and
# endgame tablebases are permitted as shipped data"). Real executables are caught
# by the magic-byte scan below regardless of what they are called.
BINARY_EXTENSIONS = {".so", ".dylib", ".pyd", ".dll", ".exe", ".o", ".a", ".class"}
BINARY_MAGICS: tuple[tuple[bytes, str], ...] = (
    (b"\x7fELF", "ELF"),
    (b"MZ", "PE/COFF (Windows)"),
    (b"\xcf\xfa\xed\xfe", "Mach-O 64-bit LE"),
    (b"\xce\xfa\xed\xfe", "Mach-O 32-bit LE"),
    (b"\xfe\xed\xfa\xcf", "Mach-O 64-bit BE"),
    (b"\xfe\xed\xfa\xce", "Mach-O 32-bit BE"),
    (b"\xca\xfe\xba\xbe", "Mach-O universal / Java class"),
    (b"\xbe\xba\xfe\xca", "Mach-O universal (LE)"),
)

# Directory-scan APIs, and the file extensions each one actually consumes.
# chess.syzygy only ever opens .rtbw/.rtbz, so "weights/ is opened as a tablebase"
# does NOT excuse a .npz sitting in the same directory.
SCAN_APIS: dict[str, frozenset[str]] = {
    "open_tablebase": frozenset({".rtbw", ".rtbz"}),
    "add_directory": frozenset({".rtbw", ".rtbz"}),
    "open_reader": frozenset({".bin"}),
}
ANY_EXTENSION = frozenset({"*"})

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
INFO = "INFO"
SKIP = "SKIP"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
@dataclass
class Check:
    ident: str
    title: str
    status: str = PASS
    lines: list[str] = field(default_factory=list)

    def say(self, line: str) -> None:
        self.lines.append(line)

    def fail(self, line: str) -> None:
        self.status = FAIL
        self.lines.append(line)

    def warn(self, line: str) -> None:
        if self.status != FAIL:
            self.status = WARN
        self.lines.append(line)


class Report:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def check(self, ident: str, title: str) -> Check:
        item = Check(ident, title)
        self.checks.append(item)
        return item

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def warned(self) -> list[Check]:
        return [c for c in self.checks if c.status == WARN]

    def render(self) -> str:
        out: list[str] = []
        for c in self.checks:
            out.append(f"[{c.status:4}] {c.ident}  {c.title}")
            for line in c.lines:
                out.append(f"         {line}")
        out.append("")
        out.append(
            f"{len(self.checks)} checks: "
            f"{len([c for c in self.checks if c.status == PASS])} pass, "
            f"{len(self.warned)} warn, {len(self.failed)} fail, "
            f"{len([c for c in self.checks if c.status == SKIP])} skipped"
        )
        if self.failed:
            out.append("FAILED: " + ", ".join(c.ident for c in self.failed))
            out.append("Do not upload.")
        else:
            out.append("No blocking failures. Read the warnings before uploading.")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# git plumbing
# ---------------------------------------------------------------------------
def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout


def git_blob(repo: Path, path: str) -> bytes:
    result = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{path}"], cwd=repo, capture_output=True, check=True
    )
    return result.stdout


def head_submission_paths(repo: Path) -> list[str]:
    """Replicate harness.package's member selection, but over the HEAD tree."""
    listed = git(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    skip = {"__pycache__", ".DS_Store"}
    chosen: list[str] = []
    for path in listed:
        parts = path.split("/")
        if skip & set(parts):
            continue
        if (len(parts) == 1 and path.endswith(".py")) or parts[0] == "weights":
            chosen.append(path)
    return sorted(chosen)


def stage_head(repo: Path, staging: Path) -> list[str]:
    paths = head_submission_paths(repo)
    for path in paths:
        target = staging / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git_blob(repo, path))
    return paths


# ---------------------------------------------------------------------------
# Static analysis helpers
# ---------------------------------------------------------------------------
@dataclass
class ModuleInfo:
    name: str
    source: str
    tree: ast.Module
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef]
    module_aliases: dict[str, str]
    from_imports: dict[str, tuple[str, str]]
    env_guards: set[str]
    parents: dict[ast.AST, ast.AST]


def _is_env_read(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr in {"environ", "getenv"}:
            return True
        if isinstance(sub, ast.Name) and sub.id in {"environ", "getenv"}:
            return True
    return False


def _env_default(node: ast.AST) -> ast.expr | None:
    """Return the default supplied to os.environ.get / os.getenv, if any."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in {"get", "getenv"} and _is_env_read(func) and len(sub.args) >= 2:
            return sub.args[1]
    return None


def _default_off_env_guard(expr: ast.expr) -> bool:
    """True if ``expr`` reads an env var and is FALSE when the var is unset.

    ``os.environ.get("X") == "1"`` is a guard (off by default).
    ``os.environ.get("X", "1") == "1"`` is NOT: it is on by default, so a print
    behind it runs on the platform, where no environment variable is set.
    """
    if not _is_env_read(expr):
        return False
    default = _env_default(expr)
    if default is None:
        return True
    if isinstance(expr, ast.Compare) and len(expr.comparators) == 1:
        right = expr.comparators[0]
        if isinstance(default, ast.Constant) and isinstance(right, ast.Constant):
            return bool(default.value != right.value)
    return False


def build_module_info(name: str, source: str) -> ModuleInfo:
    tree = ast.parse(source, filename=f"{name}.py")
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    module_aliases: dict[str, str] = {}
    from_imports: dict[str, tuple[str, str]] = {}
    env_guards: set[str] = set()

    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            functions[stmt.name] = stmt
        elif isinstance(stmt, ast.Assign) and _default_off_env_guard(stmt.value):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    env_guards.add(target.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_aliases[alias.asname or alias.name.split(".")[0]] = alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                from_imports[alias.asname or alias.name] = (node.module, alias.name)

    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    return ModuleInfo(name, source, tree, functions, module_aliases, from_imports, env_guards,
                      parents)


def ancestors(info: ModuleInfo, node: ast.AST, stop: ast.AST) -> Iterator[ast.AST]:
    current = node
    while current is not stop:
        parent = info.parents.get(current)
        if parent is None:
            return
        yield parent
        current = parent


def is_output_call(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name) and func.id == "print":
        return "print"
    if isinstance(func, ast.Attribute):
        if func.attr == "print_exc":
            return "traceback.print_exc"
        if func.attr in {"write", "writelines"}:
            value = func.value
            if isinstance(value, ast.Attribute) and value.attr in {"stderr", "stdout"}:
                return f"sys.{value.attr}.{func.attr}"
    return None


def _if_is_once_latch(node: ast.If) -> bool:
    """``if flag: ... flag = <constant>`` -- the body runs at most once per process."""
    tested = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
    for stmt in ast.walk(node):
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id in tested:
                    return True
    return False


def _handler_sets_constant_latch(handler: ast.ExceptHandler) -> set[str]:
    latched: set[str] = set()
    for stmt in ast.walk(handler):
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    latched.add(target.id)
    return latched


def classify_output(info: ModuleInfo, call: ast.Call, fn: ast.AST) -> str:
    """Return one of env-guard / once-latch / error-latch / error-path / unguarded."""
    chain = list(ancestors(info, call, fn))
    for parent in chain:
        if not isinstance(parent, ast.If):
            continue
        # Either the test reads the environment inline, or it reads a module-level
        # constant that was itself assigned from a default-off environment read
        # (search.py's `DEPTH_LOG = os.environ.get("CHESSATHON_DEPTH_LOG") == "1"`).
        if _default_off_env_guard(parent.test):
            return "env-guard"
        tested = {n.id for n in ast.walk(parent.test) if isinstance(n, ast.Name)}
        if tested & info.env_guards:
            return "env-guard"
    for parent in chain:
        if isinstance(parent, ast.If) and _if_is_once_latch(parent):
            return "once-latch"
    for index, parent in enumerate(chain):
        if not isinstance(parent, ast.ExceptHandler):
            continue
        latched = _handler_sets_constant_latch(parent)
        if not latched:
            continue
        # The latch only bounds the print if some enclosing `if` tests it.
        for outer in chain[index:]:
            if isinstance(outer, ast.If):
                tested = {n.id for n in ast.walk(outer.test) if isinstance(n, ast.Name)}
                if tested & latched:
                    return "error-latch"
    for parent in chain:
        if isinstance(parent, ast.ExceptHandler):
            return "error-path"
    return "unguarded"


def reachable_functions(
    modules: dict[str, ModuleInfo], root: tuple[str, str]
) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    queue: list[tuple[str, str]] = [root]
    order: list[tuple[str, str]] = []
    while queue:
        item = queue.pop()
        if item in seen:
            continue
        seen.add(item)
        module_name, func_name = item
        info = modules.get(module_name)
        if info is None or func_name not in info.functions:
            continue
        order.append(item)
        fn = info.functions[func_name]
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            target = _resolve_call(modules, info, node.func)
            if target is not None:
                queue.append(target)
    return order


def _resolve_call(
    modules: dict[str, ModuleInfo], info: ModuleInfo, func: ast.expr
) -> tuple[str, str] | None:
    if isinstance(func, ast.Name):
        if func.id in info.functions:
            return (info.name, func.id)
        binding = info.from_imports.get(func.id)
        if binding and binding[0] in modules:
            return binding
        return None
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        module_name = info.module_aliases.get(func.value.id, func.value.id)
        if module_name in modules:
            return (module_name, func.attr)
    return None


# ---------------------------------------------------------------------------
# Child-process probes (run against the UNZIPPED archive)
# ---------------------------------------------------------------------------
IMPORT_PROBE = """
import json, os, sys, time
sys.path.insert(0, os.getcwd())
start = time.perf_counter()
try:
    import agent
except BaseException as exc:
    print(json.dumps({"ok": False, "error": repr(exc)}))
    raise SystemExit(0)
elapsed = time.perf_counter() - start
print(json.dumps({
    "ok": True,
    "import_s": elapsed,
    "use_numba": bool(getattr(agent, "USE_NUMBA_SEARCH", None)),
    "agent_file": os.path.relpath(agent.__file__, os.getcwd()),
    "python": list(sys.version_info[:2]),
}))
"""

GAME_PROBE = """
import json, os, resource, sys, time
sys.path.insert(0, os.getcwd())
import chess
import agent

PLIES = {plies}
BASE_MS = {base_ms}
INC_MS = {inc_ms}
CAP = {cap}

board = chess.Board({fen!r})
clock = {{True: BASE_MS, False: BASE_MS}}
problems = []
worst_overshoot = 0.0
plies = 0
for _ in range(PLIES):
    if board.is_game_over(claim_draw=True):
        break
    side = board.turn
    before = time.monotonic()
    try:
        uci = agent.get_move(board.fen(), int(clock[side]))
    except BaseException as exc:
        problems.append("crash on ply %d: %r" % (plies, exc))
        break
    spent_ms = (time.monotonic() - before) * 1000.0
    clock[side] -= spent_ms
    if clock[side] <= 0:
        problems.append("flag: %s ran out on ply %d" % (side, plies))
        break
    clock[side] += INC_MS
    if not isinstance(uci, str):
        problems.append("non-string reply on ply %d: %r" % (plies, uci))
        break
    if len(uci.encode()) > CAP:
        problems.append("reply over %d bytes on ply %d" % (CAP, plies))
        break
    try:
        move = chess.Move.from_uci(uci)
    except Exception:
        problems.append("malformed uci %r on ply %d" % (uci, plies))
        break
    if move not in board.legal_moves:
        problems.append("ILLEGAL %s in %s on ply %d" % (uci, board.fen(), plies))
        break
    board.push(move)
    plies += 1

rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
rss_bytes = rss if sys.platform == "darwin" else rss * 1024
print(json.dumps({{
    "plies": plies,
    "problems": problems,
    "white_left_ms": clock[True],
    "black_left_ms": clock[False],
    "peak_rss_bytes": rss_bytes,
    "final_fen": board.fen(),
    "outcome": str(board.outcome(claim_draw=True)),
}}))
"""


def clean_env() -> dict[str, str]:
    """The platform sets none of our test switches. Neither does this."""
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith("CHESSATHON_")}
    env.pop("USE_NUMBA_SEARCH", None)
    env.pop("SEARCH_MAX_NODES", None)
    env.pop("PYTHONPATH", None)
    return env


def run_probe(code: str, cwd: Path, env: dict[str, str], timeout: float) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    for line in reversed(result.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            parsed: dict[str, Any] = json.loads(line)
            parsed["_stderr_tail"] = "\n".join(result.stderr.splitlines()[-8:])
            return parsed
    return {
        "ok": False,
        "error": f"probe produced no JSON (exit {result.returncode})",
        "_stderr_tail": "\n".join(result.stderr.splitlines()[-15:]),
    }


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def check_docs_freshness(report: Report) -> None:
    c = report.check("C00", "Limits are from the live docs and recently verified")
    age = (dt.date.today() - DOCS_VERIFIED_ON).days
    c.say(
        f"init {INIT_BUDGET_S:.0f}s | clock {BASE_MS}ms+{INCREMENT_MS}ms | "
        f"{MAX_UNZIPPED_BYTES:,}B unzipped | {MEMORY_LIMIT_BYTES // 1024 // 1024}MB RAM | "
        f"{PLY_DRAW_CAP}-ply draw | {UPLOADS_PER_DAY} uploads/day"
    )
    c.say(f"verified {DOCS_VERIFIED_ON.isoformat()} against agent-contract.md and rules.md")
    if age > DOCS_STALE_AFTER_DAYS:
        c.warn(f"these numbers are {age} days old; re-fetch both docs URLs and bump the constant")
    else:
        c.say(f"{age} day(s) old")


def check_harness_constants(report: Report, repo: Path) -> None:
    c = report.check("C00b", "harness/rules.py agrees with the live docs")
    path = repo / "harness" / "rules.py"
    if not path.exists():
        c.fail("harness/rules.py is missing")
        return
    text = path.read_text()
    expected = {
        "INIT_BUDGET_S": INIT_BUDGET_S,
        "PLY_CAP": PLY_DRAW_CAP,
        "MAX_UNZIPPED_BYTES": MAX_UNZIPPED_BYTES,
        "BASE_MS": BASE_MS,
        "INCREMENT_MS": INCREMENT_MS,
    }
    tree = ast.parse(text)
    actual: dict[str, float] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value.value, int | float):
                    actual[target.id] = float(node.value.value)
    for name, want in expected.items():
        got = actual.get(name)
        if got is None:
            c.warn(f"{name} not found in harness/rules.py")
        elif got != want:
            c.warn(f"{name} = {got:g}, live docs say {want:g} (harness is read-only; do not edit)")
    if c.status == PASS:
        c.say("all five constants match")


def check_agent_at_root(report: Report, names: list[str]) -> None:
    c = report.check("C01", "agent.py sits at the zip root")
    nested = [n for n in names if n.endswith("/agent.py")]
    if "agent.py" in names:
        c.say("agent.py is a top-level member")
    else:
        c.fail("agent.py is NOT at the zip root; the platform does `import agent`")
    if nested:
        c.fail(f"agent.py also appears inside a folder: {', '.join(nested)}")
    tops = {n.split("/")[0] for n in names}
    if len(tops) == 1 and not (tops & {"agent.py"}):
        c.fail(f"the archive is wrapped in a single folder {tops.pop()!r}")


def check_root_inventory(report: Report, names: list[str]) -> None:
    c = report.check("C02", "Root .py inventory is exactly the expected set")
    root_py = {n for n in names if "/" not in n and n.endswith(".py")}
    unexpected = sorted(root_py - EXPECTED_ROOT_PY)
    missing = sorted(REQUIRED_ROOT_PY - root_py)
    c.say(f"{len(root_py)} root .py: {', '.join(sorted(root_py))}")
    for name in unexpected:
        c.fail(f"UNEXPECTED root .py in the zip: {name}  (scratch files ship; see HANDOFF rule 8)")
    for name in missing:
        c.fail(f"required engine file missing from the zip: {name}")
    riding = sorted(root_py & TOLERATED_ROOT_PY)
    if riding:
        c.warn(
            f"ships but is not imported by agent.py: {', '.join(riding)} "
            "(package.py globs every root *.py)"
        )


def check_shadowing(report: Report, names: list[str]) -> None:
    c = report.check("C03", "No shipped file shadows a stdlib or permitted-package module")
    forbidden = set(sys.stdlib_module_names) | PERMITTED_PACKAGES
    hits = 0
    for name in names:
        path = Path(name)
        if path.suffix != ".py":
            continue
        stem = path.stem
        if stem in forbidden:
            hits += 1
            where = "zip root (first on sys.path)" if "/" not in name else "subdirectory"
            c.fail(f"{name} shadows module {stem!r} in the {where}")
    for name in names:
        if name.endswith("/__init__.py"):
            pkg = name.split("/")[0]
            if pkg in forbidden:
                hits += 1
                c.fail(f"package directory {pkg}/ shadows module {pkg!r}")
    if hits == 0:
        c.say(f"checked {len([n for n in names if n.endswith('.py')])} .py names against "
              f"{len(forbidden)} stdlib + permitted names")


def check_binaries(report: Report, unzipped: Path, names: list[str]) -> None:
    c = report.check("C04", "No native binaries (magic bytes, not extension alone)")
    hits = 0
    for name in names:
        path = unzipped / name
        if not path.is_file():
            continue
        head = path.open("rb").read(8)
        for magic, label in BINARY_MAGICS:
            if head.startswith(magic):
                hits += 1
                c.fail(f"{name}: {label} magic {head[: len(magic)].hex()}")
                break
        if Path(name).suffix.lower() in BINARY_EXTENSIONS:
            hits += 1
            c.fail(f"{name}: native-binary extension {Path(name).suffix}")
    if hits == 0:
        c.say(f"scanned {len(names)} members; no ELF / Mach-O / PE headers, no binary extensions")


def check_size(report: Report, zip_path: Path, infos: list[zipfile.ZipInfo]) -> None:
    c = report.check("C05", "Unzipped size is under the 50 MB cap")
    unzipped = sum(i.file_size for i in infos)
    compressed = zip_path.stat().st_size
    pct = 100.0 * unzipped / MAX_UNZIPPED_BYTES
    c.say(f"{unzipped:,} bytes unzipped = {pct:.2f}% of {MAX_UNZIPPED_BYTES:,}")
    c.say(f"{compressed:,} bytes compressed, {len(infos)} members")
    if unzipped > MAX_UNZIPPED_BYTES:
        c.fail(f"over the cap by {unzipped - MAX_UNZIPPED_BYTES:,} bytes")
    elif pct > 90.0:
        c.warn("over 90% of the budget")


def check_imports(report: Report, modules: dict[str, ModuleInfo], names: list[str]) -> None:
    c = report.check("C06", "Every import resolves to stdlib, a permitted package, or the zip")
    local = {Path(n).stem for n in names if n.endswith(".py")}
    local |= {n.split("/")[0] for n in names if n.endswith("/__init__.py")}
    stdlib = set(sys.stdlib_module_names)
    found: dict[str, set[str]] = {}
    for info in modules.values():
        for node in ast.walk(info.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.setdefault(alias.name.split(".")[0], set()).add(info.name)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.setdefault(node.module.split(".")[0], set()).add(info.name)
    ok: list[str] = []
    for module_name in sorted(found):
        if module_name in local:
            ok.append(f"{module_name} (shipped)")
        elif module_name in stdlib:
            ok.append(f"{module_name} (stdlib)")
        elif module_name in PERMITTED_PACKAGES:
            ok.append(f"{module_name} (permitted)")
        else:
            c.fail(
                f"import {module_name!r} in {', '.join(sorted(found[module_name]))} is not "
                f"stdlib, not shipped, and not one of {sorted(PERMITTED_PACKAGES)}"
            )
    c.say(f"{len(found)} distinct top-level imports across {len(modules)} shipped modules")
    c.say("  " + ", ".join(ok))


@dataclass
class Scanner:
    directory: str
    extensions: frozenset[str]
    where: str


def _collect_scanners(modules: dict[str, ModuleInfo]) -> list[Scanner]:
    scanners: list[Scanner] = []
    for info in modules.values():
        for node in ast.walk(info.tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            literal_args = [a.value for a in node.args if isinstance(a, ast.Constant)]
            strings = [a for a in literal_args if isinstance(a, str)]
            if name in SCAN_APIS and strings:
                scanners.append(
                    Scanner(strings[0].strip("/"), SCAN_APIS[name], f"{info.name}.py:{node.lineno}")
                )
            elif name in {"listdir", "iterdir", "scandir", "walk"} and strings:
                scanners.append(
                    Scanner(strings[0].strip("/"), ANY_EXTENSION, f"{info.name}.py:{node.lineno}")
                )
            elif name in {"glob", "rglob"}:
                directory = ""
                pattern = strings[0] if strings else "*"
                if isinstance(func, ast.Attribute):
                    for sub in ast.walk(func.value):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                            directory = sub.value.strip("/")
                            break
                if "/" in pattern:
                    directory = f"{directory}/{pattern.rsplit('/', 1)[0]}".strip("/")
                    pattern = pattern.rsplit("/", 1)[1]
                suffix = Path(pattern).suffix
                exts = frozenset({suffix}) if suffix and "*" not in suffix else ANY_EXTENSION
                scanners.append(Scanner(directory, exts, f"{info.name}.py:{node.lineno}"))
    return scanners


def check_dead_weights(report: Report, modules: dict[str, ModuleInfo], unzipped: Path,
                       names: list[str]) -> None:
    c = report.check("C07", "Every file under weights/ is actually loaded by shipped code")
    data_files = [n for n in names if not n.endswith(".py")]
    if not data_files:
        c.say("no data files in the zip")
        return

    literals: set[str] = set()
    for info in modules.values():
        for node in ast.walk(info.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.add(node.value)
                literals.add(node.value.strip("/"))
    scanners = _collect_scanners(modules)
    for scanner in scanners:
        exts = "any extension" if scanner.extensions == ANY_EXTENSION else ", ".join(
            sorted(scanner.extensions)
        )
        c.say(f"scan: {scanner.directory or '.'}/ [{exts}] from {scanner.where}")

    unreferenced: list[tuple[str, int]] = []
    weak: list[str] = []
    for name in data_files:
        path = Path(name)
        if name in literals or path.name in literals or path.stem in literals:
            continue
        covered = False
        for scanner in scanners:
            outside = str(path.parent).strip(".") not in {scanner.directory, ""}
            if outside and not name.startswith(f"{scanner.directory}/"):
                continue
            if scanner.extensions == ANY_EXTENSION:
                covered = True
                weak.append(name)
                break
            if path.suffix in scanner.extensions:
                covered = True
                break
        if not covered:
            unreferenced.append((name, (unzipped / name).stat().st_size))

    covered_count = len(data_files) - len(unreferenced)
    c.say(f"{covered_count}/{len(data_files)} data files are reachable from shipped code")
    if weak:
        c.warn(
            f"{len(weak)} file(s) covered only by an unfiltered directory scan, so this check "
            "cannot prove they are read"
        )
    for name, size in unreferenced:
        c.fail(f"DEAD WEIGHT: {name} ({size:,} bytes) is shipped and referenced by no shipped .py")
    if unreferenced:
        total = sum(s for _, s in unreferenced)
        c.fail(f"{total:,} bytes of unreferenced payload in every upload")


def check_hot_path_output(report: Report, modules: dict[str, ModuleInfo]) -> None:
    c = report.check("C08", "No unguarded per-move output in get_move or anything it calls")
    c.say(
        "rule: import-time output is fine (once per game, inside the 90 s init budget). "
        "Inside the per-move call graph an output call must be (a) behind an env flag that "
        "is FALSE when unset, (b) inside a once-per-game latch `if f: ... f = <const>`, or "
        "(c) inside an except handler whose latch an enclosing `if` tests. "
        "Unlatched except-handler output is a warning; anything else is a failure."
    )
    if "agent" not in modules:
        c.fail("agent.py not in the zip; cannot analyse the hot path")
        return
    reachable = reachable_functions(modules, ("agent", "get_move"))
    c.say(
        f"per-move call graph: {len(reachable)} function(s) -- "
        + ", ".join(f"{m}.{f}" for m, f in reachable)
    )
    counts: dict[str, int] = {}
    for module_name, func_name in reachable:
        info = modules[module_name]
        fn = info.functions[func_name]
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            kind = is_output_call(node)
            if kind is None:
                continue
            verdict = classify_output(info, node, fn)
            counts[verdict] = counts.get(verdict, 0) + 1
            where = f"{module_name}.py:{node.lineno} {kind}() in {func_name}()"
            if verdict == "unguarded":
                c.fail(f"UNGUARDED PER-MOVE OUTPUT: {where}")
            elif verdict == "error-path":
                c.warn(f"unlatched except-handler output (repeats if it keeps failing): {where}")
            else:
                c.say(f"ok ({verdict}): {where}")
    module_level = 0
    for info in modules.values():
        for node in info.tree.body:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and is_output_call(sub):
                    module_level += 1
    c.say(f"{module_level} import-time output call(s) -- once per game, not on the clock")
    if not counts:
        c.say("no output calls anywhere in the per-move call graph")


def check_runtime(report: Report, unzipped: Path, full: bool) -> None:
    env = clean_env()
    c_import = report.check("C09/C10", "import agent works, USE_NUMBA_SEARCH is True, cold import")
    if sys.version_info[:2] != PLATFORM_PYTHON:
        c_import.warn(
            f"local python is {sys.version_info.major}.{sys.version_info.minor}; the platform "
            f"runs {PLATFORM_PYTHON[0]}.{PLATFORM_PYTHON[1]} -- import timing and syntax "
            "acceptance are not identical"
        )
    c_import.say(f"probe env: no CHESSATHON_*, no USE_NUMBA_SEARCH, cwd={unzipped}")
    try:
        result = run_probe(IMPORT_PROBE, unzipped, env, timeout=300.0)
    except subprocess.TimeoutExpired:
        c_import.fail("import did not finish in 300 s")
        return
    if not result.get("ok"):
        c_import.fail(f"import agent failed: {result.get('error')}")
        tail = result.get("_stderr_tail")
        if tail:
            c_import.fail(f"stderr tail: {tail}")
        return
    c_import.say(f"imported {result['agent_file']} from the unzipped archive")
    if result.get("use_numba") is True:
        c_import.say("agent.USE_NUMBA_SEARCH is True with no environment variable set")
    else:
        c_import.fail(
            "agent.USE_NUMBA_SEARCH is not True with a clean environment -- the platform would "
            "play the slow Python search"
        )
    elapsed = float(result["import_s"])
    ratio = JUDGE_IMPORT_S_V10 / LOCAL_IMPORT_S_V10
    projected = elapsed * ratio
    c_import.say(
        f"cold import {elapsed:.1f}s locally; judge/local ratio for v10 was "
        f"{JUDGE_IMPORT_S_V10:.1f}/{LOCAL_IMPORT_S_V10:.1f} = {ratio:.2f}x, so expect "
        f"~{projected:.1f}s on the judge against a {INIT_BUDGET_S:.0f}s budget "
        f"({100 * projected / INIT_BUDGET_S:.0f}%)"
    )
    if projected > INIT_BUDGET_S:
        c_import.fail("projected judge import time exceeds the init budget")
    elif projected > 0.75 * INIT_BUDGET_S:
        c_import.warn("projected judge import time is over 75% of the init budget")

    plies = 128 if full else 24
    base_ms = BASE_MS if full else 15_000
    code = GAME_PROBE.format(
        plies=plies,
        base_ms=base_ms,
        inc_ms=INCREMENT_MS,
        cap=MOVE_REPLY_CAP_BYTES,
        fen="r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    )
    game_env = dict(env)
    game_env["CHESSATHON_REQUIRE_NUMBA"] = "1"
    c_game = report.check("C11/C12", f"Smoke game ({plies} plies, base {base_ms} ms) and peak RSS")
    try:
        game = run_probe(code, unzipped, game_env, timeout=900.0 if full else 300.0)
    except subprocess.TimeoutExpired:
        c_game.fail("smoke game did not finish in time")
        return
    if "plies" not in game:
        c_game.fail(f"smoke game produced no result: {game.get('error')}")
        tail = game.get("_stderr_tail")
        if tail:
            c_game.fail(f"stderr tail: {tail}")
        return
    problems = list(game.get("problems") or [])
    c_game.say(
        f"{game['plies']} plies played from the HANDOFF opening position; "
        f"clock left W {float(game['white_left_ms']):,.0f} ms / "
        f"B {float(game['black_left_ms']):,.0f} ms"
    )
    c_game.say(f"final outcome: {game['outcome']}")
    for problem in problems:
        c_game.fail(str(problem))
    if int(game["plies"]) < plies and not problems:
        c_game.say("game ended early with a real result, not a fault")
    rss = int(game["peak_rss_bytes"])
    c_game.say(
        f"peak RSS {rss / 1024 / 1024:.0f} MB of "
        f"{MEMORY_LIMIT_BYTES / 1024 / 1024:.0f} MB "
        f"({100 * rss / MEMORY_LIMIT_BYTES:.1f}%); v10 measured "
        f"{JUDGE_PEAK_RSS_MB_V10:.0f} MB on the judge"
    )
    if rss > MEMORY_LIMIT_BYTES:
        c_game.fail("peak RSS is over the 2 GB limit")
    elif rss > 0.75 * MEMORY_LIMIT_BYTES:
        c_game.warn("peak RSS is over 75% of the limit")


def check_worktree(report: Report, repo: Path, paths: list[str]) -> None:
    c = report.check("C13", "Working tree matches HEAD for every shipped file")
    status = git(repo, "status", "--porcelain", "--", *paths).strip()
    if status:
        for line in status.splitlines():
            c.fail(f"git status: {line}")
    drifted = 0
    for path in paths:
        live = repo / path
        if not live.exists():
            c.fail(f"{path} is in HEAD but missing from the working tree")
            continue
        if live.read_bytes() != git_blob(repo, path):
            drifted += 1
            c.fail(f"{path} differs from HEAD -- the zip was built from HEAD, NOT from this file")
    untracked = [
        line[3:]
        for line in git(repo, "status", "--porcelain").splitlines()
        if line.startswith("??") and line[3:].endswith(".py") and "/" not in line[3:]
    ]
    for name in untracked:
        c.fail(f"untracked root .py {name!r} would be swept into a working-tree build")
    if c.status == PASS:
        c.say(f"{len(paths)} shipped files, all byte-identical to HEAD, {drifted} drifted")


# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="128-ply game at the real time control")
    parser.add_argument("--no-runtime", action="store_true", help="static checks only")
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1],
        help="repository to preflight (default: the repo this script lives in)"
    )
    parser.add_argument("--keep", type=Path, help="keep the staging/zip/unzip artefacts here")
    parser.add_argument(
        "--zip", type=Path,
        help="audit an already-built zip instead of building one from HEAD "
             "(skips the working-tree check)"
    )
    arguments = parser.parse_args()

    repo = arguments.repo.resolve()
    sys.path.insert(0, str(repo))
    from harness.package import build as package_build

    workdir = Path(tempfile.mkdtemp(prefix="preflight-"))
    staging = workdir / "staging"
    unzipped = workdir / "unzipped"
    staging.mkdir()
    unzipped.mkdir()
    zip_path = workdir / "submission.zip"

    report = Report()
    print(f"preflight: repo {repo}")
    print(f"preflight: HEAD {git(repo, 'rev-parse', '--short', 'HEAD').strip()} "
          f"on {git(repo, 'rev-parse', '--abbrev-ref', 'HEAD').strip()}")
    print(f"preflight: workdir {workdir}")
    print(f"preflight: python {sys.version.split()[0]} at {sys.executable}")
    print()

    paths: list[str] = []
    if arguments.zip:
        zip_path = arguments.zip.resolve()
        print(f"preflight: auditing prebuilt zip {zip_path}")
    else:
        paths = stage_head(repo, staging)
        try:
            package_build(staging, zip_path, ("weights",))
        except SystemExit as exc:
            c = report.check("C01", "agent.py sits at the zip root")
            c.fail(f"harness/package.py refused to build: {exc}")
            print(report.render())
            shutil.rmtree(workdir, ignore_errors=True)
            return 1
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        names = archive.namelist()
        archive.extractall(unzipped)

    modules: dict[str, ModuleInfo] = {}
    parse_errors: list[str] = []
    for name in names:
        if not name.endswith(".py"):
            continue
        try:
            modules[Path(name).stem] = build_module_info(
                Path(name).stem, (unzipped / name).read_text(encoding="utf-8", errors="replace")
            )
        except SyntaxError as exc:
            parse_errors.append(f"{name}: {exc}")

    check_docs_freshness(report)
    check_harness_constants(report, repo)
    check_agent_at_root(report, names)
    check_root_inventory(report, names)
    check_shadowing(report, names)
    check_binaries(report, unzipped, names)
    check_size(report, zip_path, infos)
    if parse_errors:
        c = report.check("C06a", "Every shipped .py parses")
        for line in parse_errors:
            c.fail(line)
    check_imports(report, modules, names)
    check_dead_weights(report, modules, unzipped, names)
    check_hot_path_output(report, modules)
    if arguments.no_runtime:
        report.check("C09/C10", "Runtime probes").status = SKIP
        report.check("C11/C12", "Runtime probes").status = SKIP
    else:
        check_runtime(report, unzipped, arguments.full)
    if arguments.zip:
        report.check("C13", "Working tree matches HEAD (n/a for --zip)").status = SKIP
    else:
        check_worktree(report, repo, paths)

    print(report.render())

    if arguments.keep:
        arguments.keep.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zip_path, arguments.keep / "submission.zip")
        print(f"\nzip kept at {arguments.keep / 'submission.zip'}")
    shutil.rmtree(workdir, ignore_errors=True)
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
