# Alpine Linux on the MKTEL M39

Experimental native Linux bring-up for the MKTEL M39 keypad phone
(MT6737M, MT6328 PMIC, 2 GB RAM, 16 GB eMMC).

See [the agreed roadmap and handoff](ROADMAP.md) for current priorities,
completion criteria and remaining hardware validation.

## License

Project code and original documentation are licensed under
[GPL-2.0-only](LICENSE). Existing third-party copyright and license notices
remain applicable; linked external firmware and sources are not relicensed.

## Status

- Alpine 3.23.6 ARM64 boots with a source-built Linux 3.18.19 kernel.
- Physical terminal, fastfetch, keypad input and root USB console work.
- Software reboot and binary backlight control work.
- Alpine boots from a LUKS2 encrypted internal root (14 GB ext4).
- The LUKS2 encrypted microSD mounts as `/home` (58.4 GB ext4).
- Keypad passphrase unlock, root transition and reboot persistence work.
- Wi-Fi connects to a WPA2 hotspot with DHCP, Internet ping and DNS verified.
  Automatic startup after unlocking is installed; reboot validation remains.
- Touchscreen, audio, modem and accelerated graphics remain unfinished.

## Battery: work in progress

Charging reliability is unresolved: the latest completed charging trial on
kernel #22 stopped on a fuel-gauge release timeout and verified charging OFF.
Passing a charging-off probe did not establish sustained charging reliability.

Verified bounded charging: nominal 300 mA, 3.9 V ceiling, hardware watchdog,
30-minute maximum session and charger shutdown. After explicit arming,
unplug/reconnect starts another bounded session.

**Battery temperature sensing is deferred and unimplemented.** The BL-25BI
middle contact and its calibration remain unidentified. Battery percentage,
full-charge termination and normal recharge policy are also unfinished.
An optional experimental image starts bounded charging automatically at boot. This is supervised experimental charging, not a complete
unattended charging implementation.

On the phone: `m39-charge status`, `m39-charge arm`, `m39-charge stop`.
Screen idle control: `m39-screen on 60`, `m39-screen off`.

See [battery usage and limits](BATTERY.md), [battery research](analysis/BL25BI-RESEARCH.md) and
[charging notes](analysis/CHARGING.md). Historical notes may describe older
images. Current image hashes and device evidence are kept in local artifact
metadata and `CURRENT-STATE.md`; recovery images remain preserved.

## USB console

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-cli.txt
.venv/bin/python tools/usb-serial-console.py --interactive
```

Install libusb through your distribution. Scoped USB permission rules are in
`70-mktel-local.rules`. Exit the console with **Ctrl+]**.

## Repository scope

This repository contains bring-up tools and selected research notes. Device
backups, keys, raw logs, firmware binaries, toolchains and external source
checkouts stay local. The saved device backup contains the previously bricked
state, not a verified factory ROM. Builds still require separately acquired
kernel/toolchain/rootfs inputs; this is not yet a self-contained installer.

## Next milestones

Follow the ordered milestones in [ROADMAP.md](ROADMAP.md): dependable development
baseline, limited usable battery support, useful Linux features, then complete
battery support.
