"""tampil_portofolio.py - halaman Portofolio, Grafik, dan Riwayat (baca CSV, tabel, hitung total).
Bisa dijalankan sendiri: python tampil_portofolio.py"""
import math
import time
from collections import defaultdict
from tkinter import messagebox

from models import P, Penyimpanan, norm_tanggal, rp
from ui import PALET, Gaya, Jendela, animasi, ease_out, hitung_naik, wr


def singkat(n):
    for batas, s in ((1e12, "T"), (1e9, "M"), (1e6, "Jt"), (1e3, "Rb")):
        if abs(n) >= batas:
            return f"{n / batas:.1f} {s}"
    return f"{n:.0f}"


def urut(daftar):
    return [t for _, t in sorted(enumerate(daftar), key=lambda x: (norm_tanggal(x[1].tanggal) or "", x[0]))]


def hitung(daftar):
    saldo, beli, jual = defaultdict(float), defaultdict(float), defaultdict(float)
    for t in daftar:
        if t.jenis == "beli":
            saldo[t.aset] += t.jumlah
            beli[t.aset] += t.nilai_total()
        else:
            saldo[t.aset] -= t.jumlah
            jual[t.aset] += t.nilai_total()
    return saldo, beli, jual


def laba_rugi(daftar):
    """Biaya rata-rata: sisa unit, modal tersisa, laba/rugi terealisasi per aset."""
    qty, biaya, real = defaultdict(float), defaultdict(float), defaultdict(float)
    for t in urut(daftar):
        a, h = t.aset, t.harga_efektif()
        if t.jenis == "beli":
            qty[a] += t.jumlah
            biaya[a] += t.jumlah * h
        elif qty[a] > 0:
            rata, terjual = biaya[a] / qty[a], min(t.jumlah, qty[a])
            real[a] += (h - rata) * terjual
            biaya[a] -= rata * terjual
            qty[a] -= terjual
    return qty, biaya, real


def arus_kas(daftar):
    total, hasil = 0.0, []
    for t in urut(daftar):
        total += t.nilai_total() if t.jenis == "beli" else -t.nilai_total()
        hasil.append(total)
    return hasil[-40:]


def halaman_portofolio(app):
    t, daftar, cv = Gaya.t(), Penyimpanan.muat(), app.cv
    saldo, beli, jual = hitung(daftar)
    tb, tj = sum(beli.values()), sum(jual.values())
    qty, biaya, real = laba_rugi(daftar)
    lr, ak = sum(real.values()), arus_kas(daftar)
    teratas = max(beli, key=beli.get) if beli else None

    def ubin(fx, fy, fw, fh, nama, nilai, besar=False, uang=False, warna=None, tanda=False):  # bento: ubin berukuran beda
        k = app.kartu(fx, fy, fw, fh, hover=True)
        k.judul(nama)
        akhir = wr(warna or ("acc" if besar else "teks"))
        item = k.teks(18, 40, "0", 28 if besar else 17, True, akhir)
        hitung_naik(cv, item, nilai, lambda v: ("+" if tanda and v > 0 else "") + (P["mata"] if uang else "") + rp(v), akhir, k.warna)
        return k
    besar = ubin(0, 0, .42, .36, "Total beli", tb, True, True)
    if len(ak) >= 2:  # sparkline arus kas di dalam ubin besar, tergambar bertahap
        x0, y0, lebar = besar.x + 18, besar.y + besar.h - 80, besar.w - 36
        lo, hi = min(ak), max(ak)
        pts = [(x0 + lebar * i / (len(ak) - 1), y0 + 58 * (1 - (v - lo) / ((hi - lo) or 1))) for i, v in enumerate(ak)]
        garis = cv.create_line(*pts[0], *pts[0], fill=t["acc"], width=3, smooth=True, capstyle="round", tags=besar.tag)

        def gambar(f):
            n = (len(pts) - 1) * ease_out(f)
            j, fr = int(n), n - int(n)
            xy = [v for p in pts[:j + 1] for v in p]
            if j < len(pts) - 1:
                xy += [pts[j][0] + (pts[j + 1][0] - pts[j][0]) * fr, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * fr]
            cv.coords(garis, *xy)
        animasi(cv, gambar, 1300, delay=400)
    ubin(.435, 0, .185, .17, "Transaksi", len(daftar))
    ubin(.635, 0, .185, .17, "Aset", len(saldo))
    kt = app.kartu(.835, 0, .165, .17, hover=True)
    kt.judul("Terbesar")
    kt.teks(18, 38, teratas or "-", 15, True)
    kt.teks(18, 62, f"{beli[teratas] / tb * 100:.0f}% pembelian" if teratas and tb else "", 8, False, "redup")
    ubin(.435, .19, .30, .17, "Total jual", tj, False, True)
    ubin(.75, .19, .25, .17, "Laba/rugi terealisasi", lr, False, True, "baik" if lr >= 0 else "buruk", True)
    k = app.kartu(0, .38, 1, .62)
    if not daftar:
        k.teks(k.w / 2, 90, "Belum ada transaksi", 15, True, anchor="n")
        k.teks(k.w / 2, 124, "Tambahkan lewat tab Tambah, atau coba data contoh.", 10, False, "redup", "n")
        k.tombol(k.w / 2 - 95, 164, 190, 38, "Muat contoh data", app.contoh, primer=True)
        return
    kol = [("Aset", .14, "w"), ("Saldo Unit", .2, "e"), ("Total Beli", .19, "e"), ("Total Jual", .19, "e"), ("Harga Rata2", .14, "e"),
           ("L/R Terealisasi", .14, "e")]
    tabel = k.tabel(14, 14, k.w - 28, k.h - 28, kol)
    rows = []
    for a in sorted(saldo):
        rata = rp(biaya[a] / qty[a], 2) if qty[a] > 1e-12 else "-"
        rows.append((a, [(a, "acc2"), (rp(saldo[a], P["desimal"]), "buruk" if saldo[a] < -1e-9 else "teks"), rp(beli[a]), rp(jual[a]), rata,
                         (rp(real[a], 2), "baik" if real[a] >= 0 else "buruk")]))
    rows.append((None, [("TOTAL", "acc"), (f"{len(saldo)} aset", "redup"), (rp(tb), "acc"), (rp(tj), "acc"), "", (rp(lr, 2), "baik" if lr >= 0 else "buruk")]))
    tabel.isi(rows, cascade=True)


def halaman_grafik(app):
    t, daftar, cv = Gaya.t(), Penyimpanan.muat(), app.cv
    _, beli, jual = hitung(daftar)
    tb = sum(beli.values())
    # donat alokasi: busur tumbuh bersamaan
    k = app.kartu(0, 0, .34, .62)
    k.judul("Alokasi pembelian")
    if not tb:
        k.teks(k.w / 2, k.h / 2, "Belum ada pembelian", 10, False, "redup", "center")
    else:
        ks, cx, cyr = sorted(beli, key=lambda a: -beli[a]), k.x + k.w / 2, k.h / 2 + 14
        cy, r = k.y + cyr, min(k.w, k.h - 56) / 2 - 24
        arcs = [cv.create_arc(cx - r, cy - r, cx + r, cy + r, style="arc", width=24, outline=PALET[i % 6], start=90, extent=-.01, tags=k.tag)
                for i in range(len(ks))]
        k.teks(k.w / 2, cyr - 8, singkat(tb), 16, True, anchor="center")
        k.teks(k.w / 2, cyr + 16, f"{len(ks)} aset", 9, False, "redup", "center")

        def gerak(f, ks=ks, arcs=arcs):  # ikat nilai sekarang (ks ditimpa grafik batang)
            kum = 0
            for it, a in zip(arcs, ks):
                p = beli[a] / tb * 360 * ease_out(f)
                cv.itemconfig(it, start=90 - kum, extent=-max(p - 1.5, .01))
                kum += p
        animasi(cv, gerak, 1100, delay=250)
    # batang beli vs jual
    k = app.kartu(.35, 0, .65, .62)
    k.judul("Beli vs jual per aset")
    semua = sorted(set(beli) | set(jual), key=lambda a: -(beli[a] + jual[a]))  # terbesar dulu
    ks = semua[:6]
    mx = max([*(beli[a] for a in ks), *(jual[a] for a in ks), 1])
    if len(semua) > 6:
        k.teks(18, k.h - 24, f"+{len(semua) - 6} aset lainnya tidak ditampilkan", 9, False, "redup")
    k.teks(k.w - 18, 14, "■ beli", 9, True, PALET[0], "ne")
    k.teks(k.w - 18, 32, "■ jual", 9, True, PALET[1], "ne")
    baris, lebar = [], k.w - 170
    for i, a in enumerate(ks):
        y = k.y + 52 + i * (k.h - 70) / max(len(ks), 1)
        cv.create_text(k.x + 18, y + 12, anchor="w", text=a, fill=t["teks"], font=app.f(10, True), tags=k.tag)
        baris.append((cv.create_polygon(0, 0, 0, 0, 0, 0, fill=PALET[0], outline="", tags=k.tag),
                      cv.create_polygon(0, 0, 0, 0, 0, 0, fill=PALET[1], outline="", tags=k.tag), a, y))

    def tumbuh(f, k=k):  # ikat kartu batang (k ditimpa kartu arus kas)
        for b1, b2, a, y in baris:
            x0 = k.x + 90
            for it, nilai, dy in ((b1, beli[a], 0), (b2, jual[a], 15)):
                cv.coords(it, x0, y + dy, x0 + max(4, lebar * nilai / mx * ease_out(f)), y + dy, x0 + max(4, lebar * nilai / mx * ease_out(f)), y + dy + 11, x0, y + dy + 11)
    animasi(cv, tumbuh, 1000, delay=350)
    # garis arus kas: tergambar bertahap, titik ujung berdenyut
    k = app.kartu(0, .64, 1, .36)
    k.judul("Arus kas kumulatif (beli - jual)")
    ak = arus_kas(daftar)
    if len(ak) < 2:
        k.teks(k.w / 2, k.h / 2 + 8, "Butuh minimal 2 transaksi", 10, False, "redup", "center")
        return
    lo, hi = min(ak), max(ak)
    L, R, T, B = k.x + 70, k.x + k.w - 24, k.y + 40, k.y + k.h - 26
    pts = [(L + (R - L) * i / (len(ak) - 1), T + (B - T) * (1 - (v - lo) / ((hi - lo) or 1))) for i, v in enumerate(ak)]
    cv.create_line(L, B, R, B, fill=t["sh1"], tags=k.tag)
    cv.create_text(L - 10, T, anchor="e", text=singkat(hi), fill=t["redup"], font=app.f(9), tags=k.tag)
    cv.create_text(L - 10, B, anchor="e", text=singkat(lo), fill=t["redup"], font=app.f(9), tags=k.tag)
    garis = cv.create_line(*pts[0], *pts[0], fill=t["acc"], width=3, smooth=True, capstyle="round", tags=k.tag)

    def gambar(f):
        n = (len(pts) - 1) * ease_out(f)
        j, fr = int(n), n - int(n)
        xy = [v for p in pts[:j + 1] for v in p]
        if j < len(pts) - 1:
            xy += [pts[j][0] + (pts[j + 1][0] - pts[j][0]) * fr, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * fr]
        cv.coords(garis, *xy)

    def denyut():  # lingkaran bergelombang di ujung garis
        if P["anim"] == "mati":
            return
        x, y = pts[-1]
        halo = cv.create_oval(x, y, x, y, outline=t["acc2"], width=2, tags=k.tag)

        def j():
            if not cv.type(halo):
                return
            f = (time.time() * 1.2) % 1
            r = 5 + 14 * f
            cv.coords(halo, x - r, y - r + k.dp + k.dh, x + r, y + r + k.dp + k.dh)
            cv.itemconfig(halo, outline=campur_halo(t, k, f))
            cv.after(40, j)
        j()
    animasi(cv, gambar, 1600, delay=500, selesai=denyut)


def campur_halo(t, k, f):
    from ui import campur
    return campur(t["acc2"], k.warna, f)


def halaman_riwayat(app):
    t, daftar = Gaya.t(), Penyimpanan.muat()
    k = app.kartu(0, 0, 1, 1)
    sortir = {"kol": None, "turun": True}
    kunci = [lambda x: norm_tanggal(x.tanggal) or x.tanggal, lambda x: x.aset, lambda x: x.jenis, lambda x: x.jumlah, lambda x: x.nilai_total()]
    kol = [("Tanggal", .2, "w"), ("Aset", .16, "w"), ("Jenis", .14, "w"), ("Jumlah", .25, "e"), ("Total", .25, "e")]

    def terpilih():
        i = tabel.terpilih()
        if i is None:
            app.toast("Pilih satu baris dulu", False)
        return i

    def ubah():
        i = terpilih()
        if i is not None:
            app.edit = i
            if not app.buka("Tambah"):
                app.edit = None
                app.toast("Ubah tersedia di jendela utama (python main.py)", False)

    def hapus():
        i = terpilih()
        if i is None:
            return
        x = daftar[i]
        if P["konfirmasi"] == "tidak" or messagebox.askyesno("Hapus transaksi", f"Hapus {x.aset} {x.jenis} {x.tanggal}?"):
            daftar.pop(i)
            try:
                Penyimpanan.tulis_ulang(daftar)
            except OSError as e:
                return app.toast(f"Gagal menyimpan: {e}", False)
            app.toast("Dihapus (bisa diurungkan)")
            app.segarkan()

    def urungkan():
        try:
            ok = Penyimpanan.urungkan()
        except OSError as e:
            return app.toast(f"Gagal: {e}", False)
        app.toast("Perubahan terakhir diurungkan" if ok else "Belum ada cadangan", ok)
        if ok:
            app.segarkan()

    def urut_kolom(c):
        sortir["turun"] = not sortir["turun"] if sortir["kol"] == c else False
        sortir["kol"] = c
        isi()
    cari = k.input(14, 14, k.w - 360, 36)
    hitung_teks = k.teks(k.w - 280, 24, "", 9, False, "redup", "e")
    x0 = k.w - 14 - 250
    k.tombol(x0, 14, 72, 36, "Ubah", ubah)
    k.tombol(x0 + 80, 14, 80, 36, "Hapus", hapus)
    k.tombol(x0 + 168, 14, 82, 36, "Urungkan", urungkan)
    tabel = k.tabel(14, 64, k.w - 28, k.h - 78, kol, urut_kolom, ubah)

    def isi(_=None, anim=False):
        c = sortir["kol"]
        tabel.tanda = {kol[c][0]: "  ▼" if sortir["turun"] else "  ▲"} if c is not None else {}
        urutan = list(reversed(range(len(daftar)))) if c is None else sorted(range(len(daftar)), key=lambda i: kunci[c](daftar[i]), reverse=sortir["turun"])
        q, rows = cari.get().strip().lower(), []
        for i in urutan:
            x = daftar[i]
            if q in f"{x.aset} {x.tanggal} {x.jenis}".lower():
                rows.append((i, [x.tanggal, (x.aset, "acc2"), (x.jenis, "baik" if x.jenis == "beli" else "buruk"), rp(x.jumlah, 4), rp(x.nilai_total(), 2)]))
        tabel.isi(rows, cascade=anim)
        app.cv.itemconfig(hitung_teks, text=f"{len(rows)} dari {len(daftar)}")
    cari.bind("<KeyRelease>", isi)
    isi(anim=True)
    app.cari_cb = cari.focus_set


HALAMAN = [("Portofolio", halaman_portofolio), ("Grafik", halaman_grafik), ("Riwayat", halaman_riwayat)]

if __name__ == "__main__":
    Jendela(HALAMAN, "Portofolio").jalan()
