import json
import os
import threading
import time

import numpy as np
from flask import Flask, render_template, send_from_directory
from flask_sock import Sock

import transition as anim

CW, CH = 6, 13                     # perkiraan ukuran sel font 8 bold
FPS = 24
QL = anim.eye.QL

app = Flask(__name__)
sock = Sock(app)

BASE = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(BASE, "static")        # ganti kalau folder lagu Anda bernama lain
MUSIC_FILE = "cantik.mp3"

print("Folder lagu :", MUSIC_DIR)
print("Isi folder  :", os.listdir(MUSIC_DIR) if os.path.isdir(MUSIC_DIR) else "FOLDER TIDAK ADA")

@app.route("/lagu")
def lagu():
    return send_from_directory(MUSIC_DIR, MUSIC_FILE, conditional=True)

seq = anim.Sequence(CW, CH, anim.MAXROWS)
COLS, ROWS = seq.cols, seq.rows

META = json.dumps({
    "cols": COLS, "rows": ROWS, "cw": CW, "ch": CH, "bg": anim.BG,
    "heart": bool(seq.has_heart),
    "ht": anim.HEART_TIME, "hh": anim.HEART_HOLD, "hf": anim.HEART_FADE,
})

REC = np.dtype([("i", "<u2"), ("c", "<u2"), ("r", "u1"), ("g", "u1"), ("b", "u1")])

clients = set()
lock = threading.Lock()
state = {"code": np.full((ROWS, COLS), 32, np.int32),
         "q": np.zeros((ROWS, COLS, 3), np.int16)}


def pack(code, q, idx):
    rec = np.empty(len(idx), REC)
    rec["i"] = idx
    rec["c"] = code.ravel()[idx]
    rgb = (q.reshape(-1, 3)[idx].astype(np.int32) * 255 // (QL - 1)).astype(np.uint8)
    rec["r"], rec["g"], rec["b"] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    return rec.tobytes()


def broadcast(data):
    with lock:
        dead = []
        for ws in clients:
            try:
                ws.send(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            clients.discard(ws)


def loop():
    t0, last, was_empty = time.perf_counter(), anim.EYE_START, True
    last_sync = 0.0
    in_heart = False
    p_code = state["code"].copy()
    p_q = state["q"].copy()
    while True:
        t_frame = time.perf_counter()
        with lock:
            n = len(clients)
        if n == 0:
            was_empty = True
            in_heart = False
            time.sleep(0.2)
            continue
        if was_empty:                      # penonton pertama: mulai dari awal
            seq.restart()
            t0, last, was_empty = time.perf_counter(), anim.EYE_START, False
        te = (t_frame - t0) + anim.EYE_START
        if te - anim.T_SWITCH >= seq.total:
            seq.restart()
            t0, last = time.perf_counter(), anim.EYE_START
            te = anim.EYE_START
        dt = min(max(te - last, 0.0), 0.1)
        last = te
        if t_frame - last_sync >= 1.0:
            broadcast(json.dumps({"t": round(te, 2)}))
            last_sync = t_frame

        code, q = seq.frame(te, dt)
        diff = (code != p_code) | (np.abs(q - p_q).max(axis=2) >= 2)
        idx = np.flatnonzero(diff.ravel())
        if len(idx):
            broadcast(b"\x01" + pack(code, q, idx))
        p_code, p_q = code.copy(), q.copy()
        state["code"], state["q"] = p_code, p_q

        # sinyal waktu untuk fase Love Heart (digambar di browser)
        th = te - anim.T_SWITCH - seq.cells_end
        if seq.has_heart and th >= 0:
            broadcast(json.dumps({"h": round(th, 3)}))
            in_heart = True
        elif in_heart:
            broadcast('{"h":-1}')
            in_heart = False

        time.sleep(max(0.001, 1 / FPS - (time.perf_counter() - t_frame)))


@app.route("/")
def index():
    return render_template("index.html")


@sock.route("/ws")
def ws(ws):
    ws.send(META)
    ws.send(b"\x00" + pack(state["code"], state["q"], np.arange(ROWS * COLS)))
    with lock:
        clients.add(ws)
    try:
        while True:
            ws.receive()                   # jaga koneksi tetap hidup
    except Exception:
        pass
    finally:
        with lock:
            clients.discard(ws)


threading.Thread(target=loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)