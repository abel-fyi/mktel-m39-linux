#!/usr/bin/env python3
"""Recover M39 GPIO LED callbacks from the verified LK; build a marked base DTB."""
from pathlib import Path
import hashlib, shutil, subprocess
root=Path(__file__).resolve().parent.parent
lk=root/'backups/initial/lk.bin'
assert hashlib.sha256(lk.read_bytes()).hexdigest()=='41780ba85a06f8e428d23309d2ade5e3b1063fcdd47914d2d83439a502081290'
p=root/'tools/mt6735-kernel/drivers/misc/mediatek/leds/mt6735/leds.c'
s=p.read_text()
marker='/* M39: LK-verified GPIO on/off, never call a numeric DT value. */'
if marker not in s:
    s=s.replace('#include <mt-plat/mt_pwm.h>', '#include <mt-plat/mt_pwm.h>\n#include <mt-plat/mt_gpio.h>',1)
    helper='''/* M39: LK-verified GPIO on/off, never call a numeric DT value. */
static int m39_led_gpio_output(unsigned long pin, int level)
{
    int ret, expected = level ? GPIO_OUT_ONE : GPIO_OUT_ZERO;
    pin |= 0x80000000UL;
    /* Preserve mux/direction: refuse if another driver has claimed the pin. */
    if (mt_get_gpio_mode(pin) != GPIO_MODE_00 ||
        mt_get_gpio_dir(pin) != GPIO_DIR_OUT)
        return -EBUSY;
    ret = mt_set_gpio_out(pin, expected);
    if (ret)
        return ret;
    return mt_get_gpio_out(pin) == expected ? 0 : -EIO;
}
static int m39_lcd_led(int level) { return m39_led_gpio_output(69, level); }
static int m39_keyboard_led(int level) { return m39_led_gpio_output(42, level); }
static int m39_button_led(int level) { return m39_led_gpio_output(5, level); }

'''
    needle='struct cust_mt65xx_led *get_cust_led_dtsi(void)'
    assert s.count(needle)==1
    s=s.replace(needle,helper+needle)
    needle='\t\t\t\tswitch (pled_dtsi[i].mode) {'
    assert s.count(needle)==1
    gpio='''
                case MT65XX_LED_MODE_GPIO: {
                    u32 m39_pin;
                    if (of_property_read_u32(led_node, "m39,verified-lk-gpio", &m39_pin))
                        break;
                    if (i == MT65XX_LED_TYPE_LCD && m39_pin == 69)
                        pled_dtsi[i].data = (long)m39_lcd_led;
                    else if (i == MT65XX_LED_TYPE_KEYBOARD && m39_pin == 42)
                        pled_dtsi[i].data = (long)m39_keyboard_led;
                    else if (i == MT65XX_LED_TYPE_BUTTON && m39_pin == 5)
                        pled_dtsi[i].data = (long)m39_button_led;
                    else
                        pled_dtsi[i].data = -1;
                    break;
                }
'''
    s=s.replace(needle,needle+gpio)
    needle='\t\treturn ((cust_set_brightness) (cust->data)) (level);'
    # Only guard the GPIO case, not legitimate BLS callbacks.
    pos=s.index('case MT65XX_LED_MODE_GPIO:',s.index('int mt_mt65xx_led_set_cust'))
    tail=s[pos:]; assert needle in tail
    tail=tail.replace(needle,'\t\tif ((unsigned long)cust->data < 4096 || cust->data == -1)\n\t\t\treturn -EINVAL;\n'+needle,1)
    s=s[:pos]+tail
    p.write_text(s)
direct='/* M39 GPIO backlight bypasses the donor AAL/display stack. */'
s=p.read_text()
if direct not in s:
    needle='\t/* unsigned long flags; */\n\t/* spin_lock_irqsave(&leds_lock, flags); */'
    assert s.count(needle)==1
    bypass='''
    /* M39 GPIO backlight bypasses the donor AAL/display stack. */
    if (led_data->cust.mode == MT65XX_LED_MODE_GPIO &&
        led_data->cust.data == (long)m39_lcd_led) {
        int result;
        mutex_lock(&leds_mutex);
        result = m39_lcd_led(level);
        if (!result)
            led_data->level = level;
        mutex_unlock(&leds_mutex);
        pr_info("M39 backlight GPIO69 request=%d result=%d\\n", !!level, result);
        return;
    }
'''
    p.write_text(s.replace(needle,needle+bypass))
base=root/'analysis/boot-base-overlay-compatible.dtb'
out=root/'analysis/boot-base-m39-backlight.dtb'
shutil.copyfile(base,out)
for index,pin in [(6,69),(4,42),(5,5)]:
    node=f'/odm/led@{index}'
    result=subprocess.run(['fdtget','-l',str(out),node],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if result.returncode:
        subprocess.run(['fdtput','-c',str(out),node],check=True)
    subprocess.run(['fdtput','-t','i',str(out),node,'m39,verified-lk-gpio',str(pin)],check=True)
merged=root/'analysis/merged-m39-backlight.dtb'
subprocess.run(['fdtoverlay','-i',str(out),'-o',str(merged),str(root/'analysis/original-odmdtbo.img-400.dtb')],check=True)
for index,pin in [(6,69),(4,42),(5,5)]:
    value=subprocess.check_output(['fdtget','-t','i',str(merged),f'/odm/led@{index}','m39,verified-lk-gpio'],text=True)
    assert int(value)==pin
print('Prepared marked GPIO callbacks and verified original-overlay merge; on/off only, no PWM dimming.')
