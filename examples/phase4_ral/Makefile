# Phase 4 RAL: uvm-python register abstraction layer over the unmodified
# rtl/uart_controller.v DUT, reusing the bus agent from
# examples/phase4_uvm_milestone/.
#
# Run with: make
# Requires: iverilog on PATH (source tools/setup_iverilog.sh -- do NOT
# pipe it), and the uvm-python stack from
# notes/2026-09-06-uvm-python-toolchain-resolution.md.
#
# RTL_SRC is overridable so the mutation script can point at a mutated
# COPY of the RTL without ever touching rtl/uart_controller.v.

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

RTL_SRC ?= $(PWD)/../../rtl/uart_controller.v
VERILOG_SOURCES += $(RTL_SRC)

TOPLEVEL = uart_controller
MODULE = uart_ral_tb

include $(shell cocotb-config --makefiles)/Makefile.sim
