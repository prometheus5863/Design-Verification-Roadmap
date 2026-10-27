# cocotb installs again, and the five symptoms behind one blocked decision

**2026-10-27.** The 2026-10-26 **ranked-first** item: *"MAKE cocotb
INSTALLABLE, OR DECIDE IT IS NOT"* — one blocked decision the standing list
was carrying as five separate bullets. It is resolved in the **installs**
direction.

## 1. The recipe that works today

`notes/2026-09-06-uvm-python-toolchain-resolution.md` had the recipe from when
the egress allowlist was wider. It is still broadly right, and it is
**incomplete**: `uvm-python` 0.4.0 declares none of four transitive imports it
makes, so installing it with `--no-deps` (which is what the pinned
`cocotb<2.0` requires) leaves four `ModuleNotFoundError`s that surface **one
per import attempt**, not as a resolver error. The complete sequence, each
step verified by the import that failed before it:

```
pip install --target /tmp/dvlibs "cocotb<2.0"                  # -> cocotb 1.9.2
pip install --target /tmp/dvlibs --use-pep517 python-constraint # -> 1.4.0, builds from sdist
pip install --target /tmp/dvlibs --no-deps uvm-python==0.4.0    # -> 0.4.0
pip install --target /tmp/dvlibs --no-deps cocotb-coverage      # uvm/base/sv.py:35
pip install --target /tmp/dvlibs --no-deps cocotb-bus           # uvm/base/sv.py:38
pip install --target /tmp/dvlibs --no-deps regex                # uvm/base/uvm_cmdline_processor.py:205
```

Then `PYTHONPATH=/tmp/dvlibs`, `PATH=/tmp/dvlibs/bin:$PATH` (for
`cocotb-config`, which the Makefiles shell out to), and `source
tools/setup_iverilog.sh` **without a pipe**.

`--target` rather than `--user`: `/sessions` is 100 % full on this VM, so the
install has to land on `/dev/sda1`, and `/tmp` survives between sessions here,
so a later session will probably find it already there.

**The failure mode worth recording** is that each missing module appears only
when the import that needs it runs. Four separate `ModuleNotFoundError`s, four
separate installs, and at no point does pip say anything is missing — because
by `--no-deps` nothing is. A session that stopped at the first one would have
recorded "uvm-python does not install" and been wrong.

## 2. It does not merely import — it runs

`examples/phase4_ral` is a full uvm-python RAL bench against the unmodified
`rtl/uart_controller.v`:

```
** TESTS=1 PASS=1 FAIL=0 SKIP=0 **
UVM_INFO : 347   UVM_WARNING : 0   UVM_ERROR : 0   UVM_FATAL : 0
[UVMRegHWResetSeq] 4   [UVMRegBitBashSeq] 3   [REG_PREDICTOR] 109
```

Transcript: `examples/phase4_ral/uart_ral_tb_sim_output_2026-10-27.txt`.
The explicit predictor fires 109 times, so the mirror is being updated from the
bus **monitor** and not from the sequence's intent — which is the property that
bench was built to have and the first time it has been re-demonstrated since
2026-09-19.

## 3. The port the 2026-10-26 check was waiting for

2026-10-26 CHECKED five transcript-comparing runners for a cosmetic-edit
neutrality arm (control G2b), found none had one, ported three, and recorded
`phase4_ral` and `phase6_uvm_crv_uart` as **blocked on cocotb**. That block is
gone, so `phase4_ral` gains the arm:

- `mc_neutral_copy` performs the comment-only edit and refuses a byte-identical
  copy.
- This runner asserts **`verdict_of` returning PASS** — the criterion its
  baseline and all five of its rows are already scored by. Per the 2026-10-25
  rule: the helper shares the *edit*, which is identical everywhere, not the
  *verdict*, which is not.
- "The copy would control nothing" and "the bench is sensitive to a comment"
  exit on different messages. That is the 2026-10-25 lesson from runner B,
  which folded them into one.

**Result, the first current report this suite has had since 2026-10-07:**

```
BASELINE:   PASS on unmodified RTL
NEUTRALITY: PASS on a comment-only copy
RESULT: 5 killed, 0 survived, 0 no-verdict, 0 voided, out of 5
```

Every row's injection verdict is `OK` (one site, control A and B both held), so
all five kills are about whole mutants, and the neutrality arm makes them
attributable: the bench does not react to the RTL file merely changing.
`mutation_test_report_2026-10-27.txt`.

**And the positive control still fires.** `MC_SELFTEST=1` adds `MX`, whose
anchor `err <= 1'b0;` occurs three times on each of two lines, so sed without
`/g` leaves four behind:

```
MX  VOIDED  (HALF_INJECTED)
    the replaced pattern still occurs 4 time(s) in the mutant, down from 6
RESULT: 5 killed, 0 survived, 0 no-verdict, 1 voided, out of 6
```

`mutation_selftest_2026-10-27.txt`. This matters more than the 5/5: a guard
that has never been seen to fire is not a guard, and this one had not been run
since the toolchain went away.

## 4. What is still blocked, and what no longer is

Of the five symptoms the ranked-first item said were one decision:

| symptom | status |
|---|---|
| `phase4_ral` neutrality arm | **done today** |
| `phase6_uvm_crv_uart` neutrality arm | unblocked, not done |
| the five suites without a current report | one of five done |
| the equal-budget control re-run | unblocked, not done |
| the other `tx_empty` prediction | unblocked, not done |
| capstone box (b) SVA into the UVM env, (c) `PayloadAdmissibilityCoverage` | unblocked, not done |

So the list should stop ranking them as one blocked decision and start ranking
them as **five pieces of available work**, which is what they now are. That is
a change in the list's shape and not only in its contents.

## 5. One honest caveat about the environment

The toolchain lives in `/tmp` on this VM, outside the repository and outside
any connected folder. It is reachable by the next session only if `/tmp`
survives, which it has so far but is not guaranteed. The recipe above is the
durable artefact, not the installed tree — which is why it is written out in
full here rather than left as "it worked".
