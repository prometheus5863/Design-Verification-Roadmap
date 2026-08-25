# Study notes: Randomization (`rand`/`randc`, constraints, `randomize()`, `dist`)

*Date: 2026-08-26. Sixth automation session. Phase 2, next unchecked
`progress.md` item after "OOP testbench components" (2026-08-25).
2026-08-25's notes explicitly flagged that a quick probe suggested
`randomize()` might not elaborate on this build, and recommended opening
this session with a dedicated, proper set of minimal repros before
designing the milestone example -- exactly what Section 2 below does.*

## 1. Concepts (standard SystemVerilog, simulator-independent)

Constrained-random stimulus generation is the mechanism that lets a
verification environment produce large volumes of legal-but-varied
stimulus automatically, instead of a human enumerating every directed
test vector by hand. The core language pieces (IEEE 1800-2017 §18;
Sutherland & Spear, *SystemVerilog for Verification*, 3rd ed., ch. 11;
ChipVerify "SystemVerilog Randomization"):

- **`rand`** marks a class property as randomizable with a *uniform*
  distribution over its declared range by default. Each call to
  `randomize()` picks a fresh value.
- **`randc`** ("random-cyclic") marks a property so that, over a full
  cycle of `2^N` calls (N = the field's bit width), every possible value
  is produced exactly once before any value repeats -- useful for
  guaranteeing coverage of a small enumerated space (e.g. cycling through
  all 4 opcodes before any opcode repeats) without an explicit
  covergroup-driven directive.
- **`constraint` blocks** restrict the legal value space declaratively
  (e.g. `constraint c_range { a inside {[10:20]}; }`). Multiple
  constraint blocks on the same class combine with logical AND. The
  solver (a full constraint solver, not simple rejection sampling, in a
  compliant implementation) picks pseudo-random values satisfying *all*
  active constraints simultaneously -- this is what lets constraints on
  multiple correlated fields (e.g. "if op == DIV then divisor != 0")
  work efficiently even when naive random-and-check would need many
  retries.
- **`randomize()`** is the built-in class method (every class implicitly
  extends the ability to call it once instantiated) that triggers a
  randomization pass over all `rand`/`randc` fields subject to all active
  constraints, returning 1 on success and 0 if the constraints were
  unsatisfiable. **`randomize() with { ... }`** adds an inline, call-
  site-specific extra constraint for that one call only, without
  permanently modifying the class's constraint blocks -- the standard way
  to bias a generator "this transaction should be a write" for one
  sequence without a separate class per bias.
- **`dist`** constraints assign relative weights to specific values or
  ranges (e.g. `a dist {0 := 1, [1:10] :/ 1}` -- `:=` gives that single
  value the stated weight, `:/` divides the stated weight evenly across
  every value in the range), used to bias randomization toward
  interesting corners (e.g. mostly legal traffic, occasionally the
  boundary/error case) instead of uniform coverage of a huge space where
  the interesting bugs live in a tiny corner of it.

Why verification engineers care about this specifically (not just "more
randomness is good"): constrained-random lets a fixed amount of engineer
time generate stimulus volume that would be infeasible to hand-write
directed tests for, while the *constraints* keep every generated
transaction legal (a DUT should never be driven with stimulus outside its
protocol just because the RNG happened to produce it) -- this is the
foundation Phase 2's next milestone (constrained-random SV testbench +
coverage) and Phase 4's UVM sequences both build directly on.

## 2. Tooling finding: this Icarus Verilog 10.3 build does not implement `randomize()`/constraints

Per the practice established in every prior tooling-blocker case in this
repo (2026-08-22 iverilog install, 2026-08-24/25 SV construct gaps): each
finding below was confirmed with its own minimal standalone repro (kept
in `/tmp/repro/` this session, not committed -- the repro *content* is
reproduced inline below since it is short) before being treated as
established, not assumed from a single ambiguous error message.

**a) `Foo f = new();` (inline declaration + construction) does not
parse.** This is a *new* finding this session, distinct from anything in
the 2026-08-24/25 gap lists -- it was never hit before because every
class instance in this repo so far (`alu_transaction`, `alu_generator`,
`alu_scoreboard` in `alu_oop_tb_components.sv`) happens to have been
declared and constructed as two separate statements already (`Foo f;`
... `f = new();`), which **does** work:

```systemverilog
// FAILS: "syntax error" / "malformed statement" at the `new()` line
Foo f = new();

// WORKS:
Foo f;
f = new();
```

Flagging this explicitly so future sessions don't lose time on it the way
this session briefly did: any textbook/online example using the
single-line inline-construction idiom (extremely common in SV teaching
material) needs to be rewritten to the two-statement form for this
simulator.

**b) `randomize()` is not implemented at all.** With a plain `rand`
field (which itself parses without complaint) and split declare/
construct:

```systemverilog
class Foo;
    rand bit [7:0] a;
endclass
...
Foo f;
int ok;
f = new();
ok = f.randomize();   // elaboration error:
// "No function named `f.randomize' found in this context"
```

This is an **elaboration**-time error (compiles past the parser, fails
when Icarus tries to resolve the method call), confirming this isn't a
syntax-form issue like (a) -- the built-in `randomize()` method simply
does not exist in this build, for any class, regardless of whether it
has `rand` fields.

**c) `constraint` blocks are explicitly rejected by the parser**, with an
Icarus message that plainly says the feature is unimplemented rather than
a generic syntax error:

```
sorry: "inside" expressions not supported yet.
sorry: Constraint declarations not supported.
```

This was confirmed both for a simple `inside {[10:20]}` range constraint
and for a `dist` weighted constraint (`a dist {0 := 1, [1:10] :/ 1}`),
which fails the same way.

**d) `randomize() with { ... }` (inline call-site constraints)** also
fails to parse, consistent with (b)/(c) -- there is no `randomize()` to
attach an inline constraint to in the first place.

**e) `randc` field declarations parse and elaborate fine on their own**
(`randc bit [1:0] a;` inside a class, instantiated and read back, no
error) -- it is specifically the *`randomize()` call* that is missing,
not the `rand`/`randc` keywords themselves. This matters because it means
the *keywords* don't gate anything; only the method that would act on
them is absent.

**Net assessment:** this Icarus Verilog 10.3 build has **no constrained-
random support whatsoever** -- not "incomplete constraint-solver
performance" but a complete absence of `randomize()`, `constraint`,
`inside`, and `dist`. This is a materially bigger gap than any found in
2026-08-23/24/25 (those were missing *pieces* of SV -- `always_comb`,
`mailbox`, virtual-interface class members, etc. -- with usable
workarounds inside the language). Native constrained-random is not a
"write it differently" workaround situation; the feature is simply not
there. Combined with 2026-08-25's note that full UVM (Phase 4) depends on
several already-confirmed-missing features simultaneously (virtual
interfaces, TLM-like channels, polymorphic handle containers) *and* would
also need `randomize()` for sequences, this is a second, independent,
even more fundamental reason Phase 4 will need a different simulator
(Verilator, a commercial tool, or an EDA-Playground-style hosted
Questa/VCS/Xcelium session) rather than this sandbox's Icarus install.
That conclusion should be treated as settled after today, not
re-investigated from scratch each session -- see the "Next run should"
note at the end of `AUTOMATION_LOG.md`'s entry for today.

## 3. Practical workaround used for today's example

Because native `randomize()`/`constraint` are unavailable, but the
*concept* (constrained-random stimulus, weighted toward interesting
values) is exactly what this milestone is about, today's example
(`examples/phase2/alu_manual_constrained_random.sv`) hand-implements the
same behavior a real constraint solver would produce for the specific,
simple constraints used, via:

- **Range constraints** -> `$urandom_range(lo, hi)` directly (exact for a
  single-field range constraint; this is what a real solver reduces to
  internally for an unconstrained single-variable range anyway).
- **`randc`-like cyclic coverage** -> a manually shuffled fixed-size
  queue of all legal values, popped one at a time and reshuffled once
  exhausted, which is the textbook definition of `randc` behavior and
  was already used as an emulation basis for this repo's Phase 1
  exhaustive-vector testbenches. Genuine `randc` correctness (each value
  exactly once per cycle) is easy to guarantee by construction this way,
  which is a stronger correctness argument than `$urandom_range` +
  rejection would give.
- **`dist`-like weighted selection** -> an explicit cumulative-weight
  table and a single `$urandom_range` draw against it (the standard
  manual implementation of weighted random choice), used to bias ALU
  opcode selection toward two "interesting corner" opcodes (chosen as
  SUB, since it is the one opcode whose overflow/borrow flag logic is
  most often the source of ALU-checker bugs per the 2026-08-22
  combinational-logic notes) rather than uniform-over-5-opcodes.

This is explicitly a **workaround for this simulator**, not a claim that
`$urandom_range`-based manual selection is equivalent to real constraint
solving in general (it does not scale to correlated multi-field
constraints or `soft` constraint priority, which is exactly why real
tools implement a solver rather than leaving this to hand-written code)
-- the limitation is documented in the example file's header as well, per
this repo's established practice of never presenting a workaround as if
it were the real thing.

## References

1. IEEE 1800-2017 (SystemVerilog LRM), §18 (Random constraints).
2. Sutherland, C. & Spear, S. *SystemVerilog for Verification*, 3rd ed.,
   Springer, 2018, ch. 11 (Random Stimulus, previously cited in this
   repo's 2026-08-25 notes for ch. 9-10 material).
3. ChipVerify, "SystemVerilog Randomization" tutorial series (same source
   family already cited throughout this repo for foundational SV/UVM
   material).
4. This repo: `notes/2026-08-25-oop-testbench-components.md`, Section on
   forward-looking risks -- the initial (unconfirmed) suspicion that
   `randomize()` might not elaborate, resolved definitively this session.
