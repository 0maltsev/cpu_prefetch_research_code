# D334 incomplete-restoration quarantine correction

Review of the new guard found that normal cleanup could restore the sysctl and
clear its lease even when independent platform restoration failed. The added
regression reproduces this on1d02c9b: an injected actual hardware-restoration
failure still returned compaction_restoration_verified=true. This was a software
failure only; the guard has never been applied to the stand for S180.

Before normal platform proof publication or guard clearance, require all three
independent restoration flags and no restoration errors. The failing path now
preserves control zero, the occupied lease and the original hardware error;
supervised recovery remains responsible for resolving the incomplete platform.
The original D333/D334 quarantine rule and scientific settings are unchanged.

The regression fails for the intended reason before the fix. All22 guard cases
pass Python development/debug allocation afterward. Fresh guard/environment/
launcher/parent integration passes73 cases in4 suites,46.01 seconds. Explicit
platform doubles and temporary files are used; this is software verification.
The initial direct regression invocation lacked namespace-root ownership and
failed its prerequisite; it is retained separately from the actual reproduction
inside the isolated user/PID namespace. The affected CTest transcript preserves
its content with only trailing blank lines normalized, as documented by the
evidence preparation. Existing D334 exact transcript and150-case checkpoint
remain unchanged. AST and git whitespace checks pass; no C++ changed.

SSH succeeds with direct settings. A read-only survey found the original boot
and no S180 cgroup. Five small historical qualification files were copied with
size/hash checks for inspection; bindings are retained here. They bind an older
release and Q16c window and were not executed or reused for qualification. This
selected observation is not complete restoration, qualification or admission.
No hardware write, source preparation, measurement or run window started.

Verified duplicate D334 PC staging metadata (3435791 bytes) was removed only
after comparison with its retained evidence inventory. The redundant base64
download wrapper was also removed after verification of the decoded software
files; stand raw data was untouched. The remaining qualified outer operator,
EXT008 producer and scientific validator are still required before actual
admission, full ETA and the single conditional pilot. Stage17 is incomplete.
