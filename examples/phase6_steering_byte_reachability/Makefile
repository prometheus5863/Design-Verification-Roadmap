# Phase 6: the strong form of the 2026-11-03 "BORDERLINE PAIR UNDER STEERING"
# item.  NO SIMULATOR, NO TOOLCHAIN, NO DUT -- plain python3 over the live
# bench's own source, because the question is about the steering policy's
# control flow and 256 bytes, and an audit that needs a four-minute cocotb
# elaboration to state that is an audit nobody runs.  Same split as
# phase6_payload_admissibility_bind, whose structural half this extends.
#
#   make            # run the audit
#   make transcript # run it and refresh the committed transcript
#
# Exit status is 1 if any check fails, so it is usable as a gate.

PY ?= python3
AUDIT := steering_byte_reachability_audit.py
TRANSCRIPT := steering_byte_reachability_audit_output.txt

.PHONY: all transcript clean

all:
	$(PY) $(AUDIT)

# The transcript is captured by REDIRECTION, not written by the module, so it
# is comparable by the sibling repository's pristine-transcript route without
# a SELF_WRITING exclusion.  That was a deliberate choice: see the sibling's
# 2026-11-04 entry for what a self-written transcript costs.
transcript:
	$(PY) $(AUDIT) > $(TRANSCRIPT) 2>&1 || true

clean:
	rm -rf __pycache__
