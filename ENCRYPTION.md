# Encrypted storage (experimental)

Alpine uses a LUKS2 volume on internal eMMC for root and a second LUKS2
volume on microSD for `/home`. Both use AES-XTS with 512-bit keys.
The root filesystem has about 14 GB; the 64 GB card provides about 58.4 GB.
Bootloader, boot image and hardware calibration partitions remain unencrypted.

The keypad unlocks internal root at boot. Centre OK submits; top-right deletes
a digit. The current input interface accepts numeric passphrases. The microSD
key is stored with mode 0600 inside encrypted root, so `/home` unlocks after root.
Keep private LUKS header backups and credentials separately from this repository.
They are not embedded in the boot image or included in Git.

The current init is an experimental shell bootstrap, not a finished OpenRC
installation. Wi-Fi/SSH and a complete shutdown service are future work.
Encryption does not authenticate the boot chain or protect an already-unlocked
phone. The USB diagnostic console currently grants root access.

Provisioning is destructive and device-specific. It refuses an existing ext4
root and preserves the 16 MiB LUKS header prefix. Do not rerun it to repair a
boot problem. Builds depend on separately acquired kernel, toolchain and Alpine
inputs; the repository is not a general installer.
