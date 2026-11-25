/* SPDX-License-Identifier: GPL-2.0-or-later
 * sdOS boot splash: paints the boot screen (SD mark, "sdOS", "STATIC DIVISIONS")
 * on /dev/fb0 from the initramfs, at the same spot the frontend's boot screen draws it,
 * so power-on -> UI looks like one continuous screen. Replaces rocknix-splash.
 * Copyright (C) 2026 Static Divisions.
 */
#include <fcntl.h>
#include <linux/fb.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include "logo.h"

static int find_rotation(const char *dir, int depth) {
    if (depth > 6) return -1;
    DIR *d = opendir(dir);
    if (!d) return -1;
    struct dirent *e; int r = -1; char p[512];
    while (r < 0 && (e = readdir(d))) {
        if (e->d_name[0] == '.') continue;
        snprintf(p, sizeof p, "%s/%s", dir, e->d_name);
        if (strcmp(e->d_name, "rotation") == 0) {
            unsigned char b[4]; int fd = open(p, O_RDONLY);
            if (fd >= 0) {
                if (read(fd, b, 4) == 4) {
                    int v = (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3];
                    if (v == 90 || v == 180 || v == 270) r = v;
                }
                close(fd);
            }
        } else if (e->d_type == DT_DIR) {
            r = find_rotation(p, depth + 1);
        }
    }
    closedir(d);
    return r;
}

static uint32_t pack(const struct fb_var_screeninfo *v, int r, int g, int b) {
    return ((uint32_t)(r >> (8 - v->red.length)) << v->red.offset) |
           ((uint32_t)(g >> (8 - v->green.length)) << v->green.offset) |
           ((uint32_t)(b >> (8 - v->blue.length)) << v->blue.offset) |
           (v->transp.length ? (((1u << v->transp.length) - 1) << v->transp.offset) : 0);
}

static void draw(uint8_t *base, const struct fb_var_screeninfo *vp, const struct fb_fix_screeninfo *fp, int rot) {
    struct fb_var_screeninfo v = *vp; struct fb_fix_screeninfo f = *fp;
    int bpp = v.bits_per_pixel, W = v.xres, H = v.yres;
    int LW = (rot == 90 || rot == 270) ? H : W;     /* logical (upright) size */
    int LH = (rot == 90 || rot == 270) ? W : H;

    uint32_t bgc = pack(&v, BG_R, BG_G, BG_B);
    for (int y = 0; y < H; y++) {
        uint8_t *row = base + (size_t)y * f.line_length;
        for (int x = 0; x < W; x++) {
            if (bpp == 32) ((uint32_t *)row)[x] = bgc; else ((uint16_t *)row)[x] = (uint16_t)bgc;
        }
    }
    int ox = LOGO_X + (LW - REF_W) / 2, oy = LOGO_Y + (LH - REF_H) / 2;
    for (int ly = 0; ly < LOGO_H; ly++) {
        for (int lx = 0; lx < LOGO_W; lx++) {
            int X = ox + lx, Y = oy + ly, px, py;
            if (X < 0 || Y < 0 || X >= LW || Y >= LH) continue;
            switch (rot) {
                case 90:  px = W - 1 - Y; py = X; break;
                case 180: px = W - 1 - X; py = H - 1 - Y; break;
                case 270: px = Y; py = H - 1 - X; break;
                default:  px = X; py = Y;
            }
            const unsigned char *s = &logo_rgb[(ly * LOGO_W + lx) * 3];
            uint32_t c = pack(&v, s[0], s[1], s[2]);
            uint8_t *row = base + (size_t)py * f.line_length;
            if (bpp == 32) ((uint32_t *)row)[px] = c; else ((uint16_t *)row)[px] = (uint16_t)c;
        }
    }
}

int main(int argc, char **argv) {
    struct fb_var_screeninfo v; struct fb_fix_screeninfo f;
    memset(&v, 0, sizeof v); memset(&f, 0, sizeof f);
    if (argc == 5 && strcmp(argv[1], "--test") == 0) {     /* --test WxH rot out.ppm : render to a PPM */
        if (sscanf(argv[2], "%ux%u", &v.xres, &v.yres) != 2) return 1;
        v.bits_per_pixel = 32; v.red.offset = 16; v.green.offset = 8; v.blue.offset = 0;
        v.red.length = v.green.length = v.blue.length = 8; f.line_length = v.xres * 4;
        uint8_t *buf = calloc((size_t)f.line_length, v.yres);
        draw(buf, &v, &f, atoi(argv[3]));
        FILE *o = fopen(argv[4], "wb"); fprintf(o, "P6 %u %u 255\n", v.xres, v.yres);
        for (size_t i = 0; i < (size_t)v.xres * v.yres; i++) { uint32_t c = ((uint32_t *)buf)[i]; fputc(c >> 16 & 255, o); fputc(c >> 8 & 255, o); fputc(c & 255, o); }
        fclose(o); return 0;
    }
    int fd = open("/dev/fb0", O_RDWR);
    if (fd < 0) return 0;                       /* no framebuffer: nothing to do, never block boot */
    if (ioctl(fd, FBIOGET_VSCREENINFO, &v) || ioctl(fd, FBIOGET_FSCREENINFO, &f)) { close(fd); return 0; }
    int bpp = v.bits_per_pixel;
    if (bpp != 32 && bpp != 16) { close(fd); return 0; }
    size_t len = (size_t)f.line_length * v.yres_virtual;
    uint8_t *fb = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (fb == MAP_FAILED) { close(fd); return 0; }
    uint8_t *base = fb + (size_t)v.yoffset * f.line_length + (size_t)v.xoffset * (bpp / 8);
    /* portrait panels (e.g. RG28XX) show landscape content rotated */
    int rot = 0;
    if (v.yres > v.xres) { rot = find_rotation("/proc/device-tree", 0); if (rot != 90 && rot != 180) rot = 270; }
    draw(base, &v, &f, rot);
    msync(fb, len, MS_SYNC);
    munmap(fb, len); close(fd);
    return 0;
}
