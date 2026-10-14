# Networking bring-up

Bring-up,2026-10-14. Native WMT initialization and recovered firmware loading
now create `wlan0`. Association, DHCP and connectivity are not yet verified.
The bounded charging validation continues separately.

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
  Reviewed firmware is now staged in `/etc/firmware`; Android executables were
  not installed. `/system/etc/firmware` links to that directory for WMT.
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
3. Install signed Alpine networking packages and test Wi-Fi. Radio bring-up is
   explicitly authorized by the current Wi-Fi goal; battery guards remain active.
4. Establish SSH using public-key authentication; keep private keys off firmware
   and out of commits. USB networking is an alternative to investigate separately.

Build the query with the existing AOSP ARM64 compiler using `-Os -ffreestanding
-fno-builtin -fno-stack-protector -nostdlib -static -Wl,-e,_start`. It was compiled
with warnings treated as errors and its two queries verified on the phone.

## Native tools

OpenMTTools upstream revision `ef35f769d211a2942a6783410b58bd824dd363f9`
([source](https://gitlab.com/Dahrkael/openmttools)) already maps `0x0335` to
the `0x6735` initialization family. Its MIT license remains applicable.
`tools/openmttools-m39.patch` supplies full patch paths required by this vendor
kernel and rejects failed patch metadata reads/ioctls. `tools/build-openmttools.sh`
builds static ARM64 musl executables using the local pinned APK inputs.

Verified sequence: `mtinit -safe`, then `mtdaemon -m 3 -p /etc/firmware`,
then `echo 1 > /dev/wmtWifi`. Kernel logs confirm both ROM patches downloaded,
hardware/firmware version `0x8a00`, and successful WLAN probe. Do not replay
initialization while an existing daemon or incomplete operation is running.
Firmware remains local and excluded from Git; redistribution rights are unknown.

Signed Alpine `iw`, `wpa_supplicant`, dependencies and `tcpdump` are installed.
Both nl80211 and wext associate, receive handshake message1 and send message2,
but authentication has not completed. DHCP has not obtained a lease. A bounded
EAPOL capture confirms packets in both directions; it does not prove successful
over-the-air delivery of outgoing frames. The user reported hotspot auto-off;
with it staying enabled, authentication still fails. Test WPA2-only next.

The backup nvdata filesystem retained `/APCFG/APRDEB/WIFI` (514 bytes) and
`WIFI_CUSTOM` (6 bytes). These were restored privately to the driver's
`/data/nvram/APCFG/APRDEB/` paths, inside encrypted root. The missing-file
warning `0x01` changed to `0x10` (invalid/default MAC per this kernel).
This is recovered configuration, not verified factory calibration; neither files
nor packet captures belong in Git. Credentials are root-only and excluded from
firmware. No automatic Wi-Fi boot hook is enabled until connection is verified.

The build script expects an existing pinned upstream checkout with the included
patch applied, the existing AOSP GCC4.9 toolchain, and a musl sysroot extracted
from the two APKs in `tools/openmttools-build-inputs.json`. It verifies input
hashes and the checkout patch before building; it does not download dependencies.
