# Alpine Linux on the MKTEL M39

Experimental native Linux bring-up for the MKTEL M39 keypad phone
(MT6737M, MT6328 PMIC, 2 GB RAM, 16 GB eMMC).

## License

Project code and original documentation are licensed under
[GPL-2.0-only](LICENSE). Existing third-party copyright and license notices
remain applicable; linked external firmware and sources are not relicensed.

## Status

- Alpine 3.23.6 ARM64 boots with a source-built Linux 3.18.19 kernel.
- Physical terminal, fastfetch, keypad input and root USB console work.
- Software reboot and binary backlight control work.
- Root filesystem currently runs in RAM; runtime changes disappear on reboot.
- LUKS2 internal-root/microSD-home provisioning is in progress; encrypted boot
  has not yet been tested end to end. Preparation is paused for low battery.
- Wi-Fi, touchscreen, audio, modem and accelerated graphics remain unfinished.

## Battery: work in progress

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
images; the current verified image is
`alpine-m39-battery-experimental-unplug.partition.img`, SHA-256:
`401be1b2493107a5a5f8f4ed2982b8ae4c0d927150c5f02f086118f6d5e41856`.
The prior manual-only image remains the recovery baseline. The current local
storage-tools image additionally enables AES-XTS and bundles signed crypto/ext4
packages. Charging under storage load and low-voltage recovery remain unresolved.

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

1. Persistent encrypted Alpine storage.
2. Networking/SSH, touchscreen and a lightweight GUI.
3. Modern-kernel port and remaining battery-management features.
