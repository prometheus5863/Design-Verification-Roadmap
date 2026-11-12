# A repair installed where nothing called it, found the third time the same disk told us

**2026-11-12.** Yesterday's ranked item — make the structural CDC checker a gate
rather than a report — closed, and finished in nine checks and five mutants. Then
declaring the 14 undeclared runners into `run_all_harnesses.sh` turned the
caller green for the first time in seventeen sessions, and the first thing it
did with its new reach was go red on two harnesses that had been failing
unobserved. Diagnosing one of those produced the day's real finding, which is
not about this repository's RTL at all.

---

## 1. The gate (the ranked item)

`tools/run_cdc_gate.sh`, 9/9; `tools/run_cdc_gate_mutation.py`, 5/5 mutants, all
five detected by the predicted section.

**The item's premise was wrong, and measuring it first is what showed that.** It
read as though `cdc_structural_check.py` had no verdict to offer. It does —
`main()` has always ended `return 1 if findings else 0`, and measured properly
its contract is exactly right:

| invocation | rc |
|---|---|
| `--selftest` | 0 (25/25) |
| the four shipped sources | 0, no findings |
| all 41 `.v` files | 1, one finding |
| the deliberate crossing alone | 1 |
| bare | 2 (usage) |

What was missing was a **caller**. Nothing in the repository invoked it, and
`run_all_harnesses.sh` could not, because it needs file arguments. So the gate is
a caller with arguments, and the manifest entry is the actual repair — the same
shape as the 2026-10-15 finding that an exit code nobody reads is not a check.

My first measurement got this wrong in a way worth recording: I ran the checker
through `| tail` and read `$?`, which is **tail's** exit status, so the checker
appeared to always exit 0 and I nearly added a `--gate` flag it did not need.
That is the logged 2026-09-17 hazard about `source tools/setup_iverilog.sh |
tail` in a new costume — a pipe silently answers a different question.

### Not an expected-fail list

The tree's single finding is deliberate: the wrong multi-bit crossing in
`examples/phase6_cdc_basics/cdc_crossings_tb.v`, which that example exists in
order to be wrong about. A whole-tree gate would be permanently red, and the
obvious fix — a list of paths whose findings do not count — is the "green claim
over a red guard" `run_all_harnesses.sh` refuses by design. So the tree is
**partitioned** and both halves asserted: the shipped sources must be clean
(S2), **and the deliberate crossing must still fire** (S3). S3 is the half an
expected-fail list throws away: a gate that cannot fail is not a gate. S4 then
requires the set of files carrying findings to be *exactly*
`{cdc_crossings_tb.v}` — a set identity, not a count budget, so a finding that
**moves** from the demo into real RTL cannot net out to the same number.

### A defect in my own mutation harness

D2 came back **UNDETECTED** on its first run, which looked like a hole in S3 and
was not. The anchor was `.d(bin_skewed)`; the port is `.d_src(bin_skewed)`. The
primary replacement matched nothing, the regex fallback renamed the net's
declaration and its alias while leaving the synchroniser instance reading the old
name, the deliberate finding went on firing, and the harness blamed the gate.
**An unanchored mutation is indistinguishable from a gate that cannot see it** —
a false negative wearing the costume of a finding. Repaired twice over: the
anchor is asserted in the mutant, and the runner now digests the whole copied
tree before and after each mutation and reports `NO-OP MUTANT` as a defect in
*itself*, never as a hole in the subject. This is what
`tools/audit_mutation_anchors.sh` catches in the shell harnesses, arriving in a
Python one.

## 2. The manifest gap, and what it was hiding

Section 1 of `run_all_harnesses.sh` was **failing**: 46 paths discovered by the
rule, 32 declared, 14 in neither class. A script whose whole purpose is that its
exit code is load-bearing had been exiting nonzero for structural reasons — and
**a guard that is already red cannot go red.**

The gap was not one oversight. It accumulated over nine recorded growths because
every session added its runner where the work was and the manifest is somewhere
else. The discovery rule worked perfectly throughout; nothing made ignoring it
cost anything.

Now 49 discovered, 49 declared, Section 1 green. Sixteen entries, per-file
reasons, three of them `NOT_A_HARNESS` — including `cdc_structural_check.py`
itself, declared so *because it takes file arguments*, with its new caller
declared `HARNESS` beside it.

And then two newly reachable harnesses were red:

- **`tools/verdict_bearing_census.py`** — 13/14. `M4` shrinks the branch window
  to one line and requires `B2` to go red, on the stated premise that "every real
  one assigns several lines into its branch". True on 2026-11-08, false now:
  under the mutant the live tree still yields `VERDICT 1, CONTROL 2` (against 3
  and 7 unmutated), so `B2` passes. **The mutation asserts a property of the
  tree, not of the classifier**, and the tree moved under it. Same class as D2
  above, reached from the other side.
- **`tools/test_neutrality_controls.py`** — red at `N0`, its own negative
  control, which says in its own words "the COPY is broken, not the arm — every
  row below is meaningless". That one turned out to be §3.

## 3. The finding: a repair installed on a path nothing called

Every Icarus-based harness failed today, each reporting the same four words:
`COMPILE_ERROR`. **The repository was not broken.**

`TMPDIR` in this session pointed at a filesystem that was 100 % full. `iverilog`
could not write the temporary command file it hands to `ivlpp`, `ivlpp` received
an empty file list and said `No input files given`, and every runner converted
that into `COMPILE_ERROR` and aborted its baseline — correctly, since a baseline
that does not pass makes every mutant row meaningless.

This repository had already met that fact **twice**:

1. **2026-11-07** — `tools/setup_iverilog.sh` was given two wrapper scripts,
   `bin/iverilog` and `bin/vvp`, which probe `TMPDIR` **by writing 4096 real
   bytes** (because a zero-length create succeeds on a full filesystem, so
   `: > file` calls it writable when it is not) and fall back to a directory
   inside the install. The wrappers are correct.
2. **2026-11-09** — `progress.md` recorded the symptom in as many words:
   "`iverilog` reports a full disk as `ivlpp: No input files given` … Every
   mutation runner here would score that as `COMPILE_ERROR`, which each of them
   defines as an *injection failure* — a statement about the mutant, when it is a
   statement about the disk." The mitigation, `G0`, went into **one** runner.

Measured today:

| | count |
|---|---|
| runner files invoking the raw `usr/bin` binaries | **19 files, 20 sites** |
| runner files invoking the wrappers | **0** |
| runners carrying the `G0` disk probe | **1** |
| runners grepping for `No input files given` | **2** |

So the repair's **installed surface** and the repository's **used surface** were
disjoint, and the fix protected exactly the two paths no harness used. The
diagnosis was written down and installed in one runner out of nineteen. Three
encounters with one disk, and today is the first time anything reached every
caller.

**Why it hid for five days:** the wrappers and the raw binaries behave
*identically* whenever `TMPDIR` happens to be writable, which it was every day
until today. A latent bypass cannot be told from a working one until the
environment turns. This is the same defect class as §1's "a verdict with no
caller" and as the sibling graphene repository's "installed surface" items — and
the sibling hit its own instance of it the same morning, where a headline check
computed its quantity inline instead of calling the module's own public function.

Demonstrated rather than argued, with `TMPDIR` forced at an unwritable path:

    raw      rc=1   "Error opening temporary file .../ivrlg..."
    wrapper  rc=0   output produced

Same input, same environment. All 20 sites now point at the wrappers;
`run_cdc_sim.sh` still passes; `test_neutrality_controls.py` went from failing in
**zero** seconds to running past a 170-second budget, which is what a baseline
that now compiles looks like.

### A second bug, found in `git status`

Two zero-length files named `file` had appeared in the tree. The wrapper
heredocs in `setup_iverilog.sh` are unquoted — they must be, they expand the
install paths — and one comment inside them contained an **unescaped** backticked
`` `: > file` ``. Bash ran that command substitution at *generation* time. So
sourcing `setup_iverilog.sh` created an empty file named `file` in the caller's
working directory, in every runner and every session since 2026-11-07, and
stripped the backticked text out of the comment it was explaining.

**The comment warning that a zero-length create proves nothing was performing
one.** Reproduced in a clean directory, backticks escaped, and both halves —
the artifact and the lost text — are now checks.

## 4. The guard, and three defects in the guard

`tools/toolchain_preflight.sh`, 11/11: the wrappers exist and still probe by
writing bytes; the inherited `TMPDIR` is probed and **reported rather than
judged**, since a good `TMPDIR` is not a defect; a **forced** differential
requires the raw path to fail and the wrapper to succeed, so the guard does not
depend on being run on a broken day; the bypass set must be **empty**, as a set
identity, so a runner added tomorrow cannot quietly rejoin it; a trivial module
compiles and runs end to end; and sourcing the setup script must write nothing.
Verified against planted regressions in both directions.

Three defects in it, all found by running it, all kept in place:

1. **The bypass census came back GREEN while three files still bypassed the
   wrappers.** It matched `usr/bin/iverilog` and `usr/bin/vvp`; those three built
   the path in two steps — `os.path.join(IVL, 'usr/bin')`, then the binary name
   at the call site — so the full literal never appeared in the source. **A
   census that matches a concatenated string cannot see a concatenation.** Found
   by grepping for the directory by hand after the instrument reported clean.
2. **Section 6's second check PASSED VACUOUSLY.** It used a bare `mktemp -d`,
   which honours the very `$TMPDIR` this file is about, so it failed with "No
   space left on device", the path was the empty string, `cd ""` failed, and
   `ls -A ""` returned nothing. **A check that cannot tell "clean" from "never
   ran" is worth less than no check.**
3. **And the wrapper-content check ran before the probe source,** so it reported
   on an artifact a previous session had generated: a run that reintroduced the
   bug and then restored the fix left the wrapper buggy and the grep green.

## 5. The cross-repository census, and both predictions scored

The sibling repository built `graphene_tolerance_census_audit.py` on 2026-11-11,
and both repositories predicted what it would say about this one. Run today:

    census_repo(root=<this repo>, recursive=False)  ->  0 files, 0 rows
    census_repo(root=<this repo>, recursive=True)   -> 47 files, 6 rows

**The instrument returned the empty set**, because it was a flat `os.listdir` and
all 47 of this tree's Python files live under `tools/` or `examples/`. An empty
census is indistinguishable from a clean one. That is a defect in the sibling's
instrument, found by the first cross-repository use, and it is fixed there.

Recursively: **6 rows, all `NO_QUOTE`, zero adjudicated**, in three files
(`budget_law_exhaustive.py` 3, `uart_uvm_tb.py` 2, `payload_coverage_model.py`
1).

| prediction | verdict |
|---|---|
| **this repository, 11-11 (2):** zero adjudicated; *not* more `NO_QUOTE` rows than the sibling's 102, because these suites compare against exact expected values | **both substantive halves right, reason included** |
| …and its meta-claim that the sibling's prediction was "right in its first half and wrong in its second" | **inverted** — the sibling's first half was the count, which failed |
| **the sibling, 11-11 (3):** more `NO_QUOTE` rows than its own 102; zero adjudicated | **half right** — 6 against 102 is wrong by 17×, in the opposite direction |

And both were **unscorable as posed** until the recursion was fixed: each named a
population in a run that returned nothing.

## 6. What is red, and what clears it

Per this repository's standing rule, the red set is named rather than excused and
there is still deliberately no expected-fail list.

- **`tools/verdict_bearing_census.py`** — re-anchor `M4` on a classifier
  property (require the mutant to change the *tally*), or identify the
  now-one-line occurrences and decide whether the window should matter for them.
- **`tools/test_neutrality_controls.py`** — a run with a budget that fits, which
  needs the chunked invocation rather than a single call.

## Sources

- `tools/setup_iverilog.sh`, the 2026-11-07 wrapper scripts and their byte-writing
  `TMPDIR` probe.
- `progress.md`, the 2026-11-09 entry recording `ivlpp: No input files given` as a
  disk fault, and `G0` in
  `examples/phase6_rx_occupancy_probe/run_rx_occupancy_mutation_tests.sh`.
- `notes/2026-09-17-uart-rtl-bringup-and-status-polling-hazard.md` for the
  pipe-in-a-subshell hazard that §1 met again.
- `graphene_tolerance_census_audit.py` in the sibling repository, and that
  repository's `notes/2026-11-12-the-per-area-check-is-the-same-check.md` §7.
