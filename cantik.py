"""
Fase potret: mengubah sebuah foto menjadi gambar ASCII berwarna dan memunculkannya
dengan efek "scan" dari atas ke bawah (karakter acak lalu mengendap jadi gambar).

Dipakai oleh transition.py. Foto dibaca dari file (default: foto.jpg).
"""
import math

import numpy as np
from PIL import Image, ImageFilter, ImageOps

QL = 24  # tingkat warna per kanal, harus sama dengan eye_space.QL


def _ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


class Portrait:
    def __init__(self, path, cols, rows, cw, ch, ramp, stars,
                 crop=(0.0, 0.12, 1.0, 0.70), reveal=5.0, band=0.12):
        self.cols, self.rows = cols, rows
        self.reveal, self.band = reveal, band
        self.stars = stars
        self.ramp_codes = np.array([ord(c) for c in ramp], np.int32)
        nr = len(ramp) - 1  # ramp = 10 tingkat x 4 karakter (urut dari jarang ke rapat)

        img = ImageOps.exif_transpose(Image.open(path).convert("RGB"))
        W, H = img.size
        img = img.crop((int(crop[0] * W), int(crop[1] * H), int(crop[2] * W), int(crop[3] * H)))
        aspect = img.size[0] / img.size[1]

        # ukuran gambar dalam sel, menjaga proporsi (sel karakter tinggi : lebar = ch : cw)
        pr = rows - 2
        pc = int(round(pr * ch * aspect / cw))
        if pc > cols - 2:
            pc = cols - 2
            pr = int(round(pc * cw / (ch * aspect)))
        self.pr, self.pc = pr, pc
        self.r0, self.c0 = (rows - pr) // 2, (cols - pc) // 2

        big = img.resize((pc * 2, pr * 2), Image.LANCZOS)
        big = ImageOps.autocontrast(big, cutoff=1)
        big = big.filter(ImageFilter.UnsharpMask(radius=1.6, percent=110, threshold=2))
        small = np.asarray(big.resize((pc, pr), Image.BOX), dtype=float) / 255.0

        # kontras lokal: campur luminansi asli dengan versi ter-equalize supaya mata, alis, dan bibir menonjol
        lum0 = small @ np.array([0.299, 0.587, 0.114])
        gray = big.convert("L").resize((pc, pr), Image.BOX)
        eq = np.asarray(ImageOps.equalize(gray), dtype=float) / 255.0
        lum = np.clip(0.4 * lum0 + 0.6 * eq, 0, 1)
        ratio = np.clip(lum / np.maximum(lum0, 1e-3), 0.6, 1.9)
        col = np.clip(small * ratio[..., None], 0, 1)
        gl = col @ np.array([0.299, 0.587, 0.114])
        col = np.clip(gl[..., None] + (col - gl[..., None]) * 1.2, 0, 1)
        col = np.clip(col * 1.10, 0, 1)

        rr = np.random.RandomState(11)
        noise = rr.rand(pr, pc)
        # tingkat kerapatan 1..9, tiap tingkat punya 4 karakter yang bisa saling menggantikan
        lvl = np.clip(np.floor((lum ** 0.95) * 9.0 + (noise - 0.5) * 0.9), 0, 8).astype(np.int32) + 1
        ri = lvl * 4 + rr.randint(0, 4, size=lvl.shape)
        self.base_code = self.ramp_codes[ri]
        self.base_q = np.clip((col * (QL - 0.01)).astype(np.int16), 0, QL - 1)
        yn = np.linspace(0, 1, pr)[:, None] * np.ones((1, pc))
        self.yn = yn
        self.field = yn * 0.75 + rr.rand(pr, pc) * 0.25
        self.rng = np.random.RandomState(3)
        self.nr = nr

    def frame(self, tp):
        """tp = detik sejak potret mulai muncul. Mengembalikan (kode karakter, warna) satu layar penuh."""
        rows, cols = self.rows, self.cols
        code = np.full((rows, cols), 32, np.int32)
        q = np.zeros((rows, cols, 3), np.int16)

        # bintang latar yang berkelip
        for (sx, sy, ph, sp, a, big) in self.stars:
            tw = 0.55 + 0.45 * math.sin(tp * sp + ph) ** 2
            v = int((QL - 1) * a * tw * 0.9)
            r, c = int(sy * rows), int(sx * cols)
            if 0 <= r < rows and 0 <= c < cols:
                code[r, c] = ord("+") if big else ord(".")
                q[r, c] = (v, v, v)

        rs = slice(self.r0, self.r0 + self.pr)
        cs = slice(self.c0, self.c0 + self.pc)
        sub_code, sub_q = code[rs, cs], q[rs, cs]

        k = _ease(tp / self.reveal)
        thr = k * (1 + self.band)
        resolved = self.field < thr - self.band
        inband = (self.field >= thr - self.band) & (self.field < thr)
        unrevealed = ~(resolved | inband)

        shimmer = 1.0 + 0.07 * np.sin(2 * math.pi * (tp * 0.35 - self.yn * 1.2))
        qs = np.clip(self.base_q * shimmer[..., None], 0, QL - 1).astype(np.int16)

        sub_code[unrevealed] = 32
        sub_q[unrevealed] = 0
        sub_code[resolved] = self.base_code[resolved]
        sub_q[resolved] = qs[resolved]
        scr = self.rng.randint(8, self.nr + 1, size=self.base_code.shape)
        sub_code[inband] = self.ramp_codes[scr][inband]
        glow = (self.base_q * 0.35 + (QL - 1) * 0.65).astype(np.int16)
        sub_q[inband] = glow[inband]
        return code, q