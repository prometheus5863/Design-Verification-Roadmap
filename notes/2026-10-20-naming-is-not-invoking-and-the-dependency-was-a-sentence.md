# Naming is not invoking, and the dependency was a sentence

*2026-10-20 — on the 2026-10-18 item ranked first, and on the warning it
carried being about the right risk and the wrong number.*

## The item

2026-10-18 ranked one item first and named two mechanisms in
`tools/report_provenance_audit.py`:

> 1. **`callers_of()` resolves on BASENAME.** Six different harnesses here are
>    called `run_mutation_tests.sh`, so each is reported as a caller of the
>    others.
> 2. **The closure treats "names the runner" as "is an input to its results".**

Both are real. The second one's *mechanism* is not what that entry guessed,
and the consequence it warned about does not happen.

## The second mechanism was a comment

The entry attributed (2) to the caller relation leaking into the dependency
closure. It does not. `closure_for()` ran `PATH_RE` over the **whole text** of
every script in a report's directory, comments included. A path named in prose
became a dependency.

The edge that forced 2026-10-18 to re-run the baud bench is line 35 of
`examples/phase6_baud_error_coverage/run_mutation_tests.sh`:

```
# tools/harness_file_closure_audit.py after the first was found by hand in
```

A sentence about an auditor. That sentence made the auditor an input to the
bench's mutation report, which made the report stale the instant the auditor
was edited, which is why a bench whose behaviour had not changed had to be
re-run to keep a ratchet green. Measured repository-wide: **40 comment-only
edges, 17 % of the 235 edges this audit was building closures from.**

The sibling repository named *resolve-on-spelling* its dominant failure mode
on the same day. This is that, with the spelling being "appears in the file".

## Why "strip the comments" is the dangerous direction

`tools/mutation_controls.sh` names `rtl/uart_controller.v` **only in prose** —
its code builds the path from a variable. Strip comments and the DUT leaves
the dependency set of the DUT's own mutation tests. That is exactly the
under-report fault the comment above `_VARPREFIX_RE` records this audit's
first version committing, and an under-report here is silent.

So an edge gains a class instead of being kept or deleted:

| class | meaning | effect |
|---|---|---|
| `CODE` | named outside comments | a dependency |
| `PROSE` | named **only** inside comments | reported; held in the DIRECTORY closure, kept out of the tight one |

which is the `TIGHT`/`DIRECTORY` pattern the file already uses, so nothing is
dropped — it is demoted and still printed. Whole-line comments only: a
trailing-`#` rule would have to decide whether the `#` in `sed 's/#//'` opens
a comment, and a rule that can delete code to protect a metric is the wrong
trade.

## The caller relation now needs an invocation

`invocations_of()` requires one of three forms, all of which exist here:

- an **exec verb at a statement boundary** — `bash X`, `sh X`, `source X`,
  `. X`, `./X`, `python3 X`, reached through `timeout 300 bash X` and `env`;
- a **manifest record** — `X|HARNESS|requires|budget|note`.
  `tools/run_all_harnesses.sh` drives every run in this repository from such a
  table and then calls `bash "$path"`, so the record *is* the call;
- a **subprocess call** — `subprocess.run([... 'X' ...])` and relatives.

A bare basename is credited only when it is **unique** in the repository. When
six files share it, `bash run_mutation_tests.sh` does not say which one, and
resolving it to all six is mechanism (1) itself. Such a reference becomes a
third value, `AMBIGUOUS`: reported, never credited. `mentions_of()` keeps the
2026-10-18 relation and is printed as the **upper bound**, so the correction
can be checked against the number it replaced rather than merely appearing as
a smaller figure.

The caller lines now read:

```
run_mutation_tests.sh <- tools/run_all_harnesses.sh
    names it but does not run it (9): examples/phase6_baud_error_coverage/..., ...
```

## Two corrections to the item's own text

**The budget does not move.** The entry warned: *"repairing this LOWERS the
stale count, and the ratchet fails UNDER budget by design — so
`STALE_SUITE_BUDGET` must be lowered in the same commit."* Measured:

| figure | before | after |
|---|---|---|
| STALE reports, tight closure | 49 | 48 |
| stale **and** beside a RUNNER | 48 | 47 |
| **suites with a runner and NO CURRENT REPORT** (what the ratchet reads) | **5** | **5** |

Same five directories. `STALE_SUITE_BUDGET` stays at 5 and the caller passes
*at budget*. Control `P4` pins that equality against the budget parsed out of
`tools/run_all_harnesses.sh`, so the number and the budget cannot drift apart
silently. The warning named a real risk and the wrong number.

**Mechanism (1) was a reporting defect, not a verdict defect.** Reachability
is 15 under both relations, and `AMBIGUOUS` is **0**. Every sibling
cross-reference in this repository sits in a comment, so the comment fix
removes the sibling artefact on its own — the basename rule corrects no
present miscount. It is a guard against a bare-basename exec that does not
exist here yet, and it is pinned by planted text (`I4`, `I5`) rather than by
the tree.

## Three closure absences that are correct

The first draft of control `P3` required every mutation suite's closure to
contain `rtl/uart_controller.v` and `tools/mutation_controls.sh`. It failed on
three, and all three absences are right:

- `phase6_bfm_equivalence` mutates `bfm/uart_rx_pin_bfm.v`. It never touches
  the DUT.
- `phase6_crv_uart` and `phase6_uvm_crv_uart` carry their own controls and
  never source the shared ones.

Measured before and after the comment change, the three absences are
identical, so the change did not cause them. The universal was plausible and
false; `P3` now asserts the conditional that is actually at risk — **every
edge a script spells in code survives into its closure.**

## Mutation testing, and M6's two escapes

Six mutants, six detected, zero escaped — but only after two escapes worth
more than the final score.

`M6` removes the comment strip from the *caller* relation. It first escaped
all fifteen controls **against the tree**, because the invocation patterns
require the exec verb to sit at a statement boundary and the only
exec-verb-inside-prose lines here are `run_all_harnesses.sh`'s usage block
naming *itself*, which both relations exclude as a self-reference.

It then escaped `I6`'s own first draft, which planted
`#   bash <runner> --list` and required the strip to make the difference. It
makes none — a leading `#` is not a statement boundary, so that line is not an
invocation either way, and the draft would have passed against a predicate
with no strip at all. **The control asked a weaker question than the one it
was written to ask, and the predicate was right.** That is the failure mode
both repositories named on 2026-10-18, this time in a control written to
repair it.

What the strip is actually load-bearing for is an operator *before* the verb,
because the operator is a statement boundary:

| planted shape | unstripped | stripped |
|---|---|---|
| `#   bash <runner> --list` | False | False |
| `# to re-run: cat seeds \| bash <runner>` | **True** | False |
| `# then: cd x && bash <runner>` | **True** | False |
| `# note; bash <runner> was removed` | **True** | False |
| `bash <runner>` (real) | True | True |

`I6` plants those three and *also* requires that all three **would** be
credited unstripped, so it cannot pass against a tree or a predicate in which
the strip is irrelevant. With that, `M6` is detected.

Planting is done as **text passed to the predicate**, never as files in the
tree: writing `bash examples/.../run_mutation_tests.sh` into this repository
would make that file a real caller of a real runner and would be read by every
other audit here — the open item *a module must not plant the pattern it
censuses in the tree other audits read*, which this file can simply avoid.

## Carried out

`16 passed, 0 failed`. Transcript byte-identical across two consecutive runs.
Both halves of `tools/run_all_harnesses.sh` green: **18 PASS, 0 FAIL, 7 SKIP,
ratchet OK at budget**, identical to 2026-10-18 — the relations moved the
audit's numbers and nothing in any suite's behaviour.
