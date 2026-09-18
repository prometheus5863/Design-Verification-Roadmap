# Phase 4 milestone: cocotb + uvm-python UVM environment for the
# unmodified rtl/uart_controller.v DUT.
#
# Run with: make
# Requires: iverilog on PATH (tools/setup_iverilog.sh -- source it, do
# NOT pipe it), and `pip install python-constraint --use-pep517`,
# `pip install "cocotb<2.0"`, `pip install uvm-python` in that order --
# see notes/2026-09-06-uvm-python-toolchain-resolution.md.

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/../../rtl/uart_controller.v

TOPLEVEL = uart_controller
MODULE = uart_uvm_tb

include $(shell cocotb-config --makefiles)/Makefile.sim
