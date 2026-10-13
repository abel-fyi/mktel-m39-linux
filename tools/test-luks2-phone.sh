#!/bin/sh
# Disposable RAM loopback test; never formats a physical disk.
set -eu
image=/tmp/m39-luks2-selftest.img
key=/run/m39-selftest.key
newkey=/run/m39-selftest.newkey
wrong=/run/m39-selftest.wrongkey
mapping=m39_luks2_selftest
mountpoint=/tmp/m39-luks2-selftest-mount
loop=
cleanup() {
    result=$?
    trap - EXIT
    umount "$mountpoint" 2>/dev/null || :
    cryptsetup close "$mapping" 2>/dev/null || :
    [ -z "$loop" ] || losetup -d "$loop" 2>/dev/null || :
    rm -f "$key" "$newkey" "$wrong" "$image"
    if [ "$result" = 0 ]; then echo passed > /run/luks2-selftest.status
    else echo failed > /run/luks2-selftest.status; fi
    exit "$result"
}
trap cleanup EXIT
echo running > /run/luks2-selftest.status
umask 077
printf m39-disposable-test-passphrase > "$key"
printf m39-disposable-replacement-passphrase > "$newkey"
printf m39-incorrect-passphrase > "$wrong"
truncate -s 96M "$image"
loop=$(losetup -f)
losetup "$loop" "$image"
case "$loop" in /dev/loop[0-9]*) ;; *) exit 1;; esac
echo "Formatting disposable loop device: $loop"
cryptsetup luksFormat --batch-mode --type luks2 --cipher aes-xts-plain64 \
    --key-size 512 --sector-size 512 --pbkdf argon2id \
    --pbkdf-memory 65536 --pbkdf-parallel 2 --iter-time 1000 \
    --use-urandom --key-file "$key" "$loop"
cryptsetup luksDump "$loop"
cryptsetup open --disable-keyring --key-file "$key" "$loop" "$mapping"
mkfs.ext4 -q -O ^orphan_file,^metadata_csum_seed,^fast_commit "/dev/mapper/$mapping"
mkdir -p "$mountpoint"
mount "/dev/mapper/$mapping" "$mountpoint"
echo M39_LUKS2_ENCRYPTED_FILESYSTEM_OK > "$mountpoint/marker"
sync
umount "$mountpoint"
cryptsetup close "$mapping"
if cryptsetup open --disable-keyring --key-file "$wrong" "$loop" "$mapping"; then
    echo 'Incorrect passphrase unexpectedly unlocked the test volume' >&2; exit 1
fi
cryptsetup luksChangeKey --pbkdf argon2id --pbkdf-memory 65536 \
    --pbkdf-parallel 2 --iter-time 1000 --key-file "$key" "$loop" "$newkey"
if cryptsetup open --disable-keyring --key-file "$key" "$loop" "$mapping"; then
    echo 'Replaced passphrase unexpectedly remained valid' >&2; exit 1
fi
cryptsetup open --disable-keyring --key-file "$newkey" "$loop" "$mapping"
mount "/dev/mapper/$mapping" "$mountpoint"
grep -qx M39_LUKS2_ENCRYPTED_FILESYSTEM_OK "$mountpoint/marker"
echo M39_LUKS2_FORMAT_UNLOCK_MOUNT_AND_PASSPHRASE_CHANGE_VERIFIED
