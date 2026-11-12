#!/usr/bin/env bash
# tools/toolchain_preflight.sh -- 2026-11-12
#
# THE 2026-11-07 TMPDIR REPAIR WAS INSTALLED IN A PLACE NOTHING CALLED.
#
# WHAT HAPPENED.  On 2026-11-12 every Icarus-based harness in this repository
# failed, and each one reported the same four words: COMPILE_ERROR.  The
# repository was not broken.  TMPDIR in the session that ran them pointed at
# a filesystem that was 100 % full, iverilog could not write the temporary
# command file it hands to ivlpp, ivlpp received an empty file list and said
# "No input files given", and every runner converted that into COMPILE_ERROR
# and aborted its baseline -- correctly, since a baseline that does not pass
# makes every mutant row meaningless.
#
# This repository had ALREADY SOLVED THAT PROBLEM, five days earlier.
# tools/setup_iverilog.sh writes two wrapper scripts, bin/iverilog and
# bin/vvp, which probe TMPDIR BY WRITING 4096 REAL BYTES -- because a
# zero-length create succeeds on a full filesystem, so `: > file` reports it
# writable when it is not -- and fall back to a directory inside the install
# when the probe fails.  The wrappers are correct.  They were also, until
# today, called by NOTHING: every runner invoked the raw binaries under
# usr/bin directly, and the repair protected exactly the two paths that no
# harness used.
#
# Measured: 20 invocation sites in 19 runner files, every one of them on the
# raw path.  The repair's installed surface and the repository's used surface
# were disjoint.
#
# This is the same defect class as 2026-11-11's "the structural checker has a
# verdict and no caller" and as the sibling graphene repository's "installed
# surface" items: a fix that exists, is tested, and is not on the path that
# ships.  It stayed invisible for five days for a specific reason -- the
# wrappers and the raw binaries behave IDENTICALLY whenever TMPDIR happens to
# be writable, which it was every day until today.  A latent bypass is
# indistinguishable from a working one until the environment turns.
#
# WHAT THIS FILE DOES
# -------------------
#   1  the wrappers exist and are executable
#   2  the inherited TMPDIR is probed by writing bytes, and REPORTED -- not
#      asserted, because a good TMPDIR is not a defect
#   3  THE DIFFERENTIAL, forced rather than observed: with TMPDIR pointed at
#      an unwritable path, the raw binary MUST fail and the wrapper MUST
#      succeed.  This is deterministic on any machine, including one whose
#      real TMPDIR is fine, so the guard does not depend on being run on a
#      broken day
#   4  SET IDENTITY: no runner in this repository may reference
#      usr/bin/iverilog or usr/bin/vvp.  setup_iverilog.sh is the one
#      permitted referent, because it is the file that WRITES the wrappers
#      and must name what they wrap.  Stated as a set, so a runner added
#      tomorrow cannot quietly rejoin the bypass set
#   5  end to end: a trivial module compiles and runs through the wrappers
#
# Section 3 is the one that matters.  Sections 1, 4 and 5 can all pass on a
# machine where the bypass is harmless; only a forced differential shows that
# the wrapper is doing something the raw path does not.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
IVL="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}"
RAW_BIN="$IVL/usr/bin"
WRAP_BIN="$IVL/bin"
IVL_LIB="$IVL/usr/lib/x86_64-linux-gnu/ivl"

PASS=0
FAIL=0
SKIP=0
pass() { PASS=$((PASS + 1)); echo "  [PASS] $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  [FAIL] $1"; echo "         $2"; }
skip() { SKIP=$((SKIP + 1)); echo "  [SKIP] $1"; echo "         $2"; }

echo "======================================================================"
echo "TOOLCHAIN PREFLIGHT -- $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "does the TMPDIR repair of 2026-11-07 lie on the path the harnesses use?"
echo "======================================================================"
echo "  install   : $IVL"
echo "  raw       : $RAW_BIN"
echo "  wrappers  : $WRAP_BIN"
echo

# --- 4 (first: it is static and needs no toolchain) ----------------------
echo "----------------------------------------------------------------------"
echo "SECTION 4 -- the bypass set must be empty"
echo "----------------------------------------------------------------------"
# THE FIRST FORM OF THIS CENSUS MATCHED ONLY 'usr/bin/iverilog' AND
# 'usr/bin/vvp', AND IT PASSED WHILE THREE FILES STILL BYPASSED THE
# WRAPPERS.  They built the path in two steps --
# `IVL_BIN = os.path.join(IVL, 'usr/bin')`, then joined the binary name at
# the call site -- so the full literal never appeared in the source.  A
# census that matches a concatenated string cannot see a concatenation.  It
# now matches the DIRECTORY, which is the thing being chosen, and excludes
# only the `usr/bin/env` of a shebang.  Found by grepping for the directory
# by hand after the census came back green, which is the second time today
# a green instrument was checked by hand and was wrong.
BYPASS=$(grep -rln 'usr/bin' --include='*.sh' --include='*.py' . 2>/dev/null \
         | sed 's#^\./##' | grep -v '^tools/setup_iverilog\.sh$' \
         | grep -v '^tools/toolchain_preflight\.sh$' | sort \
         | while read -r f; do
               if grep -n 'usr/bin' "$f" | grep -v 'usr/bin/env' \
                  | grep -vqE '^[0-9]+:[[:space:]]*#'; then echo "$f"; fi
           done)
N_BYPASS=$(printf '%s\n' "$BYPASS" | grep -c . || true)
if [ "$N_BYPASS" -eq 0 ]; then
    pass "no runner references the raw usr/bin binaries"
else
    fail "$N_BYPASS file(s) call the raw binaries and so bypass the TMPDIR repair" \
         "$(printf '%s ' $BYPASS)
         Point these at \$IVL/bin instead.  They will work on any day when
         TMPDIR happens to be writable, which is why this must be a check."
fi
if grep -q 'usr/bin/iverilog' tools/setup_iverilog.sh; then
    pass "and setup_iverilog.sh still names the raw binaries, as the file that wraps them must"
else
    fail "setup_iverilog.sh no longer references the raw binaries" \
         "it is the file that WRITES the wrappers; if it stopped naming what
         they wrap, the wrappers are no longer wrapping this install."
fi

# --- 1 -------------------------------------------------------------------
echo
echo "----------------------------------------------------------------------"
echo "SECTION 1 -- the wrappers exist"
echo "----------------------------------------------------------------------"
if [ ! -x "$RAW_BIN/iverilog" ]; then
    skip "Icarus is not installed at $IVL" \
         "sections 1-3 and 5 need it; source tools/setup_iverilog.sh WITHOUT
         A PIPE first (a pipe runs it in a subshell and the install is lost)."
else
    for w in iverilog vvp; do
        if [ -x "$WRAP_BIN/$w" ]; then
            pass "$WRAP_BIN/$w exists and is executable"
        else
            fail "$WRAP_BIN/$w is missing" \
                 "setup_iverilog.sh writes it; re-source that script."
        fi
    done
    if grep -q 'head -c 4096 /dev/zero' "$WRAP_BIN/iverilog" 2>/dev/null; then
        pass "the wrapper probes TMPDIR BY WRITING BYTES, not with a zero-length create"
    else
        fail "the wrapper's TMPDIR probe is gone or no longer writes bytes" \
             "a zero-length create succeeds on a full filesystem, which is the
         2026-11-07 finding; without the byte write the wrapper is decorative."
    fi

    # --- 2 ---------------------------------------------------------------
    echo
    echo "------------------------------------------------------------------"
    echo "SECTION 2 -- the inherited TMPDIR, reported and not judged"
    echo "------------------------------------------------------------------"
    T="${TMPDIR:-/tmp}"
    PROBE="$T/.preflight_probe.$$"
    if head -c 4096 /dev/zero > "$PROBE" 2>/dev/null \
       && [ "$(wc -c < "$PROBE" 2>/dev/null)" = "4096" ]; then
        echo "  inherited TMPDIR = $T  -- WRITABLE (4096 bytes went in)"
        echo "  on a day like this the raw path would work too, which is"
        echo "  exactly how the bypass stayed invisible.  Section 3 forces it."
    else
        echo "  inherited TMPDIR = $T  -- NOT USABLE (the 4096-byte probe failed)"
        echo "  this is the 2026-11-12 condition.  Every raw-path invocation"
        echo "  in this repository would report COMPILE_ERROR right now."
        df -h "$T" 2>/dev/null | tail -1 | sed 's/^/    /'
    fi
    rm -f "$PROBE" 2>/dev/null
    pass "the inherited TMPDIR was probed by writing bytes and reported above"

    # --- 3 ---------------------------------------------------------------
    echo
    echo "------------------------------------------------------------------"
    echo "SECTION 3 -- THE DIFFERENTIAL, forced: raw must fail, wrapper must not"
    echo "------------------------------------------------------------------"
    WORK="$(mktemp -d "${IVL}/tmp/preflight.XXXXXX")"
    printf 'module triv; initial begin $display("RESULT: PASS"); $finish; end endmodule\n' \
        > "$WORK/triv.v"
    BAD="$WORK/not_a_writable_dir"      # deliberately never created
    TMPDIR="$BAD" "$RAW_BIN/iverilog" -B "$IVL_LIB" -o "$WORK/raw.vvp" \
        "$WORK/triv.v" > "$WORK/raw.log" 2>&1
    RAW_RC=$?
    TMPDIR="$BAD" "$WRAP_BIN/iverilog" -o "$WORK/wrap.vvp" \
        "$WORK/triv.v" > "$WORK/wrap.log" 2>&1
    WRAP_RC=$?
    echo "  with TMPDIR pointed at a path that does not exist:"
    echo "    raw     rc=$RAW_RC   $(head -1 "$WORK/raw.log" 2>/dev/null)"
    echo "    wrapper rc=$WRAP_RC"
    if [ "$RAW_RC" -ne 0 ]; then
        pass "the raw binary FAILS with an unusable TMPDIR (rc=$RAW_RC)"
    else
        fail "the raw binary succeeded with an unusable TMPDIR" \
             "then this version of Icarus does not need TMPDIR and the
         wrappers protect against nothing on it.  Re-decide the item rather
         than keeping a guard whose premise has gone."
    fi
    if [ "$WRAP_RC" -eq 0 ] && [ -f "$WORK/wrap.vvp" ]; then
        pass "the wrapper SUCCEEDS in the same environment, which is the whole repair"
    else
        fail "the wrapper also failed (rc=$WRAP_RC)" \
             "$(tail -3 "$WORK/wrap.log" 2>/dev/null)
         the TMPDIR fallback is not working; this is now a live outage for
         every simulation harness."
    fi

    # --- 5 ---------------------------------------------------------------
    echo
    echo "------------------------------------------------------------------"
    echo "SECTION 5 -- end to end through the wrappers"
    echo "------------------------------------------------------------------"
    if "$WRAP_BIN/iverilog" -o "$WORK/e2e.vvp" "$WORK/triv.v" > "$WORK/e2e.log" 2>&1 \
       && OUT="$("$WRAP_BIN/vvp" "$WORK/e2e.vvp" 2>&1)" \
       && printf '%s' "$OUT" | grep -q 'RESULT: PASS'; then
        pass "a trivial module compiles AND runs through bin/iverilog + bin/vvp"
    else
        fail "the end-to-end run through the wrappers failed" \
             "$(tail -3 "$WORK/e2e.log" 2>/dev/null) / ${OUT:-no output}"
    fi
    rm -rf "$WORK"
fi

echo
echo "----------------------------------------------------------------------"
echo "SECTION 6 -- sourcing the setup script must not WRITE anything"
echo "----------------------------------------------------------------------"
# FOUND 2026-11-12, BY NOTICING TWO ZERO-LENGTH FILES NAMED 'file' IN
# `git status`.  The wrapper heredocs in setup_iverilog.sh are unquoted --
# they have to be, they expand the install paths -- and one comment inside
# them read "a zero-length create succeeds on a full filesystem, so
# `: > file` reports it writable when it is not".  The backticks were not
# escaped, so bash ran the command substitution at GENERATION time: sourcing
# setup_iverilog.sh created an empty file named 'file' in the caller's
# working directory, in every runner and every session since 2026-11-07, and
# removed the backticked text from the comment it was explaining.  A comment
# warning that a zero-length create proves nothing was performing one.
#
# Two checks, because the two halves fail independently: the artifact in the
# caller's directory, and the text lost from the generated wrapper.
# ORDER MATTERS HERE, AND THE FIRST VERSION HAD IT WRONG.  The wrapper on
# disk was written by whatever ran setup_iverilog.sh LAST, which may have
# been a different session or a different version of the script, so grepping
# it first reports on a stale artifact: a run that reintroduced the bug and
# then restored the fix left the wrapper buggy and the grep green.  The probe
# source happens FIRST, which regenerates the wrappers from the script as it
# stands right now, and only then is the wrapper inspected.
PROBE_DIR="$(mktemp -d "${IVL}/tmp/preflight_probe.XXXXXX" 2>/dev/null || true)"
if [ -z "$PROBE_DIR" ] || [ ! -d "$PROBE_DIR" ]; then
    fail "could not create the probe directory, so section 6 did not run" \
         "mktemp failed under ${IVL}/tmp; this check is NOT reported as a pass,
         because it looked at nothing."
else
    ( cd "$PROBE_DIR" && . "$ROOT/tools/setup_iverilog.sh" ) > /dev/null 2>&1
    STRAY="$(ls -A "$PROBE_DIR" 2>/dev/null)"
    if [ -z "$STRAY" ]; then
        pass "sourcing tools/setup_iverilog.sh in a verified empty directory leaves it empty"
    else
        fail "sourcing tools/setup_iverilog.sh WRITES into the caller's directory" \
             "stray: $(printf '%s ' $STRAY)
         environment setup must not litter the tree it is run from; these
         files turn up in git status and in the manifest discovery rule."
    fi
    rm -rf "$PROBE_DIR"
    if [ -x "$WRAP_BIN/iverilog" ]; then
        if grep -qF ': > file' "$WRAP_BIN/iverilog"; then
            pass "and the wrapper just regenerated CONTAINS the backticked ': > file' text, so no command substitution ran at generation time"
        else
            fail "the regenerated wrapper has lost the backticked text of its own comment" \
                 "an unescaped backtick in the unquoted heredoc was executed when
         the wrapper was written.  Escape it in tools/setup_iverilog.sh."
        fi
    else
        skip "no wrapper to inspect" "Icarus is not installed at $IVL"
    fi
fi

echo
echo "======================================================================"
echo "TOTAL: $PASS passed, $FAIL failed, $SKIP skipped"
echo "======================================================================"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
