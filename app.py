#!/usr/bin/env python3
"""
Streamlit chatbot for internship vacancy information using RAG.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO
from typing import Dict, List, Tuple

import chromadb
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from chromadb.utils import embedding_functions
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


load_dotenv()


def greeting_parts_for_hour(hour: int) -> Tuple[str, str]:
    """(emoji, teks salam) sesuai jam lokal — kebiasaan Indonesia."""
    if 4 <= hour < 11:
        return "🌅", "Selamat pagi"
    if 11 <= hour < 15:
        return "☀️", "Selamat siang"
    if 15 <= hour < 19:
        return "🌤️", "Selamat sore"
    return "🌙", "Selamat malam"


def inject_app_theme_css() -> None:
    """Gradien halus + animasi pada latar; hero salam kiri & judul tengah."""
    st.markdown(
        """
        <style>
        @keyframes kbGradientDrift {
            0% { background-position: 0% 45%; }
            50% { background-position: 100% 55%; }
            100% { background-position: 0% 45%; }
        }
        @keyframes kbTitleSheen {
            0% { background-position: 0% 50%; }
            100% { background-position: 200% 50%; }
        }
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(
                125deg,
                #fdf4ff 0%,
                #eef2ff 30%,
                #ecfeff 58%,
                #f5f3ff 82%,
                #e0f2fe 100%
            );
            background-size: 220% 220%;
            animation: kbGradientDrift 24s ease-in-out infinite;
        }
        [data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0.78);
            backdrop-filter: blur(12px);
        }

        html {
        color-scheme: light;
    }

        body {

        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;

        
        color: #1f2937 !important;
        background-color: #ffffff !important;
    }

        [data-testid="stAppViewContainer"] {
        color: #1f2937 !important;
    }

        [data-testid="stMarkdownContainer"] {
        color: #1f2937 !important;
    }

        [data-testid="stCaptionContainer"] {
        color: #6b7280 !important;
    }

        .stMarkdown,
        .stText,
        p,
        span,
        label {
        color: #1f2937 !important;
    }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(250,245,255,0.93) 100%);
            border-right: 1px solid rgba(124, 58, 237, 0.1);
        }
        .kb-hero-zone {
            margin: 0.2rem 0 1.35rem 0;
            padding: 0.5rem 0 0.25rem 0;
        }
        .kb-hero-row {
            display: flex;
            flex-direction: row;
            flex-wrap: wrap;
            align-items: center;
            justify-content: flex-start;
            gap: clamp(1.75rem, 6vw, 4rem);
            row-gap: 0.75rem;
            width: 100%;
        }
        .kb-greet-plain {
            flex: 0 0 auto;
            margin: 0;
            padding: 0;
            border: none;
            background: none;
            box-shadow: none;
            font-size: 1.05rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            color: #5b21b6;
            line-height: 1.3;
        }
        .kb-greet-plain .kb-greet-emoji {
            margin-right: 0.35rem;
        }
        .kb-title-full {
            flex: 1 1 280px;
            margin: 0;
            min-width: 0;
            padding: 0;
            font-size: clamp(1rem, 2.65vw, 1.65rem);
            font-weight: 800;
            line-height: 1.28;
            letter-spacing: -0.02em;
            text-align: center;
            text-wrap: balance;
            max-width: 100%;
            background: linear-gradient(
                100deg,
                #4c1d95 0%,
                #6d28d9 20%,
                #0d9488 42%,
                #1d4ed8 62%,
                #6d28d9 82%,
                #4c1d95 100%
            );
            background-size: 220% auto;
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            color: #2563eb;
            animation: kbTitleSheen 11s linear infinite;
        }

        /* ===== FIX DARK MODE ===== */

        @media (prefers-color-scheme: dark) {

            div[data-testid="stMarkdownContainer"] p,
            div[data-testid="stMarkdownContainer"] strong,
            div[data-testid="stMarkdownContainer"] span{
            color:#ffffff !important;

                color:#FAFAFA !important;
                text-shadow:0 0 1px rgba(255,255,255,.25);
        }

            div[data-testid="stCaptionContainer"]{
            color:#d1d5db !important;
                color:#E5E7EB !important;
                text-shadow:0 0 1px rgba(255,255,255,.25);
        }

            div[data-testid="stCaptionContainer"] p{
            color:#d1d5db !important;
        }

    }

        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero_header() -> None:
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    emoji, greet = greeting_parts_for_hour(now.hour)

    st.markdown(
        f"""
        <div class="kb-hero-zone">
            <div class="kb-hero-row">
                <p class="kb-greet-plain">
                    <span class="kb-greet-emoji">{emoji}</span>{greet}
                </p>
                <h1 class="kb-title-full">
                    Asisten Pencarian Lowongan Magang & Kerja Berbasis RAG
                </h1>
            </div>
        """,
        unsafe_allow_html=True,
    )
    render_database_info()


def render_database_info() -> None:
    """Tampilkan ringkasan dataset: sumber, total lowongan, tanggal update terakhir."""
    try:
        collection = get_collection()
        total = collection.count()
    except Exception:
        total = None

    last_updated = _get_db_last_updated_date()

    with st.container(border=True):
        st.markdown("📌 **Informasi Sistem**")
        cols = st.columns(3)
        with cols[0]:
            st.caption("Data")
            st.markdown("**Kalibrr**")
        with cols[1]:
            st.caption("Total Lowongan")
            st.markdown(f"**{total if total is not None else '-'}**")
        with cols[2]:
            st.caption("Terakhir Update")
            st.markdown(f"**{last_updated if last_updated else '-'}**")


def _get_db_last_updated_date() -> str:
    """Mengambil tanggal scraping terbaru dari metadata ChromaDB."""

    try:
        collection = get_collection()
        payload = collection.get(include=["metadatas"])

        metas = payload.get("metadatas", [])

        dates = []

        for meta in metas:
            if meta and meta.get("scraped_date"):
                dates.append(str(meta["scraped_date"]))

        if dates:
            return max(dates)

    except Exception:
        pass

    try:
        sqlite_path = os.path.join(DB_DIR, "chroma.sqlite3")
        if os.path.exists(sqlite_path):
            mtime = os.path.getmtime(sqlite_path)
            return datetime.fromtimestamp(mtime).strftime("%d %B %Y")
    except Exception:
        pass

    return ""


COLLECTION_NAME = "lowongan_magang"
DB_DIR = "chroma_db"
DEEPSEEK_MODEL = "deepseek/deepseek-v3.2"

# Daftar 22 kategori spesialisasi resmi yang ditampilkan Kalibrr pada halaman
# kategori pekerjaan mereka (kalibrr.com/job-category), dipetakan ke nilai
# spesialisasi aktual pada dataset (hasil field 'function' dari payload
# Kalibrr, lihat scrape_jobs.py). Mapping ini HANYA dipakai untuk tampilan
# referensi di antarmuka; belum dipakai sebagai filter aktif pada query.

SPESIALISASI_KALIBRR_KE_DATASET = {

    # Accounting
    "akuntansi": "Accounting and Finance",
    "accounting": "Accounting and Finance",
    "finance": "Accounting and Finance",
    "keuangan": "Accounting and Finance",

    # Administration
    "administrasi": "Administration and Coordination",
    "admin": "Administration and Coordination",
    "koordinasi": "Administration and Coordination",

    # Engineering
    "arsitektur": "Architecture and Engineering",
    "engineering": "Architecture and Engineering",
    "teknik": "Architecture and Engineering",
    "sipil": "Architecture and Engineering",
    "mesin": "Architecture and Engineering",

    # Media & Creative
    "desain": "Media and Creatives",
    "designer": "Media and Creatives",
    "creative": "Media and Creatives",
    "grafis": "Media and Creatives",
    "multimedia": "Media and Creatives",

    # Customer Service
    "customer service": "Customer Service",
    "cs": "Customer Service",

    # Education
    "pendidikan": "Education and Training",
    "guru": "Education and Training",
    "training": "Education and Training",

    # Health
    "kesehatan": "Health and Medical",
    "medis": "Health and Medical",
    "dokter": "Health and Medical",
    "perawat": "Health and Medical",
    "farmasi": "Health and Medical",

    # Hospitality
    "hotel": "Hospitality and Tourism",
    "hospitality": "Hospitality and Tourism",
    "pariwisata": "Hospitality and Tourism",

    # Human Resources
    "hr": "Human Resources",
    "hrd": "Human Resources",
    "human resource": "Human Resources",
    "rekrutmen": "Human Resources",
    "recruitment": "Human Resources",
    "psikologi": "Human Resources",

    # IT
    "it": "IT and Software",
    "informatika": "IT and Software",
    "teknik informatika": "IT and Software",
    "sistem informasi": "IT and Software",
    "software": "IT and Software",
    "developer": "IT and Software",
    "frontend": "IT and Software",
    "backend": "IT and Software",
    "programmer": "IT and Software",
    "web developer": "IT and Software",

    # Legal
    "legal": "Legal",
    "hukum": "Legal",

    # Management
    "management": "Management and Consultancy",
    "manajemen": "Management and Consultancy",
    "consultant": "Management and Consultancy",

    # Manufacturing
    "manufaktur": "Manufacturing and Production",
    "produksi": "Manufacturing and Production",

    # Marketing
    "marketing": "Sales and Marketing",
    "sales": "Sales and Marketing",
    "pemasaran": "Sales and Marketing",
    "digital marketing": "Sales and Marketing",

    # Research
    "research": "Science and Research",
    "peneliti": "Science and Research",
    "riset": "Science and Research",

    # Data
    "data analyst": "IT and Software",
    "analyst": "IT and Software",
    "analisis": "IT and Software",
    "data science": "IT and Software",

    # Supply Chain
    "warehouse": "Supply Chain",
    "supply": "Supply Chain",
    "logistik": "Supply Chain",

    # Writer
    "writer": "Writing and Content",
    "content": "Writing and Content",
    "copywriter": "Writing and Content",
}

SOURCE_BADGE_COLORS = {
    "kalibrr": "#5b8def",
    "glints": "#ff7a59",
}

# Lokasi umum di Indonesia (huruf kecil). Urut panjang → pendek agar "jakarta selatan"
# menang sebelum "jakarta" saat keduanya disebut.
_BASE_LOCATION_KEYWORDS: Tuple[str, ...] = (
    "jakarta selatan",
    "jakarta barat",
    "jakarta pusat",
    "jakarta utara",
    "jakarta timur",
    "tangerang selatan",
    "tangerang city",
    "dki jakarta",
    "jabodetabek",
    "jakarta",
    "bekasi",
    "depok",
    "bogor",
    "tangerang",
    "cikarang",
    "karawang",
    "serang",
    "banten",
    "bandung",
    "surabaya",
    "medan",
    "semarang",
    "yogyakarta",
    "jogja",
    "malang",
    "makassar",
    "palembang",
    "batam",
    "balikpapan",
    "denpasar",
    "solo",
    "sidoarjo",
    "gresik",
)


def _normalize_location_text(text: str) -> str:
    t = text.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return f" {t} "


def _corpus_mentions_location(corpus_normalized: str, location_keyword: str) -> bool:
    if not location_keyword:
        return True
    kw = re.sub(r"\s+", " ", location_keyword.lower().strip())
    if not kw:
        return True
    return f" {kw} " in corpus_normalized


# Kata fungsi / umum yang tidak membedakan bidang lowongan (untuk skor re-rank).
_RETRIEVAL_STOPWORDS: frozenset[str] = frozenset(
    {
        "lowongan",
        "loker",
        "kerja",
        "cari",
        "mencari",
        "ada",
        "apakah",
        "tolong",
        "minta",
        "butuh",
        "ingin",
        "saya",
        "aku",
        "kamu",
        "program",
        "informasi",
        "info",
        "tentang",
        "mengenai",
        "untuk",
        "dengan",
        "yang",
        "dari",
        "dan",
        "atau",
        "di",
        "ke",
        "pada",
        "ini",
        "itu",
        "adalah",
        "bagaimana",
        "berapa",
        "bisa",
        "boleh",
        "dong",
        "nih",
        "deh",
        "magang",
        "intern",
        "internship",
        "maganger",
        "anak",
        "fresh",
        "graduate",
        "entry",
        "level",
        "ilmu",
    }
)

# Minimal: pertanyaan harus menyentuh topik pekerjaan/magang agar tidak menjawab topik acak (mis. resep masak).
_JOB_INTENT_MARKERS: Tuple[str, ...] = (
    "lowongan",
    "loker",
    "magang",
    "intern",
    "internship",
    "kerja",
    "pekerjaan",
    "karir",
    "career",
    "job",
    "jobs",
    "vacancy",
    "rekrutmen",
    "recruitment",
    "hiring",
    "melamar",
    "lamaran",
    "recruiter",
    "karyawan",
    "dibutuhkan",
    "dicari",
    "wfo",
    "wfh",
    "work from home",
    "remote",
    "freelance",
    "part time",
    "parttime",
    "full time",
    "fulltime",
    "fresh graduate",
    "otr",
    "cv",
    "resume",
    "posisi",
    "peluang",
    "gaji",
    "oprec",
)

# Frasa bidang (urut panjang dicek dulu) -> istilah untuk skor + filter ketat bila tidak ada yang cocok.
_DOMAIN_STRICT_PHRASES: Tuple[Tuple[str, Tuple[str, ...]], ...] = tuple(
    sorted(
        (
            (
                "ilmu komunikasi",
                (
                    "ilmu komunikasi",
                    "komunikasi",
                    "humas",
                    "public relations",
                    "jurnalistik",
                    "journalism",
                    "marcomm",
                    "copywriter",
                    "content writer",
                    "corporate communication",
                    "communication officer",
                    "relations officer",
                    "social media",
                    "broadcast",
                ),
            ),
            (
                "hubungan masyarakat",
                ("humas", "public relations", "komunikasi", "pehumas", "media relations"),
            ),
            (
                "public relations",
                ("public relations", "humas", "komunikasi", "pr officer", "media relations"),
            ),
            (
                "ilmu kedokteran",
                (
                    "kedokteran",
                    "dokter",
                    "medical",
                    "medicine",
                    "medis",
                    "kesehatan",
                    "rumah sakit",
                    "klinik",
                    "clinical",
                    "farmasi",
                    "apoteker",
                    "kefarmasian",
                    "perawat",
                    "keperawatan",
                    "nursing",
                    "bidan",
                    "kebidanan",
                    "paramedis",
                    "biomedis",
                    "biomedical",
                    "radiologi",
                    "gizi",
                    "fisioterapi",
                    "kesehatan masyarakat",
                    "public health",
                ),
            ),
            (
                "fakultas kedokteran",
                (
                    "kedokteran",
                    "dokter",
                    "medical",
                    "medis",
                    "kesehatan",
                    "rumah sakit",
                    "klinik",
                    "farmasi",
                    "perawat",
                    "keperawatan",
                ),
            ),
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

# Token pertanyaan -> sinonim/istilah terkait untuk skor relevansi di dokumen.
_FIELD_RELATED_TERMS: Dict[str, Tuple[str, ...]] = {
    "psikolog": ("psikolog", "psikologi", "konseling", "konselor", "psikometri", "klinis"),
    "psikologi": ("psikolog", "psikologi", "konseling", "konselor", "psikometri", "klinis"),
    "konseling": ("konseling", "konselor", "psikolog", "psikologi"),
    "konselor": ("konselor", "konseling", "psikolog", "psikologi"),
    "komunikasi": (
        "komunikasi",
        "ilmu komunikasi",
        "humas",
        "public relations",
        "jurnalistik",
        "journalism",
        "marcomm",
        "copywriter",
        "content writer",
        "corporate communication",
        "communication officer",
        "relations officer",
        "social media",
        "broadcast",
        "pehumas",
        "media relations",
    ),
    "jurnalistik": (
        "jurnalistik",
        "journalism",
        "journalist",
        "wartawan",
        "reporter",
        "editor",
        "copywriter",
        "content writer",
        "komunikasi",
    ),
    "humas": ("humas", "public relations", "komunikasi", "pehumas", "media relations", "marcomm"),
    "kedokteran": (
        "kedokteran",
        "dokter",
        "medical",
        "medicine",
        "medis",
        "kesehatan",
        "rumah sakit",
        "klinik",
        "clinical",
        "farmasi",
        "apoteker",
        "kefarmasian",
        "perawat",
        "keperawatan",
        "nursing",
        "bidan",
        "kebidanan",
        "paramedis",
        "paramedic",
        "biomedis",
        "biomedical",
        "radiologi",
        "radiology",
        "gizi",
        "nutrition",
        "fisioterapi",
        "rehab",
        "epidemi",
        "kesehatan masyarakat",
        "public health",
        "coass",
        "ppds",
    ),
    "dokter": (
        "dokter",
        "kedokteran",
        "medical",
        "medicine",
        "medis",
        "kesehatan",
        "rumah sakit",
        "klinik",
        "clinical",
        "coass",
        "ppds",
    ),
    "medis": (
        "medis",
        "medical",
        "medicine",
        "dokter",
        "kedokteran",
        "kesehatan",
        "rumah sakit",
        "klinik",
        "clinical",
    ),
    "kesehatan": (
        "kesehatan",
        "kesmas",
        "kesehatan masyarakat",
        "public health",
        "epidemi",
        "dokter",
        "kedokteran",
        "medical",
        "medis",
        "rumah sakit",
        "klinik",
        "farmasi",
        "perawat",
        "keperawatan",
    ),
    "farmasi": (
        "farmasi",
        "apoteker",
        "kefarmasian",
        "pharmacy",
        "pharmacist",
        "obat",
        "medical",
        "kesehatan",
    ),
    "perawat": (
        "perawat",
        "keperawatan",
        "nursing",
        "medical",
        "kesehatan",
        "rumah sakit",
        "klinik",
    ),
    "keperawatan": (
        "keperawatan",
        "perawat",
        "nursing",
        "medical",
        "kesehatan",
        "rumah sakit",
    ),
}


def _unfuse_di_prefix_cities(question: str) -> str:
    """
    Pecah penulisan umum 'dijakarta' / 'dibandung' (tanpa spasi) jadi 'di jakarta'
    agar inferensi lokasi & filter lokasi tidak meleset.
    """
    pattern = re.compile(
        r"(?i)\b(di)("
        r"jakarta|jakartaselatan|jakartautara|jakartabarat|jakartatimur|jakartapusat|"
        r"jogja|yogyakarta|bandung|surabaya|medan|semarang|bogor|depok|bekasi|tangerang|tangerangselatan|"
        r"malang|makassar|palembang|batam|solo|denpasar|balikpapan|cikarang|karawang"
        r")\b"
    )

    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)} {match.group(2)}"

    return pattern.sub(repl, question)


def _question_is_about_job_vacancies(question: str) -> bool:
    """True bila pertanyaan terasa tentang lowongan/magang/karier (bukan resep, obrolan umum, dll.)."""
    # Normalisasi: lowercase, hapus tanda baca, kompres spasi
    qn = re.sub(r"[^a-z0-9\s]", " ", question.lower())
    qn = re.sub(r"\s+", " ", qn).strip()
    # Wrap dengan spasi agar word-boundary match
    qn_padded = f" {qn} "
    for marker in _JOB_INTENT_MARKERS:
        marker_clean = str(marker).strip().lower()
        if not marker_clean:
            continue
        if f" {marker_clean} " in qn_padded:
            return True
    return False


def _compact_question_lower(question: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", question.lower())).strip()


def _match_terms_from_domain_phrases(question: str) -> Tuple[List[str], bool]:
    """Frasa multi-kata (mis. ilmu komunikasi) -> tambahan match_terms + wajib cocok di dokumen."""
    compact = _compact_question_lower(question)
    extra: List[str] = []
    strict = False
    for phrase, expansions in _DOMAIN_STRICT_PHRASES:
        if phrase in compact:
            strict = True
            for term in expansions:
                if term and term not in extra:
                    extra.append(term)
    return extra, strict


def _dedupe_preserve_order_lower(terms: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for raw in terms:
        piece = str(raw).strip().lower()
        if not piece or piece in seen:
            continue
        seen.add(piece)
        out.append(piece)
    return out


def _focus_terms_for_rerank(question: str) -> List[str]:
    """Token isi dari pertanyaan (bukan lokasi umum) untuk menaikkan lowongan yang benar-benar menyebut bidang itu."""
    qn = _normalize_location_text(question)
    raw_tokens = [t for t in qn.split() if t]
    out: List[str] = []
    seen: set[str] = set()
    location_like = frozenset(_BASE_LOCATION_KEYWORDS)
    for t in raw_tokens:
        if len(t) < 4 or t in _RETRIEVAL_STOPWORDS:
            continue
        if t in location_like:
            continue
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out


def _expanded_match_terms(terms: List[str]) -> List[str]:
    """Gabung token fokus + sinonim bidang agar 'psikolog' cocok dengan judul 'Psikologi Klinis'."""
    bucket: List[str] = []
    seen: set[str] = set()
    for t in terms:
        for piece in (t, *_FIELD_RELATED_TERMS.get(t, ())):
            if piece and piece not in seen:
                bucket.append(piece)
                seen.add(piece)
    return bucket


def _keyword_relevance_score(corpus_lower: str, match_terms: List[str]) -> int:
    if not match_terms:
        return 0
    return sum(1 for term in match_terms if term in corpus_lower)


def _retrieval_boost_phrases(question: str) -> str:
    """
    Tambahan teks untuk embedding (bukan filter keras): memperkuat relevansi
    magang / IT / bidang tertentu bila disebut di pertanyaan.
    """
    qn = _normalize_location_text(question)
    parts: List[str] = []
    if any(x in qn for x in (" magang ", " intern ", " internship ")):
        parts.append("magang intern program magang")
    it_hints = (
        " it ",
        "software",
        "developer",
        "programmer",
        "engineer",
        " data ",
        "network",
        "sistem informasi",
        "teknologi informasi",
        "fullstack",
        "backend",
        "frontend",
    )
    if any(h in qn for h in it_hints):
        parts.append("IT software teknologi informasi developer engineer")
    psych_hints = (
        " psikolog ",
        " psikologi ",
        " konseling ",
        " konselor ",
        " psikometri ",
    )
    if any(h in qn for h in psych_hints):
        parts.append("psikologi psikolog konselor konseling klinis psikometri mental health")
    comm_hints = (
        " komunikasi ",
        " jurnalistik ",
        " humas ",
        " public relations ",
        " marcomm ",
        " copywriter ",
        " content writer ",
        " broadcast ",
        " wartawan ",
        " reporter ",
    )
    if any(h in qn for h in comm_hints) or "ilmu komunikasi" in _compact_question_lower(question):
        parts.append(
            "ilmu komunikasi komunikasi humas public relations jurnalistik "
            "marcomm copywriter content writer corporate communication media"
        )
    med_hints = (
        " kedokteran ",
        " dokter ",
        " medis ",
        " kesehatan ",
        " farmasi ",
        " apoteker ",
        " perawat ",
        " keperawatan ",
        " rumah sakit ",
        " klinik ",
        " biomedical ",
        " radiologi ",
        " gizi ",
        " bidan ",
        " fisioterapi ",
        " coass ",
        " ppds ",
    )
    compact_q = _compact_question_lower(question)
    if any(h in qn for h in med_hints) or "ilmu kedokteran" in compact_q or "fakultas kedokteran" in compact_q:
        parts.append(
            "kedokteran dokter medis kesehatan rumah sakit farmasi apoteker "
            "perawat keperawatan nursing clinical medical medicine klinik biomedical"
        )
    return " ".join(parts).strip()


@st.cache_resource
def get_collection():
    client = chromadb.PersistentClient(path=DB_DIR)
    embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )


def load_filter_options() -> Dict[str, List[str]]:
    collection = get_collection()
    payload = collection.get(include=["metadatas"])
    metadatas = payload.get("metadatas", [])

    sources = sorted({str(meta.get("source", "")).strip() for meta in metadatas if meta})
    locations = sorted({str(meta.get("location", "")).strip() for meta in metadatas if meta})

    return {
        "sources": [s for s in sources if s],
        "locations": [l for l in locations if l],
    }


def _passes_keyword_filter(
    doc,
    meta,
    keyword_filter,
    position_filter,
    required_location="",
    required_employment_type="",
    required_fresh_graduate=False,
):
    location = str(meta.get("location", "")).lower()
    title = str(meta.get("title", "")).lower()
    company = str(meta.get("company", "")).lower()
    corpus = f"{doc}\n{title}\n{company}\n{location}".lower()

    if keyword_filter and keyword_filter.lower() not in corpus:
        return False

    if position_filter and position_filter.lower() not in title:
        return False

    if required_location:
        corpus_norm = _normalize_location_text(corpus)
        if not _corpus_mentions_location(corpus_norm, required_location):
            return False

    if required_employment_type:
        tipe_kerja = str(meta.get("tipe_kerja", "")).strip().lower()
        if tipe_kerja != required_employment_type.strip().lower():
            return False

    if required_fresh_graduate:
        level = str(meta.get("employment_level", "")).strip().lower()
        if level != "fresh graduate":
            return False

    return True


def _location_candidates_from_metadata(locations: List[str]) -> List[str]:
    tokens: set[str] = set()
    skip = {"n/a", "na", "kota", "kabupaten", "provinsi", "indonesia", "daerah", "indonesian"}
    for loc in locations:
        raw = str(loc).strip()
        if not raw or raw.lower() in skip:
            continue
        low = raw.lower()
        if len(low) >= 4:
            tokens.add(low)
        parts = re.split(r"[,/|()-]", low)
        for part in parts:
            cleaned = re.sub(r"[^a-z\s]", " ", part).strip()
            if not cleaned:
                continue
            for word in cleaned.split():
                if len(word) >= 4 and word not in skip:
                    tokens.add(word)
    return sorted(tokens, key=len, reverse=True)


def infer_location_keyword_from_question(question: str, locations: List[str]) -> str:
    q_norm = _normalize_location_text(question)
    candidates: List[str] = []
    seen: set[str] = set()
    for kw in sorted(_BASE_LOCATION_KEYWORDS, key=len, reverse=True):
        if kw not in seen:
            candidates.append(kw)
            seen.add(kw)
    for kw in _location_candidates_from_metadata(locations):
        if kw not in seen:
            candidates.append(kw)
            seen.add(kw)

    for token in candidates:
        if _corpus_mentions_location(q_norm, token):
            return token
    return ""


def highlight_keyword(text: str, keywords: List[str]) -> str:
    valid_keywords = [kw.strip() for kw in keywords if kw.strip()]
    if not valid_keywords:
        return text
    highlighted = text
    for keyword in valid_keywords:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        highlighted = pattern.sub(lambda match: f"<mark>{match.group(0)}</mark>", highlighted)
    return highlighted


def _source_badge_html(source: str) -> str:
    color = SOURCE_BADGE_COLORS.get(source.lower(), "#6c757d")
    return (
        f"<span style='background:{color};color:white;padding:4px 10px;border-radius:999px;"
        f"font-size:0.78rem;font-weight:600;'>{source}</span>"
    )


def _location_badge_html(location: str) -> str:
    return (
        "<span style='background:#eef2ff;color:#1f2937;padding:4px 10px;border-radius:999px;"
        f"font-size:0.78rem;font-weight:600;border:1px solid #c7d2fe;'>{location}</span>"
    )


def _job_to_line(idx: int, job: Dict[str, str]) -> str:
    return (
        f"{idx}. {job['title']} | {job['company']} | {job['location']} | "
        f"{job['source']} | {job['link']}"
    )


def export_jobs_as_csv(jobs: List[Dict[str, str]]) -> bytes:
    headers = ["title", "company", "location", "source", "link"]
    lines = [",".join(headers)]
    for job in jobs:
        row = [job[h].replace('"', '""') for h in headers]
        lines.append(",".join([f'"{value}"' for value in row]))
    return "\n".join(lines).encode("utf-8")


def export_jobs_as_pdf(jobs: List[Dict[str, str]]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, "Hasil Rekomendasi Lowongan")
    y -= 24

    pdf.setFont("Helvetica", 9)
    for idx, job in enumerate(jobs, start=1):
        raw_line = _job_to_line(idx, job)
        wrapped_lines = []
        current = ""
        for word in raw_line.split():
            candidate = f"{current} {word}".strip()
            if len(candidate) > 100:
                wrapped_lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            wrapped_lines.append(current)

        for line in wrapped_lines:
            if y < 40:
                pdf.showPage()
                pdf.setFont("Helvetica", 9)
                y = height - 40
            pdf.drawString(40, y, line)
            y -= 14
        y -= 4

    pdf.save()
    buffer.seek(0)
    return buffer.read()


def render_job_cards(jobs: List[Dict[str, str]], highlight_terms: List[str]) -> None:
    st.subheader("Lowongan Rekomendasi")
    for start in range(0, len(jobs), 2):
        row_items = jobs[start : start + 2]
        cols = st.columns(2)
        for col_idx, job in enumerate(row_items):
            with cols[col_idx]:
                with st.container(border=True):
                    title_html = highlight_keyword(job["title"], highlight_terms)
                    st.markdown(f"**{start + col_idx + 1}.** {title_html}", unsafe_allow_html=True)
                    st.caption(job["company"])
                    st.markdown(
                        f"{_source_badge_html(job['source'])} {_location_badge_html(job['location'])}",
                        unsafe_allow_html=True,
                    )

                    work_setup = job.get("work_setup", "")
                    tipe_kerja = job.get("tipe_kerja", "")
                    work_info = " | ".join([p for p in [work_setup, tipe_kerja] if p])

                    if work_info:
                        st.caption(f"💼 {work_info}")

                    status = job.get("status", "Aktif")
                    deadline = job.get("deadline", "")

                    if deadline:
                        days_left = days_until_deadline(deadline)
                        status_icon = "🟢" if status.lower() == "aktif" else "🔴"

                        if days_left is not None and days_left >= 0:
                            st.caption(f"{status_icon} **{status}** - Batas lamaran: {deadline} ({days_left} hari lagi)")
                        else:
                            st.caption(f"{status_icon} **{status}** - Batas lamaran: {deadline}")

                    if job["link"] and job["link"] != "-":
                        st.link_button("Buka link lowongan", job["link"], use_container_width=True)

                    st.code(job["link"] if job["link"] and job["link"] != "-" else "-", language=None)


def distance_to_similarity_percent(distance: float) -> str:
    """Konversi cosine distance ChromaDB menjadi persentase kecocokan (0-100%).

    ChromaDB default menggunakan cosine distance, di mana 0 = identik sempurna
    dan 2 = berlawanan sempurna. Similarity = 1 - (distance / 2).
    """
    if distance is None:
        return "-"
    try:
        similarity = max(0.0, min(1.0, 1.0 - (float(distance) / 2.0)))
        return f"{similarity * 100:.0f}%"
    except (TypeError, ValueError):
        return "-"


_EMPLOYMENT_TYPE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "Magang": ("magang", "internship", "intern"),
    "Full Time": ("full time", "full-time", "fulltime", "tetap", "penuh waktu"),
    "Part Time": ("part time", "part-time", "paruh waktu"),
    "Kontrak": ("kontrak", "contract", "contractual"),
    "Freelance": ("freelance", "lepas"),
}

_FRESH_GRADUATE_KEYWORDS: Tuple[str, ...] = (
    "fresh graduate", "freshgraduate", "fresh grad", "lulusan baru",
    "baru lulus", "entry level", "tanpa pengalaman", "tidak perlu pengalaman",
)


_WORK_SETUP_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "Remote": ("remote", "wfh", "work from home", "kerja dari rumah", "dari rumah"),
    "Hybrid": ("hybrid",),
    "Onsite": ("onsite", "on-site", "on site", "kerja di kantor", "wfo", "work from office"),
}

_QUERY_MAPPING = {
    "work_setup": {
        "remote": "Remote",
        "wfh": "Remote",
        "work from home": "Remote",

        "hybrid": "Hybrid",

        "onsite": "Onsite",
        "on-site": "Onsite",
        "on site": "Onsite",
        "wfo": "Onsite",
        "work from office": "Onsite",
    },

    "employment_type": {
        "internship": "Internship",
        "intern": "Internship",
        "magang": "Internship",

        "full time": "Full Time",
        "full-time": "Full Time",
        "fulltime": "Full Time",

        "part time": "Part Time",
        "part-time": "Part Time",

        "contract": "Contract",
        "kontrak": "Contract",
    },

    "employment_level": {
        "fresh graduate": "Fresh Graduate",
        "freshgraduate": "Fresh Graduate",
        "fresh grad": "Fresh Graduate",
        "lulusan baru": "Fresh Graduate",
        "baru lulus": "Fresh Graduate",
        "entry level": "Fresh Graduate",
    }
}


def infer_work_setup_from_question(question: str) -> str:
    """Deteksi lokasi kerja (Remote/Hybrid/Onsite) yang disebutkan secara
    natural pada kalimat pertanyaan pengguna."""
    q_norm = _normalize_location_text(question)
    for label, keywords in _WORK_SETUP_KEYWORDS.items():
        for kw in keywords:
            if _corpus_mentions_location(q_norm, _normalize_location_text(kw)):
                return label
    return ""


def infer_employment_type_from_question(question: str) -> str:
    """Deteksi jenis hubungan kerja (Magang/Full Time/Kontrak/dst) yang
    disebutkan secara natural pada kalimat pertanyaan pengguna."""
    q_norm = _normalize_location_text(question)
    for label, keywords in _EMPLOYMENT_TYPE_KEYWORDS.items():
        for kw in keywords:
            if _corpus_mentions_location(q_norm, _normalize_location_text(kw)):
                return label
    return ""


def question_mentions_fresh_graduate(question: str) -> bool:
    """Deteksi apakah pengguna secara eksplisit mencari lowongan untuk
    fresh graduate / lulusan baru / tanpa pengalaman."""
    q_norm = _normalize_location_text(question)
    for kw in _FRESH_GRADUATE_KEYWORDS:
        if _corpus_mentions_location(q_norm, _normalize_location_text(kw)):
            return True
    return False

def infer_specialization_from_question(question: str) -> str:

    q = question.lower()

    for nama_kalibrr, nama_dataset in SPESIALISASI_KALIBRR_KE_DATASET.items():

        if nama_kalibrr.lower() in q:
            return nama_dataset

        if nama_dataset.lower() in q:
            return nama_dataset

def analyze_query(question: str) -> dict:
    """
    Mengubah pertanyaan user menjadi metadata filter.
    """

    q = question.lower()

    result = {
        "work_setup": "",
        "employment_type": "",
        "employment_level": "",
        "specialization": "",
    }

    # Work Setup
    for key, value in _QUERY_MAPPING["work_setup"].items():
        if key in q:
            result["work_setup"] = value
            break

    # Employment Type
    for key, value in _QUERY_MAPPING["employment_type"].items():
        if key in q:
            result["employment_type"] = value
            break

    # Employment Level
    for key, value in _QUERY_MAPPING["employment_level"].items():
        if key in q:
            result["employment_level"] = value
            break

    # Spesialisasi
    for nama_kalibrr, nama_dataset in SPESIALISASI_KALIBRR_KE_DATASET.items():

        if nama_kalibrr.lower() in q:
            result["specialization"] = nama_dataset
            break

        if nama_dataset.lower() in q:
            result["specialization"] = nama_dataset
            break

    return result

    return ""


_DEADLINE_SOON_KEYWORDS: Tuple[str, ...] = (
    "deadline dekat", "deadline cepat", "deadline minggu ini", "segera tutup",
    "akan tutup", "hampir tutup", "buru buru", "mendesak",
)
_DEADLINE_FAR_KEYWORDS: Tuple[str, ...] = (
    "deadline masih lama", "masih lama", "belum tutup", "waktu masih panjang",
)


def question_mentions_deadline_urgency(question: str) -> str:
    """Deteksi apakah pengguna menanyakan urgensi deadline lowongan.
    Mengembalikan 'soon' jika mencari yang deadline-nya dekat,
    'far' jika mencari yang deadline-nya masih lama, atau '' jika tidak disebutkan."""
    q_norm = _normalize_location_text(question)
    for kw in _DEADLINE_SOON_KEYWORDS:
        if _corpus_mentions_location(q_norm, _normalize_location_text(kw)):
            return "soon"
    for kw in _DEADLINE_FAR_KEYWORDS:
        if _corpus_mentions_location(q_norm, _normalize_location_text(kw)):
            return "far"
    return ""


def is_deadline_expired(deadline_str: str, reference_date: "datetime | None" = None) -> bool:
    """Cek apakah tanggal deadline (format YYYY-MM-DD) sudah lewat dari
    tanggal referensi (default: hari ini). Lowongan tanpa deadline yang
    tercatat (string kosong) dianggap TIDAK expired, karena tidak ada
    bukti bahwa lowongan tersebut sudah tutup."""
    if not deadline_str:
        return False
    try:
        deadline_date = datetime.strptime(deadline_str.strip()[:10], "%Y-%m-%d")
    except ValueError:
        return False
    ref = reference_date or datetime.now()
    return deadline_date < ref


def days_until_deadline(deadline_str: str, reference_date: "datetime | None" = None) -> "int | None":
    """Hitung sisa hari menuju deadline. Mengembalikan None jika deadline
    tidak tercatat atau formatnya tidak valid."""
    if not deadline_str:
        return None
    try:
        deadline_date = datetime.strptime(deadline_str.strip()[:10], "%Y-%m-%d")
    except ValueError:
        return None
    ref = reference_date or datetime.now()
    return (deadline_date - ref).days


def retrieve_context(
    question: str,
    top_k: int = 5,
    selected_source: str = "",
    selected_location: str = "",
    keyword_filter: str = "",
    position_filter: str = "",
    inferred_location_keyword: str = "",
    inferred_employment_type: str = "",
    inferred_work_setup: str = "",
    inferred_fresh_graduate: bool = False,
    inferred_specialization: str = "",   
    deadline_urgency: str = "",
) -> Tuple[List[str], List[Dict[str, str]]]:
    collection = get_collection()
    required_location = selected_location or inferred_location_keyword
    where_filters = []
    if selected_source:
        where_filters.append({"source": {"$eq": selected_source}})

    # CATATAN PENTING: operator $contains pada parameter `where` ChromaDB
    # HANYA berlaku untuk metadata bertipe array (Chroma >= 1.5.0), BUKAN
    # untuk field string biasa seperti location/tipe_kerja/employment_level
    # pada skema ini. Menggunakan $contains pada string akan menyebabkan
    # query gagal diterapkan sebagai hard filter. Field work_setup memakai
    # $eq karena nilainya sudah dinormalisasi (Remote/Hybrid/Onsite, tepat
    # satu kata), sehingga exact match aman digunakan di level ChromaDB.
    # Field location, tipe_kerja, dan employment_level memerlukan substring
    # match (mis. "Jakarta" harus cocok dengan "South Jakarta, DKI Jakarta"),
    # sehingga filternya diterapkan secara manual di Python pada langkah
    # post-filtering candidates di bawah, bukan lewat parameter `where`.
    if inferred_work_setup:
        where_filters.append({"work_setup": {"$eq": inferred_work_setup}})

    where = None
    if len(where_filters) == 1:
        where = where_filters[0]
    elif len(where_filters) > 1:
        where = {"$and": where_filters}

    query_for_embedding = question.strip()
    boost = _retrieval_boost_phrases(question)
    if boost:
        query_for_embedding = f"{query_for_embedding} {boost}"
    if required_location:
        query_for_embedding = f"{query_for_embedding} lowongan kerja di {required_location}"

    # Ambil lebih banyak kandidat dari ChromaDB ketika ada filter terstruktur
    # ketat (tipe kerja/fresh graduate) yang diterapkan SETELAH query,
    # karena $contains tidak didukung untuk metadata string biasa di Chroma
    # (hanya untuk array metadata Chroma >= 1.5.0). Tanpa kandidat yang
    # cukup banyak di awal, hasil yang sebenarnya relevan bisa terlewat
    # karena sudah terpotong sebelum sampai ke tahap filter manual ini.
    has_strict_filter = bool(inferred_employment_type or inferred_fresh_graduate)
    max_pool = 400 if has_strict_filter else 120
    n_results = min(max_pool, max(40, top_k * (10 if has_strict_filter else 5)))


    result = collection.query(
    query_texts=[query_for_embedding],
    n_results=n_results,
    include=["documents", "metadatas", "distances"],
    )

    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0] or [None] * len(docs)

    candidates: List[Tuple[int, str, Dict[str, str], float]] = []
    for order, (doc, meta, dist) in enumerate(zip(docs, metas, distances)):
        safe_meta = meta or {}

        # Work Setup
        if inferred_work_setup:
            work_setup = str(safe_meta.get("work_setup", "")).strip().lower()

            if work_setup != inferred_work_setup.strip().lower():
                continue

        # Employment Type
        if inferred_employment_type:
            tipe = str(safe_meta.get("tipe_kerja", "")).strip().lower()

            if tipe != inferred_employment_type.strip().lower():
                continue

        # Fresh Graduate
        if inferred_fresh_graduate:
            level = str(safe_meta.get("employment_level", "")).strip().lower()

            if "fresh graduate" not in level:
                continue

        # Spesialisasi
        if inferred_specialization:
            spesialisasi = str(safe_meta.get("spesialisasi", "")).strip().lower()

            if inferred_specialization.lower() not in spesialisasi:
                continue

        if not _passes_keyword_filter(
            doc=doc,
            meta=safe_meta,
            keyword_filter=keyword_filter,
            position_filter=position_filter,
            required_location=required_location,
        ):
            continue
        # Saring lowongan yang statusnya sudah Tutup (dihitung saat
        # preprocessing berdasarkan tanggal deadline), agar tidak
        # direkomendasikan sebagai lowongan yang masih aktif/dibuka.
        if str(safe_meta.get("status", "Aktif")).strip().lower() == "tutup":
            continue
        candidates.append((order, doc, safe_meta, dist))

    phrase_terms, phrase_strict = _match_terms_from_domain_phrases(question)
    focus = _focus_terms_for_rerank(question)
    match_terms = _dedupe_preserve_order_lower(_expanded_match_terms(focus) + phrase_terms)
    strict_domain = bool(set(focus) & set(_FIELD_RELATED_TERMS.keys())) or phrase_strict
    if match_terms:
        scored: List[Tuple[int, int, int, str, Dict[str, str], float]] = []
        for order, doc, safe_meta, dist in candidates:
            title = str(safe_meta.get("title", "")).lower()
            company = str(safe_meta.get("company", "")).lower()
            location = str(safe_meta.get("location", "")).lower()
            corpus = f"{doc}\n{title}\n{company}\n{location}".lower()
            hits = _keyword_relevance_score(corpus, match_terms)
            scored.append((hits, -order, order, doc, safe_meta, dist))
        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        if strict_domain:
            scored = [row for row in scored if row[0] > 0]
        if not scored:
            return [], []
        candidates = [(row[2], row[3], row[4], row[5]) for row in scored]

    # Urutkan ulang berdasarkan urgensi deadline jika pengguna secara
    # eksplisit menanyakan hal ini (mis. "deadline minggu ini" atau
    # "yang masih lama deadline-nya"). Lowongan tanpa deadline tercatat
    # diletakkan di akhir karena urgensinya tidak dapat dipastikan.
    if deadline_urgency:
        def _deadline_sort_key(item):
            _, _, meta, _ = item
            days = days_until_deadline(str(meta.get("deadline", "")))
            if days is None:
                return float("inf")
            return days if deadline_urgency == "soon" else -days
        candidates = sorted(candidates, key=_deadline_sort_key)

    contexts: List[str] = []
    retrieved_jobs: List[Dict[str, str]] = []
    for _, doc, safe_meta, dist in candidates[:top_k]:
        contexts.append(
            f"{doc}\nRekomendasi link: {safe_meta.get('link', '-')}\n"
        )
        retrieved_jobs.append(
            {
                "title": str(safe_meta.get("title", "-")),
                "company": str(safe_meta.get("company", "-")),
                "location": str(safe_meta.get("location", "-")),
                "source": str(safe_meta.get("source", "-")),
                "link": str(safe_meta.get("link", "-")),
                "similarity": distance_to_similarity_percent(dist),
                "deadline": str(safe_meta.get("deadline", "")),
                "status": str(safe_meta.get("status", "Aktif")),
                "work_setup": str(safe_meta.get("work_setup", "")),
                "tipe_kerja": str(safe_meta.get("tipe_kerja", "")),
            }
        )
    return contexts, retrieved_jobs


def generate_answer(question: str, contexts: List[str]) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return ""

    client = OpenAI(
    api_key=api_key,
    base_url="https://api.maiarouter.ai/v1",
)

    system_prompt = (
        "Kamu adalah asisten chatbot khusus informasi lowongan magang dan pekerjaan di Indonesia. "
        "Tugasmu HANYA menjawab pertanyaan seputar lowongan kerja, magang, atau karier. "
        "Jika pertanyaan di luar topik tersebut, tolak dengan sopan dan arahkan kembali ke topik lowongan. "
        "Jawab HANYA berdasarkan konteks lowongan yang diberikan di bawah ini. "
        "DILARANG KERAS membuat, mengarang, atau menambahkan informasi lowongan apa pun yang tidak ada "
        "secara eksplisit dalam konteks tersebut, termasuk nama perusahaan, posisi, kualifikasi, atau link. "
        "Jika konteks yang diberikan tidak relevan atau tidak cukup untuk menjawab pertanyaan pengguna, "
        "katakan dengan jujur bahwa lowongan yang sesuai tidak ditemukan pada database saat ini, "
        "tanpa berusaha menebak atau memberikan jawaban di luar data yang tersedia. "
        "Gunakan Bahasa Indonesia yang ramah dan profesional."
    )

    user_prompt = f"""Pertanyaan user:
{question}

Konteks lowongan yang tersedia:
{chr(10).join(contexts)}

Format jawaban:
1) Ringkasan singkat hasil pencarian
2) Daftar lowongan relevan (judul - perusahaan - lokasi - link)
"""

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1000,
            temperature=0.3,
        )
        result = response.choices[0].message.content
        return result if result else "Tidak ada jawaban dari model."
    except Exception as exc:
        import traceback
        traceback.print_exc()

        print("ERROR ASLI:", repr(exc))

    return f"__ERROR__: {repr(exc)}"


def main() -> None:
    st.set_page_config(
        page_title="Sistem Chatbot Informasi Lowongan Magang & Kerja Berbasis Retrieval-Augmented Generation (RAG)",
        page_icon="💼",
    )

    inject_app_theme_css()
    render_hero_header()

    with st.form("search_form", clear_on_submit=False):

        question = st.text_input(
            "Cari Lowongan Kerja atau Magang",
            placeholder="Contoh: Ada lowongan Remote untuk Fresh Graduate di Jakarta?"
        )

        search_clicked = st.form_submit_button("🔍 Cari Lowongan")

    with st.expander("📂 Bidang Pekerjaan yang Tersedia"):

        with st.container(border=True):

            st.caption(
                "Chatbot dapat membantu mencari lowongan berdasarkan bidang pekerjaan berikut."
        )

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
- Accounting and Finance
- Administration and Coordination
- Architecture and Engineering
- Customer Service
- Education and Training
- General Services
- Health and Medical
- Hospitality and Tourism
- Human Resources
""")

        with col2:
            st.markdown("""
- IT and Software
- Legal
- Management and Consultancy
- Manufacturing and Production
- Media and Creatives
- Safety and Security
- Sales and Marketing
- Supply Chain
- Writing and Content
""")

    options = load_filter_options()
    with st.sidebar:
        st.header("Filter")
        # Cek API key DeepSeek
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not deepseek_key:
            st.error("⚠️ DEEPSEEK_API_KEY belum diset di file .env")
        else:
            st.success("✅ DeepSeek API terhubung")
        top_k = st.slider(
            "Jumlah lowongan ditampilkan",
            min_value=5,
            max_value=40,
            value=20,
            help="Batasi kartu hasil; naikkan jika ingin melihat lebih banyak lowongan yang lolos filter.",
        )
        selected_location = st.selectbox(
            "Lokasi",
            options=["Semua lokasi"] + options["locations"],
            index=0,
        )
        selected_source = st.selectbox(
            "Sumber",
            options=["Semua sumber"] + options["sources"],
            index=0,
        )
        keyword_filter = st.text_input(
            "Kata kunci (post-filter dokumen)",
            placeholder="Contoh: python, data analyst, ui ux",
        ).strip().lower()
        position_filter = st.text_input(
            "Posisi (judul lowongan)",
            placeholder="Contoh: data analyst, backend, intern",
        ).strip().lower()

    if search_clicked:
        if not question.strip():
            st.warning("Masukkan pertanyaan dulu.")
            return

        question_raw = question.strip()
        if not _question_is_about_job_vacancies(question_raw):
            st.warning(
                "⚠️ Maaf, saya hanya dapat membantu mengenai informasi lowongan kerja dan magang.\n\n"
                "Saya belum dapat menjawab pertanyaan di luar topik tersebut, seperti resep masakan, "
                "cuaca, berita, kesehatan, atau pengetahuan umum lainnya.\n\n"
                "**Silakan ajukan pertanyaan seperti:**\n"
                "- Lowongan magang IT di Jakarta\n"
                "- Lowongan Remote untuk Fresh Graduate\n"
                "- Lowongan Full Time di Bandung\n"
                "- Lowongan Accounting and Finance\n"
                "- Lowongan Software Engineer"
            )
            return

        question_use = _unfuse_di_prefix_cities(question_raw)

        source_filter_value = "" if selected_source == "Semua sumber" else selected_source
        location_filter_value = "" if selected_location == "Semua lokasi" else selected_location
        inferred_location_keyword = ""
        if not location_filter_value:
            inferred_location_keyword = infer_location_keyword_from_question(question_use, options["locations"])
        active_location = location_filter_value or inferred_location_keyword

        query_info = analyze_query(question_use)

        inferred_work_setup = query_info["work_setup"]

        inferred_employment_type = query_info["employment_type"]

        inferred_specialization = query_info["specialization"]

        inferred_fresh_graduate = (
            query_info["employment_level"] == "Fresh Graduate"
        )

        inferred_deadline_urgency = question_mentions_deadline_urgency(question_use)

        with st.spinner("Mencari lowongan relevan..."):
            contexts, retrieved_jobs = retrieve_context(
                question=question_use,
                top_k=top_k,
                selected_source=source_filter_value,
                selected_location=location_filter_value,
                keyword_filter=keyword_filter,
                position_filter=position_filter,
                inferred_location_keyword=inferred_location_keyword,
                inferred_employment_type=inferred_employment_type,
                inferred_work_setup=inferred_work_setup,
                inferred_fresh_graduate=inferred_fresh_graduate,
                inferred_specialization=inferred_specialization,
                deadline_urgency=inferred_deadline_urgency,
            )

        if not contexts:
            st.warning(
                "😕 Maaf, saya tidak menemukan lowongan yang sesuai pada database saat ini.\n\n"
                "Sistem hanya memberikan rekomendasi berdasarkan data yang tersedia dalam database Kalibrr "
                "dan tidak menghasilkan informasi di luar database tersebut."
            )
            return

        active_filter_notes = []
        if active_location:
            active_filter_notes.append(f"lokasi: {active_location}")
        if inferred_employment_type:
            active_filter_notes.append(f"tipe kerja: {inferred_employment_type}")
        if inferred_work_setup:
            active_filter_notes.append(f"work setup: {inferred_work_setup}")
        if inferred_fresh_graduate:
            active_filter_notes.append("jenjang: Fresh Graduate")
        if inferred_deadline_urgency == "soon":
            active_filter_notes.append("diurutkan: deadline terdekat")
        elif inferred_deadline_urgency == "far":
            active_filter_notes.append("diurutkan: deadline masih lama")
        if active_filter_notes:
            st.caption("Filter aktif - " + ", ".join(active_filter_notes))

        highlight_terms = [keyword_filter, position_filter]
        if active_location:
            highlight_terms.append(active_location)
        if inferred_employment_type:
            highlight_terms.append(inferred_employment_type)
        render_job_cards(retrieved_jobs, highlight_terms=highlight_terms)

        # Ekspor CSV/PDF: fungsi export_jobs_as_csv / export_jobs_as_pdf tetap ada di modul ini;
        # UI unduhan sementara tidak ditampilkan.

        with st.spinner("Menyusun jawaban dari DeepSeek..."):
            answer = generate_answer(question_use, contexts)

        if answer == "__SALDO_HABIS__":
            st.warning(
                "⚠️ Saldo DeepSeek API habis. Kartu lowongan di atas tetap bisa digunakan. "
                "Top up di platform.deepseek.com"
            )
        elif answer.startswith("__ERROR__"):
            st.warning(f"⚠️ Gagal menghubungi AI: {answer.replace('__ERROR__: ', '')}")
        elif answer.strip():
            st.subheader("💬 Jawaban Chatbot")
            st.write(answer)
        else:
            st.info("ℹ️ Jawaban AI tidak tersedia. Pastikan DEEPSEEK_API_KEY sudah diset di file .env")


if __name__ == "__main__":
    main()