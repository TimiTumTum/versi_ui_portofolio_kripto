"""tambah_transaksi.py - form tambah/ubah transaksi (input, validasi, simpan ke CSV).
Bisa dijalankan sendiri: python tambah_transaksi.py"""
import math
import re
from datetime import date
from tkinter import messagebox

from models import P, Penyimpanan, Transaksi, norm_tanggal, parse_angka, rp
from ui import Gaya, Jendela


def teks_angka(x):
    return ("%.8f" % x).rstrip("0").rstrip(".") or "0"


def halaman_tambah(app):
    daftar = Penyimpanan.muat()
    lama = daftar[app.edit] if app.edit is not None and app.edit < len(daftar) else None
    if lama is None:
        app.edit = None
    k = app.kartu(.14, 0, .72, .97)
    k.judul("Ubah transaksi" if lama else "Tambah transaksi")
    cw = (k.w - 36 - 28) / 2
    xk, xr = 18, 18 + cw + 28
    e_tgl = k.kolom(xk, 44, cw, "Tanggal (YYYY-MM-DD, juga 5/1/2026)", (norm_tanggal(lama.tanggal) or lama.tanggal) if lama else date.today().isoformat())
    e_aset = k.kolom(xk, 116, cw, "Aset (BTC, ETH, IDR ...)", lama.aset if lama else "")
    e_jml = k.kolom(xr, 44, cw, "Jumlah aset / uang", teks_angka(lama.jumlah) if lama else "")
    e_hrg = k.kolom(xr, 116, cw, "Harga per unit (IDR otomatis 1)", teks_angka(lama.harga) if lama else "")
    # pilih cepat aset (chip), membungkus ke baris berikutnya
    x, y = xk, 190
    for a in list(dict.fromkeys([t.aset for t in daftar][-6:] + ["IDR", "BTC", "ETH", "SOL"]))[:8]:
        lb = len(a) * 8 + 26
        if x + lb > xk + cw:
            x, y = xk, y + 32
        k.tombol(x, y, lb, 26, a, lambda a=a: pilih_aset(a))
        x += lb + 6
    jenis = {"v": lama.jenis if lama else "beli"}
    p_beli = k.tombol(xk, 268, cw / 2 - 4, 34, "Beli", lambda: pilih("beli"))
    p_jual = k.tombol(xk + cw / 2 + 4, 268, cw / 2 - 4, 34, "Jual", lambda: pilih("jual"))

    def pilih(j):
        jenis["v"] = j
        p_beli.pasang(j == "beli")
        p_jual.pasang(j == "jual")
    pilih(jenis["v"])
    total = k.teks(xr, 196, "Total: 0", 15, True, "acc")

    def pilih_aset(a):
        e_aset.delete(0, "end")
        e_aset.insert(0, a)
        hitung()
        e_jml.focus_set()

    def hitung(_=None):
        try:
            h = 1.0 if e_aset.get().strip().upper() == "IDR" else parse_angka(e_hrg.get())
            app.cv.itemconfig(total, text="Total: " + P["mata"] + rp(parse_angka(e_jml.get()) * h, 2))
        except ValueError:
            app.cv.itemconfig(total, text="Total: -")
    for e in (e_aset, e_jml, e_hrg):
        e.bind("<KeyRelease>", hitung)
    hitung()

    def simpan():
        tgl, aset = norm_tanggal(e_tgl.get()), e_aset.get().strip().upper()
        if not tgl:
            return app.toast("Tanggal tidak valid (contoh 2026-10-15)", False)
        if not re.fullmatch(r"[A-Z0-9._-]{1,12}", aset):
            return app.toast("Nama aset 1-12 karakter (huruf/angka)", False)
        try:
            jumlah = parse_angka(e_jml.get())
            harga = 1.0 if aset == "IDR" else parse_angka(e_hrg.get())
        except ValueError:
            return app.toast("Jumlah dan harga harus angka", False)
        if not (math.isfinite(jumlah) and math.isfinite(harga) and jumlah > 0 and harga > 0):
            return app.toast("Jumlah dan harga harus lebih dari 0", False)
        lain = [x for i, x in enumerate(daftar) if i != app.edit]  # saldo tanpa transaksi yang sedang diubah
        saldo = Penyimpanan.saldo(lain, aset)
        if jenis["v"] == "jual" and jumlah > saldo + 1e-9:
            if P["jual"] == "blok":
                return app.toast("Penjualan melebihi saldo (diblokir di Pengaturan)", False)
            if P["jual"] == "tanya" and not messagebox.askyesno(
                    "Saldo tidak cukup", f"Saldo tercatat {aset}: {teks_angka(saldo)}. Penjualan ini membuat saldo negatif. Lanjutkan?"):
                return
        baru = Transaksi(tgl, aset, jenis["v"], jumlah, harga)
        try:
            if lama:
                daftar[app.edit] = baru
                Penyimpanan.tulis_ulang(daftar)
            else:
                Penyimpanan.simpan(baru)
        except OSError as e:
            return app.toast(f"Gagal menyimpan: {e}", False)
        if lama:
            app.edit = None
            app.toast("Perubahan disimpan")
            return (app.buka("Riwayat") or app.buka(0))
        daftar.append(baru)  # agar saldo dan pilih-cepat berikutnya ikut berubah
        for e in (e_aset, e_jml, e_hrg):
            e.delete(0, "end")
        hitung()
        app.toast("Transaksi tersimpan")
        e_aset.focus_set()

    def batal():
        app.edit = None
        (app.buka("Riwayat") or app.buka(0))
    for e in (e_tgl, e_aset, e_jml, e_hrg):
        e.bind("<Return>", lambda _: simpan())  # Enter = simpan
    k.tombol(xr, 240, cw, 44, "Simpan Perubahan" if lama else "Simpan Transaksi", simpan, primer=True)
    if lama:
        k.tombol(xr, 294, cw, 38, "Batal", batal)
    e_aset.focus_set()
    app.simpan_cb = simpan


if __name__ == "__main__":
    Jendela([("Tambah", halaman_tambah)], "Tambah Transaksi").jalan()
