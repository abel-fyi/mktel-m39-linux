/* SPDX-License-Identifier: GPL-2.0-only */
/* Included by battery_meter_hal.c. Vendor commands remain serialized;
 * latch users also share the raw snapshot's mutex. No charger control writes. */
#include <linux/mutex.h>
#include <linux/moduleparam.h>
#include <linux/ktime.h>
#include "m39-fg-core.h"

static DEFINE_MUTEX(m39_fg_lock);
static DEFINE_MUTEX(m39_meter_command_lock);
static int m39_fg_vendor_cmd = -1;
static u64 m39_fg_vendor_started;

static int m39_fg_needs_lock(unsigned command)
{
    /* Reviewed ADC callbacks only use AUXADC, not FGADC_CON0. Everything else
     * remains protected, including unknown commands (fail closed). */
    switch (command) {
    case BATTERY_METER_CMD_GET_ADC_V_BAT_SENSE:
    case BATTERY_METER_CMD_GET_ADC_V_I_SENSE:
    case BATTERY_METER_CMD_GET_ADC_V_BAT_TEMP:
    case BATTERY_METER_CMD_GET_ADC_V_CHARGER:
        return 0;
    default:
        return 1;
    }
}

static void m39_fg_lock_timeout(void)
{
    int command = READ_ONCE(m39_fg_vendor_cmd);
    u64 started = READ_ONCE(m39_fg_vendor_started);
    u64 now = ktime_to_ns(ktime_get());
    /* Diagnostic observation only: the holder may finish during this read. */
    pr_err("M39_FG_LOCK_TIMEOUT vendor_cmd=%d held_us=%llu\n", command,
           command >= 0 && now >= started ?
           (unsigned long long)((now - started) / 1000) : 0ULL);
}

static int m39_fg_read(unsigned address, unsigned *value)
{
    if (address != 0x200 && address != 0xca4 && address != 0xcb2)
        return -EINVAL;
    return pmic_read_interface(address, value, 0xffff, 0);
}

static int m39_fg_write(unsigned value)
{
    /* Only command bits; preserve configuration even if another subsystem
     * changes low bits. Access is serialized with vendor gauge transactions. */
    return pmic_config_interface(0xca4, value & 0xff00, 0xff00, 0);
}

static u64 m39_fg_now(void) { return ktime_to_ns(ktime_get()); }
static void m39_fg_pause(void) { usleep_range(100, 200); }

static int m39_fg_raw_get(char *buffer, const struct kernel_param *parameter)
{
    static const struct m39_fg_io io = {
        m39_fg_read, m39_fg_write, m39_fg_now, m39_fg_pause
    };
    struct m39_fg_result result = {0};
    int rc;
    u64 finish = m39_fg_now() + 30000000ULL;
    (void)parameter;
    /* Transient vendor ownership is expected. Wait only inside the original
     * 30 ms acquisition budget; never return stale current or touch a busy
     * latch. Cleanup failures are still fatal and are never retried here. */
    while (!mutex_trylock(&m39_fg_lock)) {
        if (m39_fg_now() >= finish) {
            m39_fg_lock_timeout();
            return -EBUSY;
        }
        m39_fg_pause();
    }
    if (m39_fg_now() >= finish) {
        mutex_unlock(&m39_fg_lock);
        return -EBUSY;
    }
    rc = m39_fg_snapshot(&io, &result, finish);
    mutex_unlock(&m39_fg_lock);
    if (rc) {
        pr_err("M39_FG_ERROR stage=%u release_stage=%u control=%u\n",
               result.stage, result.release_stage, result.release_control);
        return -EIO;
    }
    return scnprintf(buffer, PAGE_SIZE, "%u %d\n", result.raw,
                     result.raw > 32767 ? (int)result.raw - 65535 : (int)result.raw);
}

static const struct kernel_param_ops m39_fg_raw_ops = { .get = m39_fg_raw_get };
module_param_cb(m39_fg_raw, &m39_fg_raw_ops, NULL, 0400);
