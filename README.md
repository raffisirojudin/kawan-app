# Kawan - Chatbot AI dengan Memori Permanen

Chatbot AI yang **benar-benar mengingat** kamu lintas sesi — bukan cuma selama tab browser terbuka. Dibangun dengan Streamlit, Google Gemini API, dan Supabase.

## Fitur

- 🌸 **Tema "Kuncup"** — identitas visual khas kuncup bunga yang belum mekar: hijau lumut sebagai badan, aksen blush pink mengintip di ujung, melambangkan hubungan yang "mekar" pelan-pelan seiring waktu

- 💬 **Riwayat Chat Permanen** — semua percakapan tersimpan di database, tetap ada walau browser ditutup, app di-restart, atau diakses dari device lain
- 🧠 **Memori Pintar** — AI otomatis mendeteksi & menyimpan fakta penting tentang kamu (nama, hobi, preferensi, dll) dari obrolan, lalu menggunakannya secara natural di percakapan berikutnya
- 🗑️ **Kontrol Penuh** — bisa lihat semua yang "diingat" AI tentang kamu, dan edit atau hapus fakta tertentu (atau semuanya) kapan saja
- 🎭 **Pilih Kepribadian Kawan** — atur gaya ngobrolnya: Santai, Formal, Jenaka, atau Suportif
- 🔒 **Proteksi Password (sangat disarankan)** — karena app ini menyimpan data pribadi, aktifkan `APP_PASSWORD`
- 👤 **Multi-identitas sederhana** — pakai field "Nama" untuk memisahkan riwayat tiap orang (bukan sistem login asli, lihat catatan di bawah)

## Kenapa butuh Supabase?

Streamlit Cloud **tidak punya penyimpanan permanen bawaan** — server bisa restart kapan saja dan menghapus apapun yang hanya disimpan di memori/`session_state`. Buat memori yang benar-benar nyantol, app ini perlu database eksternal. [Supabase](https://supabase.com) dipilih karena gratis (500MB, tanpa kartu kredit) dan didukung resmi oleh dokumentasi Streamlit sendiri.

## 1. Setup Supabase (sekali saja)

1. Buka [supabase.com](https://supabase.com), daftar gratis (bisa pakai GitHub)
2. Klik **"New Project"**, beri nama bebas (misal `kawan-db`), buat password database (simpan, walau tidak akan dipakai langsung di app ini), pilih region terdekat
3. Tunggu beberapa menit sampai project siap
4. Di sidebar project, klik **"SQL Editor"** → **"New query"**, lalu paste dan jalankan (klik **Run**):

```sql
create table messages (
  id bigint generated always as identity primary key,
  user_id text not null,
  role text not null,
  content text not null,
  created_at timestamptz not null default now()
);

create table memories (
  id bigint generated always as identity primary key,
  user_id text not null,
  fact text not null,
  created_at timestamptz not null default now()
);

create index on messages (user_id, created_at);
create index on memories (user_id, created_at);

-- Nonaktifkan RLS: aman untuk app ini karena key Supabase hanya dipakai
-- di server (Streamlit), tidak pernah terkirim ke browser pengguna.
alter table messages disable row level security;
alter table memories disable row level security;
```

5. Buka **Settings → API** di sidebar, salin **Project URL** dan **anon public key** — ini yang dipakai di Secrets nanti

> **Catatan:** project gratis Supabase akan **di-pause otomatis kalau tidak diakses selama 7 hari**. Data tidak hilang, cukup buka dashboard Supabase dan klik "Restore"/"Resume" kalau itu terjadi.

## 2. Install dependencies (lokal)

```bash
pip install -r requirements.txt
```

## 3. Isi Secrets

**Untuk lokal:** salin `.streamlit/secrets.toml.example` jadi `.streamlit/secrets.toml`, isi semua field. Jangan upload file ini ke GitHub.

**Untuk Streamlit Cloud:** Settings → Secrets, isi:
```toml
GEMINI_API_KEY = "key-gemini-kamu"
SUPABASE_URL = "https://xxxxxxxxxxxx.supabase.co"
SUPABASE_KEY = "anon-key-supabase-kamu"
APP_PASSWORD = "password-kamu"
```
3 yang pertama **wajib** diisi (app akan kasih pesan error jelas kalau belum lengkap). `APP_PASSWORD` opsional tapi sangat disarankan karena app ini menyimpan percakapan pribadi.

## 4. Jalankan aplikasi

```bash
streamlit run app.py
```

## 5. Cara pakai

1. Masukkan **nama kamu** di sidebar (pakai nama yang sama setiap kali buka, supaya riwayat & memorinya nyambung)
2. Ngobrol seperti biasa di kolom chat
3. Setelah beberapa pesan, cek sidebar bagian **"🧠 Yang aku ingat"** — AI otomatis mencatat fakta-fakta yang kamu sebutkan
4. Tutup browser, buka lagi besok, masukkan nama yang sama → riwayat & memorinya masih ada

## Catatan penting soal privasi

- Field **"Nama"** itu **bukan sistem login sungguhan** — cuma label buat memisahkan data di database. Siapapun yang tau/menebak nama yang kamu pakai bisa membuka riwayat & memori itu di app ini.
- Untuk pemakaian pribadi, kombinasi **nama yang konsisten + `APP_PASSWORD` aktif** sudah cukup aman (orang luar tidak bisa membuka app-nya sama sekali tanpa password).
- Kalau mau berbagi app ini ke orang lain dengan privasi terjamin, butuh sistem autentikasi sungguhan (di luar scope versi ini).

## Catatan teknis

- **Model**: `gemini-2.5-flash-lite` untuk chat maupun ekstraksi memori
- **Konteks chat**: 20 pesan terakhir + semua memori dikirim ke AI setiap giliran (supaya tetap nyambung tanpa token meledak)
- **Ekstraksi memori**: setelah setiap balasan AI, ada 1 panggilan API tambahan untuk mendeteksi fakta baru — sedikit menambah waktu & biaya per pesan, tapi itulah yang membuat memorinya "pintar"
