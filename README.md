# Chatbot Lowongan Magang (RAG)

Proyek ini mengikuti alur:
1. Scraping lowongan
2. Simpan dataset
3. Preprocessing
4. Embedding
5. Simpan ke Chroma (vector database)
6. User bertanya
7. Retrieval dokumen relevan
8. Generation jawaban pakai Gemini
9. Tampil di Streamlit

## 1) Install dependency

```bash
pip3 install --user -r requirements.txt
```

## 2) Jalankan semua pipeline (disarankan)

Satu command untuk scrape -> preprocess -> build vector DB -> jalankan Streamlit:

```bash
python3 run_pipeline.py
```

Opsi penting:

```bash
# Jalankan preprocess + vector + app (tanpa scrape)
python3 run_pipeline.py --skip-scrape

# Install dependency dulu lalu jalankan app setelah pipeline selesai
python3 run_pipeline.py --install-deps --run-app

# Lewati build DB jika sudah pernah dibuat
python3 run_pipeline.py --skip-build-db --run-app

# Jalankan app di port lain
python3 run_pipeline.py --port 8502
```

Flag yang tersedia:
- `--skip-scrape`
- `--skip-preprocess`
- `--skip-build-db`
- `--run-app`
- `--install-deps`
- `--collection`
- `--port` (default: `8501`)

## 3) Jalankan per langkah (opsional)

### Scraping data lowongan

```bash
python3 scrape_jobs.py
```

Output:
- `data/lowongan_dataset.csv`
- `data/lowongan_dataset.json`

### Preprocessing data

```bash
python3 preprocess_data.py
```

Output:
- `data/lowongan_clean.csv`

### Build embedding + Chroma DB

```bash
python3 build_vector_db.py
```

Output:
- folder `chroma_db/`

## 4) Set API key Gemini

```bash
cp .env.example .env
```

Lalu isi `GEMINI_API_KEY` di file `.env`.

## 5) Jalankan chatbot web (Streamlit)

```bash
streamlit run app.py
```

## 6) Fitur filter di UI

Filter ada di sidebar Streamlit:
- `Lokasi` (exact match metadata di Chroma)
- `Sumber` (exact match metadata di Chroma)
- `Posisi` (filter judul lowongan)
- `Kata kunci` (post-filter pada teks dokumen)
- `Jumlah dokumen retrieval` (`top_k`) sampai 20

Aplikasi juga menampilkan hasil retrieval dalam format kartu lowongan:
- Tombol link lowongan langsung
- URL lowongan ditampilkan penuh
- Highlight keyword pada judul lowongan
- Badge warna untuk sumber dan lokasi
- Layout kartu 2 kolom
- Export rekomendasi ke CSV/PDF

## Catatan sumber data

- Kalibrr sudah berhasil di-scrape.
- Glints kadang terkena proteksi anti-bot (HTTP 403), tergantung environment saat scraping dijalankan.
