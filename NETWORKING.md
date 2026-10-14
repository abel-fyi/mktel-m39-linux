# Networking bring-up

Read-only survey,2026-10-14. Wi-Fi is **not working yet**; no radio was powered
on during this investigation. The bounded charging validation continues separately.

## Findings

- Kernel has `CONFIG_MTK_COMBO_WIFI=y`, CONSYS_6735 and cfg80211; the linked image
  contains the Gen2 Wi-Fi and WMT initialization functions.
- Phone exposes `/dev/wmtdetect`, but no Wi-Fi interface, wiphy or WMT transport
  device. `iw`/`wpa_supplicant` and firmware are absent from Alpine.
- The reviewed read-only ioctl returns SoC identity `0x0335`; the combo identity
  is unavailable before initialization. Evidence: local
  `logs/network-wmt-chip-query.txt`, `logs/network-readonly-survey.txt`.
- The preserved vendor backup contains `WIFI_RAM_CODE_6735`, two ROM connectivity
  patches, `WMT_SOC.cfg`, `wmt_loader` and `wmt_launcher`. These six files were
  recovered and hashed locally in `artifacts/network-recovered/manifest.json`.
  No recovered firmware or executable was installed on the phone.
- These files come from the pre-recovery ROM, which is not verified factory
  firmware. Do not assume board calibration, compatibility or redistribution rights.

## Initialization evidence

Kernel `common_detect` exposes separate query, SET, init and power ioctls.
`tools/m39-wmt-query.c` opens the device read-only and issues only identity
queries0 and3; it has no initialization or power operation.

The recovered loader is Android ARM64 and requires `/system/bin/linker64`; it
cannot run directly as an Alpine program. Disassembly shows the0x0335 jump-table
entry reaches the0x6735 family route, followed by module initialization using
that family value. Kernel common initialization accepts0x6735, while its hardware
support also recognizes0x0335. Preserve this distinction when implementing a
native launcher. Local evidence: `logs/wmt-loader-disassembly.txt`, addresses
0xfe8–0x1028 and0x1078; table at0x13e8, slot0x0335−0x0321 targets0x1014.

The Gen2 firmware loader searches `/etc/firmware/`; WMT configuration also has
an Android-style path. Review filename/version and path handling before staging
the recovered blobs. Radio initialization needs the WMT transport/patch-loading
sequence; an enabled kernel config alone does not create a working interface.

## Next steps

1. Review and implement the minimum native WMT loader/launcher sequence, with
   explicit initialization separate from read-only querying.
2. Stage only reviewed firmware/configuration, preserving backup provenance and
   private calibration data. Keep proprietary binaries out of Git.
3. After the charging baseline holds, initialize transport, verify interface and
   firmware loading, then install signed Alpine networking packages and test Wi-Fi.
4. Establish SSH using public-key authentication; keep private keys off firmware
   and out of commits. USB networking is an alternative to investigate separately.

Build the query with the existing AOSP ARM64 compiler using `-Os -ffreestanding
-fno-builtin -fno-stack-protector -nostdlib -static -Wl,-e,_start`. It was compiled
with warnings treated as errors and its two queries verified on the phone.
