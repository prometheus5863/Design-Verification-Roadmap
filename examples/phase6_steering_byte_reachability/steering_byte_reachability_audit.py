#!/usr/bin/env python3
"""
steering_byte_reachability_audit.py -- the strong form of the 2026-11-03
"BORDERLINE PAIR UNDER STEERING" item, and the refutation of the method that
item proposed for it.

WHAT THE ITEM ASKED FOR
-----------------------
2026-11-03 Section 4 observed that the coverage-steered policy drove ZERO
borderline bytes (0x40, 0xC0) in 95 payloads, against 17 of 1884 under pure
random, and logged it honestly as `unobserved rather than shown absent`.  The
open item then proposed how to close it:

    "The strong form of the claim is about the MAP and needs no simulator at
     all: enumerate what `byte_for_class` can emit."

This file does that enumeration, and the enumeration is the easy half.  The
item's proposed method turns out to be NECESSARY BUT NOT SUFFICIENT, and this
file is mostly about why.

THE FINDING
-----------
`byte_for_class` cannot emit a borderline byte -- that part of the item is
confirmed, exactly, and it is confirmed over the WHOLE set of bytes
`_steered_item` can assign, not just that function's range.  But
`_steered_item` has SEVEN return paths and only TWO of them assign
`steer_byte` at all.  The other five return with `steer_byte = None`, and the
driver's line

    byte = (it.steer_byte if it.steer_byte is not None
            else self.rng.getrandbits(8))

then draws the payload uniformly over all 256 values.  So under the steered
policy the borderline pair is REACHABLE, with probability 2/256 per push on
any push that came from one of those five branches.  The strong form of the
claim is therefore FALSE, and an audit that had enumerated only
`byte_for_class` would have concluded the opposite.

The structural point is sharper than the statistics.  The five random-byte
branches include the LAST one -- the `cp_txq` full-bin fallback, which is
reached only when every other coverpoint is closed, and which forces
`burst_len = 8`.  cp_txq's `full` bin is the one the bench documents as
needing a long burst with the UART disabled, i.e. the hardest and therefore
typically the last bin standing.  So the TAIL of a steered run is not merely
sometimes random: it is eight uniformly random bytes per item, by
construction.

AND THE 11-03 OBSERVATION CARRIES NO INFORMATION
------------------------------------------------
Section 4 below prices the observation instead of arguing about it.  Even in
the MAXIMALLY EXPOSED case -- every one of the 95 steered payloads drawn
uniformly -- P(no borderline byte) = (254/256)^95 = 0.4747.  Seeing zero is
very close to a coin flip, so `zero of 95` is consistent with full exposure
and with no exposure alike, and it was never evidence about the map in either
direction.  11-03's own "unobserved rather than shown absent" was the right
call; what is new here is that the gap cannot be closed by looking at the map,
because the map is not what emits most steered bytes.

WHAT IS CHECKED, AND WHAT IS EXACT
----------------------------------
  S1  the steering map's IMAGE, lifted from the live bench by AST.  Nothing
      is re-typed: the literals are read out of `_steered_item`'s own source
      and `byte_for_class` is exec'd from the live definition.  V1 is an
      EXACTLY KNOWN target -- `data_class(byte_for_class(c)) == c` for all
      six classes -- because a steering map that does not land in the bin it
      names cannot close that bin, and the answer is known in advance to be
      the identity.
  S2  the branch census: how many return paths assign `steer_byte`, and how
      many leave it None.  This is the half the item's method omits.
  S3  the two-valued verdict the item asked for, and the two-valued verdict
      the policy actually has, side by side.  They disagree, and the
      disagreement is the finding.
  S4  the price of `zero of 95`, computed EXACTLY as a Fraction and compared
      against the float -- so the headline number is validated against a
      value known in advance to be rational, not against a range.
  S5  MUTATION, two mutants, and the second is the one that matters:
        M1  add 0x40 to the steering map -> the map-level verdict must flip.
        M2  run the ITEM'S OWN PROPOSED METHOD (enumerate `byte_for_class`
            only) against a bench whose random-byte branches have been
            removed, and against the real one.  It returns the SAME answer
            for both, which is exactly why it is not sufficient.
"""

import ast
import os
import sys
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
_EX = os.path.dirname(_HERE)
for _p in (os.path.join(_EX, 'phase4_uvm_milestone'),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import payload_coverage_model as M                              # noqa: E402

CRV_SRC = os.path.join(_EX, 'phase6_uvm_crv_uart', 'uart_uvm_crv_tb.py')

# The 11-03 live measurement, for Section 4.  Carried as a constant with its
# provenance because it is a number from a transcript in this repository and
# not a free parameter: steer=1 drove 95 payloads and saw 0 borderline bytes.
STEER1_PAYLOADS = 95
STEER1_BORDERLINE_SEEN = 0
RANDOM_PAYLOADS = 1884
RANDOM_BORDERLINE_SEEN = 17

_PASS, _FAIL = [], []


def check(label, ok, detail=""):
    (_PASS if ok else _FAIL).append(label)
    print("  [%s] %s" % ("PASS" if ok else "FAIL", label))
    if detail:
        print("         %s" % detail)
    return ok


def head(n, title):
    print()
    print("=" * 76)
    print("SECTION %s -- %s" % (n, title))
    print("=" * 76)


# ---------------------------------------------------------------------------
# Lifting the live bench
# ---------------------------------------------------------------------------

def lift(src=CRV_SRC):
    """Return (data_class, byte_for_class, steered_item_ast, driver_src).

    The two pure functions are exec'd from their own definitions; the steering
    method is returned as an AST node because what this audit needs from it is
    its CONTROL FLOW, not its behaviour -- and its behaviour depends on a
    coverage state that only the simulator produces.  That is the whole reason
    the strong form of the claim is structural.

    A failure to lift is a FAILURE, never a fallback to a local copy: a copy
    makes every claim below a claim about a fork.
    """
    with open(src) as fh:
        text = fh.read()
    tree = ast.parse(text, filename=src)
    want = {'data_class', 'byte_for_class'}
    found, steered = {}, None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name in want:
                mod = ast.Module(body=[node], type_ignores=[])
                ns = {}
                exec(compile(mod, src, 'exec'), ns)
                found[node.name] = ns[node.name]
            if node.name == '_steered_item':
                steered = node
    missing = want - set(found)
    if missing or steered is None:
        raise AssertionError(
            "could not lift %s from %s -- the live bench has been renamed or "
            "restructured, and this audit must be repaired rather than given "
            "a local copy of the steering map"
            % (sorted(missing) + ([] if steered else ['_steered_item']), src))
    return found['data_class'], found['byte_for_class'], steered, text


def steer_byte_assignments(node):
    """Every assignment to `*.steer_byte` inside the steering method.

    Returned as (kind, value) pairs where kind is one of 'const', 'map' or
    'none'.  Walking the AST rather than reading the six-element list means a
    branch added later with a NEW literal is picked up without editing this
    audit -- which is the failure mode the 11-03 item's method has.
    """
    out = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Assign):
            continue
        for tgt in sub.targets:
            if not (isinstance(tgt, ast.Attribute)
                    and tgt.attr == 'steer_byte'):
                continue
            v = sub.value
            if isinstance(v, ast.Constant) and v.value is None:
                out.append(('none', None))
            elif isinstance(v, ast.Constant) and isinstance(v.value, int):
                out.append(('const', v.value))
            elif isinstance(v, ast.IfExp):
                # `0x07 if (k % 2) else 0x33` -- BOTH arms are reachable
                for arm in (v.body, v.orelse):
                    if isinstance(arm, ast.Constant) and isinstance(
                            arm.value, int):
                        out.append(('const', arm.value))
                    else:
                        out.append(('opaque', ast.dump(arm)))
            elif isinstance(v, ast.Call) and isinstance(v.func, ast.Name) \
                    and v.func.id == 'byte_for_class':
                out.append(('map', None))
            else:
                out.append(('opaque', ast.dump(v)))
    return out


def returning_branches(node):
    """Classify every return path of `_steered_item` STRUCTURALLY.

    Returns (paths, shape_ok) where `paths` is a list of
    (where, assigns_steer_byte) in source order and `shape_ok` says whether
    the method really has the shape this analysis requires.

    The first draft of this function sorted `steer_byte` assignments and
    `return`s by line number and carried a running "last assignment wins"
    state.  That is a HEURISTIC, and its docstring claimed it was asserted --
    it was not.  It happens to give the right answer on the current method and
    would give a silently wrong one on a method with a nested conditional, an
    `else` clause, or an assignment after a return.  So it is replaced by a
    walk of the actual block structure: each top-level `for` is one branch,
    the trailing statements are one more, and a branch is a steering branch
    iff a `steer_byte` assignment to a non-None value appears in that block.

    `shape_ok` is False if any block holds more than one `return`, or if a
    `return` appears outside a top-level `for` and outside the tail -- the two
    ways the per-block reading could be unsound.  S2 checks it, so a future
    rewrite of the bench fails this audit rather than being mis-analysed.
    """
    def sets_byte(stmts):
        for st in stmts:
            for sub in ast.walk(st):
                if not isinstance(sub, ast.Assign):
                    continue
                for tgt in sub.targets:
                    if (isinstance(tgt, ast.Attribute)
                            and tgt.attr == 'steer_byte'
                            and not (isinstance(sub.value, ast.Constant)
                                     and sub.value.value is None)):
                        return True
        return False

    def returns_in(stmts):
        return [s for st in stmts for s in ast.walk(st)
                if isinstance(s, ast.Return)]

    paths, shape_ok = [], True
    tail = []
    for stmt in node.body:
        if isinstance(stmt, ast.For):
            rets = returns_in([stmt])
            if len(rets) != 1:
                shape_ok = False
            if rets:
                paths.append(("for@%d" % stmt.lineno, sets_byte([stmt])))
        else:
            tail.append(stmt)
    tail_rets = returns_in(tail)
    if len(tail_rets) > 1:
        shape_ok = False
    if tail_rets:
        paths.append(("tail@%d" % tail_rets[0].lineno, sets_byte(tail)))
    # Every return in the method must have been accounted for by exactly one
    # of the blocks above, or a path exists that this analysis cannot see.
    if len(returns_in(node.body)) != len(paths):
        shape_ok = False
    return paths, shape_ok


def driver_draws_random(text):
    """Is there a path in the DRIVER that draws the payload at random?

    The structural claim stands or falls on this line, so it is read out of
    the live source rather than asserted from the bench's documentation.
    """
    tree = ast.parse(text)
    for sub in ast.walk(tree):
        if isinstance(sub, ast.IfExp):
            d = ast.dump(sub)
            if 'steer_byte' in d and 'getrandbits' in d:
                return True, ast.dump(sub)
    return False, ""


def main():
    print("=" * 76)
    print("STEERING BYTE REACHABILITY AUDIT -- 2026-11-04")
    print("Can the coverage-steered policy emit a BORDERLINE payload?")
    print("=" * 76)

    data_class, byte_for_class, steered, text = lift()
    rows = M.load_measured()
    borderline = sorted(b for b in range(256)
                        if M.classify(b, rows) == M.BORDERLINE)

    # -------------------------------------------------------------- S1 ----
    head(1, "the steering map's image, lifted not re-typed")
    assigns = steer_byte_assignments(steered)
    consts = sorted({v for k, v in assigns if k == 'const'})
    uses_map = any(k == 'map' for k, _ in assigns)
    opaque = [v for k, v in assigns if k == 'opaque']
    map_range = sorted({byte_for_class(c) for c in range(6)})
    image = sorted(set(consts) | (set(map_range) if uses_map else set()))

    print("  assignments to `steer_byte` found      : %d" % len(assigns))
    print("  literal bytes assigned directly        : %s"
          % ["0x%02X" % b for b in consts])
    print("  `byte_for_class(...)` used             : %s" % uses_map)
    print("  range of `byte_for_class`              : %s"
          % ["0x%02X" % b for b in map_range])
    print("  IMAGE (every byte steering can NAME)   : %s"
          % ["0x%02X" % b for b in image])
    print("  BORDERLINE set, derived from the model : %s"
          % ["0x%02X" % b for b in borderline])

    check("no opaque `steer_byte` assignment: every one is a literal, a "
          "byte_for_class call, or None",
          not opaque,
          "an opaque assignment would make the image below a LOWER bound and "
          "every verdict in S3 unsound" if opaque else
          "%d assignments, all classified" % len(assigns))

    check("V1 the steering map lands in the bin it names: "
          "data_class(byte_for_class(c)) == c for all 6 classes",
          all(data_class(byte_for_class(c)) == c for c in range(6)),
          "EXACTLY KNOWN IN ADVANCE -- the identity, not a range.  got %s"
          % [data_class(byte_for_class(c)) for c in range(6)])

    # The pd-cross literals carry their own exact requirement: the branch
    # picks 0x07 when (k % 2) and 0x33 otherwise, and k's low bit IS the
    # popcount-parity axis of the parity x popcount cross.  So the two
    # literals must have odd and even popcount respectively, or the branch
    # steers the wrong half of its own cross.
    check("V2 the pd-cross literals match the axis they steer: 0x07 odd "
          "popcount, 0x33 even",
          bin(0x07).count('1') % 2 == 1 and bin(0x33).count('1') % 2 == 0,
          "EXACTLY KNOWN -- popcount(0x07)=%d, popcount(0x33)=%d"
          % (bin(0x07).count('1'), bin(0x33).count('1')))

    hit = sorted(set(image) & set(borderline))
    check("the item's own question: `byte_for_class` (and every other literal "
          "in the map) cannot emit a borderline byte",
          not hit,
          "image n BORDERLINE = %s -- CONFIRMED, and over the whole image "
          "rather than just byte_for_class's range"
          % ["0x%02X" % b for b in hit])

    # -------------------------------------------------------------- S2 ----
    head(2, "the half the item's method omits: five of seven branches never "
            "assign the byte at all")
    paths, shape_ok = returning_branches(steered)
    n_ret = len(paths)
    n_none = sum(1 for _, sets in paths if not sets)
    for where, sets in paths:
        print("    %-12s  %s" % (where,
                                 "steers the byte" if sets
                                 else "byte left RANDOM"))
    print("  return paths in `_steered_item`                  : %d" % n_ret)
    print("  ... that assign `steer_byte`                     : %d"
          % (n_ret - n_none))
    print("  ... that return with `steer_byte` still None     : %d" % n_none)

    check("S2a the method has the block shape this analysis requires: one "
          "return per top-level `for`, plus a tail, and no return anywhere "
          "else",
          shape_ok,
          "ASSERTED, not assumed -- the first draft of this check was a "
          "line-number heuristic whose docstring claimed otherwise.  %d "
          "paths, all accounted for" % n_ret)

    check("the method has more than one return path, so a single-path "
          "analysis of it would be unsound",
          n_ret > 1, "%d paths" % n_ret)

    check("at least one return path leaves `steer_byte` None",
          n_none > 0,
          "%d of %d paths.  Each is a path on which the steering map does "
          "NOT choose the payload." % (n_none, n_ret))

    rnd, where = driver_draws_random(text)
    check("the DRIVER draws the payload uniformly when `steer_byte` is None",
          rnd,
          "found in the live source: the conditional selects "
          "`rng.getrandbits(8)`" if rnd else
          "NOT FOUND -- if the driver no longer randomises, S3's verdict "
          "reverses and this audit's finding is obsolete")

    # -------------------------------------------------------------- S3 ----
    head(3, "two verdicts, and they disagree -- which is the finding")
    map_verdict = "UNREACHABLE" if not hit else "REACHABLE"
    policy_verdict = "REACHABLE" if (n_none > 0 and rnd) else "UNREACHABLE"
    print("  borderline, under the MAP alone (the item's question)   : %s"
          % map_verdict)
    print("  borderline, under the POLICY as wired (the real one)    : %s"
          % policy_verdict)
    print()
    print("  Both are true statements about different objects.  The item")
    print("  asked for the first and would have been closed by it; the")
    print("  second is the one a reader of 11-03 Section 4 wants, and it is")
    print("  the opposite answer.")

    check("the strong form of the 11-03 item is REFUTED: the map cannot "
          "name a borderline byte, but the policy can drive one",
          map_verdict == "UNREACHABLE" and policy_verdict == "REACHABLE",
          "map %s / policy %s" % (map_verdict, policy_verdict))

    # The tail-of-run structural point, read off the same path table.
    last_where, last_sets = paths[-1]
    check("the LAST return path -- the cp_txq full-bin fallback, reached only "
          "when every other coverpoint is closed -- is a random-byte path",
          not last_sets,
          "%s leaves the byte random, so the tail of a steered run drives "
          "uniformly random payloads at burst_len = 8 by construction.  Not "
          "an incidental exposure: the hardest bin's branch is the one that "
          "does not steer the byte." % last_where)

    # PLANTED CONTROL on that check, per the standing requirement that every
    # verdict in every vocabulary gets one.  Give the tail an assignment and
    # the check must say the opposite.
    planted = text.replace(
        "        it.burst_len = 8\n        it.parity = self.rng.randrange(3)",
        "        it.burst_len = 8\n        it.steer_byte = 0x5A\n"
        "        it.parity = self.rng.randrange(3)")
    ctrl_ok = False
    if planted != text:
        for nd in ast.walk(ast.parse(planted)):
            if isinstance(nd, ast.FunctionDef) and nd.name == '_steered_item':
                p2, _ = returning_branches(nd)
                ctrl_ok = p2[-1][1] is True
    check("C1 the tail-path check has detection power: a planted "
          "`steer_byte` in the fallback branch flips it",
          ctrl_ok,
          "planted 0x5A in the cp_txq branch and the analysis reports the "
          "tail as steering" if ctrl_ok else
          "the planted mutant did not change the verdict, so the check above "
          "is vacuous and proves nothing")

    # -------------------------------------------------------------- S4 ----
    head(4, "pricing `zero of 95`, against a value known to be rational")
    p_not = Fraction(256 - len(borderline), 256)
    exact = p_not ** STEER1_PAYLOADS
    as_float = float(exact)
    direct = ((256 - len(borderline)) / 256.0) ** STEER1_PAYLOADS
    print("  P(one uniform byte is not borderline)   = %s" % p_not)
    print("  P(none of %d is borderline), EXACT      = %s"
          % (STEER1_PAYLOADS, "%d/%d" % (exact.numerator, exact.denominator)))
    print("  ... as a float                          = %.6f" % as_float)
    print("  ... computed in floating point directly = %.6f" % direct)
    print("  observed under steering                 = %d of %d"
          % (STEER1_BORDERLINE_SEEN, STEER1_PAYLOADS))
    print("  observed under random                   = %d of %d (%.3f %%)"
          % (RANDOM_BORDERLINE_SEEN, RANDOM_PAYLOADS,
             100.0 * RANDOM_BORDERLINE_SEEN / RANDOM_PAYLOADS))

    check("V4 the exact denominator is 2^665, known in advance from "
          "(127/128)^95",
          exact.denominator == 2 ** 665 and exact.numerator == 127 ** 95,
          "EXACTLY KNOWN -- 254/256 reduces to 127/128, so the rational must "
          "be 127^95 / 2^665 and nothing else.  denominator is a power of "
          "two: %s; numerator == 127^95: %s"
          % (exact.denominator == 2 ** 665, exact.numerator == 127 ** 95))

    check("V3 the exact rational and the floating-point power agree to "
          "within 4 ulp",
          abs(as_float - direct) <= 4 * max(
              abs(as_float), 1e-300) * sys.float_info.epsilon,
          "EXACTLY KNOWN TARGET -- (254/256)^95 is rational, so the Fraction "
          "is the answer and the float is the thing under test.  "
          "diff = %.3e, 1 ulp = %.3e"
          % (abs(as_float - direct),
             as_float * sys.float_info.epsilon))

    check("`zero of 95` does not discriminate: even under MAXIMAL exposure "
          "the probability of seeing zero exceeds 1/4",
          as_float > 0.25,
          "%.4f.  So the 11-03 observation is consistent with every "
          "exposure level from none to total, and was never evidence about "
          "the map.  11-03's `unobserved rather than shown absent` was "
          "right; what is new is that the map cannot settle it either."
          % as_float)

    # How many pushes WOULD be needed for zero to mean something?
    n = 1
    while float(p_not ** n) > 0.05:
        n += 1
    check("the measurement that WOULD settle it is named with a number",
          n > STEER1_PAYLOADS,
          "%d fully-exposed steered payloads bring P(zero) below 0.05, "
          "against the %d run on 11-03 -- a %.1fx longer steered run, which "
          "is the actual cost of closing this item by simulation."
          % (n, STEER1_PAYLOADS, n / float(STEER1_PAYLOADS)))

    # -------------------------------------------------------------- S5 ----
    head(5, "mutation: one mutant for the verdict, one for the METHOD")
    mut_src = text.replace("return [0x00, 0xFF, 0x08, 0xAA, 0x33, 0x07][c]",
                           "return [0x00, 0xFF, 0x40, 0xAA, 0x33, 0x07][c]")
    check("M1 the mutant source differs from the original",
          mut_src != text, "0x08 -> 0x40 in byte_for_class")
    ns = {}
    exec(compile(ast.Module(body=[n_ for n_ in ast.parse(mut_src).body
                                  if isinstance(n_, ast.FunctionDef)
                                  and n_.name == 'byte_for_class'],
                            type_ignores=[]), '<M1>', 'exec'), ns)
    m1_image = sorted(set(consts) | {ns['byte_for_class'](c)
                                     for c in range(6)})
    m1_hit = sorted(set(m1_image) & set(borderline))
    check("M1 a steering map that CAN name a borderline byte flips the "
          "map-level verdict",
          bool(m1_hit),
          "mutant image n BORDERLINE = %s.  The S1 check has detection "
          "power; it is not vacuously true."
          % ["0x%02X" % b for b in m1_hit])

    # M2 -- the item's own proposed method, run against two benches.
    def item_method(src_text):
        """Enumerate `byte_for_class` only.  This IS what 11-03 proposed."""
        t = ast.parse(src_text)
        ns2 = {}
        for nd in ast.walk(t):
            if isinstance(nd, ast.FunctionDef) and nd.name == 'byte_for_class':
                exec(compile(ast.Module(body=[nd], type_ignores=[]),
                             '<m2>', 'exec'), ns2)
        rng = {ns2['byte_for_class'](c) for c in range(6)}
        return "UNREACHABLE" if not (rng & set(borderline)) else "REACHABLE"

    # A bench with the randomising fallback REMOVED: under it the strong
    # claim is actually true.  The item's method must not be able to tell the
    # two benches apart -- that is the whole point.
    no_random = text.replace(
        "byte = (it.steer_byte if it.steer_byte is not None\n"
        "                    else self.rng.getrandbits(8))",
        "byte = it.steer_byte")
    check("M2 the control is a real control: the fallback line was actually "
          "removed",
          no_random != text,
          "the driver's conditional is gone in the control source")
    v_real = item_method(text)
    v_ctrl = item_method(no_random)
    print("    item's method, real bench                 : %s" % v_real)
    print("    item's method, randomising fallback REMOVED: %s" % v_ctrl)
    check("M2 the item's proposed method cannot distinguish a bench that "
          "DOES drive random bytes from one that cannot",
          v_real == v_ctrl,
          "both %s.  The two benches differ on the question being asked and "
          "the method returns one answer for both, so it does not measure "
          "reachability under the policy -- only under the map.  This is why "
          "the item is being closed with a CORRECTION to its method rather "
          "than with its answer." % v_real)

    # ------------------------------------------------------------ TOTAL ---
    print()
    print("=" * 76)
    for lbl in _PASS:
        print("  PASS  %s" % lbl)
    for lbl in _FAIL:
        print("  FAIL  %s" % lbl)
    print()
    print("TOTAL: %d passed, %d failed" % (len(_PASS), len(_FAIL)))
    print("=" * 76)
    return 1 if _FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
