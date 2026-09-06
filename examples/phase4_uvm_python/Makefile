# Phase 4 milestone (partial): cocotb+uvm-python Makefile for alu_uvm_tb.py
# against the unmodified alu_dut from examples/phase2/alu_if_and_dut.sv.
#
# Run with: make
# (requires: iverilog on PATH, and `pip install cocotb<2.0 uvm-python` --
#  see notes/2026-09-06-uvm-python-toolchain-resolution.md for why cocotb
#  must be pinned below 2.0 for this uvm-python release)

SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/alu_if_and_dut.sv

TOPLEVEL = alu_dut
MODULE = alu_uvm_tb

include $(shell cocotb-config --makefiles)/Makefile.sim
