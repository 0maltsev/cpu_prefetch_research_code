# Repository tools

Stage 3 tools verify the build foundation, protocol snapshot, documentation,
dependency inventory, and release flags. `cpu_prefetch_smoke` reports build
identity only. `generate_schedule.py` is the accepted standalone Stage 7
preparation tool; it generates a complete immutable schedule and envelopes
before measurement and cannot observe a queue, clock, or outcome. No tool in
this directory is a benchmark or produces scientific results.
