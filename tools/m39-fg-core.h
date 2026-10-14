#ifndef M39_FG_CORE_H
#define M39_FG_CORE_H
// SPDX-License-Identifier: GPL-2.0
/* Bounded MT6328 current snapshot. No charger controls, counter resets or
 * calibration writes. Kernel users share the gauge: no exclusive lock is
 * claimed. Reject a lost latch, release it, and retry within 30 ms. */
#ifndef __KERNEL__
typedef unsigned long long u64;
#endif
struct m39_fg_io {
    int (*read)(unsigned, unsigned *);
    int (*write_control)(unsigned);
    u64 (*now)(void);
    void (*pause)(void);
};
struct m39_fg_result { unsigned raw, attempts, stage, release_stage, release_control; };

static int m39_fg_release(const struct m39_fg_io *p, u64 deadline, struct m39_fg_result *out) {
    unsigned control;
    out->release_stage=1;
    if (p->read(0xca4, &control)) return -1;
    out->release_control=control;
    out->release_stage=2;
    if (p->write_control((control & 255) | 0x800)) return -1;
    do {
        out->release_stage=3;
        if (p->read(0xca4, &control)) return -1;
        out->release_control=control;
        if (!(control & 0x400)) {
            out->release_stage=4;
            if (p->write_control(control & 255)) return -1;
            out->release_stage=0;
            return 0;
        }
        p->pause();
    } while (p->now() < deadline);
    out->release_stage=5;
    return -1;
}

/* Every acquired request is released before success or retry. A failed
 * release is fatal, never treated as a valid or merely stale measurement. */
static int m39_fg_snapshot(const struct m39_fg_io *p, struct m39_fg_result *out, u64 finish) {
    unsigned identity, control, raw, attempt;
    out->stage=1;
    if (p->read(0x200, &identity)) return -1;
    out->stage=2;
    if ((identity >> 8) != 0x28) return -1;
    for (attempt = 1; attempt <= 3; attempt++) {
        int complete = 0, io_failed = 0;
        u64 ready_deadline;
        out->attempts=attempt;
        do {
            out->stage=3;
            if (p->read(0xca4, &control)) return -1;
            if (!(control & 0xff00)) break;
            out->stage=4;
            if (p->now() >= finish) return -1;
            p->pause();
        } while (1);
        out->stage=9;
        if (p->now() >= finish) return -1;
        if (p->write_control((control & 255) | 0x200)) {
            out->stage=m39_fg_release(p, p->now() + 5000000ULL, out)?10:5;
            return -1;
        }
        ready_deadline = p->now() + 5000000ULL;
        do {
            out->stage=6;
            if (p->read(0xca4, &control)) { io_failed = 1; break; }
            if (control & 0x400) {
                out->stage=7;
                if (p->read(0xcb2, &raw) || p->read(0xca4, &control)) {
                    io_failed = 1;
                } else {
                    complete = !!(control & 0x400);
                }
                break;
            }
            p->pause();
        } while (p->now() < ready_deadline && p->now() < finish);
        if (m39_fg_release(p, p->now() + 5000000ULL, out)) { out->stage=10; return -1; }
        if (io_failed) return -1;
        if (complete && p->now() < finish) {
            out->raw = raw;
            out->attempts = attempt;
            out->stage=0;
            return 0;
        }
        out->stage=complete?9:8;
    }
    return -1;
}


#endif
