# D288 cold parser checks

All three changed native production files pass their full configured clang-tidy
checks with warnings as errors. The final check exposed one existing unchecked
optional lookup when reserving the archive channel FD. Reuse the descriptor
already validated and range-checked earlier in the same cold dispatcher. The
accepted descriptor set, signatures, scientific inputs and limits are unchanged.
The exact reviewed source hash and policy63 bindings follow that source change.

Fresh native verification passes all139 runner tests normally and the same139
under ASan/UBSan with the documented `detect_leaks=0` restriction. C++ formatting
also passes. Family/source static successes are retained in the first log; its
old fixed-action diagnostic is superseded by the separate corrected PASS command.
The earlier whole-repository static run is historical/mixed-source work and is
not credited as current verification.

Prepare the final clean successor and both compilers' exact codegen evidence
before qualifying it. The486f7b7 preview remains blocked on the stand. Neither
qualification nor raw validation/collection has started, and D288's one new24h
window remains unstarted. All completed measurements and failed raw evidence stay
preserved under their original identities. This checkpoint grants no execution
or Stage18 authority.
