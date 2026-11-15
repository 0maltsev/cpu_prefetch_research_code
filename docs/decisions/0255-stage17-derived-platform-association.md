# D255: derive release-to-stand association from the actual platform admission

- Status: ACCEPTED engineering correction within the approved D254 scope
- Date: 2026-11-15
- Native release: aa3285f15acbd3314cae64a628c113488a8438b8, unchanged

Actual retained qualification exposed an incorrect D254 integration assumption:
EXT006's semantic context describes the portable release and has no stand_id.
EXT004 in the same authenticated journal supplies the verified stand_id. The
original D254 gate incorrectly required that field in both contexts; its small
fixtures had included a field absent from real EXT006 output.

The explicit cold administrative adapter derives only this association from
EXT004 in a private context view, with a separate EXT002 check when the complete
current validation is available. A conflicting existing association rejects the
packet. The original context is neither changed nor described as having emitted
that derived field. Every original source, worker, inventory, boot, platform,
Q15 result, clock, geometry and complete measured-source check remains mandatory.
The original current request's stand/source and owner gates also remain unchanged.

Deploy the adapter only as separately hash-bound administrative source over the
unchanged actual qualified native release. Keep the qualified source tree and
its policy59 closure immutable. The measured binary is not rebuilt or relabelled
for an administrative correction. This changes no observations, method, count,
time window, hardware requirement, signature or experiment authority. No new
experiment or automatic retry is introduced.
