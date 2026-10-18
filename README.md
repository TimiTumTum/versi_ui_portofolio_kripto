# Portofolio Crypto & Uang — GUI Tkinter (modular, OOP, CSV)

Aplikasi desktop dengan gaya gabungan **Glassmorphism × Soft UI × Bento**. Hanya pustaka bawaan Python 3.8+
(Linux: `sudo apt install python3-tk`).

## Desain satu kanvas
(Tabel, tombol, dan kolom isian ikut digambar di kanvas; toast selalu tampil di atas semua elemen. Bila Pillow bermasalah, aplikasi otomatis memakai tampilan sederhana dan mencatatnya di `galat.log`.)
Seluruh tampilan digambar di **satu kanvas** (teks, tombol, grafik, kartu kaca), bukan tumpukan widget. Hasilnya tidak ada lagi
kotak warna janggal di sekitar teks/tombol, huruf dipilih otomatis dari font terbaik yang ada di sistem (Segoe UI / SF / Inter /
Roboto / Ubuntu / Noto / DejaVu), ukuran teks tetap dalam piksel (tidak berantakan di layar HiDPI), dan di Windows aplikasi
meminta mode DPI-aware agar teks tajam. Kolom isian, tombol, dan tabel dibuat konsisten dengan tema kaca.

## Efek kaca asli (Pillow)
Gaya **glassmorphism** memakai efek sungguhan jika Pillow terpasang: latar di belakang tiap kartu dikaburkan, diberi lapisan putih
tembus pandang, tepi bercahaya (lebih terang di atas), sudut membulat halus, dan bayangan lembut; tata letaknya **bento grid**
(ubin berukuran beda). Pasang dengan `pip install pillow`. Tanpa Pillow (atau dengan Pengaturan → Efek kaca → Sederhana)
aplikasi memakai tampilan datar yang lebih ringan. Pratinjau desain: `pratinjau_terang.png` dan `pratinjau_gelap.png`.

## Struktur proyek
| File | Peran |
|---|---|
| `main.py` | **Hub** — hanya menggabungkan halaman dari modul lain dalam satu jendela |
| `tambah_transaksi.py` | Form tambah/ubah transaksi: input → validasi → simpan ke CSV |
| `tampil_portofolio.py` | Baca CSV → tampilkan di Treeview → hitung total; grafik dan riwayat |
| `models.py` | Class OOP `Transaksi` (`__init__`, `to_list`, `__str__`), `Penyimpanan` (CSV), `Pengaturan` — tanpa tkinter |
| `ui.py` | Komponen antarmuka (satu kanvas): efek kaca, `Kartu`, `Tombol`, `Tabel` kustom, animasi, kerangka `Jendela`, halaman Pengaturan & Pintasan |
| `transaksi.csv` | Penyimpanan data |

Alur: `main → (tambah_transaksi, tampil_portofolio, ui) → models → transaksi.csv`. Modul tidak saling mengimpor kecuali
ke `ui` dan `models`, sehingga setiap modul bisa berjalan sendiri.

## Menjalankan
```
python main.py                 # aplikasi lengkap (6 halaman)
python tambah_transaksi.py     # hanya form tambah transaksi
python tampil_portofolio.py    # hanya Portofolio, Grafik, Riwayat
python ui.py                   # hanya Pengaturan dan Pintasan
python models.py               # ringkasan data + uji cepat (tanpa GUI)
```
Pada jendela mandiri, fitur yang butuh halaman lain (mis. **Ubah** transaksi dari Riwayat) memberi tahu bahwa fitur itu
tersedia di `main.py`.

## Alur kerja
**Tambah:** Tambah → input tanggal/aset/jenis/jumlah/harga → validasi (tanggal, nama aset, angka > 0, saldo) → simpan ke CSV → notifikasi.
**Tampil:** baca CSV → tabel kustom (judul bisa diklik untuk urut, hover, pilih, gulir roda mouse) → hitung total, saldo, harga rata-rata, laba/rugi → grafik animasi.

## Pengaturan (tab Pengaturan, disimpan di `pengaturan.json`)
Tema · warna aksen (5) · kekuatan kaca · orb latar · ukuran teks · kecepatan animasi · loading screen · mata uang · format angka ·
desimal saldo · tab awal · konfirmasi hapus · durasi notifikasi · sikap jual melebihi saldo · cadangkan data · reset · data contoh.

## Pintasan (tab Pintasan) — pengubah keybind
Klik tombol pintasan, tekan kombinasi baru (wajib Ctrl/Alt atau F1–F12; Esc batal). Kombinasi yang sudah dipakai ditolak; ↺
mengembalikan satu pintasan, "Reset semua" mengembalikan semuanya. Bawaan: `Ctrl+1..6` pindah halaman, `Ctrl+T` tema,
`Ctrl+F` cari di Riwayat, `Ctrl+B` cadangkan, `Ctrl+S` simpan form.

## Diagnosa bug
`python main.py --diagnosa` menguji semua halaman dan beberapa variasi pengaturan di komputermu, lalu menulis `diagnosa.txt`
(versi Python/Tk, Pillow, font, DPI, waktu bangun tiap halaman, dan galat bila ada). Kirim file itu bersama screenshot bila melapor bug.

## Kelancaran & pelaporan galat
Semua animasi dijalankan satu penjadwal berbasis waktu (durasi tepat; frame dilewati bila komputer lambat, bukan diperlambat).
Animasi ambient (orb, kilau, napas tombol) berhenti sementara saat animasi lain berjalan. Latar memakai satu gambar gradasi.
Bila ada galat tak terduga, aplikasi tetap jalan, menampilkan notifikasi, dan mencatat jejaknya ke `galat.log` —
lampirkan isi file itu bila melaporkan bug.

## Animasi
Jendela memudar masuk · loading screen dengan spinner · kartu muncul memantul · transisi halaman · garis tab meluncur ·
angka menghitung naik · baris tabel bertahap · grafik tumbuh dan titik berdenyut · gelombang riak saat klik tombol ·
tombol utama bernapas · orb melayang dengan paralaks kursor · ganti tema/aksen dengan efek "tinta" · notifikasi dengan
hitung mundur. Semua bisa dimatikan lewat Pengaturan → Animasi → Mati.

> Hanya untuk pencatatan dan latihan pemrograman; bukan harga pasar real-time dan bukan saran investasi.
