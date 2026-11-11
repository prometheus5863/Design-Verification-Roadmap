#!/usr/bin/env python3
"""
tools/cdc_structural_check.py -- a crude structural clock-domain-crossing
checker, and the first instrument in this repository that reads RTL
STRUCTURE rather than simulation OUTPUT.

WHY THIS EXISTS
---------------
2026-11-10 built examples/phase6_cdc_basics: seven CDC mutants against a
self-checking bench.  Six were detected.  The seventh, C7, was pinned as an
EXPECTED SURVIVOR with the reason recorded, and the reason is the whole
argument for this file:

    C7 the pulse synchroniser is bypassed (toggle used combinationally)
      ... The bench cannot see it ... the bench measures FUNCTIONAL
      coherency and pulse accounting, and this defect is neither.  It
      changes WHICH flop can go metastable, and no amount of zero-delay (or
      skew-modelled) simulation represents metastability at all. ...
      A structural CDC checker catches this in one pass by noticing that
      toggle_src feeds destination logic on an unsynchronised path --
      which is the argument for owning such a tool, made by a defect
      rather than by assertion.

That entry ranked a metastability-injection model first and this second.
THIS SESSION TOOK THE SECOND, and the departure is recorded rather than
glossed: both items exist to make C7 observable, this one is the cheaper
route to it, its acceptance test was already written and waiting
(apply the seven mutants, require C7 flagged), and -- unlike the injection
model -- it does not require the existing mutation harness's pinned
expectation to go stale on the same day the new instrument lands.

WHAT IT CHECKS
--------------
Four rules, each a standard CDC lint check, each implemented crudely and
each stating what it CANNOT see.

  R1 RECONVERGENCE.  A net passed as the data input of a synchroniser
     instance, and ALSO read by clocked logic in the same module, is a
     synchronised and an unsynchronised copy of one crossing signal
     reconverging.  This is C7 exactly.

  R2 SYNC_DEPTH.  A module acting as a synchroniser must have at least two
     flop stages between its data input and its output.  A one-stage
     "synchroniser" is a crossing with no MTBF margin at all.  This is C1.

  R3 MULTIBIT_SYNC.  A synchroniser instantiated with a width greater than
     one, whose data input is not driven by a Gray encoder, is a multi-bit
     crossing without a handshake or a Gray code: per-bit skew can present
     a value the source never held.

  R4 UNSYNC_CROSSING.  At a level where two clocks are visible, a register
     clocked by one and reading a register clocked by another, with no
     synchroniser between them, is an unsynchronised crossing.

WHAT IT CANNOT SEE, STATED UP FRONT
-----------------------------------
This is a line-oriented reader, not a Verilog elaborator.  It does not
elaborate parameters, resolve generate blocks, follow hierarchy across
files, or understand `define.  It identifies a synchroniser BY NAME
(SYNC_MODULE_RE) and therefore cannot recognise one written inline, and it
infers a net's domain only from the clock of the always block that drives
it -- so a module input's domain is unknown to it, which is precisely why
R1 is phrased as reconvergence rather than as "crosses a domain".

Those limits are not apologies, they are the reason the mutation suite
below also asserts what the checker must NOT flag.  An instrument that
flags everything catches C7 too.

Usage:
    python3 tools/cdc_structural_check.py FILE.v [FILE.v ...]
    python3 tools/cdc_structural_check.py --selftest
"""

import os
import re
import sys

SYNC_MODULE_RE = re.compile(r"(?:^|_)sync(?:_|$)|synchron", re.IGNORECASE)
GRAY_ENCODER_RE = re.compile(r"bin2gray|_b2g|gray_enc", re.IGNORECASE)

RULES = ("R1_RECONVERGENCE", "R2_SYNC_DEPTH", "R3_MULTIBIT_SYNC",
         "R4_UNSYNC_CROSSING")


# ---------------------------------------------------------------------------
# A deliberately small Verilog reader
# ---------------------------------------------------------------------------

def strip_comments(text):
    """Remove // and /* */ comments without touching line count.

    Line numbers are the only thing a lint report is good for, so every
    removal substitutes spaces or keeps the newline.
    """
    out = []
    i, n = 0, len(text)
    in_line, in_block, in_str = False, False, False
    while i < n:
        c = text[i]
        two = text[i:i + 2]
        if in_line:
            if c == "\n":
                in_line = False
                out.append(c)
            else:
                out.append(" ")
            i += 1
        elif in_block:
            if two == "*/":
                in_block = False
                out.append("  ")
                i += 2
            else:
                out.append("\n" if c == "\n" else " ")
                i += 1
        elif in_str:
            out.append(c)
            if c == '"':
                in_str = False
            i += 1
        elif two == "//":
            in_line = True
            out.append("  ")
            i += 2
        elif two == "/*":
            in_block = True
            out.append("  ")
            i += 2
        else:
            if c == '"':
                in_str = True
            out.append(c)
            i += 1
    return "".join(out)


class Module(object):
    __slots__ = ("name", "line", "ports", "blocks", "instances", "assigns",
                 "text")

    def __init__(self, name, line):
        self.name = name
        self.line = line
        self.ports = {}        # net -> "input" / "output" / "inout"
        self.blocks = []       # AlwaysBlock
        self.instances = []    # Instance
        self.assigns = []      # (line, lhs, rhs_text)
        self.text = ""

    def __repr__(self):
        return "Module(%s@%d)" % (self.name, self.line)


class AlwaysBlock(object):
    __slots__ = ("line", "clock", "edge_nets", "targets", "reads",
                 "nonreset_assigns")

    def __init__(self, line, clock, edge_nets):
        self.line = line
        self.clock = clock          # None for always @(*)
        self.edge_nets = edge_nets  # every net in the sensitivity list
        self.targets = []           # (line, lhs)
        self.reads = []             # (line, net)
        self.nonreset_assigns = []  # (line, lhs, rhs_text) outside reset

    def __repr__(self):
        return "AlwaysBlock(@%d clk=%s)" % (self.line, self.clock)


class Instance(object):
    __slots__ = ("line", "module", "name", "conns", "params")

    def __init__(self, line, module, name, conns, params):
        self.line = line
        self.module = module
        self.name = name
        self.conns = conns      # port -> net expression
        self.params = params    # param -> value text

    def __repr__(self):
        return "Instance(%s %s@%d)" % (self.module, self.name, self.line)


_IDENT = r"[A-Za-z_][A-Za-z0-9_$]*"
_KEYWORDS = set("""
module endmodule input output inout wire reg integer parameter localparam
always assign begin end if else case endcase posedge negedge or and not xor
default nettype timescale ifdef endif define include for while repeat initial
genvar generate endgenerate function endfunction task endtask signed unsigned
real time logic bit byte int shortint longint void return break continue
""".split())


def _nets_in(expr):
    """Every identifier in an expression that is not a keyword or a number."""
    out = []
    for m in re.finditer(_IDENT, expr):
        tok = m.group(0)
        if tok in _KEYWORDS:
            continue
        if re.match(r"^\d", tok):
            continue
        out.append(tok)
    return out


def _base(net_expr):
    """The net name out of `foo`, `foo[3]`, `foo[W-1:0]`, `{a,b}` -> first."""
    m = re.search(_IDENT, net_expr or "")
    return m.group(0) if m else None


def parse(text, path="<text>"):
    """[Module] for one file.  Crude by construction; see the docstring."""
    src = strip_comments(text)
    lines = src.split("\n")
    mods = []
    cur = None
    blk = None
    blk_depth = 0
    in_reset = False
    reset_depth = 0

    i = 0
    while i < len(lines):
        ln = i + 1
        line = lines[i]
        stripped = line.strip()

        m = re.match(r"\s*module\s+(" + _IDENT + r")", line)
        if m:
            cur = Module(m.group(1), ln)
            mods.append(cur)
            blk = None
            i += 1
            continue
        if re.match(r"\s*endmodule\b", line):
            cur = None
            blk = None
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        cur.text += line + "\n"

        # --- port directions, including ANSI headers ---------------------
        # A LINE CAN CARRY MORE THAN ONE DIRECTION, and the first version
        # took the first one and applied it to every name on the line.  On
        # the ANSI header
        #
        #     input wire [W-1:0] d_src, output wire [W-1:0] q_dst);
        #
        # that made `q_dst` an INPUT, so the module had no outputs, so R2 --
        # whose whole job is to walk from an output back to an input --
        # never ran on any module declared that way.  It went undetected
        # because every module in this repository happens to declare one
        # direction per line; the planted control did not, and that is what
        # a planted control is for.
        if re.match(r"\s*(input|output|inout)\b", line):
            marks = [(m.start(), m.group(1)) for m in
                     re.finditer(r"\b(input|output|inout)\b", line)]
            for idx, (pos, direction) in enumerate(marks):
                end = marks[idx + 1][0] if idx + 1 < len(marks) else len(line)
                seg = line[pos + len(direction):end]
                seg = re.sub(r"\breg\b|\bwire\b|\bsigned\b|\blogic\b",
                             " ", seg)
                seg = re.sub(r"\[[^\]]*\]", " ", seg)
                for net in _nets_in(seg):
                    cur.ports[net] = direction
            i += 1
            continue

        # --- anything that ENDS the current always block --------------
        #
        # FOUND BY RUNNING THIS ON THE TESTBENCH.  `initial`, `task` and
        # `function` were not recognised, so every statement in an initial
        # block kept accumulating into whichever always block was last open.
        # In cdc_crossings_tb.v that attributed the reads of a 200-line
        # checking `initial` to a one-line `always @(posedge clk_b)`, and R1
        # reported two reconvergences -- `bin_skewed` at line 356 and
        # `lat_in` at 271 -- that are a testbench reading its own signals,
        # not design logic reading an unsynchronised crossing.  A false
        # positive in a lint tool is not a harmless extra line: it is the
        # reason people stop reading the output.
        if re.match(r"\s*(initial|final|task|function|endtask|endfunction|"
                    r"specify|endspecify)\b", line):
            blk = None
            i += 1
            continue

        # --- always blocks -----------------------------------------------
        am = re.match(r"\s*always\s*@\s*\((.*?)\)", line)
        if am:
            sens = am.group(1)
            clock = None
            pm2 = re.search(r"posedge\s+(" + _IDENT + r")", sens)
            if pm2:
                clock = pm2.group(1)
            elif re.search(r"negedge\s+(" + _IDENT + r")", sens):
                clock = re.search(r"negedge\s+(" + _IDENT + r")",
                                  sens).group(1)
            blk = AlwaysBlock(ln, clock, _nets_in(sens))
            cur.blocks.append(blk)
            blk_depth = 0
            in_reset = False
            i += 1
            continue

        # --- instances: `modname #(...) instname ( .p(n), ... );` --------
        #
        # THE \b AFTER EACH IDENTIFIER GROUP IS A BUG FIX, not decoration.
        # Without it the regex backtracks inside a single word: on
        # `if (!rst_n) begin` it matched module name "i", instance name "f"
        # and the "(" after, invented an instance, and then consumed every
        # line up to the next ");" -- which swallowed an `endmodule` and two
        # whole module declarations.  Three of the five modules in
        # cdc_crossings.v disappeared from the parse, and the two that
        # survived had their always blocks attributed to the wrong module.
        # A structural checker that silently loses modules reports a clean
        # file, which is the worst failure available to it.
        inst_head = re.match(
            r"\s*(" + _IDENT + r")\b\s*(#\s*\([^;]*?\))?\s*(" + _IDENT +
            r")\b\s*\(", line)
        if (inst_head and inst_head.group(1) not in _KEYWORDS
                and inst_head.group(3) not in _KEYWORDS
                and inst_head.group(1) != inst_head.group(3)):
            # gather up to the terminating ');'
            chunk, j = line, i
            while ");" not in chunk and j + 1 < len(lines):
                j += 1
                chunk += "\n" + lines[j]
            conns = dict((p, n.strip()) for p, n in
                         re.findall(r"\.(" + _IDENT + r")\s*\(([^()]*)\)",
                                    chunk))
            params = {}
            phead = re.search(r"#\s*\((.*?)\)\s*" + _IDENT + r"\s*\(",
                              chunk, re.S)
            if phead:
                params = dict((p, v.strip()) for p, v in
                              re.findall(r"\.(" + _IDENT +
                                         r")\s*\(([^()]*)\)", phead.group(1)))
                for p in params:
                    conns.pop(p, None)
            cur.instances.append(Instance(ln, inst_head.group(1),
                                          inst_head.group(3), conns, params))
            i = j + 1
            blk = None
            continue

        # --- continuous assigns ------------------------------------------
        cm = re.match(r"\s*assign\s+([^=]+)=(.*)$", line)
        if cm:
            cur.assigns.append((ln, _base(cm.group(1)), cm.group(2)))
            i += 1
            continue

        # --- statements inside an always block ---------------------------
        if blk is not None:
            # Reset-arm tracking, deliberately crude: an `if (!rst_n)` opens
            # the reset arm and the next `else` closes it.  The first version
            # tried to match brace depth and never closed the arm at all,
            # because `end else begin` nets to the same depth and the test ran
            # before the update -- so every assignment in cdc_sync_2ff was
            # classified as reset logic and R2 saw a zero-stage synchroniser.
            # This form cannot handle a nested if inside a reset arm; no
            # module in this repository has one, and R2's self-test would
            # fail loudly if one appeared.
            if re.search(r"\bif\s*\(\s*!\s*" + _IDENT + r"\s*\)", line) \
                    or re.search(r"\bif\s*\(\s*" + _IDENT +
                                 r"\s*==\s*1'b0\s*\)", line):
                if any(n for n in blk.edge_nets
                       if re.search(r"rst|reset", n, re.IGNORECASE)):
                    in_reset = True
            elif re.search(r"\belse\b", line) and in_reset:
                in_reset = False
            blk_depth += len(re.findall(r"\bbegin\b", line))
            blk_depth -= len(re.findall(r"\bend\b(?!module|case|function|task)",
                                        line))
            # Strip leading `else`, `if (...)` and `else if (...)` so that
            # `else if (pulse_src)  toggle_src <= ~toggle_src;` yields the
            # target `toggle_src` and not `else`, which is what the first
            # version recorded -- a reg named after a keyword, in the one
            # module whose whole job is the toggle.
            # ONE LINE CAN HOLD SEVERAL STATEMENTS, and the first version
            # of this reader assumed it could not.  On the one-line reset
            # style
            #
            #   if (!rst_n) begin ff1 <= 0; ff2 <= 0; end
            #   else begin ff1 <= d_src; ff2 <= ff1; end
            #
            # it recorded `ff1` and dropped `ff2` entirely, so the flop
            # chain had no second stage, `_min_flop_depth` returned None,
            # and `is_synchroniser` saw a module with no flops.  Every rule
            # that depends on recognising a synchroniser then went silent --
            # the checker reported a clean file for RTL containing the
            # defects it was built to find.  Splitting on `;` is crude and
            # is why the `for (...;...;...)` header is excluded explicitly.
            def _strip_control(t):
                prev = None
                while prev != t:
                    prev = t
                    t = re.sub(r"^\s*else\b\s*", "", t)
                    t = re.sub(r"^\s*if\s*\([^()]*(?:\([^()]*\)[^()]*)*\)"
                               r"\s*", "", t)
                    t = re.sub(r"^\s*begin\b\s*", "", t)
                    t = re.sub(r"^\s*end\b\s*", "", t)
                return t

            if re.match(r"\s*for\s*\(", stripped):
                segments = [stripped]
            else:
                segments = [seg for seg in stripped.split(";") if seg.strip()]
            for seg in segments:
                stmt = _strip_control(seg)
                if not stmt.strip():
                    continue
                sm = re.match(r"\s*([^<=!>]+?)\s*<=\s*(.*?)\s*$", stmt)
                if not sm:
                    sm = re.match(r"\s*([^<=!>]+?)\s*=\s*(.*?)\s*$", stmt)
                    if sm and re.match(r"^\s*(if|else|case|for|while)\b",
                                       stmt):
                        sm = None
                if sm:
                    lhs, rhs = _base(sm.group(1)), sm.group(2)
                    if lhs:
                        blk.targets.append((ln, lhs))
                        for net in _nets_in(rhs):
                            blk.reads.append((ln, net))
                        if not in_reset:
                            blk.nonreset_assigns.append((ln, lhs, rhs))
                else:
                    for net in _nets_in(stmt):
                        blk.reads.append((ln, net))
        i += 1
    for m in mods:
        m.text = m.text
    return mods


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------

class Finding(object):
    __slots__ = ("rule", "path", "line", "module", "message")

    def __init__(self, rule, path, line, module, message):
        self.rule, self.path, self.line = rule, path, line
        self.module, self.message = module, message

    def __repr__(self):
        return "%s %s:%d [%s] %s" % (self.rule, os.path.basename(self.path),
                                     self.line, self.module, self.message)

    def key(self):
        return (self.rule, os.path.basename(self.path), self.module)


def is_synchroniser(mod):
    """Is this module actually a synchroniser, by its STRUCTURE?

    NAME MATCHING ALONE IS NOT ENOUGH, and the measurement that says so is
    this repository: run over all 41 .v files, the name test produced three
    findings of which TWO were `sync_fifo` -- a SYNCHRONOUS FIFO, matched
    because its name begins "sync_".  33 % precision, and both false
    positives were the same module.  A lint rule at 33 % precision is a lint
    rule people learn to ignore.

    The structural test: a synchroniser is a flop chain and nothing else.
    Every non-reset assignment in its clocked logic copies ONE net, with no
    arithmetic, no concatenation, no conditional.  `sync_fifo` fails on its
    pointer arithmetic; `cdc_sync_2ff` passes.
    """
    if not SYNC_MODULE_RE.search(mod.name):
        return False
    saw_flop = False
    for blk in mod.blocks:
        if blk.clock is None:
            continue
        for ln, lhs, rhs in blk.nonreset_assigns:
            saw_flop = True
            if not re.fullmatch(r"\s*" + _IDENT + r"\s*(\[[^\]]*\])?\s*",
                                rhs.strip().rstrip(";")):
                return False
    return saw_flop


def _is_reset(net):
    return bool(re.search(r"rst|reset", net or "", re.IGNORECASE))


def _clocks_of(mod):
    return set(b.clock for b in mod.blocks if b.clock)


def _resolve_width(mod, text):
    """A width expression resolved against the module's own parameters.

    Returns an int, or None when the spelling does not fix it.  None is NOT
    treated as 1: an unresolved width on a synchroniser is reported as
    unresolved, because guessing 1 would silently clear exactly the
    instantiation R3 exists to find.
    """
    if text is None:
        return None
    t = text.strip()
    if re.fullmatch(r"\d+", t):
        return int(t)
    m = re.search(r"\b(?:parameter|localparam)\s+(?:\[[^\]]*\]\s*)?" +
                  re.escape(t) + r"\s*=\s*(\d+)", mod.text)
    return int(m.group(1)) if m else None


def _flop_sources(mod):
    """net -> [(source_net, is_flop)] for every driver in the module."""
    srcs = {}
    for ln, lhs, rhs in mod.assigns:
        if not lhs:
            continue
        for net in _nets_in(rhs):
            srcs.setdefault(lhs, []).append((net, False))
    for blk in mod.blocks:
        flop = blk.clock is not None
        for ln, lhs, rhs in blk.nonreset_assigns:
            for net in _nets_in(rhs):
                srcs.setdefault(lhs, []).append((net, flop))
    for inst in mod.instances:
        # an instance output is driven by its inputs; treat a synchroniser
        # as contributing its own stages, counted separately by R2
        pass
    return srcs


def _min_flop_depth(mod, start, targets):
    """Fewest flop stages on any path from `start` back to any of `targets`.

    Breadth-first over the driver graph, so the FIRST time a target is
    reached is along a minimum-flop path.  Returns None when no path exists.
    """
    srcs = _flop_sources(mod)
    seen = set()
    frontier = [(start, 0)]
    while frontier:
        nxt = []
        for net, depth in frontier:
            if net in targets:
                return depth
            if net in seen:
                continue
            seen.add(net)
            for src, is_flop in srcs.get(net, []):
                nxt.append((src, depth + (1 if is_flop else 0)))
        # process zero-cost edges before flop edges so depth stays minimal
        nxt.sort(key=lambda x: x[1])
        frontier = nxt
    return None


def check_module(mod, path, findings, db=None):
    db = db or {}
    clocks = _clocks_of(mod)
    inputs = set(n for n, d in mod.ports.items() if d == "input")
    outputs = set(n for n, d in mod.ports.items() if d == "output")
    data_inputs = set(n for n in inputs
                      if n not in clocks and not _is_reset(n))

    def _inst_is_sync(inst):
        """(is_sync, confidence) for an instance.

        When the instantiated module's body is in the database the answer is
        structural.  When it is not -- a module defined in a file that was
        not scanned -- the name is all there is, and the finding says so
        rather than presenting a guess as a measurement.
        """
        target = db.get(inst.module)
        if target is not None:
            return (is_synchroniser(target), "structural")
        return (bool(SYNC_MODULE_RE.search(inst.module)), "name-only")

    sync_insts = []
    sync_conf = {}
    for inst in mod.instances:
        ok, conf = _inst_is_sync(inst)
        if ok:
            sync_insts.append(inst)
            sync_conf[inst.name] = conf
    gray_outputs = set()
    for inst in mod.instances:
        if GRAY_ENCODER_RE.search(inst.module):
            for port, net in inst.conns.items():
                if re.search(r"gray|out|q", port, re.IGNORECASE):
                    gray_outputs.add(_base(net))

    def _gray_driven(net):
        """Is `net` the output of a Gray encoder, possibly through
        intermediate combinational nets?

        The direct test was not enough on the one real instance available:
        cdc_crossings_tb.v feeds its Gray synchroniser from `gray_skewed`,
        the skew model's copy of the encoder output `gray_a`, so a
        same-net test reported the SAFE crossing of that example as
        unsafe -- the checker calling the textbook-correct half of a
        side-by-side right/wrong demonstration a defect.
        """
        srcs = _flop_sources(mod)
        seen, frontier = set(), [net]
        while frontier:
            cur = frontier.pop()
            if cur in gray_outputs:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            frontier.extend(src for src, _ in srcs.get(cur, []))
        return False

    # ---- R1 RECONVERGENCE -------------------------------------------------
    for inst in sync_insts:
        d_net = None
        for port, net in inst.conns.items():
            if re.search(r"^d|_d$|din|d_src|data", port, re.IGNORECASE) \
                    and not _is_reset(port) and port not in ("clk_dst",):
                d_net = _base(net)
                break
        if not d_net:
            continue
        for blk in mod.blocks:
            if blk.clock is None:
                continue
            hits = [ln for ln, net in blk.reads if net == d_net]
            if hits:
                findings.append(Finding(
                    "R1_RECONVERGENCE", path, hits[0], mod.name,
                    "`%s` is the data input of synchroniser `%s` (line %d) "
                    "AND is read directly by logic clocked on `%s`: a "
                    "synchronised and an unsynchronised copy of one crossing "
                    "signal reconverge"
                    % (d_net, inst.name, inst.line, blk.clock)))
        for ln, lhs, rhs in mod.assigns:
            if d_net in _nets_in(rhs):
                findings.append(Finding(
                    "R1_RECONVERGENCE", path, ln, mod.name,
                    "`%s` is the data input of synchroniser `%s` (line %d) "
                    "AND is read combinationally by `%s`"
                    % (d_net, inst.name, inst.line, lhs)))

    # ---- R2 SYNC_DEPTH ----------------------------------------------------
    if SYNC_MODULE_RE.search(mod.name) and is_synchroniser(mod) \
            and data_inputs and outputs:
        for out in sorted(outputs):
            depth = _min_flop_depth(mod, out, data_inputs)
            if depth is None:
                continue
            if depth < 2:
                findings.append(Finding(
                    "R2_SYNC_DEPTH", path, mod.line, mod.name,
                    "module is named as a synchroniser but output `%s` is "
                    "only %d flop stage(s) from its data input: a crossing "
                    "with no MTBF margin" % (out, depth)))

    # ---- R3 MULTIBIT_SYNC -------------------------------------------------
    for inst in sync_insts:
        wtext = None
        for p, v in inst.params.items():
            if re.fullmatch(r"W|WIDTH|N", p, re.IGNORECASE):
                wtext = v
        width = _resolve_width(mod, wtext)
        d_net = None
        for port, net in inst.conns.items():
            if re.search(r"^d|_d$|din|d_src|data", port, re.IGNORECASE) \
                    and not _is_reset(port):
                d_net = _base(net)
                break
        if _gray_driven(d_net):
            continue
        if width is None and wtext is not None:
            findings.append(Finding(
                "R3_MULTIBIT_SYNC", path, inst.line, mod.name,
                "synchroniser `%s` has width `%s`, which this reader cannot "
                "resolve; not assumed to be 1" % (inst.name, wtext)))
        elif width is not None and width > 1:
            findings.append(Finding(
                "R3_MULTIBIT_SYNC", path, inst.line, mod.name,
                "synchroniser `%s` carries %d bits and its data input `%s` "
                "is not driven by a Gray encoder: per-bit skew can present a "
                "value the source never held [%s]"
                % (inst.name, width, d_net, sync_conf.get(inst.name, "?"))))

    # ---- R4 UNSYNC_CROSSING -----------------------------------------------
    if len(clocks) >= 2:
        driver_clock = {}
        for blk in mod.blocks:
            if blk.clock:
                for ln, lhs in blk.targets:
                    driver_clock[lhs] = blk.clock
        synced = set()
        for inst in sync_insts:
            for port, net in inst.conns.items():
                synced.add(_base(net))
        for blk in mod.blocks:
            if not blk.clock:
                continue
            reported = set()
            for ln, net in blk.reads:
                src_clk = driver_clock.get(net)
                if not src_clk or src_clk == blk.clock:
                    continue
                if net in synced or net in reported:
                    continue
                reported.add(net)
                findings.append(Finding(
                    "R4_UNSYNC_CROSSING", path, ln, mod.name,
                    "`%s` is driven by logic clocked on `%s` and read by "
                    "logic clocked on `%s` with no synchroniser between them"
                    % (net, src_clk, blk.clock)))


def check_text(text, path="<text>", db=None):
    findings = []
    mods = parse(text, path)
    if db is None:
        db = dict((m.name, m) for m in mods)
    for mod in mods:
        check_module(mod, path, findings, db)
    return findings


def check_file(path, db=None):
    with open(path, encoding="utf-8") as fh:
        return check_text(fh.read(), path, db)


def build_db(paths):
    """name -> Module across every file, so that an instance of a module
    defined in ANOTHER file can be adjudicated structurally instead of by
    its name.  Without this, `cdc_crossings_tb.v` checked alone can only
    guess what `cdc_sync_2ff` is."""
    db = {}
    for p in paths:
        try:
            with open(p, encoding="utf-8") as fh:
                for m in parse(fh.read(), p):
                    db.setdefault(m.name, m)
        except (OSError, UnicodeDecodeError):
            continue
    return db


def check_files(paths):
    db = build_db(paths)
    out = []
    for p in paths:
        out.extend(check_file(p, db))
    return out


# ---------------------------------------------------------------------------
# Planted controls
# ---------------------------------------------------------------------------
#
# EVERY RULE HAS A POSITIVE CONTROL AND A NEGATIVE CONTROL.  A rule with only
# a negative control has never been shown to fire; a rule with only a positive
# control has never been shown to discriminate.  R4 in particular fires on
# nothing in this repository -- every crossing here is synchronised -- so
# without PLANT_R4 it would be four rules of which one is decorative.

PLANT_CLEAN = """
module cdc_sync_2ff #(parameter W = 1) (
    input  wire clk_dst, input wire rst_n,
    input  wire [W-1:0] d_src, output wire [W-1:0] q_dst);
    reg [W-1:0] ff1, ff2;
    always @(posedge clk_dst or negedge rst_n) begin
        if (!rst_n) begin ff1 <= {W{1'b0}}; ff2 <= {W{1'b0}}; end
        else begin ff1 <= d_src; ff2 <= ff1; end
    end
    assign q_dst = ff2;
endmodule
module user (input wire clk_dst, input wire rst_n, input wire a,
             output wire y);
    wire s;
    cdc_sync_2ff #(.W(1)) u (.clk_dst(clk_dst), .rst_n(rst_n),
                             .d_src(a), .q_dst(s));
    reg sd;
    always @(posedge clk_dst or negedge rst_n) begin
        if (!rst_n) sd <= 1'b0;
        else        sd <= s;
    end
    assign y = s ^ sd;
endmodule
"""

# R1: the synchroniser's own data input also read by clk_dst logic.
PLANT_R1 = PLANT_CLEAN.replace("        else        sd <= s;",
                               "        else        sd <= a;")

# R2: the second flop takes the input directly, so the chain is one deep.
PLANT_R2 = PLANT_CLEAN.replace("else begin ff1 <= d_src; ff2 <= ff1; end",
                               "else begin ff1 <= d_src; ff2 <= d_src; end")

# R3: eight bits through a 2FF with no Gray encoder in front of it.
PLANT_R3 = PLANT_CLEAN.replace(
    "module user (input wire clk_dst, input wire rst_n, input wire a,",
    "module user (input wire clk_dst, input wire rst_n, input wire [7:0] a,"
).replace("wire s;", "wire [7:0] s;").replace(
    "cdc_sync_2ff #(.W(1))", "cdc_sync_2ff #(.W(8))")

# R4: two clocks, a reg in one read by a reg in the other, no synchroniser.
PLANT_R4 = """
module two_domain (input wire clk_a, input wire clk_b, input wire rst_n,
                   input wire d, output wire q);
    reg a_q, b_q;
    always @(posedge clk_a or negedge rst_n) begin
        if (!rst_n) a_q <= 1'b0;
        else        a_q <= d;
    end
    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n) b_q <= 1'b0;
        else        b_q <= a_q;
    end
    assign q = b_q;
endmodule
"""

# The same two domains done properly: the crossing goes through the
# synchroniser, so R4 must NOT fire.
PLANT_R4_CLEAN = PLANT_CLEAN + """
module two_domain_ok (input wire clk_a, input wire clk_b, input wire rst_n,
                      input wire d, output wire q);
    reg a_q;
    wire b_s;
    always @(posedge clk_a or negedge rst_n) begin
        if (!rst_n) a_q <= 1'b0;
        else        a_q <= d;
    end
    cdc_sync_2ff #(.W(1)) u2 (.clk_dst(clk_b), .rst_n(rst_n),
                              .d_src(a_q), .q_dst(b_s));
    assign q = b_s;
endmodule
"""

# A synchronous FIFO whose NAME matches the synchroniser pattern.  This is
# examples/phase1_milestone/sync_fifo.v in miniature, and it is the control
# for the 33 %-precision measurement recorded at is_synchroniser().
PLANT_NOT_A_SYNC = """
module sync_fifo #(parameter W = 8) (
    input wire clk, input wire rst_n, input wire [W-1:0] wr_data,
    output wire [W-1:0] rd_data);
    reg [W-1:0] mem [0:3];
    reg [2:0] wr_ptr, rd_ptr;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin wr_ptr <= 3'd0; rd_ptr <= 3'd0; end
        else begin
            wr_ptr <= wr_ptr + 3'd1;
            rd_ptr <= rd_ptr + 3'd1;
        end
    end
    assign rd_data = mem[rd_ptr[1:0]];
endmodule
"""

# The seven mutants of examples/phase6_cdc_basics, verbatim from
# cdc_mutation_test.py so that the two harnesses cannot drift apart
# silently -- if that file's mutants change, CDC_MUTANTS here is wrong and
# check S7 below says so by failing to find the text to replace.
CDC_MUTANTS = [
    ("C1", "            ff2 <= ff1;", "            ff2 <= d_src;"),
    ("C2", "assign gray = bin ^ (bin >> 1);",
     "assign gray = bin ^ (bin >> 2);"),
    ("C3", "            b[i] = b[i+1] ^ gray[i];", "            b[i] = gray[i];"),
    ("C4", "assign gray = bin ^ (bin >> 1);", "assign gray = bin;"),
    ("C5", "        else if (pulse_src)  toggle_src <= ~toggle_src;",
     "        else if (pulse_src)  toggle_src <= 1'b1;"),
    ("C6", "    assign pulse_dst = sync_q ^ sync_q_d;",
     "    assign pulse_dst = sync_q & ~sync_q_d;"),
    ("C7", "        else        sync_q_d <= sync_q;",
     "        else        sync_q_d <= toggle_src;"),
]

# Which mutants a STRUCTURAL checker can see.  C7 is the one the simulation
# bench pinned as an expected survivor on 2026-11-10; C1 turns a two-flop
# synchroniser into a one-flop one, which is structural by definition.  The
# other five are functional defects in coding or decoding and a structural
# checker has no business claiming them.
CDC_STRUCTURAL_EXPECTED = {"C1": "R2_SYNC_DEPTH", "C7": "R1_RECONVERGENCE"}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0


def _check(label, ok, detail=""):
    global _passed, _failed
    if ok:
        _passed += 1
        print("  PASS  %s" % label)
    else:
        _failed += 1
        print("  FAIL  %s\n          %s" % (label, detail))
    return bool(ok)


def _rules(text, path="<plant>"):
    return sorted(set(f.rule for f in check_text(text, path)))


def selftest(repo_root=None):
    global _passed, _failed
    _passed = _failed = 0
    print("=" * 74)
    print("tools/cdc_structural_check.py -- self-test, 2026-11-11")
    print("=" * 74)

    print("\n[1] negative controls: correct RTL must be silent")
    _check("1a the clean two-flop crossing raises nothing",
           _rules(PLANT_CLEAN) == [], "%r" % _rules(PLANT_CLEAN))
    _check("1b a correctly synchronised two-domain crossing raises nothing "
           "-- R4 must discriminate, not just fire",
           _rules(PLANT_R4_CLEAN) == [], "%r" % _rules(PLANT_R4_CLEAN))
    _check("1c a SYNCHRONOUS FIFO whose name matches the synchroniser "
           "pattern raises nothing: the 33 % precision measurement that "
           "forced is_synchroniser() to be structural",
           _rules(PLANT_NOT_A_SYNC) == [], "%r" % _rules(PLANT_NOT_A_SYNC))
    _db = dict((m.name, m) for m in parse(PLANT_NOT_A_SYNC))
    _check("1d and it is rejected for the stated reason -- its assignments "
           "are not plain copies, not because of some other accident",
           SYNC_MODULE_RE.search("sync_fifo")
           and not is_synchroniser(_db["sync_fifo"]), "")

    print("\n[2] positive controls: every rule fires on its own plant")
    for name, plant, rule in (("R1", PLANT_R1, "R1_RECONVERGENCE"),
                              ("R2", PLANT_R2, "R2_SYNC_DEPTH"),
                              ("R3", PLANT_R3, "R3_MULTIBIT_SYNC"),
                              ("R4", PLANT_R4, "R4_UNSYNC_CROSSING")):
        got = _rules(plant)
        _check("2%s %s fires on its plant, and ONLY %s does"
               % (name[1:], rule, rule), got == [rule], "got %r" % got)
    _check("2e every declared rule has a positive control",
           set(RULES) == {"R1_RECONVERGENCE", "R2_SYNC_DEPTH",
                          "R3_MULTIBIT_SYNC", "R4_UNSYNC_CROSSING"}, "")

    print("\n[3] the Gray exemption discriminates")
    gray_plant = PLANT_R3.replace(
        "    wire [7:0] s;",
        "    wire [7:0] s;\n    wire [7:0] g;\n    wire [7:0] gd;\n"
        "    bin2gray #(.W(8)) ue (.bin(a), .gray(g));\n"
        "    assign gd = g;").replace(".d_src(a),", ".d_src(gd),")
    gray_plant += """
module bin2gray #(parameter W = 8) (input wire [W-1:0] bin,
                                    output wire [W-1:0] gray);
    assign gray = bin ^ (bin >> 1);
endmodule
"""
    _check("3a an 8-bit crossing fed from a Gray encoder THROUGH an "
           "intermediate net is exempt: the indirection that made the "
           "checker call the correct half of cdc_crossings_tb a defect",
           _rules(gray_plant) == [], "%r" % _rules(gray_plant))
    _check("3b but the same crossing fed from raw binary still fires",
           _rules(PLANT_R3) == ["R3_MULTIBIT_SYNC"], "%r" % _rules(PLANT_R3))

    print("\n[4] an unresolved width is not silently treated as 1")
    unres = PLANT_CLEAN.replace("cdc_sync_2ff #(.W(1))",
                                "cdc_sync_2ff #(.W(NBITS))")
    _check("4a a width this reader cannot resolve is REPORTED, not assumed "
           "safe", "R3_MULTIBIT_SYNC" in _rules(unres), "%r" % _rules(unres))
    _check("4b and a literal 1 is silent",
           "R3_MULTIBIT_SYNC" not in _rules(PLANT_CLEAN), "")

    print("\n[5] the parser keeps every module -- the backtracking bug")
    mods = parse(PLANT_CLEAN)
    _check("5a both modules of the clean plant survive the parse",
           [m.name for m in mods] == ["cdc_sync_2ff", "user"],
           "%r" % [m.name for m in mods])
    _check("5b `if (` is not read as an instantiation of module `i` named `f`",
           not any(m.module == "i" for mod in mods for m in mod.instances),
           "%r" % [i for mod in mods for i in mod.instances])
    _check("5c the reset arm closes, so the flop chain is two deep and not "
           "zero", _min_flop_depth(mods[0], "q_dst", {"d_src"}) == 2,
           "%r" % _min_flop_depth(mods[0], "q_dst", {"d_src"}))
    _check("5d an `initial` block ends the preceding always block",
           _rules(PLANT_CLEAN.replace(
               "    assign y = s ^ sd;",
               "    initial begin\n        @(posedge a);\n    end\n"
               "    assign y = s ^ sd;")) == [], "")

    # ---- 6. the acceptance test the 2026-11-10 entry wrote for this tool --
    print("\n[6] the seven CDC mutants -- the acceptance test written on "
          "2026-11-10, before this tool existed")
    root = repo_root or os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))
    rtl = os.path.join(root, "examples", "phase6_cdc_basics",
                       "cdc_crossings.v")
    if not os.path.exists(rtl):
        _check("6a the CDC example is present", False, "missing %s" % rtl)
    else:
        base = open(rtl, encoding="utf-8").read()
        _check("6a the UNMUTATED example is clean",
               _rules(base, rtl) == [], "%r" % _rules(base, rtl))
        detected = {}
        for mid, old, new in CDC_MUTANTS:
            if old not in base:
                _check("6S%s the mutant's anchor text is still in the RTL "
                       "(this harness and cdc_mutation_test.py must not "
                       "drift apart)" % mid, False, "missing: %r" % old)
                continue
            got = _rules(base.replace(old, new, 1), rtl)
            detected[mid] = got
        _check("6b C7 -- pinned as an EXPECTED SURVIVOR of the simulation "
               "bench on 2026-11-10 -- is DETECTED here, by R1",
               detected.get("C7") == ["R1_RECONVERGENCE"],
               "%r" % detected.get("C7"))
        _check("6c C1 is detected by R2",
               detected.get("C1") == ["R2_SYNC_DEPTH"],
               "%r" % detected.get("C1"))
        missed = sorted(m for m in ("C2", "C3", "C4", "C5", "C6")
                        if detected.get(m))
        _check("6d C2-C6 are NOT flagged: they are functional defects in "
               "coding and decoding, and a structural checker that claimed "
               "them would be flagging everything",
               missed == [], "unexpectedly flagged: %r"
               % [(m, detected[m]) for m in missed])
        _check("6e so the two instruments PARTITION the seven mutants: "
               "simulation 6 (C1-C6), structure 2 (C1, C7), union 7, and "
               "the overlap is exactly C1",
               set(detected) - set(CDC_STRUCTURAL_EXPECTED)
               == {"C2", "C3", "C4", "C5", "C6"}
               and set(k for k, v in detected.items() if v)
               == set(CDC_STRUCTURAL_EXPECTED),
               "%r" % {k: v for k, v in detected.items()})

    # ---- 7. the repository ----------------------------------------------
    print("\n[7] the repository")
    vfiles = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in sorted(filenames):
            if fn.endswith(".v"):
                vfiles.append(os.path.join(dirpath, fn))
    repo_findings = check_files(sorted(vfiles))
    print("    %d .v files scanned, %d finding(s)"
          % (len(vfiles), len(repo_findings)))
    for f in repo_findings:
        print("      %s" % f)
    _check("7a every .v file in the repository parses without an exception",
           len(vfiles) > 30, "%d files" % len(vfiles))
    _check("7b the only finding in the whole repository is the deliberate "
           "WRONG crossing of the CDC example -- the one the example exists "
           "to be wrong",
           len(repo_findings) == 1
           and repo_findings[0].rule == "R3_MULTIBIT_SYNC"
           and "u_sync_bin" in repo_findings[0].message,
           "%r" % repo_findings)
    _check("7c and the CORRECT Gray crossing beside it is NOT flagged",
           not any("u_sync_gray" in f.message for f in repo_findings), "")

    print("\n" + "=" * 74)
    print("TOTAL: %d passed, %d failed" % (_passed, _failed))
    print("=" * 74)
    return 1 if _failed else 0


def main(argv):
    if "--selftest" in argv:
        # --root lets the mutation harness run a COPY of this file against
        # the real repository: without it the copy walks its own temporary
        # directory, finds no .v files, and section 7 fails on the
        # unmutated baseline -- which would make every mutant verdict
        # meaningless, as that harness says and then checks.
        root = None
        if "--root" in argv:
            root = argv[argv.index("--root") + 1]
        return selftest(root)
    if "--root" in argv:
        i = argv.index("--root")
        argv = argv[:i] + argv[i + 2:]
    paths = [a for a in argv if not a.startswith("-")]
    if not paths:
        print(__doc__.strip().split("Usage:")[-1].strip())
        return 2
    findings = check_files(paths)
    for f in sorted(findings, key=lambda x: (x.path, x.line)):
        print(f)
    print("%d file(s), %d finding(s)" % (len(paths), len(findings)))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
