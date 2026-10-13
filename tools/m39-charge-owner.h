/* Supervised diagnostic ownership. A lease never enables charging itself. */
#include <linux/moduleparam.h>
#include <linux/mutex.h>
#include <linux/workqueue.h>
#include <linux/jiffies.h>

static DEFINE_MUTEX(m39_owner_lock);
static bool m39_owner_active;
static unsigned long m39_owner_deadline;
static unsigned int m39_owner_argument;

static bool m39_owner_mutating(CHARGING_CTRL_CMD cmd)
{
    return cmd == CHARGING_CMD_INIT || cmd == CHARGING_CMD_ENABLE ||
           cmd == CHARGING_CMD_SET_CV_VOLTAGE || cmd == CHARGING_CMD_SET_CURRENT ||
           cmd == CHARGING_CMD_SET_INPUT_CURRENT ||
           cmd == CHARGING_CMD_RESET_WATCH_DOG_TIMER ||
           cmd == CHARGING_CMD_SET_HV_THRESHOLD ||
           cmd == CHARGING_CMD_SET_TA_CURRENT_PATTERN;
}
static bool m39_owner_off(void)
{
    pmic_set_register_value(PMIC_RG_CSDAC_EN, 0);
    pmic_set_register_value(PMIC_RG_CHR_EN, 0);
    return !(upmu_get_reg_value(0xf48) & 24);
}
static void m39_owner_expire(struct work_struct *work);
static DECLARE_DELAYED_WORK(m39_owner_work, m39_owner_expire);
static void m39_owner_expire(struct work_struct *work)
{
    mutex_lock(&m39_owner_lock);
    if (m39_owner_active) {
        if (time_after_eq(jiffies, m39_owner_deadline)) {
            bool off = m39_owner_off();
            if (off)
                m39_owner_active = false;
            else
                schedule_delayed_work(&m39_owner_work, HZ);
            pr_info("M39 charge lease expired; charger_off_verified=%d\n", off);
        } else {
            schedule_delayed_work(&m39_owner_work, HZ);
        }
    }
    mutex_unlock(&m39_owner_lock);
}
static int m39_owner_set(const char *value, const struct kernel_param *parameter)
{
    unsigned int seconds;
    int result = kstrtouint(value, 0, &seconds);
    if (result)
        return result;
    if (seconds > 1800)
        return -ERANGE;
    mutex_lock(&m39_owner_lock);
    if (!seconds) {
        if (!m39_owner_off()) {
            result = -EIO;
        } else {
            m39_owner_active = false;
        }
    } else if (m39_owner_active) {
        result = -EBUSY; /* No extending an active session indefinitely. */
    } else if ((upmu_get_reg_value(0x200) >> 8) != 40 ||
               (upmu_get_reg_value(0xf48) & 24) ||
               (upmu_get_reg_value(0xf4e) & 31) != 3 ||
               (upmu_get_reg_value(0xf50) & 15) < 13 ||
               (upmu_get_reg_value(0xf54) & 7) != 5) {
        result = -EINVAL;
    } else {
        m39_owner_deadline = jiffies + seconds * HZ;
        m39_owner_active = true;
        schedule_delayed_work(&m39_owner_work, HZ);
    }
    mutex_unlock(&m39_owner_lock);
    return result;
}
static int m39_owner_get(char *buffer, const struct kernel_param *parameter)
{
    unsigned long remaining = 0;
    mutex_lock(&m39_owner_lock);
    if (m39_owner_active && time_before(jiffies, m39_owner_deadline))
        remaining = DIV_ROUND_UP(m39_owner_deadline - jiffies, HZ);
    mutex_unlock(&m39_owner_lock);
    return sprintf(buffer, "%lu\n", remaining);
}
static const struct kernel_param_ops m39_owner_ops = {
    .set = m39_owner_set,
    .get = m39_owner_get,
};
module_param_cb(m39_owner_seconds, &m39_owner_ops, &m39_owner_argument, 0600);
MODULE_PARM_DESC(m39_owner_seconds,
    "Supervised exclusive PMIC lease, 1..1800 seconds; 0 stops. Never enables charging.");
