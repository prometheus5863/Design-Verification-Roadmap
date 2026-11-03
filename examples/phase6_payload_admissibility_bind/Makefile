# Phase 6: the LIVE half of the payload-admissibility binding -- a third
# subscriber on the CRV environment's monitor analysis port, measuring what
# the stimulus actually drives against the uniform-payload prediction.
#
# Run one policy per invocation (see the module docstring):
#   make POLICIES=0 N_SEEDS=2
#   make POLICIES=1 N_SEEDS=2
# then:
#   python3 summarize_admissibility.py
#
# Requires the same toolchain as phase6_uvm_crv_uart; see
# notes/2026-09-06-uvm-python-toolchain-resolution.md for the version pins.

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

RTL ?= $(PWD)/../../rtl/uart_controller.v
VERILOG_SOURCES += $(RTL)

# The bench imports uart_uvm_crv_tb and payload_coverage_model, so cocotb's
# python must see both example directories as well as this one.
export PYTHONPATH := $(PWD):$(PWD)/../phase6_uvm_crv_uart:$(PWD)/../phase4_uvm_milestone:$(PYTHONPATH)

# THE CLOSURE DISTRIBUTION IS NOT OURS TO WRITE TO.  uart_uvm_crv_tb appends
# one closure row per (seed, policy) to $RESULTS_FILE, default
# `closure_results.csv` RELATIVE to the working directory -- so running this
# bench here silently created a second closure_results.csv in this directory
# holding rows that DUPLICATE the committed distribution next door (same
# seeds, same policies, same numbers).  Harmless where it landed, because
# summarize_closure.py reads the other directory; a doubled distribution if
# this bench is ever run from there.  Pointed at a scratch path for the same
# reason run_mutation_tests.sh does it: a run that is not a closure
# experiment must not contribute to the closure experiment.
RESULTS_FILE ?= /tmp/pac_closure_scratch.csv
export RESULTS_FILE

TOPLEVEL = uart_controller
MODULE = uart_uvm_payload_bind_tb

include $(shell cocotb-config --makefiles)/Makefile.sim
