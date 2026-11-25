/* SPDX-License-Identifier: GPL-2.0-or-later
 * sdos-cardwatch: if the system SD card disappears (pulled while on or asleep), power the
 * handheld off through the kernel's normal power-off path instead of leaving it hung with
 * the screen and LED dark. Static, memory-locked, touches only /proc and /sys after start.
 * usage: sdos-cardwatch [--test-disk NAME --once]  */
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/reboot.h>
#include <sys/stat.h>

static char disk[256];

static int boot_disk(void) {
    FILE *f = fopen("/proc/mounts", "r"); char dev[256], mnt[256];
    if (!f) return -1;
    while (fscanf(f, "%255s %255s %*[^\n]", dev, mnt) == 2) {
        if (strcmp(mnt, "/flash") == 0 && strncmp(dev, "/dev/", 5) == 0) {
            char *n = dev + 5, *p;
            snprintf(disk, sizeof disk, "%s", n);
            if (strncmp(disk, "mmcblk", 6) == 0 || strncmp(disk, "nvme", 4) == 0) { if ((p = strrchr(disk, 'p'))) *p = 0; }
            else { p = disk + strlen(disk); while (p > disk && p[-1] >= '0' && p[-1] <= '9') *--p = 0; }
            fclose(f); return 0;
        }
    }
    fclose(f); return -1;
}

static void kmsg(const char *m) {
    int fd = open("/dev/kmsg", O_WRONLY); if (fd >= 0) { (void)!write(fd, m, strlen(m)); close(fd); }
}

int main(int argc, char **argv) {
    int once = 0;
    if (argc >= 3 && strcmp(argv[1], "--test-disk") == 0) { snprintf(disk, sizeof disk, "%s", argv[2]); once = argc > 3; }
    else if (boot_disk() < 0) { fprintf(stderr, "sdos-cardwatch: /flash not mounted from a disk; nothing to watch\n"); return 0; }
    char path[160]; snprintf(path, sizeof path, "/sys/block/%s", disk);
    struct stat st;
    if (stat(path, &st) != 0) { fprintf(stderr, "sdos-cardwatch: %s missing at start\n", path); return 0; }
    if (once) { puts(path); return 0; }
    mlockall(MCL_CURRENT | MCL_FUTURE);
    fprintf(stderr, "sdos-cardwatch: watching %s\n", path);
    int gone = 0;
    for (;;) {
        sleep(1);
        if (stat(path, &st) == 0) { gone = 0; continue; }
        if (++gone < 3) continue;          /* 3 s in a row: really gone */
        kmsg("<2>sdos-cardwatch: system card removed, powering off\n");
        sleep(1);
        reboot(RB_POWER_OFF);              /* no sync: the card is gone */
    }
}
