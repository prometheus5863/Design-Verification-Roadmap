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
#   source tools/setup_iverilog.sh
#   iverilog -g2012 -o sim my_design.v
#   vvp sim
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

export -f iverilog vvp 2>/dev/null || true

echo "iverilog/vvp are now available as shell functions in this session."
IVERILOG_VERSION_OUTPUT="$("${IVERILOG_INSTALL_DIR}/usr/bin/iverilog" -V 2>&1)"
echo "${IVERILOG_VERSION_OUTPUT%%$'\n'*}"
