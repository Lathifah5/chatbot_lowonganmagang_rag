#!/usr/bin/env python3
"""
Build Chroma vector database from preprocessed dataset.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import chromadb
import pandas as pd
from chromadb.utils import embedding_functions


def build_chroma(
    input_csv: Path,
    db_dir: Path,
    collection_name: str = "lowongan_magang",
) -> None:
    df = pd.read_csv(input_csv).fillna("")
    if "document" not in df.columns:
        raise ValueError("Kolom 'document' tidak ditemukan. Jalankan preprocess_data.py dulu.")
    required_cols = [
        "title", "company", "location", "spesialisasi", "work_setup", "tipe_kerja",
        "employment_level", "salary", "deadline", "status", "link",
        "source", "scraped_date",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Kolom berikut tidak ditemukan pada {input_csv}: {missing_cols}. "
            "Jalankan ulang preprocess_data.py versi terbaru terlebih dahulu."
        )

    texts = df["document"].astype(str).tolist()
    ids = [f"job-{i}" for i in range(len(df))]
    
    metadatas = []

    for _, row in df.iterrows():

            title = str(row["title"]).strip()
            title_lower = title.lower()

            tipe = str(row["tipe_kerja"]).strip()

            # Normalisasi Employment Type
            if any(k in title_lower for k in ["internship", "intern", "magang"]):
                tipe = "Internship"

            elif "contract" in tipe.lower() or "kontrak" in tipe.lower():
                tipe = "Contract"

            elif "part" in tipe.lower():
                tipe = "Part Time"

            elif "full" in tipe.lower():
                tipe = "Full Time"

            metadatas.append(
                {
                    "title": title,
                    "company": str(row["company"]),
                    "location": str(row["location"]),
                    "spesialisasi": str(row["spesialisasi"]),
                    "work_setup": str(row["work_setup"]),
                    "tipe_kerja": tipe,
                    "employment_level": str(row["employment_level"]),
                    "salary": str(row["salary"]),
                    "deadline": str(row["deadline"]),
                    "status": str(row["status"]),
                    "link": str(row["link"]),
                    "source": str(row["source"]),
                    "scraped_date": str(row["scraped_date"]),
                }
            )
    

    db_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(db_dir))
    embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
    )

    # Reset collection content for reproducible rebuild.
    existing = collection.get(include=[])
    if existing.get("ids"):
        collection.delete(ids=existing["ids"])

    collection.add(ids=ids, documents=texts, metadatas=metadatas)
    print(f"Vector DB selesai. Total dokumen masuk Chroma: {len(ids)}")
    print(f"DB path: {db_dir}")
    print(f"Collection: {collection_name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/lowongan_clean.csv", help="Path data bersih CSV")
    parser.add_argument("--db-dir", default="chroma_db", help="Direktori penyimpanan Chroma")
    parser.add_argument("--collection", default="lowongan_magang", help="Nama collection Chroma")
    args = parser.parse_args()

    build_chroma(Path(args.input), Path(args.db_dir), args.collection)


if __name__ == "__main__":
    main()