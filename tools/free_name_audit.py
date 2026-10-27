#!/usr/bin/env python3
"""
tools/free_name_audit.py -- find names that are guaranteed NameErrors.

WHY THIS EXISTS
---------------
2026-10-27 found that examples/phase6_uvm_crv_uart/uart_uvm_crv_tb.py had
been UNRUNNABLE since 2026-10-11.  Commit ace870a extracted the tail of
`report_phase` into a new `_tail` method and left behind

    print(line)

where `line` was a LOCAL of `report_phase`.  Nothing caught it for sixteen
days, for two reasons that are both this repository's recorded themes:

  1. cocotb was believed un-installable, so nothing ran the file at all; and
  2. the crash fires ONE STATEMENT AFTER the `RESULT:` line that
     run_mutation_tests.sh greps, so the runner scored the crashing bench
     as a clean PASS.

2026-10-26 recorded the SAME fault class from the other side: refactoring
tools/test_neutrality_controls.py's override table deleted CP_LINE,
COMMENT_TEXT, REAL_SED and REAL_LINE, and runner B "aborted with a
NameError instead of a verdict".  That one was found by RUNNING it.  This
audit finds the class WITHOUT running anything, which is the whole point:
every runner here is gated on a toolchain, and a NameError on a cold path
is invisible to a bench that never reaches that path.

WHAT IT CHECKS
--------------
For every committed .py file, every name that is

  * REFERENCED inside a function or class body, and
  * resolved by Python to the GLOBAL scope (not a local, not a parameter,
    not a closure cell from an enclosing function), and
  * not bound anywhere at module level, not declared `global` and assigned
    somewhere, and not a builtin

is reported.  Such a name raises NameError the moment its line executes.
This is a decidable, zero-judgement property: it is computed from
CPython's own scope analysis (the `symtable` module), not from a grep.

WHAT IT DOES *NOT* CLAIM
------------------------
Soundness limits, stated rather than hidden, because an audit that
overstates its reach is this repository's most-recorded fault:

  * `from X import *` at module level makes the module's global set
    OPEN.  Such a file is reported UNSOUND, never CLEAN -- a star import
    could be supplying the name, and this audit cannot tell.
  * names injected at runtime (`globals()[...] = ...`, exec, a module
    patched by its importer) are invisible here and would be reported as
    findings.  None exist in this repository today; if one appears, the
    right response is to make the injection explicit, not to loosen this
    check.
  * a file that does not parse is reported UNPARSEABLE, which is a
    finding, not a pass.
  * the converse is NOT checked: this says nothing about a name that is
    bound but bound to the wrong thing.

Run:  python3 tools/free_name_audit.py [--root DIR] [--selftest]
Exit: 0 iff every file is CLEAN.  Any FINDING, UNSOUND or UNPARSEABLE
      file is a non-zero exit, so a caller cannot read "no findings"
      off a run that could not look.
"""

import argparse
import ast
import builtins
import os
import sys
import symtable

BUILTINS = set(dir(builtins))

# Names CPython makes available in a module's global namespace without any
# assignment appearing in the source.  Referencing these is legitimate.
IMPLICIT_MODULE_GLOBALS = {
    "__name__", "__file__", "__doc__", "__package__", "__loader__",
    "__spec__", "__builtins__", "__debug__", "__path__", "__dict__",
    "__class__", "__module__", "__qualname__", "__annotations__",
}

SKIP_DIR_NAMES = {".git", "sim_build", "__pycache__", ".pytest_cache"}


def module_bound_names(top):
    """Names bound at module level: assigned, imported, def/class, or
    declared `global` and assigned inside some function."""
    bound = set()
    for sym in top.get_symbols():
        if sym.is_assigned() or sym.is_imported() or sym.is_namespace():
            bound.add(sym.get_name())

    # `global X; X = ...` inside a function binds X at module level.
    def walk(table):
        for sym in table.get_symbols():
            if sym.is_declared_global() and sym.is_assigned():
                bound.add(sym.get_name())
        for child in table.get_children():
            walk(child)

    walk(top)
    return bound


def has_star_import(src):
    """True iff the module really executes `from X import *` at any scope.

    This uses the PARSER, not a line grep.  The first draft of this file
    grepped the text and flagged ITSELF, because its own positive controls
    contain `from os.path import *` inside a string literal -- a grep
    cannot tell source from data.  That is the same confusion this audit
    exists to remove, found in the audit, before it was committed.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == "*" for alias in node.names):
                return True
    return False


def scope_path(table, parents):
    parts = [t.get_name() for t in parents[1:]] + [table.get_name()]
    return ".".join(parts) if parts else "<module>"


def audit_source(src, filename):
    """Return (status, findings). status in CLEAN/FINDING/UNSOUND/UNPARSEABLE."""
    try:
        top = symtable.symtable(src, filename, "exec")
    except SyntaxError as exc:
        return "UNPARSEABLE", [("<module>", "<syntax error>", str(exc))]

    if has_star_import(src):
        return "UNSOUND", [("<module>", "<star import>",
                            "module-level `from ... import *` leaves the "
                            "global set open; this file cannot be cleared")]

    allowed = module_bound_names(top) | BUILTINS | IMPLICIT_MODULE_GLOBALS
    findings = []

    def walk(table, parents):
        if table.get_type() in ("function", "class"):
            for sym in table.get_symbols():
                name = sym.get_name()
                if not sym.is_referenced():
                    continue
                if sym.is_local() or sym.is_parameter() or sym.is_free():
                    continue
                if not sym.is_global():
                    continue
                if name in allowed:
                    continue
                findings.append((scope_path(table, parents), name,
                                 "referenced, resolves to global scope, "
                                 "bound nowhere at module level"))
        for child in table.get_children():
            walk(child, parents + [table])

    walk(top, [])
    return ("FINDING" if findings else "CLEAN"), findings


def python_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIR_NAMES)
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def run(root, quiet=False):
    files = python_files(root)
    counts = {"CLEAN": 0, "FINDING": 0, "UNSOUND": 0, "UNPARSEABLE": 0}
    all_findings = []

    for path in files:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        rel = os.path.relpath(path, root)
        status, findings = audit_source(src, rel)
        counts[status] += 1
        if status != "CLEAN":
            all_findings.append((rel, status, findings))

    if not quiet:
        print("=" * 72)
        print("FREE-NAME AUDIT -- names that raise NameError when reached")
        print("=" * 72)
        print()
        print("  root           : %s" % root)
        print("  python files   : %d" % len(files))
        print()
        print("  CLEAN          : %d" % counts["CLEAN"])
        print("  FINDING        : %d" % counts["FINDING"])
        print("  UNSOUND        : %d  (star import -- cannot be cleared)"
              % counts["UNSOUND"])
        print("  UNPARSEABLE    : %d" % counts["UNPARSEABLE"])
        print()
        if all_findings:
            print("-" * 72)
            for rel, status, findings in all_findings:
                print()
                print("  %s  [%s]" % (rel, status))
                for scope, name, why in findings:
                    print("      scope %s" % scope)
                    print("      name  %s" % name)
                    print("      why   %s" % why)
            print()
            print("-" * 72)
        else:
            print("  no findings: every referenced global name is bound.")
            print()
        bad = counts["FINDING"] + counts["UNSOUND"] + counts["UNPARSEABLE"]
        print("  RESULT         : %s  (%d file(s) not clean)"
              % ("PASS" if bad == 0 else "FAIL", bad))
        print("=" * 72)

    return counts, all_findings


# ----------------------------------------------------------------------
# POSITIVE CONTROLS
#
# A check that cannot fail reports green indefinitely -- this repository
# has recorded that shape three sessions running (2026-10-25's G6 behind
# an earlier refusal, 2026-10-26's N1 for runner E using a defect that
# bench cannot see).  So every control below is asserted to fire, and each
# one names the specific way this audit could be vacuous.
#
# P1 is the real 2026-10-27 defect, verbatim: an extracted method keeping
# a reference to a local of the method it was extracted from.
# ----------------------------------------------------------------------
CONTROLS = [
    ("P1 extracted method keeps caller's local (the real 2026-10-11 defect)",
     '''
class C:
    def _tail(self, x):
        print(x)
        print(line)

    def report(self):
        line = "=" * 72
        print(line)
        self._tail(1)
''', "FINDING", "line"),

    ("P2 name deleted by a refactor but still referenced (2026-10-26's fault)",
     '''
REAL_SED = "s/a/b/"

def runner_b():
    return (REAL_SED, CP_LINE)
''', "FINDING", "CP_LINE"),

    ("P3 typo in a module-level constant's name",
     '''
MAX_TX = 8

def f():
    return MAX_TXX
''', "FINDING", "MAX_TXX"),

    ("P4 nested function referencing an undefined global",
     '''
def outer():
    def inner():
        return nowhere
    return inner
''', "FINDING", "nowhere"),

    ("P5 class body referencing an undefined global",
     '''
class C:
    x = undefined_at_class_scope
''', "FINDING", "undefined_at_class_scope"),
]

NEGATIVE_CONTROLS = [
    ("N1 closure over an enclosing function's local must NOT be reported",
     '''
def outer():
    line = "=" * 72
    def inner():
        return line
    return inner
'''),
    ("N2 module global defined AFTER the function must NOT be reported",
     '''
def f():
    return LATER

LATER = 3
'''),
    ("N3 `global` + assignment inside a function must NOT be reported",
     '''
def setup():
    global CACHE
    CACHE = {}

def use():
    return CACHE
'''),
    ("N4 builtins and dunders must NOT be reported",
     '''
def f():
    return len(__file__) + int("3") + ValueError.__name__
'''),
    ("N5 imported name must NOT be reported",
     '''
import os
from sys import argv

def f():
    return os.sep + argv[0]
'''),
    ("N6 comprehension variable must NOT be reported",
     '''
def f(xs):
    return [y for y in xs if y]
'''),
    ("N7 method referring to another method via self must NOT be reported",
     '''
class C:
    def a(self):
        return 1
    def b(self):
        return self.a()
'''),
]

UNSOUND_CONTROL = (
    "U1 a star import must be reported UNSOUND, never CLEAN",
    '''
from os.path import *

def f():
    return join("a", "b")
''')

UNPARSEABLE_CONTROL = (
    "U2 a file that does not parse must be reported UNPARSEABLE, never CLEAN",
    '''
def f(:
    pass
''')


def selftest():
    print("=" * 72)
    print("FREE-NAME AUDIT SELFTEST -- can this check fail at all?")
    print("=" * 72)
    print()
    passed = failed = 0

    print("  POSITIVE CONTROLS (the audit MUST report each defect)")
    for label, src, want_status, want_name in CONTROLS:
        status, findings = audit_source(src, "<control>")
        names = [n for _, n, _ in findings]
        ok = (status == want_status) and (want_name in names)
        print("    %-4s %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            print("         wanted %s/%s, got %s/%s"
                  % (want_status, want_name, status, names))
        passed += ok
        failed += (not ok)

    print()
    print("  NEGATIVE CONTROLS (the audit MUST stay silent -- no false alarms)")
    for label, src in NEGATIVE_CONTROLS:
        status, findings = audit_source(src, "<control>")
        ok = status == "CLEAN"
        print("    %-4s %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            print("         got %s %s" % (status, findings))
        passed += ok
        failed += (not ok)

    print()
    print("  SOUNDNESS CONTROLS (the audit MUST refuse to clear these)")
    for label, src, want in ((UNSOUND_CONTROL[0], UNSOUND_CONTROL[1], "UNSOUND"),
                             (UNPARSEABLE_CONTROL[0], UNPARSEABLE_CONTROL[1],
                              "UNPARSEABLE")):
        status, _ = audit_source(src, "<control>")
        ok = status == want
        print("    %-4s %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            print("         wanted %s, got %s" % (want, status))
        passed += ok
        failed += (not ok)

    print()
    print("  TOTAL: %d passed, %d failed" % (passed, failed))
    print("=" * 72)
    return 0 if failed == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None,
                    help="repository root (default: the directory above tools/)")
    ap.add_argument("--selftest", action="store_true",
                    help="run the positive/negative controls and exit")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    root = args.root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    counts, findings = run(root)
    bad = counts["FINDING"] + counts["UNSOUND"] + counts["UNPARSEABLE"]
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
