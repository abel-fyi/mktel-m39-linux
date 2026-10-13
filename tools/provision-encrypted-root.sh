#!/bin/sh
# One-time provisioning of the already-created expanded LUKS2 root volume.
set -eu
umask 077
expected_cid=${M39_EXPECTED_CID:?Expected device CID required}
expected_boot=${M39_EXPECTED_BOOT:?Expected boot UUID required}
root_uuid=6d927e89-060f-4d58-91f2-03e6aac501c9
home_uuid=eba1f308-4a4c-4e6a-a821-74d57a9a8aa3
device=/dev/mmcblk0p26
key=/run/m39-setup.key
homekey=/run/m39-home.key
root=/mnt/alpine-internal
phase=checking
written=0
total=0
owns_mapping=0
mounted=0
status() {
    phase=$1
    printf '{"phase":"%s","pid":%s,"boot_id":"%s","written_bytes":%s,"total_bytes":%s}\n' \
        "$phase" "$$" "$expected_boot" "$written" "$total" > /run/m39-root-provision.json.tmp
    mv /run/m39-root-provision.json.tmp /run/m39-root-provision.json
}
cleanup() {
    result=$?
    trap - EXIT
    if [ "$mounted" = 1 ]; then umount "$root" || result=1; fi
    if [ "$owns_mapping" = 1 ]; then cryptsetup close m39_root || result=1; fi
    rm -f "$key" "$homekey"
    if [ "$result" != 0 ]; then status failed; fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
status checking
for utility in cryptsetup dd mkfs.ext4 dumpe2fs sha256sum blockdev; do command -v "$utility" >/dev/null; done
[ "$(cat /proc/sys/kernel/random/boot_id)" = "$expected_boot" ]
[ "$(cat /sys/class/block/mmcblk0/device/cid)" = "$expected_cid" ]
[ "$(cat /sys/class/block/mmcblk0p26/start)" = 393216 ]
[ "$(cat /sys/class/block/mmcblk0p26/size)" = 30108672 ]
[ "$(cryptsetup luksUUID "$device")" = "$root_uuid" ]
[ "$(cryptsetup luksUUID /dev/mmcblk1p1)" = "$home_uuid" ]
[ "$(wc -c < "$key")" = 20 ]
[ "$(wc -c < "$homekey")" = 64 ]
! cryptsetup status m39_root >/dev/null 2>&1
! grep -q '^/dev/mapper/' /proc/mounts
! grep -q '^/dev/mmcblk' /proc/mounts
cryptsetup open --test-passphrase --key-file "$homekey" /dev/mmcblk1p1
cryptsetup open --readonly --disable-keyring --key-file "$key" "$device" m39_root
owns_mapping=1
if dumpe2fs -h /dev/mapper/m39_root >/dev/null 2>&1; then
    echo 'Existing ext4 root found; refusing to overwrite it.' >&2
    exit 1
fi
cryptsetup close m39_root
owns_mapping=0
header_before=$(dd if="$device" bs=1048576 count=16 2>/dev/null | sha256sum | cut -d ' ' -f 1)
# Preserve the full 16MiB LUKS metadata/keyslot prefix. Clear only the data area.
total=$(( (30108672 - 32768) * 512 ))
whole=$((total / 1048576))
remainder=$((total % 1048576 / 512))
position=0
status clearing_old_android
while [ "$position" -lt "$whole" ]; do
    count=128
    [ "$((position + count))" -le "$whole" ] || count=$((whole - position))
    dd if=/dev/zero of="$device" bs=1048576 seek=$((16 + position)) count="$count" conv=notrunc,fsync
    position=$((position + count))
    written=$((position * 1048576))
    status clearing_old_android
done
if [ "$remainder" != 0 ]; then
    dd if=/dev/zero of="$device" bs=512 seek=$((32768 + whole * 2048)) count="$remainder" conv=notrunc,fsync
fi
written=$total
header_after=$(dd if="$device" bs=1048576 count=16 2>/dev/null | sha256sum | cut -d ' ' -f 1)
[ "$header_before" = "$header_after" ]
status creating_filesystem
cryptsetup open --disable-keyring --key-file "$key" "$device" m39_root
owns_mapping=1
mkfs.ext4 -q -L alpine-root -m 1 -O ^orphan_file,^metadata_csum_seed,^fast_commit /dev/mapper/m39_root
mkdir -p "$root"
mount -o noatime /dev/mapper/m39_root "$root"
mounted=1
status copying_alpine
for directory in bin etc lib sbin usr root var; do cp -a "/$directory" "$root/"; done
for directory in proc sys dev run tmp mnt opt home media srv; do mkdir -p "$root/$directory"; chmod 755 "$root/$directory"; done
chmod 1777 "$root/tmp"
mkdir -p "$root/etc/keys"
chmod 700 "$root/etc/keys"
cp "$homekey" "$root/etc/keys/microsd-home.key"
chmod 600 "$root/etc/keys/microsd-home.key"
cp /run/encrypted-root-init.sh "$root/sbin/m39-init"
chmod 755 "$root/sbin/m39-init"
printf '%s\n' "$root_uuid" > "$root/etc/m39-rootfs-id"
printf '%s\n' "$home_uuid" > "$root/etc/m39-home-uuid"
printf '/dev/mapper/m39_root / ext4 defaults,noatime 0 1\n/dev/mapper/m39_home /home ext4 defaults,noatime 0 2\n' > "$root/etc/fstab"
echo M39_INTERNAL_ENCRYPTED_ROOT_PERSISTENCE_TEST > "$root/root/persistence-test"
sync
df -h "$root"
umount "$root"
mounted=0
cryptsetup close m39_root
owns_mapping=0
status complete
echo M39_PERSISTENT_ENCRYPTED_ROOT_PROVISIONED
