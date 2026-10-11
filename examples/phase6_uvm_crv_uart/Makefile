# Phase 6: constrained-random / coverage-driven UART stimulus driven from a
# real UVM sequence (uvm-python on cocotb), against the unmodified
# rtl/uart_controller.v.
#
# Run with: make            (N_SEEDS=6 by default; override on the command line)
# Requires: iverilog on PATH, `pip install python-constraint --use-pep517`,
#           `pip install "cocotb<2.0" uvm-python`, and
#           export PATH="$HOME/.local/bin:$PATH" so cocotb-config is found.
# See notes/2026-09-06-uvm-python-toolchain-resolution.md for the version pins.

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# RTL is overridable so run_mutation_tests.sh can point the SAME testbench at
# a mutated COPY of the DUT without editing anything under rtl/.
RTL ?= $(PWD)/../../rtl/uart_controller.v
VERILOG_SOURCES += $(RTL)

TOPLEVEL = uart_controller
MODULE = uart_uvm_crv_tb

include $(shell cocotb-config --makefiles)/Makefile.sim
