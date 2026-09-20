#!/usr/bin/env bash
# tools/setup_formal.sh
#
# Phase 5 formal toolchain, installed without root, in the same spirit as
# tools/setup_iverilog.sh. SOURCE it, do not pipe it -- the PATH export
# below is lost in a subshell, exactly as documented for setup_iverilog.sh
# on 2026-09-18.
#
#     source tools/setup_formal.sh
#
# What it installs:
#   yowasp-yosys   -- Yosys + SymbiYosys (sby) + yosys-smtbmc, as WebAssembly
#                     builds on PyPI. No apt, no root, no compiler needed.
#   z3-solver      -- the SMT solver sby's smtbmc engine calls. Ships a
#                     native `z3` binary in the same bin directory.
#
# Why WASM: this VM has no root and is rebuilt every session, so the usual
# oss-cad-suite tarball is not an option. The WASM builds are ~10x slower to
# start (each invocation prints "Preparing to run ... This might take a
# while") but are otherwise the real Yosys.
#
# sby calls its helpers as plain `yosys` and `yosys-smtbmc`; YoWASP installs
# them as `yowasp-yosys` and `yowasp-yosys-smtbmc`, so this script drops
# shims into $FORMAL_BIN.

FORMAL_BIN="${FORMAL_BIN:-$HOME/.formal_bin}"

python3 -m pip install --quiet --user yowasp-yosys z3-solver || {
    echo "setup_formal: pip install failed (network?)" >&2
    return 1 2>/dev/null || exit 1
}

mkdir -p "$FORMAL_BIN"
for real in yosys yosys-smtbmc yosys-witness; do
    cat > "$FORMAL_BIN/$real" <<EOF
#!/bin/sh
exec "\$HOME/.local/bin/yowasp-$real" "\$@"
EOF
    chmod +x "$FORMAL_BIN/$real"
done
cat > "$FORMAL_BIN/sby" <<'EOF'
#!/bin/sh
exec "$HOME/.local/bin/yowasp-sby" "$@"
EOF
chmod +x "$FORMAL_BIN/sby"

export PATH="$FORMAL_BIN:$HOME/.local/bin:$PATH"

echo "setup_formal: yosys  -> $(yosys -V 2>/dev/null | head -1)"
echo "setup_formal: z3     -> $(z3 --version 2>/dev/null)"
echo "setup_formal: sby    -> $(sby --help 2>&1 | head -1)"
echo "setup_formal: PATH now includes $FORMAL_BIN"
