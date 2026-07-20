#!/usr/bin/env python3
"""
Preprocess raw scraped vacancies for RAG ingestion.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


def normalize_text(value: str) -> str:
    value = "" if pd.isna(value) else str(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def compute_status(deadline_str: str, reference_date=None) -> str:
    """Hitung status lowongan (Aktif/Tutup) berdasarkan tanggal deadline.

    Lowongan tanpa deadline tercatat dianggap 'Aktif' karena tidak ada
    bukti bahwa lowongan tersebut sudah ditutup oleh perusahaan.
    """
    from datetime import datetime

    deadline_str = (deadline_str or "").strip()
    if not deadline_str:
        return "Aktif"
    try:
        deadline_date = datetime.strptime(deadline_str[:10], "%Y-%m-%d")
    except ValueError:
        return "Aktif"
    ref = reference_date or datetime.now()
    return "Tutup" if deadline_date < ref else "Aktif"


def build_document(row: pd.Series) -> str:
    return f"""Judul Pekerjaan : {row['title']}
Perusahaan : {row['company']}
Lokasi : {row['location']}
Spesialisasi : {row['spesialisasi']}
Work Setup : {row['work_setup']}
Tipe Kerja : {row['tipe_kerja']}
Employment Level : {row['employment_level']}
Gaji : {row['salary']}
Deadline : {row['deadline']}
Status : {row['status']}
Deskripsi :
{row['description']}
Link :
{row['link']}
"""


def preprocess(input_path: Path, output_path: Path) -> None:
    if input_path.suffix.lower() == ".csv":
        df = pd.read_csv(input_path)
    else:
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)

    expected_cols = [
        "title", "company", "location", "description", "link", "source",
        "tipe_kerja", "work_setup", "spesialisasi", "scraped_date",
        "deadline", "employment_level", "salary",
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    df = df[expected_cols].copy()

    for col in expected_cols:
        df[col] = df[col].map(normalize_text)

    # Remove unusable rows and duplicate vacancies.
    df = df[(df["title"] != "") & (df["link"] != "")]
    df = df.drop_duplicates(subset=["link"], keep="first").reset_index(drop=True)

    # Hitung status (Aktif/Tutup) berdasarkan tanggal deadline sebelum
    # membangun teks dokumen, karena build_document membutuhkan kolom ini.
    df["status"] = df["deadline"].map(compute_status)

    df["document"] = df.apply(build_document, axis=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Preprocess selesai. Total data bersih: {len(df)}")
    print(f"Tersimpan di: {output_path}")
    with_tipe_kerja = int((df["tipe_kerja"] != "").sum())
    with_work_setup = int((df["work_setup"] != "").sum())
    with_spesialisasi = int((df["spesialisasi"] != "").sum())
    with_deadline = int((df["deadline"] != "").sum())
    with_employment_level = int((df["employment_level"] != "").sum())
    with_salary = int((df["salary"] != "").sum())
    print(f"Data dengan tipe_kerja terisi: {with_tipe_kerja}/{len(df)}")
    print(f"Data dengan work_setup terisi: {with_work_setup}/{len(df)}")
    work_setup_counts = df["work_setup"].value_counts().to_dict()
    print(f"Distribusi work_setup: {work_setup_counts}")
    print(f"Data dengan spesialisasi terisi: {with_spesialisasi}/{len(df)}")
    print(f"Data dengan deadline terisi: {with_deadline}/{len(df)}")
    print(f"Data dengan employment_level terisi: {with_employment_level}/{len(df)}")
    print(f"Data dengan salary terisi: {with_salary}/{len(df)}")
    status_counts = df["status"].value_counts().to_dict()
    print(f"Distribusi status lowongan: {status_counts}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
    "--input",
    default="data/lowongan_dataset.csv",
    help="Path dataset mentah (CSV/JSON)",
)
    parser.add_argument(
        "--output",
        default="data/lowongan_clean.csv",
        help="Path output dataset bersih (CSV)",
    )
    args = parser.parse_args()

    preprocess(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()