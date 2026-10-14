# Maintainable Alpine upgrades

Agreed 2026-10-14. Status: planned, not achieved.

## Objective

Run a conventional persistent Alpine installation that can follow supported
stable releases through APK, with reproducible device integration and a tested
recovery path. Preserve encrypted root/home and working hardware support.
An ISO is installation media; normal updates do not require reinstalling it.

We cannot guarantee compatibility with every future release. The current vendor
Linux 3.18.19 kernel is a compatibility and security limitation; updated Alpine
packages do not make that kernel maintained. A supported modern kernel is a
separate requirement for the full long-term objective, not an assumed outcome.

## Work order and acceptance

1. **Remote maintenance and inventory.** Establish public-key SSH, verify Wi-Fi
   after reboot, and inventory APK repositories/packages, PID1/startup, kernel
   configuration, initramfs dependencies and private device calibration. Record
   what runs from persistent root versus the boot image.
2. **Conventional service management.** Migrate to OpenRC with explicit services
   for terminal, screen idle, Wi-Fi and charging. Preserve charger ownership,
   watchdog/fault shutdown and encrypted unlock/handoff. Verify boot, service
   restart, shutdown and recovery; never enable duplicate charger controllers.
3. **Reproducible device integration.** Package original device tools/configs as
   local APKs; pin external build inputs, preserve their licenses and document
   firmware acquisition. Keep credentials/calibration out of Git and firmware.
   Rebuild the necessary boot image from documented inputs rather than ad hoc
   edits. Confirm that userspace package updates survive reboot/root handoff.
4. **Validated stable upgrade.** Confirm the latest official stable release at
   execution time, read its release notes, and test package/kernel compatibility
   in a disposable rootfs before changing the installed system. Preserve a
   recoverable root/boot snapshot, APK inventory and LUKS headers. Perform one
   supported release upgrade, then verify unlock, root/home data, terminal,
   Wi-Fi/SSH, charging guards, reboot and shutdown. Document exact results and
   restore procedure. Unsupported syscalls or initramfs/userspace mismatches are
   blockers to resolve, not reasons to force the upgrade.
5. **Modern-kernel feasibility.** Assess upstream MT6735/MT6737 support and the
   drivers needed for this board. Establish incremental boot/USB/storage tests
   using a separate candidate image while keeping the working image recoverable.
   Report supported functions, missing drivers and maintenance requirements.

The first deliverable is a proven stable userspace upgrade with a repeatable
procedure. Full future maintainability additionally requires a supported kernel
and ongoing validation; this checklist cannot promise perpetual compatibility.

## Update policy

Follow stable release branches intentionally. Do not switch to edge or perform
unattended branch/kernel upgrades to approximate "always latest". Keep boot and
userspace versions compatible, and verify recovery before disruptive updates.

Baseline: Alpine 3.23.6 ARM64, custom vendor kernel #23, shell PID1, encrypted
persistent root/home, verified WPA2 networking. SSH/OpenRC migration and release
upgrade have not been performed. No package upgrade is authorized by a status
claim: record actual implementation and hardware evidence as this work proceeds.

Official references: [release branches](https://alpinelinux.org/releases/) and
[upgrade guide](https://wiki.alpinelinux.org/wiki/Upgrading_Alpine).
