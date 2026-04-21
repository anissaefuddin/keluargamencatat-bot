PRD — Project Requirements Document (Revised)
1. Overview

Aplikasi ini adalah asisten pencatatan keuangan pintar berbasis Telegram Bot untuk keluarga (2–3 pengguna), dengan pemrosesan AI lokal di PC rumah dan penyimpanan data di Google Sheets.

Tujuan utama:

Menghilangkan friksi dalam pencatatan keuangan
Mengubah kebiasaan “tidak mencatat” menjadi “cukup kirim pesan”
2. Success Metrics (Kriteria Keberhasilan)

Untuk memastikan sistem benar-benar berhasil, berikut metrik yang harus dicapai:

2.1 Akurasi
Ekstraksi nominal dari teks: ≥ 98%
Ekstraksi nominal dari struk (OCR): ≥ 90%
Transkripsi voice note: ≥ 92% akurasi
Klasifikasi kategori: ≥ 85% benar tanpa koreksi manual
2.2 Performa
Waktu respon bot (end-to-end): ≤ 10 detik
Waktu tulis ke Google Sheets: ≤ 5 detik
2.3 Reliability
Tingkat keberhasilan pencatatan transaksi: ≥ 99%
Error rate maksimal: < 1% per hari
3. Requirements (Updated)
Functional
Input: teks, foto, audio
Output: pencatatan otomatis + konfirmasi
Query: analytics sederhana via chat
Non-Functional (NEW)
Reliabilitas: sistem tetap berjalan walau ada kegagalan parsial
Privasi: semua data diproses lokal (tidak ke cloud AI)
Performa: respon <10 detik
Backup: data tidak hilang jika server mati
Maintainability: mudah dijalankan ulang via Docker
4. Core Features + Acceptance Criteria
4.1 Smart Data Extraction

Acceptance Criteria:

Sistem dapat membaca nominal dari teks/foto/audio
Jika confidence < 80% → bot meminta konfirmasi user
Jika parsing gagal → bot meminta input ulang
4.2 Auto Categorization

Acceptance Criteria:

Sistem otomatis menentukan kategori
Jika confidence rendah → user diminta memilih kategori
User bisa override kategori
4.3 Google Sheets Sync

Acceptance Criteria:

Data masuk ke Sheets ≤ 10 detik
Tidak ada duplikasi transaksi (id unik)
Jika gagal kirim → retry otomatis 3x
4.4 Family Authorization

Acceptance Criteria:

Bot hanya merespons Telegram ID yang terdaftar
User tidak dikenal → diabaikan tanpa respon
4.5 Chat Analytics

Acceptance Criteria:

Query seperti “pengeluaran minggu ini” berhasil dijawab
Data diambil langsung dari Sheets
Response ≤ 5 detik
5. Data Contract (Google Sheets)
5.1 Format Tabel: Transaksi
Field	Type	Format	Contoh
id_transaksi	String	UUID	trx-20260421-001
tanggal	Datetime	ISO 8601	2026-04-21T10:30:00+07:00
tipe_transaksi	Enum	pemasukan/pengeluaran	pengeluaran
kategori	String	predefined	makanan
nominal	Integer	angka murni (tanpa Rp)	150000
keterangan	String	bebas	makan siang
pengguna	String	Telegram username	@anis
5.2 Aturan Data
Timezone default: Asia/Jakarta (UTC+7)
Nominal disimpan sebagai integer (bukan string rupiah)
Kategori harus dari daftar referensi
Tidak boleh ada field kosong kecuali keterangan
5.3 Duplicate Handling
Duplicate dicek dari:
timestamp ±1 menit
nominal sama
user sama

Jika terdeteksi → bot konfirmasi:

“Transaksi ini sepertinya duplikat, tetap simpan?”

5.4 Manual Correction
User bisa kirim:
“ubah terakhir jadi 120 ribu”
“kategori tadi transport”
Sistem update baris terakhir di Sheets
6. Error Handling & Fallback
6.1 OCR Gagal

Bot:

“Saya tidak bisa membaca struk, mohon ketik manual ya.”

Fallback: input manual
6.2 Audio Tidak Jelas

Bot:

“Audio kurang jelas, bisa ulangi atau ketik saja?”

Fallback: teks
6.3 Confidence Rendah

Bot:

“Apakah benar Rp150.000 kategori Makanan? (Ya/Tidak)”

6.4 Google Sheets Error
Retry otomatis 3x

Jika gagal:

“Gagal menyimpan, akan dicoba ulang otomatis”

6.5 Server Offline
Bot tidak merespons
Setelah online:
proses backlog (opsional)
log error
7. Security & Privacy (Enhanced)
7.1 Authorization
Whitelist Telegram ID
Disimpan di config lokal
7.2 Credential Management
Google Service Account disimpan di:
.env atau file terenkripsi
Tidak hardcode di source code
7.3 Data Privacy
Semua AI processing:
lokal (Ollama / Whisper)
Tidak ada data dikirim ke API eksternal
7.4 Logging
Log aktivitas:
input user
hasil parsing
error
Disimpan lokal (rotating log)
7.5 Backup Strategy
Backup Google Sheets:
export harian (CSV)
Backup config:
manual copy / git
7.6 Failure Mitigation
Jika PC mati:
sistem berhenti sementara
tidak ada data hilang (Telegram tetap simpan message)
8. Architecture (Updated Note)

Tambahan:

Retry layer untuk Google Sheets
Confidence scoring dari AI
Logging & fallback layer
9. Tech Stack (Updated with Fallback)
Backend
Python (aiogram / python-telegram-bot)
AI
Ollama (LLM + Vision)
Whisper.cpp (speech-to-text)
Fallback Strategy
OCR gagal → manual input
Audio gagal → teks
AI ragu → konfirmasi user
10. Risks & Mitigation (NEW)
Risiko	Mitigasi
OCR tidak akurat	fallback manual
User malas konfirmasi	default kategori + edit
Server mati	restart + log
Sheets error	retry queue
AI lambat	batasi ukuran input