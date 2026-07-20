#!/usr/bin/env python3
"""
Debug script: cek distribusi nilai isOpenToFreshGrads dari data CSV yang
sudah di-scrape, untuk memastikan field tersebut benar-benar terbaca,
dan ambil 1 sample mentah langsung dari URL filter resmi Kalibrr
(open_to_fresh_grads) sebagai pembanding.
"""

from __future__ import annotations

import json
import sys

import pandas as pd
import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "id-ID,id;q=0.9,en;q=0.8"}

print("=== BAGIAN 1: Cek data CSV yang sudah di-scrape ===")
try:
    df = pd.read_csv("data/lowongan_clean.csv")
    print(f"Total baris: {len(df)}")
    print("Distribusi employment_level:")
    print(df["employment_level"].value_counts())
except FileNotFoundError:
    print("File data/lowongan_clean.csv tidak ditemukan, skip bagian ini.")

print()
print("=== BAGIAN 2: Ambil sample LANGSUNG dari URL filter resmi Kalibrr (open_to_fresh_grads) ===")
url = "https://www.kalibrr.com/id-ID/home/te/open_to_fresh_grads"
print(f"Mencoba: {url}")
try:
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
except requests.RequestException as exc:
    print(f"GAGAL mengambil halaman: {exc}")
    sys.exit(1)

soup = BeautifulSoup(response.text, "html.parser")
next_data = soup.select_one("script#__NEXT_DATA__")
if not next_data or not next_data.text:
    print("GAGAL: tag __NEXT_DATA__ tidak ditemukan. Slug ini mungkin tidak valid.")
    sys.exit(1)

try:
    payload = json.loads(next_data.text)
    jobs = payload["props"]["pageProps"]["jobs"]
except (KeyError, json.JSONDecodeError, TypeError) as exc:
    print(f"GAGAL parsing payload: {exc}")
    sys.exit(1)

if not jobs:
    print("GAGAL: list 'jobs' kosong untuk slug ini.")
    sys.exit(1)

print(f"\nBerhasil! Ditemukan {len(jobs)} jobs pada slug open_to_fresh_grads.")
print("\nMengecek field isOpenToFreshGrads pada 5 job pertama:")
for job in jobs[:5]:
    name = job.get("name", "?")
    is_fresh = job.get("isOpenToFreshGrads")
    work_exp = job.get("workExperience")
    print(f"  - {name!r}: isOpenToFreshGrads={is_fresh!r}, workExperience={work_exp!r}")

with open("debug_freshgrads_sample.json", "w", encoding="utf-8") as f:
    json.dump(jobs[0], f, ensure_ascii=False, indent=2)
print("\n1 sample job lengkap disimpan ke debug_freshgrads_sample.json")
