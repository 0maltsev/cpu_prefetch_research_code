# Read-only storage evidence `STAND-STORAGE-XEON-CPU-FETCH-20260822-01`

This append-only evidence set was captured as the unprivileged `nobody`
account on candidate stand `185.184.131.153` at
`2026-08-22T11:02:43Z`. It contains `findmnt`, `lsblk`, `df`, and `/proc/mdstat`
observations. Every source file is covered by `SHA256SUMS`; the manifest
SHA-256 is
`9469ad245de27d7211db2a746ae1016dfdebb3a8df07b846fe499ad290617c83`.

The stand exposes one mounted durable data namespace: ext4 `/` on `/dev/md3`,
with 817,134,194,688 bytes reported available at capture time. `/dev/md3` is an
active two-member RAID1 over the two observed SATA SSDs. `/boot` is a separate
small RAID1 filesystem and the other mounts are memory or system filesystems.

This is discovery evidence, not a capacity or durability acceptance record.
The two RAID1 members are not two separately addressed artifact-copy domains:
both copies written through `/dev/md3` would share one filesystem, mount,
operator, and failure/control boundary. The accepted D-020 policy therefore
still lacks its second explicit durable domain, custody/permission proof,
reserve calculation, append-only exercise, crash recovery, and hash readback.
Available bytes are a point-in-time observation and cannot be compared with a
run budget until the pilot plan supplies exact horizons and counts.

No file-capacity stress, durable artifact write, privileged control,
calibration, pilot, or confirmatory operation occurred.
