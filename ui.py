"""ui.py - komponen antarmuka (satu kanvas): kaca asli (Pillow), kartu bento, tombol soft, tabel kustom, animasi, kerangka jendela
(Jendela), serta halaman Pengaturan dan Pintasan. Bisa dijalankan sendiri: python ui.py"""
import math
import os
import re
import shutil
import itertools
import time
import tkinter as tk
import tkinter.font as tkfont
import traceback
from datetime import datetime

try:  # efek kaca asli butuh Pillow (pip install pillow); tanpa itu dipakai tampilan sederhana
    from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageTk
    ADA_PIL = True
except ImportError:
    ADA_PIL = False

from models import AKSEN, FILE_CSV, KEYS, OPSI, P, Pengaturan, Penyimpanan, Transaksi, rp, tampil_kunci

W, H = 1060, 680

# ---------------------------------------------------------------- gaya visual
TEMA = {
    "terang": dict(bg1="#cdc6ff", bg2="#b3e9f1", orb=("#a78bfa", "#5eead4", "#f9a8d4"), kartu="#ffffff", alfa=.5, kilau=.16,
                   bayang=(40, 30, 110, 85), tepi_rgb="#ffffff", teks="#1f2347", redup="#6a6f95", acc="#6366f1", acc2="#14b8a6",
                   baik="#0f9f78", buruk="#e0476b", sh1="#bcb8e6", sh2="#ffffff", tepi=.85),
    "gelap": dict(bg1="#080c1c", bg2="#0c1a30", orb=("#4f46e5", "#0d9488", "#a21caf"), kartu="#ffffff", alfa=.075, kilau=.07,
                  bayang=(0, 0, 10, 170), tepi_rgb="#9fb0ff", teks="#eef0ff", redup="#9aa0c6", acc="#818cf8", acc2="#2dd4bf",
                  baik="#4ade9f", buruk="#ff7a98", sh1="#04060d", sh2="#1b2542", tepi=.2),
}


def campur(a, b, t):
    t = max(0.0, min(1.0, t))
    ra = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    rb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ra, rb))


class Gaya:
    _c = {}
    konteks = None  # warna rata-rata kartu kaca yang sedang diisi (efek asli)

    @classmethod
    def t(cls):
        kunci = (P["tema"], P["aksen"])
        if kunci not in cls._c:
            d, gelap = dict(TEMA[P["tema"]]), P["tema"] == "gelap"
            c = [campur(x, "#ffffff", .22) if gelap else x for x in AKSEN[P["aksen"]]]
            d.update(acc=c[0], acc2=c[1], orb=tuple(campur(x, d["bg1"], .25) if gelap else campur(x, "#ffffff", .3) for x in AKSEN[P["aksen"]]))
            cls._c[kunci] = d
        return cls._c[kunci]

    @classmethod
    def latar(cls):
        return campur(cls.t()["bg1"], cls.t()["bg2"], .5)

    @classmethod
    def kaca(cls, kuat=1.0):
        if cls.konteks:  # warna rata-rata kartu kaca aktif agar widget anak menyatu dengan latar kartu
            return cls.konteks if kuat <= 1 else campur(cls.konteks, "#ffffff", min(.35, .1 * (kuat - 1)))
        return campur(cls.latar(), cls.t()["kartu"], cls.t()["alfa"] * kuat * {"tipis": .6, "normal": 1.0, "tebal": 1.6}[P["kaca"]])

    @classmethod
    def tepi(cls):
        return campur(cls.latar(), "#ffffff", cls.t()["tepi"])


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_back(t, s=1.9):
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


class Animator:
    """Satu penjadwal untuk semua animasi: berbasis waktu (durasi tepat, frame dilewati bila lambat) dan satu timer saja."""
    daftar, jalan, root, hook = [], False, None, None

    @classmethod
    def sibuk(cls):
        return bool(cls.daftar)

    @classmethod
    def tambah(cls, w, fungsi, durasi, selesai, delay):
        cls.daftar.append((w, fungsi, durasi, selesai, time.perf_counter() + delay / 1000))
        cls.root = w._root()
        if not cls.jalan:
            cls.jalan = True
            cls.root.after(1, cls.tik)

    @classmethod
    def _aman(cls, fn, *a):
        try:
            fn(*a)
            return True
        except tk.TclError:  # widget sudah dihancurkan
            return False
        except Exception:  # satu animasi rusak tidak boleh menghentikan yang lain
            if cls.hook:
                cls.hook(traceback.format_exc())
            return False

    @classmethod
    def tik(cls):
        kini, antrean, cls.daftar, sisa = time.perf_counter(), cls.daftar, [], []
        for a in antrean:
            w, fungsi, durasi, selesai, t0 = a
            if kini < t0:
                sisa.append(a)
                continue
            f = min(1.0, (kini - t0) * 1000 / durasi) if durasi > 0 else 1.0  # durasi dalam ms, waktu dalam detik
            if not cls._aman(fungsi, f):
                continue
            if f < 1.0:
                sisa.append(a)
            elif selesai:
                cls._aman(selesai)
        cls.daftar = sisa + cls.daftar
        try:
            if cls.daftar:
                cls.root.after(16, cls.tik)
            else:
                cls.jalan = False
        except tk.TclError:
            cls.daftar, cls.jalan = [], False


def animasi(w, fungsi, durasi=500, selesai=None, delay=0, fps=60):
    """Jalankan fungsi(f), f naik 0..1 selama `durasi` ms (diskalakan oleh pengaturan kecepatan animasi)."""
    k = Pengaturan.kali()
    Animator.tambah(w, fungsi, durasi * k, selesai, delay * k)


class Kaca:
    """Efek kaca asli (Pillow): latar dikaburkan di belakang tiap kartu, lapisan putih, tepi bercahaya, bayangan lembut."""
    ORB = ((.12, .15, .34), (.9, .85, .38), (.62, .42, .22))
    _dasar, _lain, rusak = {}, {}, False

    @staticmethod
    def rgb(c):
        return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))

    @classmethod
    def aktif(cls):
        return ADA_PIL and P["kaca_mode"] == "asli" and not cls.rusak

    @classmethod
    def kunci(cls):
        return (P["tema"], P["aksen"], P["orb"], P["kaca"])

    @classmethod
    def dasar(cls, t):
        """Latar: gradasi + orb kabur (di-cache per tema/aksen)."""
        k = cls.kunci()[:3]
        if k not in cls._dasar:
            if len(cls._dasar) > 4:
                cls._dasar.clear()
            c1, c2 = cls.rgb(t["bg1"]), cls.rgb(t["bg2"])
            im = Image.new("RGB", (W, H))
            d = ImageDraw.Draw(im)
            for y in range(H):
                f = y / (H - 1)
                d.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * f) for a, b in zip(c1, c2)))
            if P["orb"] == "tampil":
                for (fx, fy, fr), c in zip(cls.ORB, t["orb"]):
                    m, r = Image.new("L", (W, H), 0), int(W * fr * .62)
                    ImageDraw.Draw(m).ellipse([W * fx - r, H * fy - r, W * fx + r, H * fy + r], fill=235)
                    im.paste(Image.new("RGB", (W, H), cls.rgb(c)), (0, 0), m.filter(ImageFilter.GaussianBlur(70)))
            cls._dasar[k] = im
        return cls._dasar[k]

    @classmethod
    def _simpan(cls, kunci, buat):
        if kunci not in cls._lain:
            if len(cls._lain) > 160:
                cls._lain.clear()
            cls._lain[kunci] = buat()
        return cls._lain[kunci]

    @classmethod
    def badan(cls, dasar, x, y, w, h, t):
        """Badan kartu: latar di belakangnya dikaburkan, diberi lapisan putih dan kilau atas. Mengembalikan (gambar, warna rata-rata)."""
        def buat():
            pad = 26
            kotak = (max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad))
            potong = dasar.crop(kotak)
            cw, ch = potong.size
            kecil = potong.resize((cw // 4 + 1, ch // 4 + 1), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3.5))  # blur cepat di resolusi kecil
            kabur = ImageEnhance.Color(kecil.resize((cw, ch), Image.BILINEAR)).enhance(1.2)
            dalam = kabur.crop((x - kotak[0], y - kotak[1], x - kotak[0] + w, y - kotak[1] + h))
            putih = Image.new("RGB", (w, h), cls.rgb(t["kartu"]))
            b = Image.blend(dalam, putih, min(.9, t["alfa"] * {"tipis": .7, "normal": 1.0, "tebal": 1.45}[P["kaca"]]))
            rata = b.resize((1, 1), Image.BOX).getpixel((0, 0))
            b = Image.blend(b, Image.new("RGB", (w, h), rata), .6)  # nyaris rata agar label di atasnya serasi
            kilau = ImageOps.invert(Image.linear_gradient("L").resize((w, h))).point(lambda v: int(v * t["kilau"]))
            b = Image.composite(putih, b, kilau)
            r = b.resize((1, 1), Image.BOX).getpixel((0, 0))
            return b, "#%02x%02x%02x" % r
        return cls._simpan(("badan", cls.kunci(), x, y, w, h), buat)

    @classmethod
    def ubin(cls, dasar, x, y, w, h, t):
        """Gambar RGBA kartu kaca (badan kabur + tepi bercahaya + bayangan). Mengembalikan (gambar, warna rata-rata, margin)."""
        def buat():
            badan, warna = cls.badan(dasar, x, y, w, h, t)
            m, s, R = 26, 3, max(6, min(22, h // 2 - 1))
            kanvas = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
            bayang = Image.new("RGBA", kanvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(bayang).rounded_rectangle([m + 3, m + 12, m + w - 3, m + h + 8], R + 2, fill=t["bayang"])
            kanvas = Image.alpha_composite(kanvas, bayang.filter(ImageFilter.GaussianBlur(10)))
            mask = Image.new("L", (w * s, h * s), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * s - 1, h * s - 1], R * s, fill=255)
            cincin = Image.new("L", (w * s, h * s), 0)
            ImageDraw.Draw(cincin).rounded_rectangle([0, 0, w * s - 1, h * s - 1], R * s, outline=255, width=int(1.8 * s))
            atas = ImageOps.invert(Image.linear_gradient("L").resize((w, h))).point(lambda v: 60 + v * 195 // 255)
            cincin = ImageChops.multiply(cincin.resize((w, h), Image.LANCZOS), atas)  # tepi lebih terang di atas
            b2 = badan.copy()
            b2.paste(Image.new("RGB", (w, h), cls.rgb(t["tepi_rgb"])), (0, 0), cincin)
            kanvas.paste(b2.convert("RGBA"), (m, m), mask.resize((w, h), Image.LANCZOS))
            return kanvas, warna, m
        return cls._simpan(("ubin", cls.kunci(), x, y, w, h), buat)


def hitung_naik(cv, item, nilai, fmt, akhir, awal, durasi=900):
    """Angka menghitung naik sambil memudar masuk (teks canvas)."""
    animasi(cv, lambda f: cv.itemconfig(item, text=fmt(nilai * ease_out(f)), fill=campur(awal, akhir, f * 2.2)), durasi)


def rr(x1, y1, x2, y2, r):
    """Titik poligon persegi membulat (dipakai dengan smooth=True)."""
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    return [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2,
            x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]


def wr(k):
    """Nama warna tema ('teks', 'acc', ...) atau kode hex."""
    return Gaya.t().get(k, k)


def pilih_huruf(root):
    """Pilih keluarga huruf terbaik yang tersedia di sistem (tampilan konsisten di Windows/macOS/Linux)."""
    ada = set(tkfont.families(root))
    return next((f for f in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", "Roboto", "Ubuntu", "Noto Sans", "DejaVu Sans", "Arial")
                 if f in ada), "Helvetica")


def pop(app, daftar, mulai=0, jeda=70, jarak=44, durasi=720):
    """Kartu muncul bergantian: meluncur dengan pantulan."""
    for i, k in enumerate(daftar):
        k.geser(3000)  # sembunyikan sampai gilirannya
        animasi(app.cv, lambda f, k=k: k.geser(round(jarak * (1 - ease_back(f)))), durasi, delay=mulai + i * jeda)


class Tombol:
    """Tombol soft di kanvas: bayangan gelap + sorotan terang (neumorphism), sorot halus saat hover, riak saat klik."""

    def __init__(s, k, dx, dy, w, h, teks, cmd, primer=False, aktif=False):
        s.k, s.cv, s.cmd, s.primer, s.aktif, s.hov, s.tekan, s.nafas, s.g = k, k.app.cv, cmd, primer, aktif, 0.0, False, 0.0, 0
        s.x, s.y, s.w, s.h, s.teks, s.tag = k.x + dx, k.y + dy, w, h, teks, f"b{next(Kartu._n)}"
        cv, t, tg = s.cv, Gaya.t(), (k.tag, s.tag)
        s.sg = cv.create_polygon(rr(s.x + 2, s.y + 4, s.x + w + 2, s.y + h + 4, h / 2), smooth=True, outline="", tags=tg,
                                 fill=campur(k.warna, t["sh1"], .85))
        s.st = cv.create_polygon(rr(s.x - 1, s.y - 2, s.x + w - 1, s.y + h - 2, h / 2), smooth=True, outline="", tags=tg,
                                 fill=campur(k.warna, t["sh2"], .9 if P["tema"] == "terang" else .6))
        s.bd = cv.create_polygon(rr(s.x, s.y, s.x + w, s.y + h, h / 2), smooth=True, outline="", fill=k.warna, tags=tg)
        s.tx = cv.create_text(s.x + w / 2, s.y + h / 2, text=teks, font=k.app.f(10, True), tags=tg)
        for ev, fn in (("<Enter>", lambda e: s.sorot(1.0)), ("<Leave>", lambda e: s.sorot(0.0)),
                       ("<ButtonPress-1>", s.tekan_), ("<ButtonRelease-1>", s.lepas)):
            cv.tag_bind(s.tag, ev, fn)
        s.warnai()
        if primer:
            s._napas()

    def warnai(s):
        t, terang = Gaya.t(), s.primer or s.aktif
        dasar = t["acc"] if terang else (campur(s.k.warna, "#ffffff", .45) if P["tema"] == "terang" else campur(s.k.warna, t["sh2"], .6))
        s.cv.itemconfig(s.bd, fill=campur(dasar, "#ffffff", .18 * (s.hov + s.nafas)))
        s.cv.itemconfig(s.tx, fill="#ffffff" if terang else t["teks"])

    def sorot(s, ke):
        s.g += 1
        g, awal = s.g, s.hov
        s.cv.config(cursor="hand2" if ke else "")

        def langkah(f):
            if g == s.g:
                s.hov = awal + (ke - awal) * f
                s.warnai()
        animasi(s.cv, langkah, 140)

    def tekan_(s, e):
        s.tekan = True
        for i in (s.sg, s.st):
            s.cv.itemconfig(i, state="hidden")
        s.cv.move(s.bd, 2, 2)
        s.cv.move(s.tx, 2, 2)

    def lepas(s, e):
        if not s.tekan:
            return
        s.tekan = False
        for i in (s.sg, s.st):
            s.cv.itemconfig(i, state="normal")
        s.cv.move(s.bd, -2, -2)
        s.cv.move(s.tx, -2, -2)
        kotak = s.cv.bbox(s.bd)
        if kotak and kotak[0] <= e.x <= kotak[2] and kotak[1] <= e.y <= kotak[3]:  # dilepas di luar tombol = batal
            s.riak(e.x, e.y)
            s.cmd()

    def riak(s, x, y):
        o = s.cv.create_oval(x, y, x, y, outline="", width=2, tags=s.k.tag)

        def f(p):
            r = p * s.w * .7
            s.cv.coords(o, x - r, y - r, x + r, y + r)
            s.cv.itemconfig(o, outline=campur("#ffffff", s.k.warna, p))
        animasi(s.cv, f, 380, selesai=lambda: s.cv.delete(o))

    def pasang(s, aktif):
        s.aktif = aktif
        s.warnai()

    def ubah_teks(s, teks):
        s.teks = teks
        s.cv.itemconfig(s.tx, text=teks)

    def _napas(s):  # tombol utama berdenyut halus saat diam
        if not s.cv.find_withtag(s.tag):
            return
        if P["anim"] != "mati" and s.hov < .01 and not Animator.sibuk():
            s.nafas = .4 * (1 + math.sin(time.time() * 2.2))
            s.warnai()
        s.cv.after(70, s._napas)


class Tabel:
    """Tabel kustom di kanvas (tanpa widget tertanam): judul kolom bisa diklik untuk mengurutkan, baris bergaris halus, sorot saat
    hover, pilih baris, gulir roda mouse. kolom = [(judul, pecahan lebar, rata 'w'/'e')]; baris = [(kunci, [sel])], sel = teks atau (teks, warna).
    Hanya baris yang muat utuh yang digambar, jadi tidak perlu pemotongan."""
    BH, BR = 32, 30

    def __init__(s, k, dx, dy, w, h, kolom, urut=None, dobel=None):
        s.k, s.cv, s.w, s.h, s.kolom, s.urut, s.dobel = k, k.app.cv, w, h, kolom, urut, dobel
        s.x, s.y, s.rows, s.off, s.pilih, s.hov, s.tampil, s.gen, s.tanda = k.x + dx, k.y + dy, [], 0, None, None, 0, 0, {}
        t, terang = Gaya.t(), P["tema"] == "terang"
        s.t, s.dasar = t, campur(k.warna, "#ffffff" if terang else "#000000", .32 if terang else .25)
        s.tag = f"t{next(Kartu._n)}"
        s.hit = s.cv.create_polygon(rr(s.x, s.y, s.x + w, s.y + h, 10), smooth=True, fill=s.dasar, outline=t["sh1"], tags=k.tag)
        k.app.tabel.append(s)
        s.gambar()

    def isi(s, rows, cascade=False):
        s.rows, s.off, s.pilih, s.gen = rows, 0, None, s.gen + 1
        s.tampil = 0 if cascade else len(rows)
        s.gambar()
        if cascade:
            s._muncul(s.gen)

    def _muncul(s, g):  # baris muncul satu per satu
        if g != s.gen or not s.cv.coords(s.hit):  # halaman sudah diganti -> berhenti
            return
        s.tampil += 1
        s.gambar()
        if s.tampil < min(len(s.rows), 14):
            s.cv.after(45, lambda: s._muncul(g))
        else:
            s.tampil = len(s.rows)
            s.gambar()

    def terpilih(s):
        return s.rows[s.pilih][0] if s.pilih is not None and s.pilih < len(s.rows) else None

    def lihat(s):
        return (s.h - s.BH - 6) // s.BR

    def lokal(s, e):
        """Koordinat kursor relatif terhadap tabel (posisi terkini, ikut animasi kartu), atau None bila di luar."""
        b = s.cv.coords(s.hit)
        if not b:
            return None
        x, y = e.x - min(b[0::2]), e.y - min(b[1::2])
        return (x, y) if 0 <= x <= s.w and 0 <= y <= s.h else None

    def baris_di(s, y):
        if y < s.BH:
            return None
        i = s.off + int((y - s.BH) // s.BR)
        return i if i < min(s.tampil, len(s.rows), s.off + s.lihat()) else None

    def mouse(s, e):
        p = s.lokal(e)
        i = s.baris_di(p[1]) if p else None
        if i != s.hov:
            s.hov = i
            s.gambar()

    def gulir(s, d):
        s.off = min(max(0, s.off + 2 * d), max(0, len(s.rows) - s.lihat()))
        s.gambar()

    def klik(s, x, y):
        if y < s.BH:
            kiri = 0
            for i, (_, f, _) in enumerate(s.kolom):
                kiri += f * s.w
                if x < kiri:
                    return s.urut(i) if s.urut else None
            return None
        i = s.baris_di(y)
        if i is not None:
            s.pilih = i
            s.gambar()

    def klik_dobel(s, x, y):
        if s.dobel and s.baris_di(y) is not None:
            s.dobel()

    def gambar(s):
        c, t, f, tg = s.cv, s.t, s.k.app.f, (s.k.tag, s.tag)
        c.delete(s.tag)
        c.create_polygon(rr(s.x, s.y, s.x + s.w, s.y + s.BH, 10), smooth=True, fill=campur(s.dasar, t["acc"], .12), outline="", tags=tg)
        x = s.x
        for j, fr, rata in s.kolom:
            lb = fr * s.w
            c.create_text(x + (lb - 14 if rata == "e" else 14), s.y + s.BH / 2, text=j + s.tanda.get(j, ""), anchor=rata, fill=t["redup"], font=f(9, True), tags=tg)
            x += lb
        for n in range(s.off, min(len(s.rows), s.tampil, s.off + s.lihat())):
            y = s.y + s.BH + (n - s.off) * s.BR
            lat = campur(s.dasar, t["acc"], .28) if n == s.pilih else campur(s.dasar, t["acc"], .12) if n == s.hov else campur(s.dasar, t["teks"], .035) if n % 2 else None
            if lat:
                c.create_rectangle(s.x + 1, y, s.x + s.w - 1, y + s.BR, fill=lat, outline="", tags=tg)
            x = s.x
            for (_, fr, rata), sel in zip(s.kolom, s.rows[n][1]):
                lb = fr * s.w
                teks, warna = sel if isinstance(sel, tuple) else (sel, "teks")
                c.create_text(x + (lb - 14 if rata == "e" else 14), y + s.BR / 2, text=teks, anchor=rata, fill=wr(warna), font=f(10), tags=tg)
                x += lb
        if len(s.rows) > s.lihat():  # bilah gulir tipis
            tinggi, total = s.h - s.BH - 10, len(s.rows)
            jempol = max(24, tinggi * s.lihat() / total)
            y0 = s.y + s.BH + 5 + (tinggi - jempol) * s.off / max(1, total - s.lihat())
            c.create_polygon(rr(s.x + s.w - 8, y0, s.x + s.w - 4, y0 + jempol, 2), smooth=True, fill=campur(s.dasar, t["acc"], .45), outline="", tags=tg)


class Kartu:
    """Kartu kaca di kanvas utama. Semua isinya (teks, tombol, grafik) memakai tag yang sama sehingga bergerak bersama."""
    _n = itertools.count()

    def __init__(s, app, x, y, w, h, hover=False):
        s.app, s.x, s.y, s.w, s.h, s.hover = app, x, y, w, h, hover
        s.tag, s.dp, s.dh, s.naik, s.g, s.widgets = f"k{next(Kartu._n)}", 0.0, 0.0, False, 0, []
        cv, t, ok = app.cv, Gaya.t(), False
        if Kaca.aktif():
            try:
                img, s.warna, m = Kaca.ubin(Kaca.dasar(t), x, y, w, h, t)
                s.foto = ImageTk.PhotoImage(img)
                cv.create_image(x - m, y - m, anchor="nw", image=s.foto, tags=s.tag)
                ok = True
            except Exception:  # Pillow bermasalah: catat lalu pakai tampilan sederhana
                Kaca.rusak = True
                app.catat(traceback.format_exc())
        if not ok:  # cadangan tanpa Pillow: poligon datar bertepi + bayangan
            s.warna = Gaya.kaca()
            cv.create_polygon(rr(x + 2, y + 7, x + w + 2, y + h + 7, 20), smooth=True, fill=campur(Gaya.latar(), "#000000", .1), outline="", tags=s.tag)
            cv.create_polygon(rr(x, y, x + w, y + h, 20), smooth=True, fill=s.warna, outline=Gaya.tepi(), tags=s.tag)

    def geser(s, dy):
        s.app.cv.move(s.tag, 0, dy - s.dp)
        s.dp = dy

    def angkat(s, naik):  # terangkat sedikit saat kursor di atas kartu
        s.g += 1
        g, awal = s.g, s.dh

        def langkah(f):
            if g == s.g:
                nilai = awal + ((-5 if naik else 0) - awal) * ease_out(f)
                s.app.cv.move(s.tag, 0, nilai - s.dh)
                s.dh = nilai
        animasi(s.app.cv, langkah, 180)

    def hapus(s):
        s.app.cv.delete(s.tag)
        for w in s.widgets:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def teks(s, dx, dy, t, ukuran=11, tebal=False, warna="teks", anchor="nw"):
        return s.app.cv.create_text(s.x + dx, s.y + dy, text=t, anchor=anchor, fill=wr(warna), font=s.app.f(ukuran, tebal), tags=s.tag)

    def judul(s, t):
        return s.teks(18, 14, t.upper(), 8, True, "redup")

    def tombol(s, dx, dy, w, h, teks, cmd, primer=False, aktif=False):
        return Tombol(s, dx, dy, w, h, teks, cmd, primer, aktif)

    def input(s, dx, dy, w, h=34, awal=""):
        """Kolom isian: bidang membulat datar di kanvas + Entry dengan warna yang sama persis (tanpa kotak janggal)."""
        cv, t, terang = s.app.cv, Gaya.t(), P["tema"] == "terang"
        isi = campur(s.warna, "#ffffff" if terang else "#000000", .5 if terang else .28)
        bg = cv.create_polygon(rr(s.x + dx, s.y + dy, s.x + dx + w, s.y + dy + h, 12), smooth=True, fill=isi, outline=t["sh1"], tags=s.tag)
        e = tk.Entry(cv, font=s.app.f(11), bg=isi, fg=t["teks"], insertbackground=t["teks"], relief="flat", bd=0, highlightthickness=0)
        e.insert(0, awal)
        cv.create_window(s.x + dx + 12, s.y + dy + 7, window=e, anchor="nw", width=w - 24, height=h - 14, tags=s.tag)
        e.bind("<FocusIn>", lambda ev: cv.itemconfig(bg, outline=t["acc"], width=2))
        e.bind("<FocusOut>", lambda ev: cv.itemconfig(bg, outline=t["sh1"], width=1))
        s.widgets.append(e)
        return e

    def kolom(s, dx, dy, w, label, awal=""):
        s.teks(dx, dy, label, 9, False, "redup")
        return s.input(dx, dy + 17, w, 34, awal)

    def tabel(s, dx, dy, w, h, kolom, urut=None, dobel=None):
        return Tabel(s, dx, dy, w, h, kolom, urut, dobel)


PALET = ["#6366f1", "#14b8a6", "#f472b6", "#f59e0b", "#38bdf8", "#a78bfa"]


def halaman_pengaturan(app):
    cv, grup = app.cv, {}

    def ubah(kunci, nilai):
        if kunci in ("tema", "aksen", "kaca"):
            app.riak_tema(lambda: P.__setitem__(kunci, nilai))
        elif kunci in ("orb", "font", "kaca_mode"):
            P[kunci] = nilai
            app.terapkan()
        else:  # tidak perlu bangun ulang: cukup perbarui status tombol (lebih mulus)
            P[kunci] = nilai
            Pengaturan.simpan()
            for v, b in grup.get(kunci, []):
                b.pasang(P[kunci] == v)

    def kartu(fx, nama, daftar):
        k = app.kartu(fx, 0, .49, .79)
        k.judul(nama)
        y = 44
        for kunci in daftar:
            label, opsi = next(((n, o) for kk, n, o in OPSI if kk == kunci), ("Warna aksen", None))
            k.teks(18, y + 7, label, 10, False, "redup")
            x = 160
            if opsi is None:  # warna aksen: lingkaran dua warna
                for a, (c1, c2, _) in AKSEN.items():
                    cx, cy = k.x + x + 15, k.y + y + 15
                    tg = (k.tag, f"sw_{a}")
                    cv.create_arc(cx - 13, cy - 13, cx + 13, cy + 13, start=45, extent=180, fill=c1, outline=c1, tags=tg)
                    cv.create_arc(cx - 13, cy - 13, cx + 13, cy + 13, start=225, extent=180, fill=c2, outline=c2, tags=tg)
                    if P["aksen"] == a:
                        cv.create_oval(cx - 16, cy - 16, cx + 16, cy + 16, outline=Gaya.t()["teks"], width=2, tags=k.tag)
                    cv.tag_bind(f"sw_{a}", "<Button-1>", lambda e, a=a: ubah("aksen", a))
                    x += 38
            else:
                lb = max(64, 300 // len(opsi))
                for nilai, teks in opsi:
                    b = k.tombol(x, y, lb, 30, teks, lambda kk=kunci, v=nilai: ubah(kk, v), aktif=P[kunci] == nilai)
                    grup.setdefault(kunci, []).append((nilai, b))
                    x += lb + 6
            y += 40
    kartu(0, "Tampilan", ["tema", "aksen", "kaca", "kaca_mode", "orb", "font", "anim", "splash"])
    kartu(.51, "Perilaku", ["mata", "format", "desimal", "awal", "konfirmasi", "toast", "jual"])
    d = app.kartu(0, .81, 1, .19)
    d.judul("Data & pengaturan")

    def reset():
        Pengaturan.reset()
        app.terapkan()
        app.toast("Pengaturan dikembalikan ke bawaan")
    d.tombol(18, 40, 150, 32, "Cadangkan data", app.cadangkan)
    d.tombol(176, 40, 150, 32, "Reset pengaturan", reset)
    d.tombol(334, 40, 130, 32, "Muat contoh", app.contoh)
    d.teks(d.w - 18, 56, ("Efek kaca asli butuh Pillow: pip install pillow  ·  " if not ADA_PIL else "") + "Disimpan di pengaturan.json",
           8, False, "redup", "e")


def halaman_pintasan(app):
    """Pengubah keybind: klik tombol, tekan kombinasi baru (wajib Ctrl/Alt atau F1-F12), Esc untuk batal."""
    modifier = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R", "Super_L", "Super_R",
                "Caps_Lock", "ISO_Level3_Shift", "Num_Lock"}

    def tangkap(id_, label, tombol):
        if app.menangkap:
            return
        app.menangkap = True
        app.root.focus_force()
        tombol.ubah_teks("Tekan tombol…")

        def selesai(pesan=None, ok=False):
            app.menangkap = False
            app.root.unbind_all("<KeyPress>")
            if pesan:
                app.toast(pesan, ok)
            app.segarkan()

        def tekan(e):
            if e.keysym in modifier:
                return
            if e.keysym == "Escape":
                return selesai()
            mod = ("Control-" if e.state & 4 else "") + ("Alt-" if e.state & 0x20008 else "")
            if not mod and not (e.keysym.startswith("F") and e.keysym[1:].isdigit()):
                return selesai("Gunakan Ctrl/Alt atau tombol F1-F12", False)
            seq = f"<{mod}Key-{e.keysym}>"
            lain = next((n for k2, n, _ in KEYS if k2 != id_ and P["keybind"].get(k2) == seq), None)
            if lain:
                return selesai(f"Sudah dipakai: {lain}", False)
            P["keybind"][id_] = seq
            Pengaturan.simpan()
            app.pasang_keybind()
            selesai(f"{label}: {tampil_kunci(seq)}", True)
        app.root.bind_all("<KeyPress>", tekan)

    def kembalikan(id_, bawaan):
        P["keybind"][id_] = bawaan
        Pengaturan.simpan()
        app.pasang_keybind()
        app.segarkan()

    def kartu(fx, nama, daftar):
        k = app.kartu(fx, 0, .49, .72)
        k.judul(nama)
        for n, (id_, label, bawaan) in enumerate(daftar):
            y = 44 + n * 44
            k.teks(18, y + 8, label, 10, False, "teks")
            tb = k.tombol(230, y, 130, 32, tampil_kunci(P["keybind"][id_]), lambda: None)
            tb.cmd = lambda i=id_, l=label, b=tb: tangkap(i, l, b)
            k.tombol(370, y, 44, 32, "↺", lambda i=id_, d=bawaan: kembalikan(i, d))
    kartu(0, "Navigasi", KEYS[:6])
    kartu(.51, "Aksi", KEYS[6:])
    b = app.kartu(0, .74, 1, .26)
    b.judul("Cara memakai")
    b.teks(18, 40, "Klik tombol pintasan, lalu tekan kombinasi baru (wajib memakai Ctrl/Alt atau tombol F1-F12). Esc membatalkan.\n"
                   "Kombinasi yang sudah dipakai ditolak. Tombol ↺ mengembalikan satu pintasan ke bawaan.", 10, False, "redup")

    def reset_semua():
        P["keybind"].clear()
        P["keybind"].update({k: d for k, _, d in KEYS})
        Pengaturan.simpan()
        app.pasang_keybind()
        app.segarkan()
        app.toast("Semua pintasan dikembalikan")
    b.tombol(18, b.h - 56, 190, 34, "Reset semua pintasan", reset_semua)


class types_e:
    """Titik kursor sederhana (x, y) untuk uji posisi."""
    def __init__(self, x, y):
        self.x, self.y = x, y


class Jendela:
    """Kerangka jendela (satu kanvas): latar, header, tab, toast, tema, pintasan. Menerima halaman [(nama, fungsi)]."""

    def __init__(self, halaman, judul="Portofolio Crypto & Uang"):
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)  # teks tajam di layar HiDPI
            except Exception:
                pass
        self.hal, self.judul = halaman, judul
        self.top = 148 if len(halaman) > 1 else 92  # tanpa bilah tab, konten naik
        self.LB, self.TB = 1016, 660 - self.top
        self.root = r = tk.Tk()
        r.title(judul)
        r.resizable(False, False)
        r.report_callback_exception = self.lapor
        Animator.hook = self.catat
        self.fam = pilih_huruf(r)
        self.cv = tk.Canvas(r, width=W, height=H, highlightthickness=0, bd=0)
        self.cv.place(x=0, y=0, width=W, height=H)
        self.isi, self.hias, self.tab, self.tt, self.ind, self.gen, self._ix, self.tabel = [], [], [], None, None, 0, 0, []
        self._kb, self.menangkap, self.cari_cb, self.simpan_cb, self._ink, self.edit = [], False, None, None, False, None
        self.halaman = next((i for i, (n, _) in enumerate(halaman) if n == P["awal"]), 0)
        x, y = (r.winfo_screenwidth() - W) // 2, (r.winfo_screenheight() - H) // 2
        self.alpha(0)
        r.geometry(f"{W}x{H}+{x}+{y}")
        self.cv.bind("<Motion>", self._gerak)
        self.cv.bind("<Button-1>", lambda e: self._tabel(e, "klik"))
        self.cv.bind("<Double-1>", lambda e: self._tabel(e, "klik_dobel"))
        self.cv.bind("<MouseWheel>", lambda e: self._roda(-1 if e.delta > 0 else 1))
        self.cv.bind("<Button-4>", lambda e: self._roda(-1))
        self.cv.bind("<Button-5>", lambda e: self._roda(1))
        self.latar()
        self.pasang_keybind()
        self.splash() if P["splash"] == "tampil" else self.bangun()
        animasi(r, lambda f: self.alpha(ease_out(f)), 420)  # memudar masuk

    def alpha(self, v):
        try:
            self.root.attributes("-alpha", v)
        except tk.TclError:
            pass

    def f(self, ukuran, tebal=False):
        """Huruf berukuran piksel tetap (tidak terpengaruh skala DPI), diskalakan oleh pengaturan ukuran teks."""
        return (self.fam, -round(ukuran * 1.36 * {"kecil": .9, "normal": 1.0, "besar": 1.12}[P["font"]]), "bold" if tebal else "normal")

    def latar(self):
        cv, t = self.cv, Gaya.t()
        cv.delete("all")
        if Kaca.aktif():  # gradasi + orb kabur hasil Pillow
            try:
                self._dasar_foto = ImageTk.PhotoImage(Kaca.dasar(t))
                cv.create_image(0, 0, anchor="nw", image=self._dasar_foto)
                return
            except Exception:
                Kaca.rusak = True
                self.catat(traceback.format_exc())
        self._bg = tk.PhotoImage(width=1, height=H)  # gradasi vertikal: 1 piksel lebar lalu diperlebar (ringan)
        self._bg.put(" ".join("{%s}" % campur(t["bg1"], t["bg2"], i / (H - 1)) for i in range(H)))
        self._bgz = self._bg.zoom(W, 1)
        cv.create_image(0, 0, anchor="nw", image=self._bgz)
        for k, (fx, fy, fr) in enumerate(((.12, .15, .32), (.9, .85, .36), (.62, .4, .2)) if P["orb"] == "tampil" else ()):
            dasar = campur(t["bg1"], t["bg2"], fy)
            for j in range(9):  # lingkaran bertumpuk = orb berpendar lembut
                rr_ = W * fr * (1 - j / 9)
                cv.create_oval(W * fx - rr_, H * fy - rr_, W * fx + rr_, H * fy + rr_, width=0,
                               fill=campur(dasar, t["orb"][k], .04 + .5 * (j / 8) ** 2))

    def kartu(self, fx, fy, fw, fh, hover=False):
        """Kartu bento di area konten (pecahan 0..1)."""
        k = Kartu(self, round(22 + self.LB * fx), round(self.top + self.TB * fy), round(self.LB * fw), round(self.TB * fh), hover)
        self.isi.append(k)
        return k

    def _tabel(self, e, aksi):
        for tb in self.tabel:
            p = tb.lokal(e)
            if p:
                getattr(tb, aksi)(*p)

    def _roda(self, d):
        x, y = self.root.winfo_pointerx() - self.root.winfo_rootx(), self.root.winfo_pointery() - self.root.winfo_rooty()
        for tb in self.tabel:
            if tb.lokal(types_e(x, y)):
                tb.gulir(d)

    def _gerak(self, e):  # kartu yang di-hover terangkat, tabel menyorot baris
        for tb in self.tabel:
            tb.mouse(e)
        for k in self.isi:
            if k.hover:
                di = k.x <= e.x <= k.x + k.w and k.y + k.dp <= e.y <= k.y + k.dp + k.h
                if di != k.naik:
                    k.naik = di
                    k.angkat(di)

    def splash(self):
        k = Kartu(self, 360, 230, 340, 224)
        self.hias.append(k)
        t, cv = Gaya.t(), self.cv
        cv.create_text(k.x + 170, k.y + 52, text="◆", font=self.f(20, True), fill=t["acc"], tags=k.tag)
        busur = cv.create_arc(k.x + 142, k.y + 24, k.x + 198, k.y + 80, style="arc", width=3, outline=t["acc2"], start=0, extent=110, tags=k.tag)
        k.teks(170, 100, self.judul, 12, True, anchor="n")
        ket = k.teks(170, 128, "Menyiapkan aplikasi…", 9, False, "redup", "n")
        x0, y0 = k.x + 40, k.y + 168
        cv.create_polygon(rr(x0, y0, x0 + 260, y0 + 8, 4), smooth=True, fill=campur(k.warna, t["sh1"], .5), outline="", tags=k.tag)
        isi = cv.create_polygon(rr(x0, y0, x0 + 8, y0 + 8, 4), smooth=True, fill=t["acc"], outline="", tags=k.tag)
        tahap = ((.35, "Memuat transaksi…"), (.7, "Menyusun portofolio…"), (1.01, "Siap! ✨"))

        def putar():  # spinner berputar terus selama splash
            if not cv.find_withtag(k.tag):
                return
            cv.itemconfig(busur, start=(time.time() * 320) % 360)
            cv.after(16, putar)
        putar()

        def maju(f):
            cv.coords(isi, *rr(x0, y0, x0 + max(8, 260 * f), y0 + 8, 4))
            cv.itemconfig(ket, text=next(tx for b, tx in tahap if f < b))

        def keluar():
            animasi(cv, lambda f: k.geser(70 * f * f), 260, selesai=lambda: (k.hapus(), self.hias.remove(k), self.bangun()))
        animasi(cv, maju, 1300, selesai=keluar)

    def bangun(self, animasi_=True):
        for k in self.hias + self.isi:
            k.hapus()
        self.hias, self.isi, self.tab, self.ind, self.tabel = [], [], [], None, []
        self.latar()
        t = Gaya.t()
        h = Kartu(self, 22, 18, 1016, 60)
        self.hias.append(h)
        self.kilau(h.teks(22, 30, "◆  " + self.judul, 15, True, "acc", "w"))
        h.tombol(h.w - 106, 13, 90, 34, "Tema", self.ganti_tema)
        h.teks(h.w - 124, 30, "bukan harga pasar real-time", 9, False, "redup", "e")
        bar = None
        if len(self.hal) > 1:
            bar = Kartu(self, 22, 86, len(self.hal) * 128 + 20, 48)
            self.hias.append(bar)
            for i, (nama, _) in enumerate(self.hal):
                self.tab.append(bar.tombol(10 + 128 * i, 7, 116, 34, nama, lambda i=i: self.buka(i)))
            self._ix = 10 + 128 * self.halaman
            self.ind = self.cv.create_polygon(rr(bar.x + self._ix, bar.y + 42, bar.x + self._ix + 116, bar.y + 45, 1.5), smooth=True,
                                              fill=t["acc2"], outline="", tags=bar.tag)  # garis penanda tab yang meluncur
        self.buka(self.halaman, False)
        if animasi_:
            pop(self, [h], jarak=-40)
            if bar:
                pop(self, [bar], mulai=120, jarak=-30)
            pop(self, self.isi, mulai=260)

    def buka(self, i, animasi_=True):
        """Buka halaman menurut indeks atau nama; False bila halaman itu tidak ada di jendela ini."""
        if isinstance(i, str):
            i = next((j for j, (n, _) in enumerate(self.hal) if n == i), None)
        if i is None or not 0 <= i < len(self.hal):
            return False
        if animasi_ and i == self.halaman and self.isi:  # sudah di tab ini
            return True
        self.halaman = i
        self.gen += 1
        g, lama = self.gen, self.isi
        self.isi = []
        for j, p in enumerate(self.tab):
            p.pasang(j == i)
        self.geser(i)

        def baru():
            for k in lama:
                k.hapus()
            if g != self.gen:  # sudah ada perpindahan yang lebih baru
                return
            self.cari_cb = self.simpan_cb = None
            self.tabel = []
            self.hal[i][1](self)
            if animasi_:
                pop(self, self.isi)
        if animasi_ and lama:  # halaman lama meluncur turun sebelum diganti
            animasi(self.cv, lambda f: [k.geser(30 * f * f) for k in lama], 180, selesai=baru)
        else:
            baru()
        return True

    def geser(self, i):
        if not self.ind:
            return
        a, b = self._ix, 10 + 128 * i

        def langkah(f):
            nilai = a + (b - a) * ease_out(f)
            self.cv.move(self.ind, nilai - self._ix, 0)
            self._ix = nilai
        animasi(self.cv, langkah, 300)

    def kilau(self, item):  # judul berganti warna pelan-pelan
        t = Gaya.t()

        def j():
            if not self.cv.type(item):
                return
            if not Animator.sibuk():
                self.cv.itemconfig(item, fill=campur(t["acc"], t["acc2"], ((math.sin(time.time() * 1.6) + 1) / 2) * (P["anim"] != "mati")))
            self.cv.after(90, j)
        j()

    def segarkan(self):
        self.buka(self.halaman, False)

    def ganti_tema(self):
        self.riak_tema(lambda: P.__setitem__("tema", "gelap" if P["tema"] == "terang" else "terang"))

    def riak_tema(self, perubahan):
        """Perubahan tampilan dengan 'tinta': kotak warna latar baru membesar dari kursor, UI dibangun ulang, lalu menyusut."""
        perubahan()
        if P["anim"] == "mati" or self._ink:
            return self.terapkan()
        self._ink = True
        x, y = self.root.winfo_pointerx() - self.root.winfo_rootx(), self.root.winfo_pointery() - self.root.winfo_rooty()
        ink, R = tk.Frame(self.root, bg=Gaya.latar()), 1300

        def pos(r):
            ink.place(x=round(x - r), y=round(y - r), width=round(2 * r), height=round(2 * r))

        def ganti():
            self.terapkan()
            ink.tkraise()
            animasi(ink, lambda f: pos(R * (1 - ease_out(f))), 420, selesai=lambda: (ink.destroy(), setattr(self, "_ink", False)))
        animasi(ink, lambda f: pos(R * ease_out(f)), 420, selesai=ganti)

    def terapkan(self):
        """Simpan pengaturan lalu bangun ulang tampilan (tab aktif dipertahankan)."""
        Pengaturan.simpan()
        self.bangun(False)

    def pasang_keybind(self):
        for s in self._kb:
            self.root.unbind(s)
        self._kb = []
        aksi = {"tab_" + n.lower(): (lambda i=i: self.buka(i)) for i, (n, _) in enumerate(self.hal)}
        aksi.update(tema=self.ganti_tema, cari=self.fokus_cari, cadang=self.cadangkan, simpan=lambda: self.simpan_cb and self.simpan_cb())
        for id_, fn in aksi.items():
            seq = P["keybind"].get(id_)
            m = re.search(r"-([a-z])>$", seq or "")
            for s in ([seq] + ([seq[:m.start(1)] + m.group(1).upper() + ">"] if m else [])) if seq else []:
                try:
                    self.root.bind(s, lambda e, fn=fn: None if self.menangkap else (fn(), "break")[1])
                    self.root.bind_class("Entry", s, lambda e: None)  # lepas pintasan emacs bawaan Entry (Ctrl+T/F/B)
                    self._kb.append(s)
                except tk.TclError:
                    pass

    def fokus_cari(self):
        self.buka("Riwayat")
        self.root.after(260, lambda: self.cari_cb and self.cari_cb())

    def cadangkan(self):
        try:
            folder = os.path.join(os.path.dirname(FILE_CSV), "cadangan")
            os.makedirs(folder, exist_ok=True)
            tujuan = os.path.join(folder, datetime.now().strftime("transaksi-%Y%m%d-%H%M%S.csv"))
            shutil.copyfile(FILE_CSV, tujuan)
        except OSError as e:
            return self.toast(f"Gagal mencadangkan: {e}", False)
        self.toast("Cadangan: " + os.path.basename(tujuan))

    def contoh(self):
        for a in (("2026-01-05", "IDR", "beli", 50000000, 1), ("2026-01-12", "BTC", "beli", .15, 1500000000),
                  ("2026-02-03", "ETH", "beli", 2.5, 45000000), ("2026-03-10", "BTC", "jual", .05, 1650000000),
                  ("2026-04-02", "SOL", "beli", 30, 2800000)):
            Penyimpanan.simpan(Transaksi(*a))
        self.toast("Data contoh ditambahkan")
        self.buka(0)

    def toast(self, teks, ok=True):
        cv, t = self.cv, Gaya.t()
        if self.tt:
            cv.delete(self.tt)
        tag = self.tt = f"toast{next(Kartu._n)}"
        lebar = max(190, len(teks) * 8 + 76)
        x0, y0 = W - lebar - 22, H - 74
        cv.create_polygon(rr(x0 + 2, y0 + 8, x0 + lebar + 2, y0 + 54, 20), smooth=True, fill=campur(Gaya.latar(), "#000000", .12), outline="", tags=tag)
        cv.create_polygon(rr(x0, y0, x0 + lebar, y0 + 46, 20), smooth=True, fill=campur(Gaya.latar(), t["kartu"], .55 if P["tema"] == "terang" else .12),
                          outline=Gaya.tepi(), tags=tag)
        warna = t["baik"] if ok else t["buruk"]
        cv.create_text(x0 + 22, y0 + 22, text=("✔  " if ok else "✘  ") + teks, anchor="w", fill=warna, font=self.f(10, True), tags=tag)
        bar = cv.create_polygon(rr(x0 + 16, y0 + 38, x0 + lebar - 16, y0 + 41, 1.5), smooth=True, fill=warna, outline="", tags=tag)
        sisa, st = lebar + 40, {"d": lebar + 40}
        cv.move(tag, sisa, 0)  # mulai di luar layar kanan

        def masuk(f):
            nilai = sisa * (1 - ease_back(f))
            cv.move(tag, nilai - st["d"], 0)
            st["d"] = nilai

        def hitung_mundur():
            kk = Pengaturan.kali()
            if kk:
                animasi(cv, lambda f: cv.coords(bar, *rr(x0 + 16, y0 + 38, x0 + 16 + (lebar - 32) * max(.02, 1 - f), y0 + 41, 1.5)), P["toast"] / kk)
        animasi(cv, masuk, 450, selesai=hitung_mundur)

        def tutup():
            if self.tt != tag:
                return
            animasi(cv, lambda f: (cv.move(tag, (sisa * ease_out(f)) - (st["d"]), 0), st.__setitem__("d", sisa * ease_out(f))), 300,
                    selesai=lambda: (cv.delete(tag), setattr(self, "tt", None) if self.tt == tag else None))
        self.root.after(P["toast"], tutup)

    def catat(self, teks):
        try:
            with open(os.path.join(os.path.dirname(FILE_CSV), "galat.log"), "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{teks}\n")
        except OSError:
            pass

    def lapor(self, tipe, nilai, tb):
        """Galat dari callback Tk dicatat ke galat.log (widget yang sudah dihancurkan diabaikan)."""
        if tipe is tk.TclError and any(s in str(nilai) for s in ("bad window path", "invalid command name")):
            return
        self.catat("".join(traceback.format_exception(tipe, nilai, tb)))
        try:
            self.toast("Terjadi kesalahan (lihat galat.log)", False)
        except tk.TclError:
            pass

    def jalan(self):
        self.root.mainloop()


def diagnosa(halaman):
    """Uji semua halaman di Tk sesungguhnya (juga beberapa variasi pengaturan) dan tulis laporan ke diagnosa.txt."""
    import platform
    import sys
    asli = {k: (dict(v) if isinstance(v, dict) else v) for k, v in P.items()}
    P["anim"], P["splash"] = "mati", "lewati"
    app = Jendela(halaman)
    app.root.update()
    b = [f"Python {sys.version.split()[0]} | {platform.platform()}", f"Tk {tk.TkVersion} | Tcl {tk.TclVersion}",
         f"Pillow: {'ya' if ADA_PIL else 'tidak'} | efek kaca aktif: {Kaca.aktif()}",
         f"Huruf: {app.fam} | layar {app.root.winfo_screenwidth()}x{app.root.winfo_screenheight()} | dpi {app.root.winfo_fpixels('1i'):.0f}"]

    def coba(nama, fn):
        t0 = time.perf_counter()
        try:
            fn()
            app.root.update()
            b.append(f"[OK] {nama}: {(time.perf_counter() - t0) * 1000:.0f} ms")
        except Exception:
            b.append(f"[GALAT] {nama}:\n{traceback.format_exc()}")
    for i, (nama, _) in enumerate(halaman):
        coba("halaman " + nama, lambda i=i: app.buka(i, False))
    for kunci, nilai in (("tema", "gelap"), ("aksen", "sunset"), ("kaca", "tebal"), ("kaca_mode", "sederhana"), ("font", "besar"), ("orb", "sembunyi")):
        def ubah(kunci=kunci, nilai=nilai):
            P[kunci] = nilai
            app.terapkan()
        coba(f"{kunci}={nilai}", ubah)
    coba("toast", lambda: app.toast("uji"))
    P.update(asli)
    Pengaturan.simpan()
    log = os.path.join(os.path.dirname(FILE_CSV), "galat.log")
    if os.path.exists(log):
        with open(log, encoding="utf-8") as f:
            b.append("--- galat.log (akhir) ---\n" + f.read()[-1500:])
    jalur = os.path.join(os.path.dirname(FILE_CSV), "diagnosa.txt")
    with open(jalur, "w", encoding="utf-8") as f:
        f.write("\n".join(b) + "\n")
    print("\n".join(b), "\nLaporan disimpan:", jalur)
    app.root.destroy()


if __name__ == "__main__":
    Jendela([("Pengaturan", halaman_pengaturan), ("Pintasan", halaman_pintasan)], "Pengaturan & Pintasan").jalan()
