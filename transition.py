import importlib.util
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

FONT_SIZE = 8
MAXROWS = 50 
FPS = 24
TK_MS = 13.0
EYE_START = 0.0
T_SWITCH = 36.0
TRANS = 4.5  
BQ_HOLD = 10.0
BQ_OUT = 2.5 
REVEAL = 5.0
PORT_HOLD = 9.0
BQ_TIME = 14.0 
PHOTO = "cantikk.jpg"
PHOTO_CROP = (0.0, 0.12, 1.0, 0.70)
FADE = 0.6
HEART = True
HEART_TIME = 10.0
HEART_HOLD = 8.0
HEART_FADE = 1.2
BG = "#060208"


def load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


eye = load("eye_space", "eye.py")
bq = load("bouquet_window", "bouquet.py")
port = load("portrait_ascii", "cantik.py")


def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


class Sequence:
    """Menghasilkan (kode karakter, warna) tiap sel untuk waktu tertentu."""

    def __init__(self, cw, ch, rows):
        eye.init(cw, ch, rows)
        self.cols, self.rows = eye.COLS, eye.ROWS
        self.sc = bq.Scene(self.cols, self.rows, ch / cw)
        self.eye_codes = np.array([ord(c) for c in eye.RAMP], np.int32)
        self.bq_codes = np.array([ord(c) for c in bq.GLYPHS], np.int32)
        rad = eye.RSC
        self.rad = rad / rad.max()
        self.portrait = None
        photo = os.path.join(HERE, PHOTO)
        if os.path.exists(photo):
            self.portrait = port.Portrait(photo, self.cols, self.rows, cw, ch, "".join(bq.GLYPHS),
                                          self.sc.stars, crop=PHOTO_CROP, reveal=REVEAL)
            self.cells_end = BQ_HOLD + REVEAL + PORT_HOLD
        else:
            print("foto '%s' tidak ditemukan, fase potret dilewati" % PHOTO)
            self.cells_end = BQ_TIME
        self.has_heart = HEART and os.path.exists(os.path.join(HERE, "love.py"))
        self.total = self.cells_end + ((HEART_TIME + HEART_HOLD + HEART_FADE) if self.has_heart else 0.0)

    def restart(self):
        eye.reset()

    def frame(self, te, dt):
        """te = waktu pada garis waktu animasi mata."""
        tb = te - T_SWITCH
        if tb >= self.cells_end:   # fase huruf sudah selesai (sisanya Love Heart yang menggambar sendiri)
            return (np.full((self.rows, self.cols), 32, np.int32),
                    np.zeros((self.rows, self.cols, 3), np.int16))
        p = ease(tb / TRANS) if tb > 0 else 0.0
        fb = clamp((tb - BQ_HOLD) / BQ_OUT) if self.portrait is not None else 0.0
        code = q = None
        if p < 1.0:
            idx, q = eye.render_cells(te, dt)
            code = self.eye_codes[idx]
        if p > 0.0 and fb < 1.0:
            bq.paint_scene(self.sc, tb)
            gi, qb = bq.to_cells(self.sc, 0.0)
            codeb = self.bq_codes[gi]
            if p >= 1.0:
                code, q = codeb, qb
            else:
                # bouquet "tumbuh" dari tengah layar keluar, dengan tepi acak
                field = self.rad * 0.65 + self.sc.h1 * 0.35
                thr = p * 1.15
                show = field < thr
                code = np.where(show, codeb, code)
                q = np.where(show[..., None], qb, q)
                ring = (field >= thr) & (field < thr + 0.05)
                code = np.where(ring, ord("*"), code)
                q = np.where(ring[..., None], (np.array([22, 8, 14]) * (1 - 0.5 * p)).astype(np.int16), q)
            if fb > 0:
                q = (q * (1 - fb)).astype(np.int16)
        if code is None:
            code = np.full((self.rows, self.cols), 32, np.int32)
            q = np.zeros((self.rows, self.cols, 3), np.int16)
        if self.portrait is not None and tb > BQ_HOLD:
            pc, pq = self.portrait.frame(tb - BQ_HOLD)
            use = pc != 32
            code = np.where(use, pc, code)
            q = np.where(use[..., None], pq, q)
        f = clamp((tb - (self.cells_end - FADE)) / FADE)
        if f > 0:
            q = (q * (1 - f)).astype(np.int16)
        return code.astype(np.int32), q.astype(np.int16)


def plan_updates(code, q, d_code, d_q, budget):
    same = code == d_code
    delta = np.abs(q - d_q).max(axis=2)
    blank_both = (code == 32) & (d_code == 32)
    need = (~blank_both) & ((~same) | (delta >= 2))
    cells = np.flatnonzero(need)
    if len(cells) > budget:
        prio = ((~same).astype(np.int16) * 6 + delta).ravel()[cells]
        top = np.argpartition(-prio, budget)[:budget]
        cells = cells[top]
    return cells


def main():
    import tkinter as tk
    import tkinter.font as tkf

    root = tk.Tk()
    root.title("Eye -> Space -> Bouquet -> Potret -> Love Heart")
    root.resizable(False, False)
    root.configure(bg=BG)
    root.bind("<Escape>", lambda e: root.destroy())

    fams = set(tkf.families())
    mono = next((f for f in ("Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Liberation Mono",
                             "Courier New", "Courier") if f in fams), "Courier")
    scr_h = root.winfo_screenheight()
    fnt = tkf.Font(root=root, family=mono, size=FONT_SIZE, weight="bold")
    ch = fnt.metrics("linespace")
    cw = fnt.measure("M")
    rows = max(20, min(MAXROWS, (scr_h - 110) // ch))
    seq = Sequence(cw, ch, rows)
    cols, rows = seq.cols, seq.rows
    W, H = cols * cw, rows * ch
    root.geometry(f"{W}x{H}+{(root.winfo_screenwidth() - W) // 2}+{max(0, (scr_h - H) // 2 - 20)}")
    cv = tk.Canvas(root, width=W, height=H, bg=BG, highlightthickness=0)
    cv.pack()

    heart = None
    if seq.has_heart:
        heart_mod = load("love_heart", "love.py")
        heart = heart_mod.LoveHeart(cv, W, H, duration=HEART_TIME)

    items = np.zeros((rows, cols), dtype=object)
    items[:] = 0
    d_code = np.full((rows, cols), 32, np.int32)
    d_q = np.zeros((rows, cols, 3), np.int16)
    hexc = {}
    st = {"t0": time.perf_counter(), "budget": 2500, "cost": 0.012, "last": EYE_START}

    def hx(rgb):
        k = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        s_ = hexc.get(k)
        if s_ is None:
            s_ = "#%02x%02x%02x" % tuple(v * 255 // (eye.QL - 1) for v in k)
            hexc[k] = s_
        return s_

    def restart(_=None):
        st["t0"] = time.perf_counter()
        st["last"] = EYE_START
        seq.restart()
        if heart:
            heart.reset()

    root.bind("r", restart)
    root.bind("R", restart)
    cv.bind("<Button-1>", restart)

    def tick():
        t0 = time.perf_counter()
        te = (t0 - st["t0"]) + EYE_START
        if te - T_SWITCH >= seq.total:
            restart()
            te = EYE_START
        dt = min(max(te - st["last"], 0.0), 0.1)
        st["last"] = te
        code, q = seq.frame(te, dt)
        cells = plan_updates(code, q, d_code, d_q, st["budget"])
        t1 = time.perf_counter()
        for f in cells:
            r_, c_ = divmod(int(f), cols)
            cd = int(code[r_, c_])
            it = items[r_, c_]
            if cd == 32:
                if it != 0:
                    cv.itemconfig(it, text="")
                d_code[r_, c_] = 32
                d_q[r_, c_] = q[r_, c_]
                continue
            fill = hx(q[r_, c_])
            if it == 0:
                items[r_, c_] = cv.create_text((c_ + 0.5) * cw, (r_ + 0.5) * ch, text=chr(cd),
                                               fill=fill, font=fnt, anchor="center")
            else:
                cv.itemconfig(it, text=chr(cd), fill=fill)
            d_code[r_, c_] = cd
            d_q[r_, c_] = q[r_, c_]
        if heart and (te - T_SWITCH) >= seq.cells_end:
            th = (te - T_SWITCH) - seq.cells_end
            heart.update(th)
            k = clamp((th - (HEART_TIME + HEART_HOLD)) / HEART_FADE)
            if k > 0:
                heart.fade(k)
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