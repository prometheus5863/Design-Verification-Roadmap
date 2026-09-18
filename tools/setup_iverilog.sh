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
    TMP_DEB="$(mktemp --suffix=.deb)"
    if ! curl -sL -o "${TMP_DEB}" "${IVERILOG_DEB_URL}"; then
        echo "ERROR: failed to download iverilog .deb from ${IVERILOG_DEB_URL}" >&2
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

iverilog() {
    "${IVERILOG_INSTALL_DIR}/usr/bin/iverilog" -B "${IVL_LIB_DIR}" "$@"
}

vvp() {
    "${IVERILOG_INSTALL_DIR}/usr/bin/vvp" -M "${IVL_LIB_DIR}" "$@"
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
cat > "${IVERILOG_BIN_DIR}/iverilog" <<EOF
#!/bin/sh
exec "${IVERILOG_INSTALL_DIR}/usr/bin/iverilog" -B "${IVL_LIB_DIR}" "\$@"
EOF
cat > "${IVERILOG_BIN_DIR}/vvp" <<EOF
#!/bin/sh
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
