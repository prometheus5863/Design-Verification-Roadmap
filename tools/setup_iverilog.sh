#!/usr/bin/env bash
# tools/setup_iverilog.sh
#
# Downloads and extracts a working Icarus Verilog (iverilog/vvp) install
# WITHOUT requiring root/apt privileges, for use in sandboxes where
# `apt-get install iverilog` fails on a dpkg lock permission error (as it
# does in the automation sandbox this roadmap repo's daily sessions run
# in -- see AUTOMATION_LOG.md, 2026-08-22 and 2026-08-23 entries).
#
# How it works: Icarus Verilog's Ubuntu 22.04 ("jammy") .deb package is
# downloaded directly from the public Ubuntu archive (no apt/dpkg index
# needed) and unpacked with `dpkg-deb -x`, which only extracts files to a
# target directory and does NOT require install privileges (unlike
# `dpkg -i` / `apt-get install`, which do). The extracted iverilog/vvp
# binaries then need to be told where to find their helper
# libraries/plugins (ivlpp, ivl, *.vpi) via the -B (compile-time) and -M
# (simulation-time) flags, since those binaries expect a fixed system
# path (/usr/lib/x86_64-linux-gnu/ivl) that doesn't exist when extracted
# to a non-standard location.
#
# Usage:
#   source tools/setup_iverilog.sh      # source it -- do NOT pipe it
#   iverilog -g2012 -o sim my_design.v
#   vvp sim
#
# (Piping, e.g. `source tools/setup_iverilog.sh | tail`, runs the script
# in a subshell, so the functions and the PATH change it makes vanish
# and you get a confusing "command not found" -- logged 2026-09-17.)
#
# To use a custom install location, `export IVERILOG_INSTALL_DIR=/some/dir`
# BEFORE sourcing (default: /tmp/iverilog_install).
#
# (After sourcing, this script defines `iverilog` and `vvp` as shell
# functions that wrap the real binaries with the required -B/-M flags
# already applied, so example files' own header comments -- which show
# the plain `iverilog ...` / `vvp sim` invocation for a normal Icarus
# Verilog install -- work unmodified.)
#
# Verified working with Icarus Verilog 10.3 on Ubuntu 22.04 amd64,
# 2026-08-23 (see examples/phase1/*_sim_output_2026-08-23.txt for
# real simulation output produced this way).

set -o pipefail

# NOTE: intentionally not using `set -u` (nounset) here -- this script is
# meant to be `source`d into a caller's shell, and nounset would abort on
# any pre-existing unset variable reference elsewhere in that shell, which
# is a surprising side effect for a setup script to impose. If customizing
# the install location, `export IVERILOG_INSTALL_DIR=...` BEFORE sourcing
# this script (a plain prefix assignment on the `source` line is not
# reliably propagated across all bash invocation styles).
IVERILOG_INSTALL_DIR="${IVERILOG_INSTALL_DIR:-/tmp/iverilog_install}"
IVERILOG_DEB_URL="http://archive.ubuntu.com/ubuntu/pool/universe/i/iverilog/iverilog_10.3-1build1_amd64.deb"

if [ ! -x "${IVERILOG_INSTALL_DIR}/usr/bin/iverilog" ]; then
    echo "Setting up Icarus Verilog (no root required)..."
    mkdir -p "${IVERILOG_INSTALL_DIR}"
    # TMP_DEB LIVES BESIDE THE INSTALL, NOT IN $TMPDIR (fixed 2026-11-07).
    #
    # It used to be `mktemp --suffix=.deb`, which honours $TMPDIR.  In the
    # automation sandbox $TMPDIR resolves onto a filesystem that has been
    # 100 % full for twelve consecutive sessions, so curl could not write the
    # 1.8 MB .deb and exited nonzero -- and this script reported
    # "failed to download", which is a NETWORK diagnosis for a DISK fault.
    # Measured that day: the same URL fetched fine with curl by hand, 200 and
    # 1858972 bytes, while the script kept failing.  Three consecutive
    # sessions had recorded "no toolchain installed" as a deliberate choice;
    # a session that had tried would have been sent to the network by this
    # message.  The install directory is already on /tmp by default, so
    # putting the download there removes the dependence on $TMPDIR entirely.
    TMP_DEB="${IVERILOG_INSTALL_DIR}/iverilog.deb.partial"
    CURL_RC=0
    curl -sSL -o "${TMP_DEB}" "${IVERILOG_DEB_URL}" 2> "${IVERILOG_INSTALL_DIR}/curl.err" || CURL_RC=$?
    if [ "${CURL_RC}" -ne 0 ] || [ ! -s "${TMP_DEB}" ]; then
        # SAY WHICH FAULT IT WAS.  curl exits 23 on a write error and 6/7/28
        # on name-resolution, connection and timeout faults; the free space
        # on the target filesystem distinguishes them even when it does not.
        FREE_KB="$(df -Pk "${IVERILOG_INSTALL_DIR}" 2>/dev/null | awk 'NR==2{print $4}')"
        echo "ERROR: could not fetch the iverilog .deb to ${TMP_DEB}" >&2
        echo "       curl exit ${CURL_RC}; $(wc -c < "${TMP_DEB}" 2>/dev/null || echo 0) bytes written; ${FREE_KB:-unknown} KB free on that filesystem" >&2
        if [ "${CURL_RC}" = "23" ] || [ "${FREE_KB:-1000000}" -lt 4096 ] 2>/dev/null; then
            echo "       This is a DISK fault, not a network one: there is no room to" >&2
            echo "       write the download.  Free space, or set IVERILOG_INSTALL_DIR" >&2
            echo "       to a filesystem that has some." >&2
        else
            echo "       curl.err: $(tr -d '\n' < "${IVERILOG_INSTALL_DIR}/curl.err" 2>/dev/null | tail -c 200)" >&2
        fi
        rm -f "${TMP_DEB}"
        return 1 2>/dev/null || exit 1
    fi
    if ! dpkg-deb -x "${TMP_DEB}" "${IVERILOG_INSTALL_DIR}"; then
        echo "ERROR: dpkg-deb -x failed to extract ${TMP_DEB}" >&2
        return 1 2>/dev/null || exit 1
    fi
    rm -f "${TMP_DEB}"
    echo "Icarus Verilog extracted to ${IVERILOG_INSTALL_DIR}"
else
    echo "Icarus Verilog already set up at ${IVERILOG_INSTALL_DIR}"
fi

IVL_LIB_DIR="${IVERILOG_INSTALL_DIR}/usr/lib/x86_64-linux-gnu/ivl"

# THE TOOLCHAIN NEEDS A WRITABLE TMPDIR AT COMPILE TIME TOO (2026-11-07).
#
# Fixing the download's TMPDIR was only half of it.  `iverilog` writes its own
# preprocessor scratch files into $TMPDIR on every compile, so with $TMPDIR on
# a full filesystem the INSTALL succeeds and then every compile dies with
#
#     iverilog: Error opening temporary file /.../ivrlg5194391
#
# which, like the download message it replaced, names a symptom and not the
# cause.  Measured 2026-11-07 by deliberately pointing TMPDIR at the full
# filesystem after the download fix landed -- i.e. the second fault was found
# by testing the first fix rather than by reading.
#
# IVL_TMPDIR is a directory inside the install, which is on the same
# filesystem the binaries were just written to and is therefore writable by
# construction.  It is used only when the inherited $TMPDIR is not writable,
# so a caller who has set a good TMPDIR keeps it.
IVL_TMPDIR="${IVERILOG_INSTALL_DIR}/tmp"
mkdir -p "${IVL_TMPDIR}"

ivl_tmpdir() {
    # Echo a TMPDIR that is actually writable: the inherited one if it is,
    # otherwise the install's own.
    #
    # THE PROBE WRITES BYTES, AND THAT IS THE WHOLE POINT.  `test -w` is true
    # on a full filesystem, and so is `: > file` -- a zero-length create needs
    # an inode and no data block, so it SUCCEEDS at 0 bytes free.  The first
    # version of this probe did exactly that, reported the full filesystem as
    # writable, never took the fallback, and the compile then failed one layer
    # down with "ivlpp: No input files given" -- a third misattributed message
    # for the same disk fault.  Caught 2026-11-07 by re-running the
    # verification against the REAL full directory after a first run had
    # "passed" against a path that merely did not exist.
    if [ -n "${TMPDIR:-}" ] \
       && head -c 4096 /dev/zero > "${TMPDIR}/.ivl_probe.$$" 2>/dev/null \
       && [ "$(wc -c < "${TMPDIR}/.ivl_probe.$$" 2>/dev/null)" = "4096" ]; then
        rm -f "${TMPDIR}/.ivl_probe.$$"
        printf '%s' "${TMPDIR}"
    else
        rm -f "${TMPDIR:-/nonexistent}/.ivl_probe.$$" 2>/dev/null
        printf '%s' "${IVL_TMPDIR}"
    fi
}

iverilog() {
    TMPDIR="$(ivl_tmpdir)" "${IVERILOG_INSTALL_DIR}/usr/bin/iverilog" \
        -B "${IVL_LIB_DIR}" "$@"
}

vvp() {
    TMPDIR="$(ivl_tmpdir)" "${IVERILOG_INSTALL_DIR}/usr/bin/vvp" \
        -M "${IVL_LIB_DIR}" "$@"
}

# NOTE: these functions are deliberately NOT exported with `export -f`.
#
# An exported bash function POISONS cocotb's simulator auto-detection.
# cocotb's Makefile.inc sets `SHELL := bash`, and Makefile.icarus does
#     CMD := $(shell :; command -v iverilog)
#     ICARUS_BIN_DIR := $(shell dirname $(CMD))
# In a bash that has imported an exported `iverilog` FUNCTION,
# `command -v iverilog` prints the bare word "iverilog" rather than a
# path, so dirname yields "." and cocotb then looks for "./iverilog",
# fails, and reports the misleading
#     *** Unable to locate command >iverilog<
# in a shell where `iverilog -V` plainly works. Diagnosed 2026-09-18.
#
# Leaving the functions unexported keeps them for interactive use in this
# shell while letting every child process resolve the wrapper SCRIPTS
# installed on PATH below -- which give a real path and a correct
# ICARUS_BIN_DIR.

# ---------------------------------------------------------------------
# Also install REAL wrapper SCRIPTS on PATH, not just shell functions.
#
# Shell functions are invisible to any child process that does its own
# command lookup. cocotb's Makefile.icarus does exactly that -- it
# resolves iverilog with a `$(shell which ...)`-style check -- so a
# `make` run in a shell that has sourced this script still fails with:
#
#     Makefile.icarus:53: *** Unable to locate command >iverilog<.  Stop.
#
# even though `iverilog -V` works in that same shell. Found 2026-09-18
# while bringing up examples/phase4_uvm_milestone. `export -f` does not
# help: it exports to bash children, and make does not invoke bash for
# its command lookup. Two-line scripts on PATH do help, and they also
# make the -B/-M flags available to anything that shells out.
#
# This supersedes the 2026-09-17 workaround of calling the real binary
# by absolute path to wrap it in `timeout` -- with these wrappers,
# `timeout 150 vvp sim` works directly, because vvp is now a file.
# ---------------------------------------------------------------------
IVERILOG_BIN_DIR="${IVERILOG_INSTALL_DIR}/bin"
mkdir -p "${IVERILOG_BIN_DIR}"
# The wrapper SCRIPTS carry the TMPDIR fallback too, and they are the ones
# that matter most: a child process (make, cocotb, a mutation runner) resolves
# these and never sees the shell functions above.
cat > "${IVERILOG_BIN_DIR}/iverilog" <<EOF
#!/bin/sh
# The probe WRITES BYTES: a zero-length create succeeds on a full
# filesystem, so \`: > file\` reports it writable when it is not
# (2026-11-07).  THE BACKTICKS ARE ESCAPED, AND ON 2026-11-12 THEY WERE
# NOT: this heredoc is unquoted (it must expand the install paths), so
# bash ran the command substitution at GENERATION time.  Sourcing this
# script created a zero-length file named 'file' in the caller's working
# directory -- every runner, every session -- and deleted the backticked
# text from the comment it was explaining.  The comment warning that a
# zero-length create proves nothing was performing one.
if [ -z "\${TMPDIR:-}" ] \\
   || ! head -c 4096 /dev/zero > "\${TMPDIR}/.ivl_probe.\$\$" 2>/dev/null \\
   || [ "\$(wc -c < "\${TMPDIR}/.ivl_probe.\$\$" 2>/dev/null)" != "4096" ]; then
    rm -f "\${TMPDIR:-/nonexistent}/.ivl_probe.\$\$" 2>/dev/null
    TMPDIR="${IVL_TMPDIR}"
else
    rm -f "\${TMPDIR}/.ivl_probe.\$\$"
fi
export TMPDIR
exec "${IVERILOG_INSTALL_DIR}/usr/bin/iverilog" -B "${IVL_LIB_DIR}" "\$@"
EOF
cat > "${IVERILOG_BIN_DIR}/vvp" <<EOF
#!/bin/sh
# The probe WRITES BYTES: a zero-length create succeeds on a full
# filesystem, so \`: > file\` reports it writable when it is not
# (2026-11-07).  THE BACKTICKS ARE ESCAPED, AND ON 2026-11-12 THEY WERE
# NOT: this heredoc is unquoted (it must expand the install paths), so
# bash ran the command substitution at GENERATION time.  Sourcing this
# script created a zero-length file named 'file' in the caller's working
# directory -- every runner, every session -- and deleted the backticked
# text from the comment it was explaining.  The comment warning that a
# zero-length create proves nothing was performing one.
if [ -z "\${TMPDIR:-}" ] \\
   || ! head -c 4096 /dev/zero > "\${TMPDIR}/.ivl_probe.\$\$" 2>/dev/null \\
   || [ "\$(wc -c < "\${TMPDIR}/.ivl_probe.\$\$" 2>/dev/null)" != "4096" ]; then
    rm -f "\${TMPDIR:-/nonexistent}/.ivl_probe.\$\$" 2>/dev/null
    TMPDIR="${IVL_TMPDIR}"
else
    rm -f "\${TMPDIR}/.ivl_probe.\$\$"
fi
export TMPDIR
exec "${IVERILOG_INSTALL_DIR}/usr/bin/vvp" -M "${IVL_LIB_DIR}" "\$@"
EOF
chmod +x "${IVERILOG_BIN_DIR}/iverilog" "${IVERILOG_BIN_DIR}/vvp"
case ":${PATH}:" in
    *":${IVERILOG_BIN_DIR}:"*) ;;
    *) PATH="${IVERILOG_BIN_DIR}:${PATH}"; export PATH ;;
esac

echo "iverilog/vvp are now available as shell functions AND as scripts in"
echo "${IVERILOG_BIN_DIR} (added to PATH -- needed for cocotb's make flow)."
IVERILOG_VERSION_OUTPUT="$("${IVERILOG_INSTALL_DIR}/usr/bin/iverilog" -V 2>&1)"
echo "${IVERILOG_VERSION_OUTPUT%%$'\n'*}"
