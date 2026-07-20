#!/usr/bin/env python3
"""
Debug script: cetak struktur mentah satu job dari payload Kalibrr,
untuk menemukan nama field yang benar untuk lokasi, tipe kerja, dan kategori.

Cara pakai:
    python3 debug_kalibrr_fields.py

Hasil akan tersimpan di debug_kalibrr_sample.json — kirim isi file itu
(atau screenshot-nya) supaya bisa dicek field yang benar.
"""

from __future__ import annotations

import json
import sys

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

URL = "https://www.kalibrr.com/id-ID/home/te/internship-jobs"


def main() -> None:
    print(f"Mengambil halaman: {URL}")
    try:
        response = requests.get(URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"GAGAL mengambil halaman: {exc}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, "html.parser")
    next_data = soup.select_one("script#__NEXT_DATA__")
    if not next_data or not next_data.text:
        print("GAGAL: tag __NEXT_DATA__ tidak ditemukan di halaman.")
        print("Kemungkinan struktur halaman Kalibrr sudah berubah.")
        sys.exit(1)

    try:
        payload = json.loads(next_data.text)
        jobs = payload["props"]["pageProps"]["jobs"]
    except (KeyError, json.JSONDecodeError, TypeError) as exc:
        print(f"GAGAL parsing payload: {exc}")
        print("Mencoba cetak struktur payload top-level untuk diagnosis:")
        print(json.dumps(list(payload.keys()) if isinstance(payload, dict) else str(payload)[:500], indent=2))
        sys.exit(1)

    if not jobs:
        print("GAGAL: list 'jobs' kosong.")
        sys.exit(1)

    print(f"\nBerhasil! Ditemukan {len(jobs)} jobs pada payload.")
    print("Menyimpan 1 sample job lengkap ke debug_kalibrr_sample.json ...\n")

    sample_job = jobs[0]
    with open("debug_kalibrr_sample.json", "w", encoding="utf-8") as f:
        json.dump(sample_job, f, ensure_ascii=False, indent=2)

    # Cetak ringkasan key-key top-level dan tipe datanya, untuk gambaran cepat.
    print("=== Daftar key top-level pada 1 job sample ===")
    for key, value in sample_job.items():
        value_preview = str(value)
        if len(value_preview) > 80:
            value_preview = value_preview[:80] + "..."
        print(f"  {key!r}: ({type(value).__name__}) {value_preview}")

    print("\n=== Mencari key yang kemungkinan berisi LOKASI ===")
    location_hint_keys = ["city", "cities", "location", "address", "place", "region"]
    found_any = False
    for key in sample_job.keys():
        if any(hint in key.lower() for hint in location_hint_keys):
            print(f"  DITEMUKAN kandidat: {key!r} = {json.dumps(sample_job[key], ensure_ascii=False)[:200]}")
            found_any = True
    if not found_any:
        print("  Tidak ada key yang cocok dengan kata kunci lokasi pada level ini.")
        print("  Coba cek isi lengkap debug_kalibrr_sample.json secara manual.")

    print("\n=== Mencari key yang kemungkinan berisi TIPE KERJA ===")
    work_hint_keys = ["setup", "remote", "hybrid", "employment", "type", "schedule"]
    for key in sample_job.keys():
        if any(hint in key.lower() for hint in work_hint_keys):
            print(f"  DITEMUKAN kandidat: {key!r} = {json.dumps(sample_job[key], ensure_ascii=False)[:200]}")

    print("\n=== Mencari key yang kemungkinan berisi KATEGORI/SPESIALISASI ===")
    category_hint_keys = ["category", "industry", "function", "specialization", "field"]
    for key in sample_job.keys():
        if any(hint in key.lower() for hint in category_hint_keys):
            print(f"  DITEMUKAN kandidat: {key!r} = {json.dumps(sample_job[key], ensure_ascii=False)[:200]}")

    print("\nSelesai. Silakan kirim isi file debug_kalibrr_sample.json ke chat.")


if __name__ == "__main__":
    main()