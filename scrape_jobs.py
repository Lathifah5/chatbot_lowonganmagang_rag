#!/usr/bin/env python3
"""
Scrape internship/job vacancies for chatbot dataset bootstrap.

Sources:
- Kalibrr (direct public page payload)
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

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

# Board listing: https://www.kalibrr.com/id-ID/home/te/<slug> (lowongan Indonesia)
# Setiap slug dipetakan ke kategori/spesialisasi yang lebih ringkas untuk dataset,
# karena Kalibrr tidak selalu mengirim field kategori yang konsisten per job pada
# payload listing. Mapping ini dipakai sebagai fallback spesialisasi.
_SLUG_TO_SPESIALISASI: Dict[str, str] = {
    "internship-jobs": "Umum",
    "magang-jobs": "Umum",
    "fresh-graduate-jobs": "Umum",
    "entry-level-jobs": "Umum",
    "part-time-jobs": "Umum",
    "it-jobs": "IT & Software",
    "developer-jobs": "IT & Software",
    "software-engineer-jobs": "IT & Software",
    "data-jobs": "Data",
    "engineering-jobs": "Engineering",
    "frontend-jobs": "IT & Software",
    "backend-jobs": "IT & Software",
    "full-stack-jobs": "IT & Software",
    "machine-learning-jobs": "Data",
    "ai-jobs": "Data",
    "quality-assurance-jobs": "IT & Software",
    "project-management-jobs": "Project Management",
    "product-management-jobs": "Project Management",
    "cybersecurity-jobs": "IT & Software",
    "devops-jobs": "IT & Software",
    "ui-ux-jobs": "Design",
    "business-analyst-jobs": "Data",
    "mobile-developer-jobs": "IT & Software",
    "java-developer-jobs": "IT & Software",
    "python-developer-jobs": "IT & Software",
    "golang-developer-jobs": "IT & Software",
    "react-developer-jobs": "IT & Software",
    "android-developer-jobs": "IT & Software",
    "ios-developer-jobs": "IT & Software",
    "cloud-engineer-jobs": "IT & Software",
    "network-engineer-jobs": "IT & Software",
    "system-administrator-jobs": "IT & Software",
    "database-administrator-jobs": "IT & Software",
    "blockchain-jobs": "IT & Software",
    "technical-support-jobs": "IT & Software",
    "marketing-jobs": "Marketing",
    "sales-jobs": "Sales",
    "human-resources-jobs": "Human Resources",
    "accounting-jobs": "Accounting & Finance",
    "finance-jobs": "Accounting & Finance",
    "customer-service-jobs": "Customer Service",
    "graphic-design-jobs": "Design",
    "content-writer-jobs": "Marketing",
    "video-editor-jobs": "Design",
    "social-media-jobs": "Marketing",
    "digital-marketing-jobs": "Marketing",
    "business-development-jobs": "Sales",
    "operations-jobs": "Operations",
    "supply-chain-jobs": "Operations",
    "logistics-jobs": "Operations",
    "warehouse-jobs": "Operations",
    "manufacturing-jobs": "Engineering",
    "civil-engineer-jobs": "Engineering",
    "mechanical-engineer-jobs": "Engineering",
    "electrical-engineer-jobs": "Engineering",
    "nurse-jobs": "Kesehatan",
    "teacher-jobs": "Pendidikan",
    "administrative-jobs": "Administrasi",
    "receptionist-jobs": "Administrasi",
    "legal-jobs": "Legal",
    "remote-jobs": "Umum",
    "work-from-home-jobs": "Umum",
    "banking-jobs": "Accounting & Finance",
    "insurance-jobs": "Accounting & Finance",
    "real-estate-jobs": "Sales",
    "hospitality-jobs": "Hospitality",
    "chef-jobs": "Hospitality",
    "barista-jobs": "Hospitality",
    "call-center-jobs": "Customer Service",
    "virtual-assistant-jobs": "Administrasi",
    "data-entry-jobs": "Administrasi",
    "accounting-staff-jobs": "Accounting & Finance",
}

KALIBRR_QUERIES: List[str] = list(_SLUG_TO_SPESIALISASI.keys())
KALIBRR_LISTING_TEMPLATE = "https://www.kalibrr.com/id-ID/home/te/{slug}"


@dataclass
class JobRecord:
    title: str
    company: str
    location: str
    description: str
    link: str
    source: str
    tipe_kerja: str = ""
    work_setup: str = ""
    spesialisasi: str = ""
    scraped_date: str = ""
    deadline: str = ""
    employment_level: str = ""
    salary: str = ""


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def to_absolute_kalibrr_link(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if path.startswith("/"):
        return f"https://www.kalibrr.com{path}"
    return f"https://www.kalibrr.com/{path}"


def build_kalibrr_detail_link(job: Dict) -> str:
    slug = str(job.get("slug", "")).strip("/")
    job_id = str(job.get("id", "")).strip()
    company_code = str((job.get("company") or {}).get("code", "")).strip("/")

    # Canonical detail URL pattern from Kalibrr listing cards:
    # /c/<company-code>/jobs/<job-id>/<slug>
    if company_code and job_id and slug:
        return to_absolute_kalibrr_link(f"/c/{company_code}/jobs/{job_id}/{slug}")
    if slug:
        return to_absolute_kalibrr_link(slug)
    return ""


def extract_location(job: Dict) -> str:
    """Ekstrak lokasi dari field googleLocation.addressComponents (city, region).

    Payload listing Kalibrr tidak memiliki field 'cities' seperti yang
    diasumsikan sebelumnya; lokasi sebenarnya tersimpan di
    googleLocation.addressComponents.city / .region.
    """
    google_location = job.get("googleLocation") or {}
    address = google_location.get("addressComponents") or {}
    city = clean_text(address.get("city"))
    region = clean_text(address.get("region"))

    if city and region and city != region:
        return f"{city}, {region}"
    return city or region or "N/A"


def extract_work_setup(job: Dict) -> str:
    """Ekstrak lokasi kerja (Remote/Hybrid/Onsite) dari payload job Kalibrr.

    Field asli yang dikonfirmasi dari payload mentah:
    - isHybrid (bool), isWorkFromHome (bool) -> work setup
    """
    is_hybrid = bool(job.get("isHybrid"))
    is_wfh = bool(job.get("isWorkFromHome"))

    if is_wfh:
        return "Remote"
    if is_hybrid:
        return "Hybrid"
    return "Onsite"


_TENURE_NORMALIZATION: Dict[str, str] = {
    "internship": "Magang",
    "full time": "Full Time",
    "fulltime": "Full Time",
    "part time": "Part Time",
    "parttime": "Part Time",
    "contractual": "Kontrak",
    "contract": "Kontrak",
    "freelance": "Freelance",
    "temporary": "Sementara",
}


def extract_tipe_kerja(job: Dict) -> str:
    """Ekstrak jenis kontrak/hubungan kerja (tenure) dari payload job Kalibrr,
    dinormalisasi ke label Bahasa Indonesia yang konsisten.

    PENTING: nilai asli field 'tenure' pada payload Kalibrr berbahasa
    Inggris (contoh: "Internship", "Contractual", "Full Time"). Nilai ini
    HARUS dinormalisasi di sini agar konsisten dengan keyword deteksi
    Bahasa Indonesia yang dipakai pada app.py (_EMPLOYMENT_TYPE_KEYWORDS).
    Jika tidak dinormalisasi, hard filter di app.py akan gagal mencocokkan
    nilai (mis. mencari "Magang" padahal data tersimpan sebagai "Internship"),
    menyebabkan filter diam-diam tidak diterapkan.
    """
    raw_tenure = clean_text(job.get("tenure"))
    if not raw_tenure:
        return ""
    normalized = _TENURE_NORMALIZATION.get(raw_tenure.strip().lower())
    return normalized or raw_tenure


def extract_spesialisasi(job: Dict) -> str:
    """Ekstrak spesialisasi/kategori dari field 'function' pada payload Kalibrr.

    Contoh nilai asli: "Accounting and Finance", "IT and Software", dst.
    """
    return clean_text(job.get("function"))


def extract_deadline(job: Dict) -> str:
    """Ekstrak tanggal batas lamaran (deadline) dari field applicationEndDate.

    Field ini dikonfirmasi langsung dari payload mentah Kalibrr
    (__NEXT_DATA__), formatnya ISO 8601 (contoh: 2026-08-02T17:00:00+00:00).
    """
    raw_date = job.get("applicationEndDate")
    if not raw_date:
        return ""
    # Ambil bagian tanggal saja (YYYY-MM-DD), buang waktu dan timezone.
    return str(raw_date)[:10]


def extract_employment_level(job: Dict) -> str:
    """Ekstrak jenjang pengalaman (Fresh Graduate/Entry Level/dst) dari
    field educationLevel atau workExperience pada payload Kalibrr.

    Field ini berupa kode angka pada payload mentah (contoh: educationLevel=200,
    workExperience=100), bukan teks langsung. Kalibrr tidak mempublikasikan
    dokumentasi resmi pemetaan kode ini, sehingga nilai mentah disimpan
    sebagai referensi tanpa diterjemahkan menjadi label yang bisa salah arti.
    """
    is_fresh_grad = bool(job.get("isOpenToFreshGrads"))
    if is_fresh_grad:
        return "Fresh Graduate"
    work_exp = job.get("workExperience")
    if work_exp is not None:
        return f"Pengalaman kerja (kode level: {work_exp})"
    return ""


def extract_salary(job: Dict) -> str:
    """Ekstrak informasi gaji dari field baseSalary/maximumSalary/salaryCurrency
    pada payload Kalibrr. Banyak lowongan tidak mencantumkan gaji secara
    terbuka (salaryShown=False atau nilai None), sehingga hasilnya sering
    berupa string kosong -- ini bukan bug, melainkan keterbatasan data asli.
    """
    if not job.get("salaryShown", True):
        return ""
    base = job.get("baseSalary")
    maximum = job.get("maximumSalary")
    currency = job.get("salaryCurrency") or "IDR"
    if base and maximum:
        return f"{currency} {base:,.0f} - {maximum:,.0f}"
    if base:
        return f"{currency} {base:,.0f}"
    return ""


def load_job_records_from_json(path: Path) -> Dict[str, JobRecord]:
    """Load existing dataset rows keyed by job URL (for merge + refresh)."""
    with path.open(encoding="utf-8") as handle:
        rows = json.load(handle)
    out: Dict[str, JobRecord] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        link = str(row.get("link", "")).strip()
        if not link:
            continue
        src = clean_text(row.get("source")) or "Kalibrr"
        out[link] = JobRecord(
            title=clean_text(row.get("title")),
            company=clean_text(row.get("company")),
            location=clean_text(row.get("location")),
            description=clean_text(row.get("description")),
            link=link,
            source=src,
            tipe_kerja=clean_text(row.get("tipe_kerja")),
            work_setup=clean_text(row.get("work_setup")),
            spesialisasi=clean_text(row.get("spesialisasi")),
            scraped_date=clean_text(row.get("scraped_date")),
            deadline=clean_text(row.get("deadline")),
            employment_level=clean_text(row.get("employment_level")),
            salary=clean_text(row.get("salary")),
        )
    return out


def scrape_kalibrr(max_records: int = 1500, merge_from: Optional[Path] = None) -> List[JobRecord]:
    records: Dict[str, JobRecord] = {}
    if merge_from is not None and merge_from.exists():
        records = load_job_records_from_json(merge_from)

    today_str = date.today().isoformat()

    for query_slug in KALIBRR_QUERIES:
        if len(records) >= max_records:
            break

        url = KALIBRR_LISTING_TEMPLATE.format(slug=query_slug)
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        next_data = soup.select_one("script#__NEXT_DATA__")
        if not next_data or not next_data.text:
            continue

        try:
            payload = json.loads(next_data.text)
            jobs = payload["props"]["pageProps"]["jobs"]
        except (KeyError, json.JSONDecodeError, TypeError):
            continue

        if not isinstance(jobs, list):
            continue

        for job in jobs:
            if len(records) >= max_records:
                break

            link = build_kalibrr_detail_link(job)
            if not link:
                continue

            company = (job.get("company") or {}).get("name", "")
            location = extract_location(job)
            description = clean_text(job.get("teaser")) or clean_text(job.get("description"))
            tipe_kerja = extract_tipe_kerja(job)
            work_setup = extract_work_setup(job)
            spesialisasi = extract_spesialisasi(job) or _SLUG_TO_SPESIALISASI.get(query_slug, "")
            deadline = extract_deadline(job)
            employment_level = extract_employment_level(job)
            salary = extract_salary(job)

            # Selalu timpa entri lama agar teaser/deskripsi ikut data terbaru dari listing.
            records[link] = JobRecord(
                title=clean_text(job.get("name")),
                company=clean_text(company),
                location=location,
                description=description,
                link=link,
                source="Kalibrr",
                tipe_kerja=tipe_kerja,
                work_setup=work_setup,
                spesialisasi=spesialisasi,
                scraped_date=today_str,
                deadline=deadline,
                employment_level=employment_level,
                salary=salary,
            )

    return list(records.values())


def scrape_glints_direct(max_records: int = 100) -> List[JobRecord]:
    """
    Direct scrape attempt for Glints.
    In some environments this is blocked by Glints firewall (HTTP 403).
    """
    records: Dict[str, JobRecord] = {}
    today_str = date.today().isoformat()
    seeds = [
        "https://glints.com/id/opportunities/jobs/explore?keyword=magang",
        "https://glints.com/id/opportunities/jobs/explore?keyword=internship",
        "https://glints.com/id/opportunities/jobs/explore?keyword=software%20engineer",
    ]

    for url in seeds:
        if len(records) >= max_records:
            break
        try:
            response = requests.get(url, headers=HEADERS, timeout=8)
        except requests.RequestException:
            continue

        if response.status_code != 200:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("a[href*='/id/opportunities/jobs/']")
        for card in cards:
            if len(records) >= max_records:
                break
            href = card.get("href", "")
            link = href if href.startswith("http") else f"https://glints.com{href}"
            if "/id/opportunities/jobs/" not in link or link in records:
                continue
            title = clean_text(card.get_text(" ", strip=True))
            records[link] = JobRecord(
                title=title,
                company="",
                location="",
                description="",
                link=link,
                source="Glints",
                tipe_kerja="",
                spesialisasi="",
                scraped_date=today_str,
            )

    return list(records.values())


def save_outputs(records: List[JobRecord], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "lowongan_dataset.json"
    csv_path = output_dir / "lowongan_dataset.csv"

    rows = [asdict(record) for record in records]

    with json_path.open("w", encoding="utf-8") as jf:
        json.dump(rows, jf, ensure_ascii=False, indent=2)

    with csv_path.open("w", newline="", encoding="utf-8") as cf:
        writer = csv.DictWriter(
            cf,
            fieldnames=[
                "title", "company", "location", "description", "link", "source",
                "tipe_kerja", "work_setup", "spesialisasi", "scraped_date",
                "deadline", "employment_level", "salary",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape lowongan ke data/lowongan_dataset.{json,csv}")
    parser.add_argument(
        "--max-records",
        type=int,
        default=1500,
        help="Target maksimum total baris (gabungan file lama + baru, dedupe by link).",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Jangan gabung dengan data/lowongan_dataset.json yang sudah ada.",
    )
    args = parser.parse_args()

    data_dir = Path("data")
    existing = data_dir / "lowongan_dataset.json"
    merge_path = None if args.no_merge else existing

    kalibrr_data = scrape_kalibrr(max_records=args.max_records, merge_from=merge_path)
    glints_data = scrape_glints_direct(max_records=120)

    # Merge and deduplicate by link.
    merged: Dict[str, JobRecord] = {item.link: item for item in kalibrr_data}
    for item in glints_data:
        merged[item.link] = item

    all_records = list(merged.values())
    save_outputs(all_records, data_dir)

    source_counts: Dict[str, int] = {}
    for rec in all_records:
        source_counts[rec.source] = source_counts.get(rec.source, 0) + 1

    print(f"Total data tersimpan: {len(all_records)}")
    for source, count in sorted(source_counts.items()):
        print(f"- {source}: {count}")

    with_tipe_kerja = sum(1 for rec in all_records if rec.tipe_kerja)
    with_work_setup = sum(1 for rec in all_records if rec.work_setup)
    with_spesialisasi = sum(1 for rec in all_records if rec.spesialisasi)
    with_deadline = sum(1 for rec in all_records if rec.deadline)
    with_employment_level = sum(1 for rec in all_records if rec.employment_level)
    with_salary = sum(1 for rec in all_records if rec.salary)
    print(f"Data dengan tipe_kerja terisi: {with_tipe_kerja}/{len(all_records)}")
    print(f"Data dengan work_setup terisi: {with_work_setup}/{len(all_records)}")
    work_setup_counts: Dict[str, int] = {}
    for rec in all_records:
        if rec.work_setup:
            work_setup_counts[rec.work_setup] = work_setup_counts.get(rec.work_setup, 0) + 1
    print(f"Distribusi work_setup: {work_setup_counts}")
    print(f"Data dengan spesialisasi terisi: {with_spesialisasi}/{len(all_records)}")
    print(f"Data dengan deadline terisi: {with_deadline}/{len(all_records)}")
    print(f"Data dengan employment_level terisi: {with_employment_level}/{len(all_records)}")
    print(f"Data dengan salary terisi: {with_salary}/{len(all_records)} (wajar jika rendah, banyak lowongan tidak menampilkan gaji)")

    if source_counts.get("Glints", 0) == 0:
        print(
            "Catatan: Glints tidak mengembalikan data dari environment ini "
            "(kemungkinan anti-bot/firewall 403)."
        )


if __name__ == "__main__":
    main()