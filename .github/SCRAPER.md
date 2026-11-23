# Scraper nama toko dan email dengan Python

Seluruh pengambilan data dijalankan oleh `.github/scraper.py`, tanpa Places API,
API key, atau Google Cloud billing. Python menggunakan Playwright untuk membuka
Google Maps di Chromium, mencari toko, menggulir daftar hasil, dan membaca nama
serta website toko. Requests dan BeautifulSoup mencari email publik di website
toko, termasuk maksimal dua halaman kontak/tentang yang ditautkan dari homepage.

## Menjalankan di GitHub Actions

1. Commit dan push file scraper serta workflow ke repository. Workflow harus
   tersedia di branch default agar tombol manual tampil.
2. Buka **Actions → Scraper Toko Google Maps → Run workflow**.
3. Isi `query`, misalnya `toko komputer di Bandung`, dan `max_results` (1–60,
   default 20). Tidak perlu memasukkan URL atau secret.
4. Setelah selesai, unduh artifact `hasil-scraper-...` berisi `stores.csv` dan
   `stores.json`. Artifact disimpan selama tujuh hari.

Workflow ada di `.github/workflows/scraper.yml` (folder `workflows`, bentuk jamak),
menggunakan runner Windows Server 2025 x64, Python 3.13 x64, dan PowerShell `pwsh`.
Workflow berjalan manual melalui `workflow_dispatch`. PowerShell memasang
dependency dan browser, lalu memanggil Python. Logika pengambilan data ada di Python.

## Menjalankan lokal melalui PowerShell

```powershell
py -m venv .venv-scraper
.venv-scraper\Scripts\python.exe -m pip install -r .github/requirements-scraper.txt
.venv-scraper\Scripts\python.exe -m playwright install chromium
.venv-scraper\Scripts\python.exe .github/scraper.py --query 'toko komputer di Bandung' --max-results 20
```

Tambahkan `--headed` untuk menampilkan browser saat menjalankan lokal:

```powershell
.venv-scraper\Scripts\python.exe .github/scraper.py --query 'toko komputer di Bandung' --max-results 5 --headed
```

Script tidak memerlukan `.env`. Hasil default tersimpan di `scraper-output/`;
gunakan `--output-dir` untuk mengubahnya. Tes offline dapat dijalankan dengan:

```powershell
.venv-scraper\Scripts\python.exe -m unittest discover -s .github -p test_scraper.py -v
```

## Hasil dan batasan

Kolom hasil: `name`, `email`, `website`, `google_maps_url`, `place_id`,
`email_source`, dan `status`. `place_id` berisi identifier yang tersedia dalam
URL Maps; jika tidak tersedia, kolom dibiarkan kosong. Satu email menghasilkan satu baris; toko dengan
beberapa email dapat muncul beberapa kali. Toko tanpa email tetap disimpan
dengan email kosong. Status:

- `found`: email ditemukan.
- `no_website`: profil Maps tidak mencantumkan website.
- `email_not_found`: tidak ada email pada halaman yang diperiksa.
- `website_error`: website gagal diakses atau kontennya bukan HTML.
- `maps_error`: detail profil Maps gagal dimuat; nama dari daftar tetap disimpan.

Script mencari email pada website karena profil Google Maps umumnya tidak
menampilkan email. Email tidak ditebak dan belum diverifikasi keaktifannya.
Website yang hanya menampilkan email melalui JavaScript mungkin tidak terbaca.
Kegagalan satu website tidak menghentikan pemrosesan toko lain.

## Jika pengambilan Maps gagal

Script menyimpan `maps-debug.png` dan `maps-debug.html` ketika terjadi kegagalan
utama saat membaca Maps. File ini ikut diunggah sebagai artifact untuk membantu
memeriksa tampilan yang diterima runner. Jika Chromium belum terpasang, jalankan
`python -m playwright install chromium` memakai Python environment yang sama
dengan scraper.

Google dapat meminta verifikasi/CAPTCHA atau mengubah struktur halaman. Script
berhenti ketika mendeteksi verifikasi; tidak melewati CAPTCHA. Kegagalan utama
menghasilkan exit code 1. Hasil yang lebih sedikit dari `max_results` bisa terjadi
jika daftar tidak bertambah setelah beberapa kali scroll. Batas tersebut bukan
jaminan jumlah toko dan tidak mencakup seluruh toko dalam suatu wilayah.

Referensi: [Playwright Python](https://playwright.dev/python/docs/library).
