#!/usr/bin/env python3
"""
Bouquet lily ASCII animasi dalam jendela (tkinter), bukan di terminal.

Kebutuhan:  pip install numpy pillow   (tkinter biasanya sudah ikut Python;
            di Arch: sudo pacman -S tk)
Jalankan :  python bouquet_window.py
Kontrol  :  klik jendela / tombol R = ulangi dari awal,  Esc = keluar
Atur ukuran lewat konstanta FONT_SIZE dan MAXROWS di bawah.
"""
import math
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw

FONT_SIZE = 8     # lebih kecil = karakter lebih banyak = lebih detail (tapi lebih berat)
MAXROWS = 60      # batas jumlah baris karakter
FPS = 24
ASPECT = 0.85     # lebar jendela relatif terhadap tingginya
TK_MS = 13.0      # jatah waktu per frame untuk menggambar ulang sel di tkinter
QL = 24           # jumlah tingkat warna per kanal (makin kecil makin sedikit update)

TAU = math.pi * 2
M32 = 0xFFFFFFFF


# ----------------------------------------------------------------- helpers
def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def sign(v):
    return (v > 0) - (v < 0)


def mulberry(seed):
    state = [seed & M32]

    def rnd():
        s = (state[0] + 0x6D2B79F5) & M32
        state[0] = s
        t = ((s ^ (s >> 15)) * (1 | s)) & M32
        t = (((t + (((t ^ (t >> 7)) * (61 | t)) & M32)) & M32) ^ t)
        return ((t ^ (t >> 14)) & M32) / 4294967296.0

    return rnd


def V(*a):
    return np.array(a, dtype=float)


def norm(a):
    n = np.linalg.norm(a)
    return a / (n if n else 1.0)


def hex_rgb(h):
    n = int(h[1:], 16)
    return np.array([(n >> 16) & 255, (n >> 8) & 255, n & 255], dtype=float)


def mix_rgb(h1, h2, t):
    return hex_rgb(h1) * (1 - t) + hex_rgb(h2) * t if isinstance(h1, str) and isinstance(h2, str) else h1 * (1 - t) + h2 * t


LIGHT = norm(V(-0.45, -0.65, 0.65))

# ----------------------------------------------------------------- timeline
GROW_END = 3.3
LOOP = 11.0
FADE = 0.45

# ----------------------------------------------------------------- palet
PAL = {
    "red":      dict(c=["#600812", "#d81e26", "#ff6a5c"], an="#f6c838", fk="#4a0208", rays=False),
    "cream":    dict(c=["#a2a868", "#efe4d0", "#fff8ec"], an="#a8541a", fk="#8a6a50", rays=False),
    "peach":    dict(c=["#5a2a14", "#dcc0a0", "#f2e2cc"], an="#9c4a14", fk="#8a4a20", rays=True),
    "magenta":  dict(c=["#f4cdea", "#d43cbc", "#e478d4"], an="#f2b44a", fk="#4e0646", rays=False),
    "yellow":   dict(c=["#a06c1c", "#dcc054", "#f2e4a2"], an="#b45c14", fk=None, rays=False),
    "tan":      dict(c=["#6e3622", "#c48e6e", "#eed0b8"], an="#8e3c14", fk="#4e2012", rays=True),
    "plum":     dict(c=["#3e1430", "#8e4a7a", "#bc80a8"], an="#f4c440", fk="#3a0626", rays=False, longStamens=True),
    "oxblood":  dict(c=["#2e0608", "#74141a", "#9e3a34"], an="#ffd83c", fk="#2a0206", rays=False, longStamens=True),
    "maroon":   dict(c=["#2e5e22", "#7a0e1c", "#a8222c"], an="#e0a020", fk=None, rays=False),
    "budgreen": dict(c=["#2a6a26", "#4caa40", "#8ad870"], an="#e0a020", fk=None, rays=False),
}
for _p in PAL.values():
    _p["rgb"] = [hex_rgb(h) for h in _p["c"]]
    _p["anrgb"] = tuple(int(v) for v in hex_rgb(_p["an"]))
    _p["fkrgb"] = tuple(int(v) for v in hex_rgb(_p["fk"])) if _p["fk"] else None

# x, y, panjang kelopak, palet, arah hadap, putaran, urutan mekar
LILY_DEFS = [
    [19, -1000, 170, "tan", [0.00, -0.55, 0.83], 0.35, 4],
    [-186, -894, 175, "cream", [-0.42, -0.42, 0.80], 0.10, 6],
    [206, -900, 175, "yellow", [0.45, -0.40, 0.80], 0.55, 8],
    [-274, -820, 100, "yellow", [-0.88, -0.30, 0.37], 0.20, 9],
    [289, -810, 100, "tan", [0.88, -0.30, 0.37], 0.80, 10],
    [-258, -680, 210, "yellow", [-0.74, -0.05, 0.67], 0.45, 7],
    [250, -662, 215, "plum", [0.80, -0.20, 0.56], 0.15, 5],
    [-276, -335, 192, "yellow", [-0.76, 0.10, 0.64], 0.60, 11],
    [271, -300, 168, "oxblood", [0.75, 0.20, 0.63], 0.30, 12],
    [140, -505, 265, "cream", [0.20, -0.10, 0.97], 0.25, 2],
    [-146, -535, 250, "magenta", [-0.22, -0.15, 0.96], 0.70, 1],
    [-21, -800, 250, "red", [0.00, -0.30, 0.95], 0.52, 0],
    [0, -325, 245, "peach", [0.00, 0.05, 1.00], 0.05, 3],
]
STAY_BUDS = [
    [-52, -1028, 70, "budgreen"],
    [104, -1036, 80, "maroon"],
]
BASE_LEAF_DEFS = [
    [-40, -45, math.pi - 0.06, 330, 26, 0.1],
    [-60, -130, math.pi + 0.08, 250, 26, 0.14],
    [-70, -210, math.pi + 0.6, 215, 22, 0.08],
    [-20, 20, math.pi - 0.32, 230, 22, 0.16],
    [-45, -95, math.pi + 0.32, 200, 22, 0.1],
    [-35, -170, math.pi - 0.2, 180, 20, 0.14],
    [45, -55, 0.05, 260, 26, 0.13],
    [65, -140, -0.06, 240, 26, 0.16],
    [25, 15, 0.3, 220, 22, 0.18],
    [55, -100, -0.38, 200, 22, 0.1],
    [70, -205, -0.62, 190, 20, 0.08],
    [35, -175, 0.22, 170, 20, 0.15],
]

# ----------------------------------------------------------------- dunia (batang, daun, bunga)
R = mulberry(54440)


def make_stem(x, y):
    bx = clamp(x * 0.26, -80, 80) + (R() - 0.5) * 24
    cx = bx + (x - bx) * 0.42 + (R() - 0.5) * 24
    start = R() * 0.15
    dur = 0.8 + R() * 0.2
    return SimpleNamespace(bx=bx, by=0.0, cx=cx, cy=y * 0.5, x=x, y=y, start=start, dur=dur, thick=1.0)


def stem_point(st, u):
    a = 1 - u
    return (a * a * st.bx + 2 * a * u * st.cx + u * u * st.x,
            a * a * st.by + 2 * a * u * st.cy + u * u * st.y)


def stem_angle(st, u):
    dx = 2 * (1 - u) * (st.cx - st.bx) + 2 * u * (st.x - st.cx)
    dy = 2 * (1 - u) * (st.cy - st.by) + 2 * u * (st.y - st.cy)
    return math.atan2(dy, dx)


lilies = []
for (x, y, s, key, axis, spin, order) in LILY_DEFS:
    st = make_stem(x, y)
    bloom_start = 1.4 + order * 0.03 + R() * 0.08
    bloom_dur = 1.35 + R() * 0.2
    lilies.append(SimpleNamespace(
        x=x, y=y, s=s, p=PAL[key], st=st, axis=norm(V(*axis)), spin=spin * TAU,
        budStart=st.start + st.dur - 0.1, bloomStart=bloom_start, bloomDur=bloom_dur,
        seed=1000 + order * 97))

stay_buds = []
for (x, y, s, key) in STAY_BUDS:
    st = make_stem(x, y)
    spin = R() * TAU
    stay_buds.append(SimpleNamespace(x=x, y=y, s=s, p=PAL[key], st=st, spin=spin,
                                     budStart=st.start + st.dur - 0.15, seed=7))

# tiap batang punya "kaki" sendiri, menyebar di dasar
_all = [f.st for f in lilies] + [f.st for f in stay_buds]
_all.sort(key=lambda s: s.x)
_n = len(_all)
_feet = [lerp(-72, 72, i / (_n - 1)) for i in range(_n)]
for i in range(1, _n - 1, 4):
    _feet[i], _feet[i + 1] = _feet[i + 1], _feet[i]
for i, st in enumerate(_all):
    st.bx = _feet[i] + (R() - 0.5) * 6
    st.thick = 0.55 + R() * 0.5
    _extk = 0.55 + R() * 0.45  # (dipertahankan agar urutan acak sama)
    bow = (R() - 0.5) * 50 + sign(st.x) * 12
    st.cx = lerp(st.bx, st.x, 0.45) + bow
    st.cy = st.y * 0.45
_all[int(_n * 0.2)].thick = 1.35
_all[int(_n * 0.62)].thick = 1.3

base_leaves = []
for i, (x, y, ang, L, w, droop) in enumerate(BASE_LEAF_DEFS):
    base_leaves.append(SimpleNamespace(
        x=x, y=y, ang=ang, L=L, w=w,
        bend=(1 if math.cos(ang) > 0 else -1) * L * droop,
        start=0.35 + i * 0.06 + R() * 0.1, dur=0.65))

# ----------------------------------------------------------------- angin
def wind_amt(t):
    return smooth((t - 2.9) / 1.6)


def sway_x(y, t, bottom=None):
    w = wind_amt(t)
    h = clamp(-y / 1100, 0, 1.2)
    if w <= 0 or h <= 0:
        return 0.0
    ph = -y * 0.0016
    gust = (math.sin(t * 1.2 - ph) * 0.6 + math.sin(t * 2.2 - ph * 1.6 + 1.3) * 0.22
            + math.sin(t * 0.53 + 0.7) * 0.35)
    return w * 11 * (h ** 1.5) * gust


def flutter(seed, t):
    return wind_amt(t) * 2 * math.sin(t * 2.4 + seed)


# ----------------------------------------------------------------- layar / kanvas
class Scene:
    """Menyimpan ukuran layout dan kanvas gambar kecil (piksel persegi)."""

    def __init__(self, cols, rows, ca=2.0):
        self.cols, self.rows = cols, rows
        self.SW, self.SH = cols * 2, int(round(rows * 2 * ca))
        res = 0.0
        hb = self.SH * (1 - res)
        self.S = min(self.SW / 960, hb / 1330)
        self.ox = self.SW / 2
        self.oy = self.SH * res + hb / 2 + 545 * self.S + max(0, (hb - 1330 * self.S) / 2) * 0.6
        self.bottom = (self.SH - self.oy) / self.S + 40
        sr = mulberry(424242)
        count = int(cols * rows / 55)
        self.stars = [(sr(), sr(), sr() * TAU, 0.5 + sr() * 1.4, 0.55 + sr() * 0.45, sr() < 0.18)
                      for _ in range(count)]
        # derau statis per sel, untuk pemilihan karakter
        rr = np.random.RandomState(7)
        self.h1 = rr.rand(rows, cols)
        self.h2 = rr.rand(rows, cols)
        self.jit = 0.82 + 0.36 * rr.rand(rows, cols)
        self.img = None
        self.d = None

    def P(self, x, y):
        return (x * self.S + self.ox, y * self.S + self.oy)

    def w(self, world_w, mn=1):
        return max(mn, int(round(world_w * self.S)))


def draw_stem(sc, st, t, fl=0.0):
    d = sc.d
    p = ease_in_out((t - st.start) / st.dur)
    if p <= 0:
        return 0.0
    ext = max(60, sc.bottom + 30)
    meet_y = max(ext * 1.5, 320)
    foot_x = st.bx * (1 - ext / meet_y)
    curve_len = math.hypot(st.x - st.bx, st.y) * 1.05
    e = ext / (ext + curve_len)
    pts = []
    ext_p = clamp(p / e)
    for k in range(7):
        u = (k / 6) * ext_p
        pts.append((lerp(foot_x, st.bx, u), lerp(ext, 0, u)))
    q = 0.0 if e >= 1 else clamp((p - e) / (1 - e))
    if q > 0:
        n = max(2, math.ceil(30 * q))
        for k in range(1, n + 1):
            u = (k / n) * q
            x, y = stem_point(st, u)
            pts.append((x + sway_x(y, t) + fl * u * u, y))
    pp = [sc.P(x, y) for x, y in pts]
    th = st.thick
    w1 = sc.w(13 * th * 1.3, 2)
    d.line(pp, fill=(18, 58, 20, 255), width=w1, joint="curve")
    w2 = max(1, w1 - 2)
    d.line(pp, fill=(44, 116, 40, 255), width=w2, joint="curve")
    if w1 >= 4:
        hl = [(x - 2.4 * th * sc.S, y) for x, y in pp]
        d.line(hl, fill=(112, 176, 72, 200), width=max(1, w1 // 4), joint="curve")
    return q


def bez(p0, p1, p2, p3, n=8):
    out = []
    for i in range(n + 1):
        u = i / n
        a = 1 - u
        out.append((a ** 3 * p0[0] + 3 * a * a * u * p1[0] + 3 * a * u * u * p2[0] + u ** 3 * p3[0],
                    a ** 3 * p0[1] + 3 * a * a * u * p1[1] + 3 * a * u * u * p2[1] + u ** 3 * p3[1]))
    return out


def draw_leaf_at(sc, x, y, ang, L, w, b):
    if L < 1:
        return
    c, s = math.cos(ang), math.sin(ang)

    def tr(p):
        return sc.P(x + c * p[0] - s * p[1], y + s * p[0] + c * p[1])

    top = bez((0, 0), (L * 0.25, -w), (L * 0.68, -w * 0.62 + b * 0.55), (L, b))
    bot = bez((L, b), (L * 0.68, w * 0.5 + b * 0.55), (L * 0.25, w * 0.85), (0, 0))
    poly = [tr(p) for p in top + bot[1:]]
    sc.d.polygon(poly, fill=(47, 122, 44, 255), outline=(30, 94, 34, 255))
    rib = [tr(p) for p in [(L * 0.02, 0), (L * 0.5, b * 0.3 + 0), (L * 0.93, b * 0.92)]]
    sc.d.line(rib, fill=(10, 38, 12, 235), width=sc.w(w * 0.2, 1))


def draw_base_leaf(sc, lf, t):
    p = ease_out((t - lf.start) / lf.dur)
    rustle = wind_amt(t) * 0.02 * math.sin(t * 1.6 + lf.L)
    if p > 0:
        draw_leaf_at(sc, lf.x + sway_x(lf.y, t), lf.y, lf.ang + rustle, lf.L * p, lf.w * (0.5 + 0.5 * p), lf.bend * p)


# ----------------------------------------------------------------- lily 3D
def frame3(A, spin):
    ref = norm(V(0, 0, 1) * (1 - smooth((abs(A[2]) - 0.75) / 0.22)) + V(0, -1, 0) * smooth((abs(A[2]) - 0.75) / 0.22))
    U = norm(np.cross(A, ref))
    Vv = np.cross(A, U)
    c, s = math.cos(spin), math.sin(spin)
    return U * c + Vv * s, U * -s + Vv * c


def rot_to(v, frm, to):
    k0 = np.cross(frm, to)
    sn = np.linalg.norm(k0)
    cs = float(np.dot(frm, to))
    if sn < 1e-6:
        return v
    k = k0 / sn
    return v * cs + np.cross(k, v) * sn + k * np.dot(k, v) * (1 - cs)


PN = 12
BV = np.array([-1, -0.66, -0.33, 0, 0.33, 0.66, 1.0])
BV_MID = (BV[:-1] + BV[1:]) / 2
UU = np.arange(PN + 1) / PN
UMID = (np.arange(PN) + 0.5) / PN


def build_petal(A, U, Vv, phi, L, hw_max, th_b, th_t, cup, twist, fold):
    Rd = U * math.cos(phi) + Vv * math.sin(phi)
    T = -U * math.sin(phi) + Vv * math.cos(phi)
    th = th_b + (th_t - th_b) * UU ** 1.45
    d = np.outer(np.cos(th), A) + np.outer(np.sin(th), Rd)
    n = np.outer(np.sin(th), A) - np.outer(np.cos(th), Rd)
    m = 0.38
    left = np.sin((math.pi / 2) * np.clip(UU / m, 0, 1)) ** 0.8
    right = np.clip((1 - UU) / (1 - m), 0, 1) ** 0.8
    hw = hw_max * (np.where(UU < m, left, right) + 0.14 * (1 - UU))
    step = d * (L / PN)
    p = np.vstack([np.zeros(3), np.cumsum(step[:-1], axis=0)])
    ctr = p + np.outer(twist * L * UU ** 3, T)
    grid = (ctr[:, None, :]
            + T[None, None, :] * (hw[:, None] * BV[None, :])[..., None]
            + n[:, None, :] * (((cup * BV ** 2 + fold * np.abs(BV))[None, :]) * hw[:, None])[..., None])
    return SimpleNamespace(ctr=ctr, hws=hw, nrm=n, T=T, grid=grid, cup=cup, fold=fold,
                           nMid=n[int(PN * 0.45 + 0.5)], z=0.0)


def draw_petal(sc, fx, fy, pt, pal, seed, bud_mix):
    d = sc.d
    S, ox, oy = sc.S, sc.ox, sc.oy
    throat, body, tip = pal["rgb"]
    green = hex_rgb("#3e8a32")
    c0 = throat * (1 - bud_mix) + green * bud_mix
    c1 = body * (1 - bud_mix) + throat * bud_mix
    stops = [0.0, lerp(0.32, 0.25, bud_mix), 0.75, 1.0]
    grad = np.stack([np.interp(UMID, stops, [c0[ch], c1[ch], body[ch], tip[ch]]) for ch in range(3)], axis=1)

    frontness = smooth((pt.nMid[2] + 0.22) / 0.44)
    open_detail = 1 - bud_mix

    # pencahayaan per pita
    vm = BV_MID
    nb = pt.nMid[None, :] - pt.T[None, :] * (2 * pt.cup * vm + pt.fold * np.sign(vm))[:, None]
    nb = nb / np.linalg.norm(nb, axis=1)[:, None]
    dd = nb @ LIGHT
    lit_front = 0.55 + 0.68 * np.clip(dd, 0, None)
    lit_back = (0.55 + 0.68 * np.clip(-dd, 0, None)) * 0.8
    lam = (lit_back + (lit_front - lit_back) * frontness) * pt.tone
    dark = np.clip(1 - lam + np.abs(vm) * 0.07, 0, 0.62)
    light = np.where((dark <= 0.01) & (lam > 1.02), np.clip((lam - 1) * 0.45, 0, 0.16), 0.0)
    col = grad[:, None, :] * (1 - dark)[None, :, None]
    col = col * (1 - light)[None, :, None] + np.array([255, 248, 240.0]) * light[None, :, None]
    col = np.clip(col, 0, 255).astype(int).tolist()

    gx = ((pt.grid[..., 0] + fx) * S + ox).tolist()
    gy = ((pt.grid[..., 1] + fy) * S + oy).tolist()
    for i in range(PN):
        gxi, gyi, gxn, gyn = gx[i], gy[i], gx[i + 1], gy[i + 1]
        for j in range(6):
            c = tuple(col[i][j]) + (255,)
            d.polygon([(gxi[j], gyi[j]), (gxi[j + 1], gyi[j + 1]), (gxn[j + 1], gyn[j + 1]), (gxn[j], gyn[j])],
                      fill=c, outline=c)

    def px(q):
        return ((q[0] + fx) * S + ox, (q[1] + fy) * S + oy)

    def at(i, v):
        return pt.ctr[i] + pt.T * pt.hws[i] * v + pt.nrm[i] * (pt.cup * v * v + pt.fold * abs(v)) * pt.hws[i]

    # tulang tengah (midrib)
    rib_a = (0.5 + 0.5 * frontness) * (0.35 + 0.65 * open_detail)
    rc = tuple(int(v) for v in throat * 0.65)
    rib = [px(pt.ctr[i] + pt.nrm[i] * 1.5) for i in range(int(PN * 0.9) + 1)]
    d.line(rib, fill=rc + (int(255 * 0.26 * rib_a),), width=max(1, sc.w(max(3, pt.hws[6] * 0.28) * 0.8)))
    d.line(rib, fill=rc + (int(255 * 0.78 * rib_a),), width=1)

    # bintik dan garis cokelat
    mark_a = frontness * open_detail
    if mark_a > 0.01:
        r = mulberry(seed)
        if pal["rays"]:
            a0 = px(pt.ctr[1])
            for k in range(7):
                v = (k / 6 - 0.5) * 1.3
                e = int(math.floor(PN * (0.3 + r() * 0.14)))
                d.line([a0, px(at(e, v))], fill=pal["fkrgb"] + (int(255 * 0.6 * mark_a),), width=1)
        if pal["fkrgb"]:
            for k in range(9):
                i = 1 + int(math.floor(r() * PN * 0.36))
                x, y = px(at(i, (r() - 0.5) * 1.5))
                rad = (1.1 + r() * 1.1) * S * 1.5
                d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=pal["fkrgb"] + (int(255 * 0.55 * mark_a),))


def draw_lily3(sc, fx, fy, A, spin, L, open_, pal, seed, bud_shape=0.0, Aref=None):
    if L < 2:
        return
    if Aref is None:
        Aref = A
    S, ox, oy, d = sc.S, sc.ox, sc.oy, sc.d
    Ur, Vr = frame3(Aref, spin)
    U, Vv = rot_to(Ur, Aref, A), rot_to(Vr, Aref, A)
    o = open_
    bud_mix = 1 - smooth((o - 0.04) / 0.42)
    petals = []
    for k in range(6):
        inner = k % 2 == 1
        phi = k * math.pi / 3
        th_b = lerp(lerp(0.78, 0.5, bud_shape), 0.98 if inner else 1.04, o)
        th_t = lerp(lerp(-0.5, -0.32, bud_shape), 2.45 if inner else 2.6, o ** 1.15)
        hw = L * lerp(lerp(0.36, 0.3, bud_shape), 0.27 if inner else 0.235, smooth(o))
        cup = lerp(0.15, 0.1, o)
        fold = lerp(0.05, 0.42, o)
        twist = ((k * 53 + seed) % 7 - 3) / 3 * 0.07 * o
        pt = build_petal(A, U, Vv, phi, (0.97 if inner else 1) * L * 1.03, hw, th_b, th_t, cup, twist, fold)
        pt.k = k
        Rr = Ur * math.cos(phi) + Vr * math.sin(phi)
        pt.key = Rr[2] + (0.12 if inner else 0)
        pt.tone = 0.84 + (((k * 71 + seed * 13) % 11) / 10) * 0.3
        petals.append(pt)
    petals.sort(key=lambda p: p.key)

    sv = smooth((o - 0.45) / 0.5)

    def P(x, y):
        return ((fx + x) * S + ox, (fy + y) * S + oy)

    def draw_centre():
        if sv <= 0:
            return
        r_t = L * 0.26
        al = sv * clamp(A[2] + 0.3)
        cx, cy = P(0, 0)
        for rr, a, colr in ((r_t, 0.22, (160, 180, 70)), (r_t * 0.55, 0.4, (200, 220, 110))):
            rp = rr * S
            d.ellipse([cx - rp, cy - rp, cx + rp, cy + rp], fill=colr + (int(255 * a * al),))
        for k in range(6):
            phi = k * math.pi / 3 + math.pi / 6 + 0.08
            Rd = U * math.cos(phi) + Vv * math.sin(phi)
            side = 0.7 if (abs(A[2]) < 0.7 and not pal.get("longStamens")) else 1.0
            ln = L * (0.6 + ((k * 37 + seed) % 10) / 50) * sv * side
            mid = A * ln * 0.55 + Rd * ln * 0.14
            end = A * ln * 0.82 + Rd * ln * 0.52
            curve = []
            for i in range(7):
                u = i / 6
                a = 1 - u
                curve.append(P(2 * a * u * mid[0] + u * u * end[0], 2 * a * u * mid[1] + u * u * end[1]))
            d.line([P(0, 0)] + curve, fill=(226, 226, 160, 230), width=1)
            ex, ey = P(end[0], end[1])
            ra = max(1.0, L * 0.05 * S)
            d.ellipse([ex - ra, ey - ra * 0.7, ex + ra, ey + ra * 0.7], fill=pal["anrgb"] + (255,))
        pe = A * (L * 0.74 * sv) + U * (L * 0.08 * sv)
        d.line([P(0, 0), P(pe[0], pe[1])], fill=(200, 214, 140, 190), width=1)
        px_, py_ = P(pe[0], pe[1])
        rp = max(1.0, L * 0.035 * S)
        d.ellipse([px_ - rp, py_ - rp, px_ + rp, py_ + rp], fill=(168, 206, 102, 255))

    done = False
    for pt in petals:
        if not done and pt.key > 0.5:
            draw_centre()
            done = True
        draw_petal(sc, fx, fy, pt, pal, seed + pt.k, bud_mix)
    if not done:
        draw_centre()


def bud_axis(st):
    a = stem_angle(st, 1)
    return norm(V(math.cos(a), math.sin(a), 0.22))


def draw_lily(sc, f, t):
    bud_p = ease_out((t - f.budStart) / 0.6)
    if bud_p <= 0:
        return
    b = clamp((t - f.bloomStart) / f.bloomDur)
    o = smooth(b / 0.75)
    L = f.s * lerp(0.5 * bud_p, 1, ease_in_out(b))
    k = smooth((b - 0.1) / 0.8)
    A0 = norm(bud_axis(f.st) * (1 - k) + f.axis * k)
    dx = sway_x(f.y, t) + flutter(f.seed, t)
    A = norm(V(A0[0] + dx * 0.004, A0[1], A0[2]))
    draw_lily3(sc, f.x + dx, f.y, A, f.spin, L, o, f.p, f.seed, 0.0, f.axis)


def draw_world(sc, t):
    stem_p = {}
    for f in stay_buds:
        stem_p[id(f)] = draw_stem(sc, f.st, t, flutter(f.seed, t))
    for f in lilies:
        stem_p[id(f)] = draw_stem(sc, f.st, t, flutter(f.seed, t))
    for lf in base_leaves:
        draw_base_leaf(sc, lf, t)
    for f in stay_buds:
        bp = ease_out((t - f.budStart) / 0.75)
        dx = sway_x(f.y, t) + flutter(f.seed, t)
        if bp > 0:
            draw_lily3(sc, f.x + dx, f.y, bud_axis(f.st), f.spin, f.s * bp, 0.03, f.p, f.seed, 1.0)
    for f in lilies:
        draw_lily(sc, f, t)


def paint_scene(sc, t):
    sc.img = Image.new("RGB", (sc.SW, sc.SH), (0, 0, 0))
    sc.d = ImageDraw.Draw(sc.img, "RGBA")
    for (sx, sy, ph, sp, a, big) in sc.stars:
        tw = 0.55 + 0.45 * math.sin(t * sp + ph) ** 2
        v = int(255 * a * tw)
        x, y = int(sx * sc.SW), int(sy * sc.SH)
        sc.d.rectangle([x, y, x + (1 if big else 0), y + (1 if big else 0)], fill=(v, v, v, 255))
    draw_world(sc, t)


# ----------------------------------------------------------------- ASCII
LEVELS = ["    ", ".'`,", ":;,'", "-~^\"", "=+<>", "*xvc", "oaesz", "%&$kh", "#8BMW", "@QNgR"]
VAR = 4
GLYPHS = np.array([c for lv in LEVELS for c in lv[:VAR]])


def to_cells(sc, fade=0.0):
    """Ubah gambar scene jadi (indeks glyph per sel, warna terkuantisasi per sel). Indeks 0 = sel kosong."""
    small = sc.img.resize((sc.cols, sc.rows), Image.BOX)
    c = np.asarray(small, dtype=float) / 255.0
    if fade > 0:
        c = c * (1 - fade)
    m = c.max(axis=2)
    on = m >= 0.06
    v = m ** 0.6
    lvl = 1 + np.clip(np.floor(v * (len(LEVELS) - 1) + (sc.h1 - 0.5) * 1.1), 0, len(LEVELS) - 2)
    idx = (lvl * VAR + np.floor(sc.h2 * VAR)).astype(np.int32)
    gi = np.where(on, idx, 0).astype(np.int32)
    lum = (c @ np.array([0.299, 0.587, 0.114]))[..., None]
    col = np.clip(lum + (c - lum) * 1.1, 0, 1)
    col = col * np.minimum(1.0 / np.maximum(m, 1e-6), 1.36)[..., None] * sc.jit[..., None]
    rgb = np.clip(col * 0.95, 0, 1)
    q = np.clip((rgb * (QL - 0.01)).astype(np.int16), 0, QL - 1)
    return gi, q


def plan_updates(gi, q, d_gi, d_q, budget):
    """Pilih sel mana saja yang perlu digambar ulang (maksimal `budget` sel per frame)."""
    same = gi == d_gi
    delta = np.abs(q - d_q).max(axis=2)
    blank_both = (gi == 0) & (d_gi == 0)
    need = (~blank_both) & ((~same) | (delta >= 2))
    cells = np.flatnonzero(need)
    if len(cells) > budget:
        prio = ((~same).astype(np.int16) * 6 + delta).ravel()[cells]
        top = np.argpartition(-prio, budget)[:budget]
        cells = cells[top]
    return cells


# ----------------------------------------------------------------- jendela tkinter
def main():
    import tkinter as tk
    import tkinter.font as tkf

    root = tk.Tk()
    root.title("Bouquet")
    root.resizable(False, False)
    root.configure(bg="#000000")
    root.bind("<Escape>", lambda e: root.destroy())

    fams = set(tkf.families())
    mono = next((f for f in ("Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Liberation Mono",
                             "Courier New", "Courier") if f in fams), "Courier")
    scr_h = root.winfo_screenheight()
    fnt = tkf.Font(root=root, family=mono, size=FONT_SIZE, weight="bold")
    ch = fnt.metrics("linespace")
    cw = fnt.measure("M")
    rows = max(20, min(MAXROWS, (scr_h - 110) // ch))
    cols = int(rows * ch * ASPECT / cw)
    W, H = cols * cw, rows * ch
    root.geometry(f"{W}x{H}+{(root.winfo_screenwidth() - W) // 2}+{max(0, (scr_h - H) // 2 - 20)}")
    cv = tk.Canvas(root, width=W, height=H, bg="#000000", highlightthickness=0)
    cv.pack()

    sc = Scene(cols, rows, ch / cw)
    items = np.zeros((rows, cols), dtype=object)
    items[:] = 0
    d_gi = np.zeros((rows, cols), np.int32)
    d_q = np.zeros((rows, cols, 3), np.int16)
    hexc = {}
    st = {"t0": time.perf_counter(), "budget": 2500, "cost": 0.012}

    def hx(rgb):
        k = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        s_ = hexc.get(k)
        if s_ is None:
            s_ = "#%02x%02x%02x" % tuple(v * 255 // (QL - 1) for v in k)
            hexc[k] = s_
        return s_

    def restart(_=None):
        st["t0"] = time.perf_counter()

    root.bind("r", restart)
    root.bind("R", restart)
    cv.bind("<Button-1>", restart)

    def tick():
        t0 = time.perf_counter()
        t = t0 - st["t0"]
        if t >= LOOP:
            st["t0"] = t0
            t = 0.0
        fade = clamp((t - (LOOP - FADE)) / FADE)
        paint_scene(sc, t)
        gi, q = to_cells(sc, fade)
        cells = plan_updates(gi, q, d_gi, d_q, st["budget"])
        t1 = time.perf_counter()
        for f in cells:
            r_, c_ = divmod(int(f), cols)
            g = int(gi[r_, c_])
            it = items[r_, c_]
            if g == 0:
                if it != 0:
                    cv.itemconfig(it, text="")
                d_gi[r_, c_] = 0
                d_q[r_, c_] = q[r_, c_]
                continue
            fill = hx(q[r_, c_])
            if it == 0:
                items[r_, c_] = cv.create_text((c_ + 0.5) * cw, (r_ + 0.5) * ch, text=GLYPHS[g],
                                               fill=fill, font=fnt, anchor="center")
            else:
                cv.itemconfig(it, text=GLYPHS[g], fill=fill)
            d_gi[r_, c_] = g
            d_q[r_, c_] = q[r_, c_]
        if len(cells) > 50:
            per = (time.perf_counter() - t1) / len(cells)
            st["cost"] = 0.7 * st["cost"] + 0.3 * per
            st["budget"] = int(min(12000, max(400, (TK_MS / 1000.0) / max(st["cost"], 1e-6))))
        el = (time.perf_counter() - t0) * 1000
        root.after(max(1, int(1000 / FPS - el)), tick)

    root.after(100, tick)
    root.mainloop()


if __name__ == "__main__":
    main()