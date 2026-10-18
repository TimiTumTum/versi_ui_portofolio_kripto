"""models.py - data aplikasi (OOP): Transaksi, Penyimpanan (CSV), Pengaturan. Tanpa tkinter.
Bisa dijalankan sendiri: python models.py (ringkasan data dan uji cepat)."""
import copy
import csv
import json
import math
import os
import re
import shutil
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
FILE_CSV = os.path.join(BASE, "transaksi.csv")
FILE_HARGA = os.path.join(BASE, "harga_pasar.csv")
FILE_SET = os.path.join(BASE, "pengaturan.json")
HEADER = ["Tanggal", "Aset", "Jenis", "Jumlah", "Harga per Unit", "Nilai Total"]


def parse_angka(teks):
    """Baca angka gaya Indonesia atau internasional: 1.000,5 / 1,5 / 0.5 / 1.000.000."""
    t = teks.strip().replace(" ", "").replace("_", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    return float(t)


def norm_tanggal(teks):
    """Ubah 2026-1-5, 2026/01/05, atau 5-1-2026 menjadi 2026-01-05; None jika tidak valid."""
    teks = teks.strip()
    for pola, urut in ((r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", (0, 1, 2)), (r"(\d{1,2})\D+(\d{1,2})\D+(\d{4})", (2, 1, 0))):
        m = re.fullmatch(pola, teks)
        if m:
            try:
                return date(*(int(m.group(i + 1)) for i in urut)).isoformat()
            except ValueError:
                return None
    return None


class Transaksi:
    def __init__(self, tanggal, aset, jenis, jumlah, harga):
        self.tanggal = tanggal
        self.aset = aset.upper()
        self.jenis = jenis.lower()
        self.jumlah = jumlah
        self.harga = harga

    def __str__(self):
        return f"{self.tanggal} {self.aset} {self.jenis} {self.jumlah:g} @ {self.harga:g}"

    def harga_efektif(self):
        return 1.0 if self.aset == "IDR" else self.harga  # uang rupiah selalu 1 per unit

    def nilai_total(self):
        return self.jumlah * self.harga_efektif()

    def to_list(self):
        return [self.tanggal, self.aset, self.jenis, self.jumlah, self.harga, self.nilai_total()]

    @classmethod
    def dari_baris(cls, row):
        """Buat Transaksi dari satu baris CSV; None jika baris tidak valid."""
        try:
            jenis = row["Jenis"].strip().lower()
            if jenis not in ("beli", "jual"):
                return None
            jumlah, harga = float(row["Jumlah"]), float(row["Harga per Unit"])
            if not (math.isfinite(jumlah) and math.isfinite(harga) and jumlah > 0 and harga > 0):
                return None
            return cls(row["Tanggal"].strip(), row["Aset"].strip(), jenis, jumlah, harga)
        except (KeyError, ValueError, AttributeError, TypeError):
            return None


class Penyimpanan:
    rusak = []

    @staticmethod
    def muat():
        """Baca transaksi valid. Baris tidak valid disimpan di Penyimpanan.rusak (tidak dibuang)."""
        Penyimpanan.rusak = []
        if not os.path.exists(FILE_CSV):
            return []
        hasil = []
        with open(FILE_CSV, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                t = Transaksi.dari_baris(row)
                if t:
                    hasil.append(t)
                elif any(isinstance(v, str) and v.strip() for v in row.values()):
                    Penyimpanan.rusak.append(row)
        return hasil

    @staticmethod
    def muat_harga():
        harga = {}
        if os.path.exists(FILE_HARGA):
            with open(FILE_HARGA, newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    try:
                        v = float(r["Harga"])
                        if math.isfinite(v) and v > 0:
                            harga[r["Aset"].strip().upper()] = v
                    except (KeyError, ValueError, AttributeError, TypeError):
                        pass
        return harga

    @staticmethod
    def simpan_harga(harga):
        with open(FILE_HARGA, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Aset", "Harga"])
            for a, v in sorted(harga.items()):
                w.writerow([a, v])

    @staticmethod
    def simpan(t):
        baru = not os.path.exists(FILE_CSV) or os.path.getsize(FILE_CSV) == 0
        sambung = False
        if not baru:
            shutil.copyfile(FILE_CSV, FILE_CSV + ".bak")  # agar penambahan juga bisa diurungkan
            with open(FILE_CSV, "rb") as f:
                f.seek(-1, os.SEEK_END)
                sambung = f.read(1) not in (b"\n", b"\r")
        with open(FILE_CSV, "a", newline="", encoding="utf-8") as f:
            if sambung:
                f.write("\r\n")
            w = csv.writer(f)
            if baru:
                w.writerow(HEADER)
            w.writerow(t.to_list())

    @staticmethod
    def urungkan():
        """Tukar transaksi.csv dengan cadangannya (.bak); memanggil dua kali = batal urungkan."""
        a, b, tmp = FILE_CSV, FILE_CSV + ".bak", FILE_CSV + ".tmp"
        if not os.path.exists(b):
            return False
        if os.path.exists(a):
            os.replace(a, tmp)
        os.replace(b, a)
        if os.path.exists(tmp):
            os.replace(tmp, b)
        return True

    @staticmethod
    def impor(jalur):
        """Gabungkan baris valid dari CSV lain (koma/titik koma) tanpa duplikat; kembalikan (baru, duplikat, dilewati)."""
        def kunci(t, tg):
            return (tg, t.aset, t.jenis, round(t.jumlah, 8), round(t.harga, 8))

        ada = {kunci(t, norm_tanggal(t.tanggal) or t.tanggal) for t in Penyimpanan.muat()}
        with open(jalur, newline="", encoding="utf-8-sig") as f:
            kepala = f.readline()
            f.seek(0)
            baris = list(csv.DictReader(f, delimiter=";" if kepala.count(";") > kepala.count(",") else ","))
        baru, dup, lewat = [], 0, 0
        for r in baris:
            t = Transaksi.dari_baris(r)
            tg = norm_tanggal(t.tanggal) if t else None
            if not tg or t.jumlah <= 0 or t.harga <= 0:
                lewat += 1
            elif kunci(t, tg) in ada:
                dup += 1
            else:
                t.tanggal = tg
                ada.add(kunci(t, tg))
                baru.append(t)
        if baru:
            Penyimpanan.tulis_ulang(Penyimpanan.muat() + baru)
        return len(baru), dup, lewat

    @staticmethod
    def tulis_ulang(daftar):
        """Tulis ulang seluruh CSV secara atomik; versi lama disimpan sebagai transaksi.csv.bak."""
        if os.path.exists(FILE_CSV):
            shutil.copyfile(FILE_CSV, FILE_CSV + ".bak")
        sementara = FILE_CSV + ".tmp"
        with open(sementara, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(HEADER)
            for t in daftar:
                w.writerow(t.to_list())
            for r in Penyimpanan.rusak:  # baris tidak valid tetap dipertahankan
                w.writerow([r.get(h) or "" for h in HEADER])
        os.replace(sementara, FILE_CSV)

    @staticmethod
    def saldo(daftar, aset):
        return sum(t.jumlah if t.jenis == "beli" else -t.jumlah for t in daftar if t.aset == aset.upper())


# ---------------------------------------------------------------- pengaturan
AKSEN = {"aurora": ("#6366f1", "#14b8a6", "#f472b6"), "sunset": ("#f43f5e", "#f59e0b", "#a855f7"),
         "samudra": ("#0ea5e9", "#6366f1", "#14b8a6"), "hutan": ("#10b981", "#84cc16", "#0ea5e9"),
         "mawar": ("#ec4899", "#8b5cf6", "#f59e0b")}
# (kunci, label, [(nilai, teks tombol)]) -- sumber tunggal untuk validasi dan halaman Pengaturan
OPSI = [
    ("tema", "Tema", [("terang", "Terang"), ("gelap", "Gelap")]),
    ("kaca", "Kekuatan kaca", [("tipis", "Tipis"), ("normal", "Normal"), ("tebal", "Tebal")]),
    ("kaca_mode", "Efek kaca", [("asli", "Asli"), ("sederhana", "Sederhana")]),
    ("orb", "Orb latar", [("tampil", "Tampil"), ("sembunyi", "Sembunyi")]),
    ("font", "Ukuran teks", [("kecil", "Kecil"), ("normal", "Normal"), ("besar", "Besar")]),
    ("anim", "Animasi", [("mati", "Mati"), ("lambat", "Lambat"), ("normal", "Normal"), ("cepat", "Cepat")]),
    ("splash", "Loading screen", [("tampil", "Tampil"), ("lewati", "Lewati")]),
    ("mata", "Mata uang", [("", "Tanpa"), ("Rp ", "Rp"), ("$ ", "$")]),
    ("format", "Format angka", [("id", "1.234,56"), ("en", "1,234.56")]),
    ("desimal", "Desimal saldo", [(2, "2"), (4, "4"), (8, "8")]),
    ("awal", "Tab awal", [("Portofolio", "Portofolio"), ("Tambah", "Tambah"), ("Grafik", "Grafik"), ("Riwayat", "Riwayat")]),
    ("konfirmasi", "Konfirmasi hapus", [("ya", "Ya"), ("tidak", "Tidak")]),
    ("toast", "Durasi notifikasi", [(1800, "Singkat"), (2600, "Sedang"), (5000, "Lama")]),
    ("jual", "Jual > saldo", [("tanya", "Tanya"), ("izinkan", "Izinkan"), ("blok", "Blokir")]),
]
KEYS = [("tab_portofolio", "Buka Portofolio", "<Control-Key-1>"), ("tab_tambah", "Buka Tambah", "<Control-Key-2>"),
        ("tab_grafik", "Buka Grafik", "<Control-Key-3>"), ("tab_riwayat", "Buka Riwayat", "<Control-Key-4>"),
        ("tab_pengaturan", "Buka Pengaturan", "<Control-Key-5>"), ("tab_pintasan", "Buka Pintasan", "<Control-Key-6>"),
        ("tema", "Ganti tema", "<Control-Key-t>"), ("cari", "Cari di Riwayat", "<Control-Key-f>"),
        ("cadang", "Cadangkan data", "<Control-Key-b>"), ("simpan", "Simpan form transaksi", "<Control-Key-s>")]
DEF = dict(tema="terang", aksen="aurora", kaca="normal", kaca_mode="asli", orb="tampil", font="normal", anim="normal", splash="tampil",
           mata="", format="id", desimal=4, awal="Portofolio", konfirmasi="ya", toast=2600, jual="tanya", keybind={k: d for k, _, d in KEYS})


class Pengaturan:
    """Pengaturan pengguna di pengaturan.json; nilai tidak valid diganti nilai bawaan."""
    s = copy.deepcopy(DEF)

    @staticmethod
    def muat():
        izin = {k: [v for v, _ in o] for k, _, o in OPSI}
        izin["aksen"] = list(AKSEN)
        try:
            with open(FILE_SET, encoding="utf-8") as f:
                d = json.load(f)
            for k in izin:
                if isinstance(d, dict) and d.get(k) in izin[k]:
                    Pengaturan.s[k] = d[k]
            kb = d.get("keybind") if isinstance(d, dict) else None
            if isinstance(kb, dict):
                baru = {k: (kb.get(k) if isinstance(kb.get(k), str) and re.fullmatch(r"<[^<>\s]{1,40}>", kb.get(k)) else dd)
                        for k, _, dd in KEYS}
                if len(set(baru.values())) == len(baru):  # ada duplikat -> pakai bawaan
                    Pengaturan.s["keybind"] = baru
        except (OSError, ValueError, TypeError):
            pass

    @staticmethod
    def simpan():
        try:
            with open(FILE_SET, "w", encoding="utf-8") as f:
                json.dump(Pengaturan.s, f, indent=2, ensure_ascii=False)
            return True
        except OSError:
            return False

    @staticmethod
    def reset():
        Pengaturan.s.clear()
        Pengaturan.s.update(copy.deepcopy(DEF))

    @staticmethod
    def kali():  # pengali durasi animasi
        return {"mati": 0, "lambat": 1.8, "normal": 1.0, "cepat": .55}.get(Pengaturan.s["anim"], 1.0)


Pengaturan.muat()
P = Pengaturan.s


def tampil_kunci(seq):
    """'<Control-Key-t>' -> 'Ctrl+t'."""
    return "+".join(p.replace("Control", "Ctrl") for p in seq.strip("<>").split("-") if p != "Key")


def rp(v, d=0):
    """Format angka sesuai pengaturan (1.234,56 atau 1,234.56)."""
    s = f"{v:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") if P["format"] == "id" else s


if __name__ == "__main__":
    daftar = Penyimpanan.muat()
    print(f"{len(daftar)} transaksi, {len({t.aset for t in daftar})} aset, {len(Penyimpanan.rusak)} baris tidak valid")
    for t in daftar[-5:]:
        print("  ", t)
    assert norm_tanggal("5/1/2026") == "2026-01-05" and parse_angka("1.000,5") == 1000.5
    print("pengaturan:", {k: v for k, v in P.items() if k != "keybind"})
    print("uji cepat OK")
