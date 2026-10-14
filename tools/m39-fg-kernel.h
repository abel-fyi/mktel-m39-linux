/* SPDX-License-Identifier: GPL-2.0-only */
/* Included by battery_meter_hal.c. All vendor bm_ctrl_cmd transactions and
 * this diagnostic snapshot share the same mutex. No charger control writes. */
#include <linux/mutex.h>
#include <linux/moduleparam.h>
#include <linux/ktime.h>
#include "m39-fg-core.h"

static DEFINE_MUTEX(m39_fg_lock);

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
    (void)parameter;
    /* Never wait behind an unbounded legacy transaction. Busy is an error,
     * never stale current or permission to continue charging. */
    if (!mutex_trylock(&m39_fg_lock))
        return -EBUSY;
    rc = m39_fg_snapshot(&io, &result);
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
