#!/usr/bin/env python3
"""Add diagnostic initcall markers in the verified reserved M39 scanout RAM."""
from pathlib import Path
root = Path(__file__).resolve().parent.parent
path = root / 'tools/mt6735-kernel/init/main.c'
text = path.read_text()
marker = '/* M39 source bring-up: reserved scanout breadcrumbs, no storage writes. */'
def upgrade_early(text):
    if 'static void __init m39_trace_setup(void)' in text:
        return text
    start = text.index('\n    /* Live M39 atag,videolfb')
    end = text.index('\n\tfor (level = 0;', start)
    body = text[start:end].replace(
        'writel(1, m39_trace_scanout + 0x110028);',
        'writel(0xffffffff, m39_trace_scanout + 0x110010);\n        writel(1, m39_trace_scanout + 0x110028);')
    text = text[:start] + '\n    m39_trace_setup();\n' + text[end:]
    setup = ('static void __init m39_trace_setup(void)\n{\n'
             '    if (m39_trace_scanout)\n        return;\n' + body + '\n}\n\n')
    needle = 'static void m39_trace_call(initcall_t fn, unsigned int state, int result)'
    assert text.count(needle) == 1
    text = text.replace(needle, setup + needle)
    needle = '\tsmp_prepare_cpus(setup_max_cpus);'
    assert text.count(needle) == 1
    return text.replace(needle, '\tm39_trace_setup();\n' + needle)

if marker in text:
    path.write_text(upgrade_early(text))
    print('Boot trace already prepared')
    raise SystemExit(0)
helper = '''/* M39 source bring-up: reserved scanout breadcrumbs, no storage writes. */
static void __iomem *m39_trace_scanout;
static unsigned int m39_trace_sequence;
static void m39_trace_call(initcall_t fn, unsigned int state, int result)
{
    void __iomem *record;
    if (!m39_trace_scanout)
        return;
    record = m39_trace_scanout + 0x110000;
    writel(++m39_trace_sequence, record + 8);
    writeq((unsigned long)fn, record + 24);
    writel(result, record + 32);
    wmb();
    writel(state, record + 12);
    wmb();
}

'''
needle = 'int __init_or_module do_one_initcall(initcall_t fn)\n'
assert text.count(needle) == 1
text = text.replace(needle, helper + needle)
text = text.replace('\tts = sched_clock();\n#if defined(CONFIG_MT_ENG_BUILD)', '\tm39_trace_call(fn, 1, 0);\n\tts = sched_clock();\n#if defined(CONFIG_MT_ENG_BUILD)', 1)
text = text.replace('\tts = sched_clock() - ts;\n\tmsgbuf[0] = 0;', '\tm39_trace_call(fn, 2, ret);\n\tts = sched_clock() - ts;\n\tmsgbuf[0] = 0;', 1)
needle = '\tstrcpy(initcall_command_line, saved_command_line);'
assert text.count(needle) == 1
text = text.replace(needle, '''	if (m39_trace_scanout) {
        unsigned int x, y;
        writel(level, m39_trace_scanout + 0x110010);
        for (y = level * 8; y < level * 8 + 8; y++)
            for (x = 0; x < 32; x++)
                writel(0xff00ff00, m39_trace_scanout + y * 1024 + x * 4);
        wmb();
    }
''' + needle)
needle = 'static void __init do_initcalls(void)\n{\n\tint level;\n'
assert text.count(needle) == 1
text = text.replace(needle, needle + '''
    /* Live M39 atag,videolfb reserves [0xbfea0000,0xbffc0000).
     * Record uses its unused tail, outside 320 rows of 1024-byte pixels.
     * Failure to map only disables diagnostics, never prevents boot. */
    m39_trace_scanout = ioremap(0xbfea0000, 0x120000);
    if (m39_trace_scanout) {
        memset_io(m39_trace_scanout + 0x110000, 0, 64);
        writeq(0x54494e4939334dULL, m39_trace_scanout + 0x110000);
        writel(1, m39_trace_scanout + 0x110028);
        wmb();
    }
''')
path.write_text(upgrade_early(text))
print('Prepared initcall markers: record physical 0xbffb0000, green stage blocks')
