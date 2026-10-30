# Phase 6: the black-box protocol checker BOUND into the uvm-python
# constrained-random environment, against the unmodified
# rtl/uart_controller.v.
#
# Run with:  source ../../tools/setup_cocotb.sh   (do NOT pipe it)
#            make
#
# The stimulus is examples/phase6_uvm_crv_uart/uart_uvm_crv_tb.py, IMPORTED
# rather than copied -- see the testbench docstring for why that is the one
# design decision that matters here.  PYTHONPATH therefore carries both
# directories.

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

ROOT := $(PWD)/../..

# RTL is overridable so run_mutation_tests.sh can point the SAME bench at a
# mutated COPY of the DUT without editing anything under rtl/.  The checker
# and the wrapper are NOT overridable: a mutation experiment that is allowed
# to mutate the instrument is not measuring the instrument.
RTL ?= $(ROOT)/rtl/uart_controller.v

VERILOG_SOURCES += $(RTL)
VERILOG_SOURCES += $(ROOT)/checkers/uart_protocol_checker.v
VERILOG_SOURCES += $(PWD)/uart_checker_bind_top.v

TOPLEVEL = uart_checker_bind_top
MODULE = uart_uvm_checker_bind_tb

export PYTHONPATH := $(PWD):$(ROOT)/examples/phase6_uvm_crv_uart:$(PYTHONPATH)

include $(shell cocotb-config --makefiles)/Makefile.sim
