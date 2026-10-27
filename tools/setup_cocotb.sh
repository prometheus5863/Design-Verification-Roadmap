#!/usr/bin/env bash
# tools/setup_cocotb.sh -- the resumable, offline-reusable form of the
# cocotb + uvm-python recipe recorded in
# notes/2026-10-27-cocotb-installs-again-and-the-port-it-unblocked.md.
#
# =====================================================================
# WHAT THIS ADDS, AND WHAT IT DOES NOT CLAIM
# =====================================================================
# The recipe is already written down and already correct.  This script
# does not supersede it, does not re-decide the 2026-10-26 ranked-first
# item (that was resolved the same day, in the "it installs" direction),
# and does not claim to have found an unrecorded blocker.  It adds four
# things the prose form does not have:
#
#   1. A RESUMABLE FETCH, which is the difference between the recipe
#      working and appearing to be blocked.  Measured on 2026-10-27:
#      pypi.org and files.pythonhosted.org both answer 200; sustained
#      throughput is ~26-28 kB/s; the cocotb 1.9.2 wheel is 4 209 565
#      bytes, so one fetch needs ~155 s; A SHELL CALL IN THIS
#      AUTOMATION ENVIRONMENT IS CAPPED AT 180 s and no background
#      process survives it; and `pip download` DOES NOT RESUME -- the
#      first attempt here died at 150 s having written 3 141 632 of
#      4 209 565 bytes, and a retry restarts at zero.  `curl -C -` does
#      resume (HTTP 206), which is how the remainder came down.
#
#      So a plain `pip install "cocotb<2.0"` on this link fails in a way
#      that is INDISTINGUISHABLE FROM A BLOCKED EGRESS ALLOWLIST, and
#      fails again identically on every retry.  Whether that is what
#      produced the 2026-10-11..2026-10-26 "cocotb does not install"
#      claim CANNOT BE PROVED from here -- the past allowlist is not
#      observable -- but it is sufficient on its own to produce that
#      history with nothing having changed.  Stated as a hypothesis with
#      its measurements, not as a finding.
#
#   2. NO NETWORK ON RE-RUN.  The wheelhouse is a directory of pinned
#      files and install is --no-index throughout, so a second session
#      needs no egress at all.  /tmp survives between sessions here.
#
#   3. A --verify THAT CAN FAIL, and is shown failing in the committed
#      transcript against a bare venv.  A setup script that exits 0 on a
#      half-built stack is the "control that cannot fail" shape this
#      repository has recorded three sessions running.
#
#   4. A --smoke THAT RUNS THE REAL DUT.  Imports are necessary and not
#      sufficient; --smoke compiles rtl/uart_controller.v and drives it
#      from a cocotb test.
#
# =====================================================================
# ICARUS IS NOT THIS SCRIPT'S BUSINESS -- A CORRECTION TO ITS OWN FIRST
# DRAFT
# =====================================================================
# The first draft of this file installed its own `iverilog`/`vvp`
# wrapper scripts on PATH and asserted, in a committed comment, that
# "tools/setup_iverilog.sh defines shell FUNCTIONS, which make cannot
# see" and that this "was never written down".
#
# BOTH HALVES WERE FALSE.  tools/setup_iverilog.sh ALREADY installs real
# wrapper SCRIPTS on PATH, and already documents the problem more
# thoroughly than the draft did -- diagnosed 2026-09-18, including the
# subtler finding that `export -f` actively POISONS cocotb's simulator
# auto-detection, because `command -v iverilog` in a bash holding an
# exported function prints a bare word instead of a path, so
# Makefile.icarus computes ICARUS_BIN_DIR="." and reports "Unable to
# locate command >iverilog<" in a shell where `iverilog -V` works.
#
# This is precisely the fault 2026-10-25 recorded -- AN OPEN ITEM THAT
# ASSERTED WHAT WAS INSIDE A FILE AND WAS WRONG, where "C has had one
# all along, and a stronger one" -- committed again, by the session that
# had just read that entry, about a file in tools/ next to this one.
# The draft's duplicate wrappers are removed; this script SOURCES
# tools/setup_iverilog.sh and owns only the Python side.
#
# =====================================================================
# USAGE
# =====================================================================
#   source tools/setup_cocotb.sh            # do NOT pipe it
#   make -C examples/phase4_ral
#
#   bash tools/setup_cocotb.sh --verify     report; exit 1 if incomplete
#   bash tools/setup_cocotb.sh --smoke      compile and RUN against the DUT
#
# Environment: COCOTB_VENV (default /tmp/cocotb_venv),
#              COCOTB_WHEELHOUSE (default /tmp/cocotb_wheels),
#              IVERILOG_INSTALL_DIR (honoured by setup_iverilog.sh).
#
# ---------------------------------------------------------------------
# THE PINS, AND WHY EACH IS PINNED
# ---------------------------------------------------------------------
#   cocotb            1.9.2        uvm-python 0.4.0 requires cocotb<2.0
#   uvm-python        0.4.0        the release these benches target
#   cocotb-coverage   1.2.0        2.0 declares requires-python >=3.11 and
#                                  this VM is 3.10.12; pip HARD-REFUSES it
#                                  with "requires a different Python".
#                                  The recorded recipe installs
#                                  cocotb-coverage unpinned, which gets
#                                  2.0 and that refusal.
#   cocotb-bus        0.3.0        imported by uvm.base.sv
#   regex             2024.11.6    imported by uvm.base.uvm_cmdline_processor
#   pyyaml            6.0.2        a DECLARED dependency of cocotb-coverage,
#                                  absent from the recorded recipe's list of
#                                  four.  pip reports it missing under
#                                  --no-deps.  NOTE, to avoid overstating:
#                                  NOTHING RUN SO FAR HAS NEEDED IT -- both
#                                  phase4_ral and phase6_uvm_crv_uart,
#                                  coverage report included, complete
#                                  without it.  It is pinned because a
#                                  declared dependency that is merely not
#                                  yet reached is a latent import error,
#                                  which is the same shape as the four the
#                                  recorded recipe found one at a time.
#   find_libpython    0.5.1        cocotb uses it to locate libpython
#   python-constraint 1.4.0        ships ONLY a .tar.bz2 sdist; installed
#                                  with --no-build-isolation so the venv's
#                                  own setuptools is used.  The 2026-09-06
#                                  note says --use-pep517; with --no-index
#                                  that fails, because build isolation then
#                                  cannot fetch `wheel` and `packaging`.

set -o pipefail

COCOTB_VENV="${COCOTB_VENV:-/tmp/cocotb_venv}"
COCOTB_WHEELHOUSE="${COCOTB_WHEELHOUSE:-/tmp/cocotb_wheels}"

# The /sessions filesystem on this VM is routinely 100% full; anything
# calling mktemp -d lands there by default and fails mid-run rather than
# refusing cleanly.  Logged 2026-10-26 from both repositories, with two
# different symptoms.  Also why the venv and wheelhouse default to /tmp.
export TMPDIR="${TMPDIR:-/tmp}"

_COCOTB_PINS="
cocotb 1.9.2
regex 2024.11.6
uvm-python 0.4.0
cocotb-bus 0.3.0
cocotb-coverage 1.2.0
pyyaml 6.0.2
find-libpython 0.5.1
python-constraint 1.4.0
"

_cs_say () { echo "[setup_cocotb] $*"; }

# Fetch one pinned distribution into the wheelhouse, resumably.
#
# Uses the PER-VERSION PyPI JSON endpoint (/pypi/NAME/VERSION/json),
# never /pypi/NAME/json.  The all-releases document for `regex` is
# >600 kB and for `setuptools` larger; at this link speed a 25-40 s curl
# cap truncates it mid-string and python reports a JSONDecodeError, which
# reads like a bug in this script rather than a truncated download.
# Cost two attempts on 2026-10-27.
_cs_fetch_one () {
    local name="$1" version="$2" meta url fname size attempt
    meta="$(curl -s -m 40 "https://pypi.org/pypi/${name}/${version}/json" \
            | python3 -c '
import sys, json
d = json.load(sys.stdin)
urls = d["urls"]
cands = [u for u in urls
         if u["filename"].endswith(".whl")
         and ("py3-none-any" in u["filename"]
              or ("cp310" in u["filename"] and "x86_64" in u["filename"]
                  and "manylinux" in u["filename"]))]
if not cands:
    cands = urls           # sdist-only, e.g. python-constraint
u = cands[0]
print(u["url"], u["filename"], u["size"])
' 2>/dev/null)"
    if [ -z "${meta}" ]; then
        _cs_say "ERROR: could not read PyPI metadata for ${name}==${version}" >&2
        return 1
    fi
    read -r url fname size <<<"${meta}"

    local dest="${COCOTB_WHEELHOUSE}/${fname}"
    if [ -s "${dest}" ] && [ "$(stat -c %s "${dest}")" = "${size}" ]; then
        _cs_say "have   ${fname}"
        return 0
    fi
    # Each leg is capped well under the 180 s shell-call limit so a single
    # call always makes progress; -C - resumes from what is on disk.
    for attempt in 1 2 3 4 5 6; do
        curl -L -C - -o "${dest}" "${url}" -s -m 100 >/dev/null 2>&1
        if [ -s "${dest}" ] && [ "$(stat -c %s "${dest}")" = "${size}" ]; then
            _cs_say "got    ${fname} (${size} bytes, ${attempt} leg(s))"
            return 0
        fi
        _cs_say "resuming ${fname}: $(stat -c %s "${dest}" 2>/dev/null || echo 0)/${size}"
    done
    _cs_say "ERROR: ${fname} incomplete after 6 legs" >&2
    return 1
}

_cs_build_wheelhouse () {
    mkdir -p "${COCOTB_WHEELHOUSE}" || return 1
    local name version rc=0
    while read -r name version; do
        [ -z "${name}" ] && continue
        _cs_fetch_one "${name}" "${version}" || rc=1
    done <<<"${_COCOTB_PINS}"
    return "${rc}"
}

_cs_install () {
    if [ ! -x "${COCOTB_VENV}/bin/python" ]; then
        _cs_say "creating venv at ${COCOTB_VENV}"
        python3 -m venv "${COCOTB_VENV}" || return 1
    fi
    local pip="${COCOTB_VENV}/bin/pip" sdist
    # --no-deps throughout: the pin list IS the dependency closure, and
    # letting pip resolve sends it to the network for cocotb-coverage
    # 2.0, which this Python cannot install.
    "${pip}" install -q --no-index --no-deps "${COCOTB_WHEELHOUSE}"/*.whl 2>&1 | tail -3
    for sdist in "${COCOTB_WHEELHOUSE}"/*.tar.bz2 "${COCOTB_WHEELHOUSE}"/*.tar.gz; do
        [ -e "${sdist}" ] || continue
        "${pip}" install -q --no-index --no-build-isolation "${sdist}" 2>&1 | tail -3
    done
}

# Icarus belongs to tools/setup_iverilog.sh -- see the header correction.
_cs_setup_iverilog () {
    local here
    here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
    # shellcheck disable=SC1091
    . "${here}/setup_iverilog.sh" >/dev/null 2>&1 || {
        _cs_say "ERROR: could not source ${here}/setup_iverilog.sh" >&2
        return 1
    }
}

_cs_export_path () {
    case ":${PATH}:" in
        *":${COCOTB_VENV}/bin:"*) : ;;
        *) PATH="${COCOTB_VENV}/bin:${PATH}" ;;
    esac
    export PATH
}

_cs_verify () {
    local rc=0 py="${COCOTB_VENV}/bin/python" mod tool
    echo "===================================================================="
    echo "cocotb STACK VERIFY"
    echo "===================================================================="
    echo "  venv       : ${COCOTB_VENV}"
    echo "  wheelhouse : ${COCOTB_WHEELHOUSE}"
    echo
    if [ ! -x "${py}" ]; then
        echo "  FAIL  no venv python at ${py}"
        echo
        echo "  RESULT: FAIL"
        echo "===================================================================="
        return 1
    fi
    echo "  python     : $("${py}" -V 2>&1)"
    echo
    for mod in cocotb find_libpython constraint cocotb_coverage cocotb_bus regex yaml uvm; do
        if "${py}" -c "import ${mod}" >/dev/null 2>&1; then
            echo "  PASS  import ${mod}"
        else
            echo "  FAIL  import ${mod}"; rc=1
        fi
    done
    echo
    # Necessary-but-not-sufficient: uvm-python's RAL subpackage is what
    # examples/phase4_ral needs, and a bare `import uvm` can succeed
    # while it is unusable.
    if "${py}" -c "
from uvm.base.uvm_config_db import UVMConfigDb
from uvm.reg.uvm_reg_block import UVMRegBlock
from uvm.reg.uvm_reg_predictor import UVMRegPredictor
from uvm.reg.sequences.uvm_reg_bit_bash_seq import UVMRegBitBashSeq
from uvm import UVMTest, UVMEnv, UVMDriver
" >/dev/null 2>&1; then
        echo "  PASS  uvm-python RAL + component classes importable"
    else
        echo "  FAIL  uvm-python RAL + component classes importable"; rc=1
    fi
    # `type -P`, NOT `command -v`.  The first draft of this verify used
    # `command -v iverilog`, which prints the bare word "iverilog" when a
    # shell FUNCTION of that name exists -- and sourcing
    # tools/setup_iverilog.sh defines exactly such a function.  So the
    # draft reported "PASS  iverilog on PATH (iverilog)" in a shell where
    # nothing executable was on PATH at all, which is the precise failure
    # mode that file documented on 2026-09-18: make does its own lookup
    # and cannot see a function.  `type -P` searches PATH only and
    # returns a real path or nothing, so this check now asks the
    # question make asks.
    for tool in iverilog vvp cocotb-config; do
        local path_to
        path_to="$(type -P "${tool}" 2>/dev/null)"
        case "${path_to}" in
            /*) echo "  PASS  ${tool} is an executable file on PATH (${path_to})" ;;
            *)  echo "  FAIL  ${tool} is not an executable file on PATH" \
                     "(a shell function does not count: make cannot see one)"
                rc=1 ;;
        esac
    done
    echo
    echo "  RESULT: $([ "${rc}" -eq 0 ] && echo PASS || echo FAIL)"
    echo "===================================================================="
    return "${rc}"
}

_cs_smoke () {
    local root d out
    root="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
    d="${TMPDIR}/cocotb_smoke.$$"
    mkdir -p "${d}" || return 1
    cat > "${d}/test_cocotb_smoke.py" <<'EOF'
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge


@cocotb.test()
async def smoke(dut):
    """Reset the real UART and read one architectural invariant back."""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0
    for sig in ("psel", "penable", "pwrite", "paddr", "pwdata"):
        getattr(dut, sig).value = 0
    dut.rx.value = 1
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    assert dut.pready.value == 1, "pready is tied high in the v1 scope"
    dut._log.info("SMOKE PASS: cocotb drove the real UART DUT")
EOF
    cat > "${d}/Makefile" <<EOF
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
VERILOG_SOURCES += ${root}/rtl/uart_controller.v
TOPLEVEL = uart_controller
MODULE = test_cocotb_smoke
include \$(shell cocotb-config --makefiles)/Makefile.sim
EOF
    ( cd "${d}" && make ) 2>&1 | tail -20
    out="${d}/results.xml"
    # make's own exit status is NOT usable here: it is 0 even when a
    # cocotb test FAILS.  Verified 2026-10-27 with a deliberately
    # failing cocotb test against this same DUT -- MAKE EXIT STATUS = 0
    # with TESTS=1 PASS=0 FAIL=1.  results.xml carries the <failure>
    # element; the exit status does not.  Scoring on `make` would make
    # this smoke test a control that cannot fail.
    if [ ! -f "${out}" ] || grep -q "<failure" "${out}" 2>/dev/null; then
        echo "  RESULT: FAIL  (results.xml: ${out})"
        return 1
    fi
    echo "  RESULT: PASS  (cocotb compiled and ran against rtl/uart_controller.v)"
    return 0
}

_cs_main () {
    case "${1:-}" in
        --verify) _cs_setup_iverilog; _cs_export_path; _cs_verify; return $? ;;
        --smoke)  _cs_setup_iverilog; _cs_export_path; _cs_smoke;  return $? ;;
    esac
    _cs_build_wheelhouse  || return 1
    _cs_install           || return 1
    _cs_setup_iverilog    || return 1
    _cs_export_path
    _cs_verify
}

_cs_main "$@"
