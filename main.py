"""main.py - hub: menggabungkan halaman dari semua modul dalam satu jendela.
Setiap modul juga bisa dijalankan sendiri (python tambah_transaksi.py, tampil_portofolio.py, ui.py, models.py)."""
from tambah_transaksi import halaman_tambah
from tampil_portofolio import halaman_grafik, halaman_portofolio, halaman_riwayat
import sys

from ui import Jendela, diagnosa, halaman_pengaturan, halaman_pintasan

HALAMAN = [("Portofolio", halaman_portofolio), ("Tambah", halaman_tambah), ("Grafik", halaman_grafik),
           ("Riwayat", halaman_riwayat), ("Pengaturan", halaman_pengaturan), ("Pintasan", halaman_pintasan)]

if __name__ == "__main__":
    if "--diagnosa" in sys.argv:  # uji semua halaman di komputermu, hasil di diagnosa.txt
        diagnosa(HALAMAN)
    else:
        Jendela(HALAMAN).jalan()
