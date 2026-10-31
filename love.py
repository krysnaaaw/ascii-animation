"""
Fase "Love Heart": hati besar yang tersusun dari kalimat "aku cinta kamu" dalam banyak bahasa.
Port dari versi turtle: sekarang menggambar di canvas tkinter yang sama dengan animasi lain,
dan digerakkan oleh waktu (update(t)) bukan oleh timer sendiri.

Dipakai oleh transition.py.
"""
import math as m
import random as r
import tkinter.font as tkf

PHRASES = [
    "I love you", "Seni seviyorum", "Te amo", "Je t'aime",
    "Ich liebe dich", "Ti amo", "Eu te amo", "Я тебя люблю",
    "사랑해", "愛してる", "我爱你", "मैं तुमसे प्यार करता हूँ",
    "Σ' αγαπώ", "Ik hou van jou", "Jag älskar dig", "Kocham cię",
    "ฉันรักเธอ", "Anh yêu em", "Aku cinta kamu", "Я тебе кохаю",
]
SIZES = (9, 10, 11, 12)
GAP = 7
LIFT = 34
ANIM_S = 0.672          # lama satu kalimat "mendarat" (42 frame x 16 ms di versi asli)
BG = "#060208"
FONTS = ("Arial", "Liberation Sans", "Noto Sans", "DejaVu Sans", "Helvetica")
FLASH = (1.0, 0.78, 0.78)
BGC = tuple(int(BG[i:i + 2], 16) / 255 for i in (1, 3, 5))


def clamp(v):
    return max(0.0, min(1.0, v))


def hexc(c):
    return "#%02x%02x%02x" % tuple(int(clamp(v) * 255) for v in c)


def mix(a, b, k):
    return tuple(p + (q - p) * k for p, q in zip(a, b))


def dim(c, k):
    return tuple(v * k for v in c)


class LoveHeart:
    def __init__(self, cv, width, height, duration=10.0, seed=11):
        self.cv = cv
        self.W, self.H = width, height
        self.duration = duration
        self.rng = r.Random(seed)
        fams = set(tkf.families(root=cv))
        self.family = next((f for f in FONTS if f in fams), "Helvetica")

        # ukuran hati menyesuaikan jendela; ukuran font ikut skala (versi asli: SC=21, jendela 800x800)
        base = [self._pt(2 * m.pi * i / 720, 1.0) for i in range(720)]
        ys = [p[1] for p in base]
        self.sc = min(width * 0.92 / 32.0, height * 0.90 / (max(ys) - min(ys)))
        self.fscale = self.sc / 21.0
        self.poly = [self._pt(2 * m.pi * i / 720, self.sc) for i in range(720)]
        self.edges = list(zip(self.poly, self.poly[1:] + self.poly[:1]))
        self.ymax = max(p[1] for p in self.poly)
        self.ymin = min(p[1] for p in self.poly)
        self.cy = (self.ymax + self.ymin) / 2

        self.fonts = {}
        self.sizes = tuple(sorted({max(7, int(round(s * self.fscale))) for s in SIZES}))
        self.order = self._build()
        self.main_ids = []
        self.active = []
        self.glints = []
        self.spawned = 0
        self.last_glint = 0.0

    # ------------------------------------------------------------ geometri hati
    @staticmethod
    def _pt(a, sc):
        x = 16 * (m.sin(a) ** 3)
        y = 13 * m.cos(a) - 5 * m.cos(2 * a) - 2 * m.cos(3 * a) - m.cos(4 * a)
        return x * sc, y * sc

    def _font(self, size):
        if size not in self.fonts:
            self.fonts[size] = tkf.Font(root=self.cv, family=self.family, size=size, weight="bold")
        return self.fonts[size]

    def _spans(self, y):
        xs = []
        for (x1, y1), (x2, y2) in self.edges:
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        return list(zip(xs[0::2], xs[1::2]))

    @staticmethod
    def _intersect(A, B, minw):
        out = []
        for a in A:
            for b in B:
                lo, hi = max(a[0], b[0]), min(a[1], b[1])
                if hi - lo > minw:
                    out.append((lo, hi))
        return out

    def _dist(self, x, y):
        return m.hypot(x / (16 * self.sc), (y - self.cy) / (14.5 * self.sc))

    def _phrases(self):
        while True:
            order = PHRASES[:]
            self.rng.shuffle(order)
            yield from order

    def _build(self):
        rng = self.rng
        cycle = self._phrases()
        row_h = max(self._font(z).metrics("linespace") for z in self.sizes) + 4
        half = row_h / 2
        placed = []
        minw = 14 * self.fscale
        gap = GAP * self.fscale

        y = self.ymax - half
        while y > self.ymin + half:
            row = self._intersect(self._spans(y + half), self._spans(y - half), minw)
            for lo, hi in row:
                lo += 4
                hi -= 4
                cur = lo + rng.uniform(0, 8)
                line = []
                while True:
                    fit = None
                    for _ in range(10):
                        text = next(cycle)
                        size = rng.choice(self.sizes)
                        w = self._font(size).measure(text)
                        if cur + w <= hi:
                            fit = (text, size, w)
                            break
                    if not fit:
                        break
                    text, size, w = fit
                    line.append([cur + w / 2, text, size, w])
                    cur += w + gap
                if not line:
                    continue
                if len(line) > 1:
                    left = hi - (line[-1][0] + line[-1][3] / 2)
                    for i, it in enumerate(line):
                        it[0] += left * i / (len(line) - 1)
                else:
                    line[0][0] = (lo + hi) / 2
                for i, (x, text, size, w) in enumerate(line):
                    edge = i == 0 or i == len(line) - 1
                    placed.append(dict(x=x, y=y, text=text, size=size, edge=edge))
            y -= row_h

        wine, crimson, blood = (0.58, 0.0, 0.09), (0.90, 0.05, 0.14), (0.98, 0.10, 0.16)
        for p in placed:
            rad = min(1.0, self._dist(p["x"], p["y"]))
            base = mix(wine, crimson, 0.25 + 0.75 * rad)
            base = mix(base, blood, rng.uniform(0, 0.35) + (0.3 if p["edge"] else 0))
            p["color"] = tuple(min(1, v) for v in base)
            p["rad"] = rad
            # koordinat layar (y ke bawah), hati dipusatkan di tengah canvas
            p["sx"] = self.W / 2 + p["x"]
            p["sy"] = self.H / 2 - (p["y"] - self.cy)

        edges = [p for p in placed if p["edge"]]
        inner = [p for p in placed if not p["edge"]]
        edges.sort(key=lambda p: m.atan2(p["x"], p["y"] - self.cy) % (2 * m.pi))
        inner.sort(key=lambda p: -p["rad"] + rng.uniform(0, 0.08))
        return edges + inner

    # ------------------------------------------------------------ animasi
    def reset(self):
        for p in self.order:
            for k in ("shadow", "halo", "main"):
                if k in p:
                    try:
                        self.cv.delete(p[k])
                    except Exception:
                        pass
                    del p[k]
        self.main_ids = []
        self.active = []
        self.glints = []
        self.spawned = 0
        self.last_glint = 0.0

    def _spawn(self, p, t):
        cv = self.cv
        x, y = p["sx"], p["sy"]
        size = p["size"]
        font = (self.family, size, "bold")
        big = (self.family, size + 1, "bold")
        lift = LIFT * self.fscale
        p["shadow"] = cv.create_text(x + 2, y + 3, text=p["text"], font=font, fill=BG)
        p["halo"] = cv.create_text(x, y, text=p["text"], font=big, fill=BG)
        p["main"] = cv.create_text(x, y - lift, text=p["text"], font=font, fill=BG)
        p["t0"] = t
        p["dx"] = self.rng.uniform(-10, 10) * self.fscale
        self.main_ids.append((p["main"], p["color"]))
        self.active.append(p)

    def _animate(self, p, t):
        cv = self.cv
        u = clamp((t - p["t0"]) / ANIM_S)
        e = 1 - (1 - u) ** 3
        c = p["color"]
        x, y = p["sx"], p["sy"]
        hover = (1 - e) * LIFT * self.fscale
        px = x + p["dx"] * (1 - e)
        py = y - hover
        cv.itemconfig(p["shadow"], fill=hexc(mix(BGC, dim(c, 0.30), e)))
        cv.itemconfig(p["halo"], fill=hexc(mix(BGC, dim(c, 0.20), e * e)))
        cv.coords(p["halo"], px, py)
        flash = 0.75 * m.sin(m.pi * clamp((u - 0.55) / 0.45))
        col = mix(mix(BGC, c, e ** 1.5), FLASH, flash)
        cv.itemconfig(p["main"], fill=hexc(col))
        cv.coords(p["main"], px, py)
        if u >= 1:
            cv.coords(p["halo"], x, y)
            cv.coords(p["main"], x, y)
            cv.itemconfig(p["main"], fill=hexc(c))
            cv.itemconfig(p["halo"], fill=hexc(dim(c, 0.20)))
            cv.itemconfig(p["shadow"], fill=hexc(dim(c, 0.30)))
            return False
        return True

    def update(self, t):
        """t = detik sejak fase hati dimulai."""
        n = int(len(self.order) * min(1.0, t / self.duration))
        while self.spawned < n:
            self._spawn(self.order[self.spawned], t)
            self.spawned += 1
        self.active = [p for p in self.active if self._animate(p, t)]

        # kilau acak setelah semua kalimat mendarat
        if self.spawned >= len(self.order) and not self.active:
            if t - self.last_glint >= 0.14 and self.main_ids:
                self.last_glint = t
                i, c = self.rng.choice(self.main_ids)
                self.cv.itemconfig(i, fill=hexc(mix(c, FLASH, 0.6)))
                self.glints.append((t + 0.26, i, c))
            keep = []
            for (until, i, c) in self.glints:
                if t >= until:
                    self.cv.itemconfig(i, fill=hexc(c))
                else:
                    keep.append((until, i, c))
            self.glints = keep

    def fade(self, k):
        """Memudar ke latar (k: 0 = penuh, 1 = hilang)."""
        self.glints = []
        for p in self.order:
            if "main" not in p:
                continue
            c = p["color"]
            self.cv.itemconfig(p["main"], fill=hexc(mix(c, BGC, k)))
            self.cv.itemconfig(p["halo"], fill=hexc(mix(dim(c, 0.20), BGC, k)))
            self.cv.itemconfig(p["shadow"], fill=hexc(mix(dim(c, 0.30), BGC, k)))