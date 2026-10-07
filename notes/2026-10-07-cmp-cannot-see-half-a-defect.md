# `cmp` cannot see half a defect

**Date:** 2026-10-07
**Added:** `tools/mutation_controls.sh`, `tools/test_mutation_controls.sh`,
`tools/audit_mutation_anchors.sh`
**Changed:** `examples/phase4_ral/run_mutation_tests.sh`
**Transcripts:** `tools/mutation_controls_selftest_output.txt`,
`tools/mutation_anchor_audit_output.txt`,
`examples/phase4_ral/mutation_test_report_2026-10-07.txt`
**Closes:** the 2026-10-01 item *every mutant in this repository needs control B*

---

## 1. The sentence the whole session turns on

```
    sed 's|A|B|'    replaces the FIRST match ON EACH LINE.
```

Four of this repository's mutation harnesses guard injection with

```bash
    if cmp -s "$mut" "$RTL"; then  ...row voided...  fi
```

which catches a `sed` that matched **nothing**. It cannot catch a `sed` that
matched **something and not everything**. If the anchor occurs twice on one
line, exactly one occurrence is replaced, the mutant carries **half** the
defect, `cmp` reports a difference, and the harness scores the row. Whatever
verdict comes back — KILLED or SURVIVED — is a verdict about a mutant nobody
designed.

This is the graphene repository's 2026-10-06 **coherence trap** in a different
medium. There, a counterfactual set `R_c = 0` in one of the two places `R_c`
entered the model, and the half-removed version answered the session's
question **with the opposite sign** — and the wrong answer was the plausible
one.

## 2. Three controls, and why control B uses the regex

| | test | form |
|---|---|---|
| **A** | the inserted text is PRESENT in the mutant and ABSENT from the original | fixed-string |
| **B** | the replaced pattern is ABSENT from the mutant | the BRE itself |
| **C** | how many sites the anchor matched | reported, not enforced |

Control B applies **the pattern**, not a literal recovered from it, because
several anchors in this repository are genuinely regexes — `2.b10` uses `.` as
a wildcard for `'` — so there is no literal to recover. `grep`'s BRE dialect
is the same POSIX one `sed` uses, so the pattern transfers unchanged.

Control A *does* need a literal, and sometimes there isn't one: a replacement
containing `&` (the whole-match reference) or `\1` produces text that depends
on what matched. The helper then returns `A_SKIPPED` and says so. **A control
that guesses is worse than one that abstains and says so** — that is 2026-10-01
restated, since the fault there was a control that could not fail.

Control C is reported and not enforced. `sed` mutates every matching line, so
a multi-site mutant is fully injected and its kill is real. What is wrong is
the **description**: a row labelled as one defect that changes three sites
means the kill names the suite's response to a compound change. Nothing is
broken; something is unstated.

## 3. The distinction that needs a count, not a judgement

Two different faults both leave the pattern matching the mutant:

- a **half-injection** — `sed` replaced one per line, the rest survived;
- a **self-matching anchor** — the pattern matches its own replacement, so
  control B is *vacuous* rather than failing.

They are separated by whether the **occurrence count went down**. Fewer
occurrences than the original: half-injection. As many or more: self-matching,
and the repair is a tighter anchor, not a looser control.

**Writing the self-test produced exactly this confusion.** The first attempt
at the half-injection case used anchor `en ? ` with replacement `en ? ~`, which
occurs twice on one line **and** matches its own replacement — so it came back
`B_SELF_MATCHING` instead of `HALF_INJECTED`. The two faults are easy to write
by accident in the same breath. That is the evidence that the distinction needs
a count; the note is kept in the test file beside the case it describes.

A fourth verdict has teeth. **`OK_A_VACUOUS`**: control B held, so the mutant
is complete, but the inserted text already existed in the original, so control
A **cannot fail** on that row. A harness with control A only could not have
verified such a mutant at all.

## 4. The audit: the headline is negative and the body is not

16 sed-injected mutants, three harnesses, two python-injected rows named and
skipped, no simulator, no network.

**No committed mutant is half-injected.** Every row whose `sed` is the real
injection passes control B, so no committed verdict in this repository is a
verdict about a partial mutant. The controls move a class of fault from
undetectable to detected; they do not retroactively find one. That is reported
as a negative result because it is one.

Three rows are usable and are **not what their own harness can certify**:

| row | verdict | what it costs |
|---|---|---|
| `phase6_crv_uart` M3 | `OK_A_VACUOUS` | its inserted text already exists in the DUT |
| `phase6_rx_pin_driver` M4 | `OK_MULTISITE:2` | one described defect, two sites |
| `phase6_rx_pin_driver` M3 | `A_SKIPPED:unparsable` | `0,/re/s||repl|` — no control can be formed |

The first is the item's own answer. M3 replaces
`tx_state <= cfg_two_stop ? TX_STOP2 : TX_IDLE;` with `tx_state <= TX_IDLE;`,
and that inserted text **already sits at `rtl/uart_controller.v:204`**, in the
TX_STOP2 branch. So the arrival control 2026-09-30 asked for — grep the mutant
for the inserted text — cannot fail on this row. **Only control B certifies
that mutant, and control B is precisely what the harnesses did not have.** The
item asked whether the existing harnesses need control B; one of their own
committed rows is the answer.

The third is worth a sentence of its own. `0,/re/s||repl|` is an
address-scoped substitution with an **empty pattern**, which reuses the address
regex. No text-level control can be formed for it by either harness or audit,
so it is recorded as uncontrollable rather than papered over. The repair is to
write the pattern out.

## 5. The auditor needed auditing first

The audit's **first run reported twelve failures**, every one of them
`B_NO_ANCHOR` — "the pattern matches 0 lines of the original".

They were all false. The audit read each harness's mutant table by sourcing
its declarations, and those fragments set their **own** `RTL`, `WORK` and
`HERE`. Sourcing the `phase4_ral` fragment overwrote the audit's `RTL` with a
path relative to `tools/`, so every subsequent `grep` ran against a file that
did not exist — and "the anchor is not in the original" is exactly what a
control says about a missing file.

Twelve false findings that looked exactly like twelve real ones, in the first
run of a script whose entire purpose is to catch controls that cannot fail.
**09-30's rule applies to the auditor**: a control has to sit where the failure
enters, and this one was reading a variable the thing under audit could write.
Every name is prefixed `AUDIT_` now and every table load runs in a subshell
that only prints its rows. The story is in the script's header, because the
next person to add a harness will reach for the same convenient `source`.

## 6. The guard is shown to fire, on the real toolchain

`phase4_ral` now sources the controls; a row whose controls do not hold is
**VOIDED**, counted separately, never as a kill and never as a survivor. Every
scored row prints why its injection is clean.

Icarus Verilog 10.3, cocotb 1.9.2, uvm-python 0.4.0, Python 3.10.12: baseline
PASS, **5 of 5 killed, 0 survived, 0 no-verdict, 0 voided**, 11.8 s. No
committed number moved, which §4 predicted.

And `MC_SELFTEST=1` adds row **MX**, whose anchor `err <= 1'b0;` occurs three
times on each of `rtl/uart_controller.v:243` and `:249`:

```
MX  VOIDED  (HALF_INJECTED)
    HALF_INJECTED: the replaced pattern still occurs 4 time(s) in the
    mutant, down from 6 -- sed made 2 substitution(s), one per matching
    line, and the rest of the occurrences survived.  cmp -s passes this row.
```

In selftest mode the run requires **exactly one** voided row, so the guard's
failure path is exercised by the regression rather than argued for in a
comment. **A guard that has never been seen to fire is not a guard** — this
repository has found that three times (09-17, 09-18, 10-06).

## 7. Methodological note

09-17: a suite can pass against broken RTL. 09-18: and print PASS over its own
errors. 09-19/09-20: the subsystem reporting the verdict is not the subsystem
doing the checking. 09-26: a reachability pre-pass answers "did my attempts
reach it", not "is it reachable". 09-30: a control has to sit where the failure
enters. 10-01: and an arrival control that cannot fail is not a control. 10-05:
a metric can be printed beside the thing it does not measure. 10-06: and the
detector that measures a metric can misattribute what it measured.

**10-07: AND AN INJECTION GUARD IS A MEASUREMENT, SO "DID THE FILE CHANGE" IS
THE WRONG QUESTION. THE QUESTION IS WHETHER THE REPLACED TEXT WENT AWAY — AND
THE TWO FAULTS THAT BOTH LEAVE IT PRESENT ARE SEPARATED BY A COUNT, NOT BY A
JUDGEMENT.**

## 8. A rule crossed between the two repositories, in each direction

The graphene repository's session today hit a mutation survivor whose measured
effect was **6.6e-11 relative** against a value committed to six figures, and
adopted **this repository's 2026-10-01 rule** — *a constant that can be mutated
with no observable effect is not a suite weakness* — reclassifying it as a
control that must survive. The two methodological series have run separately
since 08-21; that is the first rule to cross, and it crossed because **the same
reflex produced the same wrong filing in both.**

Today's rule is a candidate to cross the other way. The graphene mutation
harnesses inject with `src.replace(old, new)` after checking
`src.count(old) != 1` — which is control B's **anchor** test, not control B. It
asks whether the text was there *before*, not whether it is gone *after*. The
same gap exists here in the two python-injected rows, which use
`assert old in s`. `mc_controls_text` exists for them and nothing calls it yet.

## 9. Toolchain note

Both 10-03 gotchas held: **source `tools/setup_iverilog.sh` without a pipe**
(piping runs it in a subshell and the `iverilog`/`vvp` shell functions vanish),
and wrap the real binary rather than the shell function under `timeout`. The
uvm-python stack installed in one call: `cocotb<2.0` → 1.9.2,
`python-constraint --use-pep517` → 1.4.0, `uvm-python` → 0.4.0.

**One new gotcha.** `pip install` puts `cocotb-config` in `$HOME/.local/bin`,
which is **not** on `PATH` in a fresh `device_bash` shell. The phase4_ral
`Makefile` then resolves `$(shell cocotb-config --makefiles)` to the empty
string and fails with

```
make: cocotb-config: No such file or directory
make: *** No rule to make target '/Makefile.sim'.  Stop.
```

— a message that names neither cocotb nor `PATH`, and which the harness
correctly reported as `NORESULT` rather than as a kill. Export
`PATH="$HOME/.local/bin:$PATH"` before running any cocotb harness here.
