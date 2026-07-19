"""
db_seed_bisindo.py
==================
Setup schema PostgreSQL + pgvector untuk BISINDO-LLM.
Adaptasi dari logika database di repo asli (yang menyimpan ASL signs).

Jalankan sekali saat setup awal:
  python3 db_seed_bisindo.py --create_tables
  python3 db_seed_bisindo.py --seed_sample   # isi data contoh untuk testing

Perubahan dari repo asli:
  - Tabel ASL signs → bisindo_signs (tambah kolom regional_tag, is_sibi_diff)
  - Embedding dim: 384 (MiniLM) → 768 (IndoBERT)
  - Tambah tabel: point_cloud_data, signers
"""

import argparse
import json
import os
import pickle
import numpy as np
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_PARAMS = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "port":     int(os.environ.get("DB_PORT", 5432)),
    "dbname":   os.environ.get("DB_NAME", "bisindo_llm"),
    "user":     os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASS", ""),
}


def get_conn():
    return psycopg2.connect(**DB_PARAMS)


# ── DDL: Buat tabel ────────────────────────────────────────────────────────────

CREATE_TABLES_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabel signer (informan komunitas Tuli)
CREATE TABLE IF NOT EXISTS signers (
    id          SERIAL PRIMARY KEY,
    signer_code VARCHAR(50) UNIQUE NOT NULL,   -- "signer01" (anonim)
    kota_asal   VARCHAR(100),
    is_native   BOOLEAN DEFAULT true,          -- penutur asli BISINDO?
    usia        INTEGER,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Tabel utama isyarat BISINDO
-- Adaptasi dari tabel ASL signs repo asli, dengan kolom tambahan BISINDO
CREATE TABLE IF NOT EXISTS bisindo_signs (
    id               SERIAL PRIMARY KEY,
    gloss_bisindo    VARCHAR(200) UNIQUE NOT NULL,  -- label kata BISINDO
    gloss_sibi       VARCHAR(200),                  -- padanan SIBI standar
    terjemahan_bi    TEXT,                          -- terjemahan Bahasa Indonesia
    embedding        vector(768),                   -- IndoBERT 768-dim (repo asli: 384)
    pose_frames      JSONB,                         -- animasi pose untuk expressive
    regional_tag     VARCHAR(100),                  -- "Surabaya", "Malang", dst
    is_sibi_diff     BOOLEAN DEFAULT false,         -- berbeda dengan SIBI?
    sibi_explanation TEXT,                          -- penjelasan perbedaan (dari LLM)
    video_ref        VARCHAR(500),                  -- referensi video sumber
    validated        BOOLEAN DEFAULT false,         -- sudah divalidasi komunitas Tuli?
    created_at       TIMESTAMP DEFAULT NOW(),
    updated_at       TIMESTAMP DEFAULT NOW()
);

-- Tabel point cloud frame (untuk dataset training)
CREATE TABLE IF NOT EXISTS point_cloud_data (
    id             SERIAL PRIMARY KEY,
    sign_id        INTEGER REFERENCES bisindo_signs(id) ON DELETE CASCADE,
    signer_id      INTEGER REFERENCES signers(id),
    take_number    INTEGER NOT NULL,
    frame_idx      INTEGER NOT NULL,
    holistic_coords FLOAT[] NOT NULL,  -- 225 koordinat (33 pose + 42 tangan)
    created_at     TIMESTAMP DEFAULT NOW()
);

-- Index untuk pencarian cosine similarity (sama dengan repo asli)
-- Repo asli menggunakan dim 384, BISINDO-LLM menggunakan 768
CREATE INDEX IF NOT EXISTS bisindo_signs_embedding_idx
    ON bisindo_signs
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Index untuk query cepat
CREATE INDEX IF NOT EXISTS bisindo_signs_gloss_idx
    ON bisindo_signs (gloss_bisindo);
CREATE INDEX IF NOT EXISTS bisindo_signs_regional_idx
    ON bisindo_signs (regional_tag);
CREATE INDEX IF NOT EXISTS bisindo_signs_sibi_diff_idx
    ON bisindo_signs (is_sibi_diff) WHERE is_sibi_diff = true;

-- Trigger: update updated_at otomatis
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS bisindo_signs_updated_at ON bisindo_signs;
CREATE TRIGGER bisindo_signs_updated_at
    BEFORE UPDATE ON bisindo_signs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
"""


def create_tables():
    print("[DB] Membuat tabel...")
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLES_SQL)
    conn.commit()
    conn.close()
    print("[DB] ✓ Tabel berhasil dibuat:")
    print("       - signers")
    print("       - bisindo_signs  (+ pgvector index 768-dim)")
    print("       - point_cloud_data")


# ── Seed data sample ───────────────────────────────────────────────────────────

SAMPLE_SIGNS = [
    # (gloss_bisindo, gloss_sibi, terjemahan_bi, is_sibi_diff, sibi_explanation, regional_tag)
    ("MAKAN",      "MAKAN",      "makan",              False, "",                                                    "Surabaya"),
    ("MINUM",      "MINUM",      "minum",              False, "",                                                    "Surabaya"),
    ("PERGI",      "PERGI",      "pergi",              False, "",                                                    "Surabaya"),
    ("DATANG",     "DATANG",     "datang",             False, "",                                                    "Surabaya"),
    ("SAYA",       "SAYA",       "saya / aku",         False, "",                                                    "Surabaya"),
    ("KAMU",       "KAMU",       "kamu / anda",        False, "",                                                    "Surabaya"),
    ("DIA",        "DIA",        "dia / beliau",       False, "",                                                    "Surabaya"),
    ("TIDAK",      "TIDAK",      "tidak / bukan",      True,
     "Di BISINDO Jawa Timur, TIDAK menggunakan gerakan kepala ke samping yang lebih tegas. "
     "SIBI standar menggunakan gerakan tangan yang berbeda.",                                                        "Surabaya"),
    ("BUKU",       "BUKU",       "buku",               False, "",                                                    "Surabaya"),
    ("SEKOLAH",    "SEKOLAH",    "sekolah",            True,
     "Isyarat SEKOLAH di BISINDO Jawa Timur berbeda lokasi tangan dibanding SIBI. "
     "Di Jawa Timur lebih sering menggunakan isyarat yang berasal dari komunitas SLB setempat.",                    "Surabaya"),
    ("GURU",       "GURU",       "guru",               False, "",                                                    "Malang"),
    ("MURID",      "SISWA",      "murid / siswa",      True,
     "Komunitas Tuli Jawa Timur lebih sering menggunakan MURID daripada SISWA "
     "sebagai isyarat. Bentuk isyaratnya juga berbeda dari SIBI standar.",                                          "Malang"),
    ("MENGERTI",   "MENGERTI",   "mengerti / paham",   False, "",                                                    "Surabaya"),
    ("TOLONG",     "TOLONG",     "tolong / bantu",     False, "",                                                    "Surabaya"),
    ("TERIMA KASIH", "TERIMA KASIH", "terima kasih",   False, "",                                                    "Surabaya"),
]


def seed_sample_data():
    """
    Isi database dengan data contoh untuk testing.
    Dalam produksi, data ini akan digantikan oleh rekaman asli dari komunitas Tuli.
    Embedding menggunakan zero vector sebagai placeholder (ganti dengan IndoBERT asli).
    """
    print("[DB] Mengisi data sample...")
    conn = get_conn()
    inserted = 0

    with conn.cursor() as cur:
        for gloss_b, gloss_s, terjemahan, is_diff, explanation, region in SAMPLE_SIGNS:
            # Placeholder embedding (zero vector 768-dim)
            # Ganti dengan: embedding_model.encode(terjemahan).tolist()
            placeholder_emb = [0.0] * 768

            cur.execute(
                """
                INSERT INTO bisindo_signs
                    (gloss_bisindo, gloss_sibi, terjemahan_bi, embedding,
                     is_sibi_diff, sibi_explanation, regional_tag, validated)
                VALUES (%s, %s, %s, %s::vector, %s, %s, %s, %s)
                ON CONFLICT (gloss_bisindo) DO NOTHING
                """,
                (
                    gloss_b, gloss_s, terjemahan,
                    placeholder_emb, is_diff, explanation, region, True,
                ),
            )
            inserted += 1

    conn.commit()
    conn.close()
    print(f"[DB] ✓ {inserted} isyarat sample dimasukkan")
    print("     (embedding masih placeholder — jalankan embed_bisindo_signs.py untuk mengisi)")


def embed_all_signs(embedding_model_name: str = "firqaaa/indo-sentence-bert-base"):
    """
    Hitung embedding IndoBERT untuk semua isyarat di database.
    Jalankan setelah seed_sample_data() atau setelah menambah kata baru.
    """
    from sentence_transformers import SentenceTransformer
    print(f"[DB] Memuat embedding model: {embedding_model_name}...")
    model = SentenceTransformer(embedding_model_name)

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, terjemahan_bi FROM bisindo_signs WHERE terjemahan_bi IS NOT NULL")
        rows = cur.fetchall()

    print(f"[DB] Menghitung embedding untuk {len(rows)} isyarat...")
    for sign_id, terjemahan in rows:
        emb = model.encode(terjemahan, normalize_embeddings=True).tolist()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE bisindo_signs SET embedding = %s::vector WHERE id = %s",
                (emb, sign_id)
            )

    conn.commit()
    conn.close()
    print(f"[DB] ✓ Selesai. {len(rows)} embedding diperbarui.")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BISINDO-LLM Database Setup")
    parser.add_argument("--create_tables", action="store_true")
    parser.add_argument("--seed_sample",   action="store_true")
    parser.add_argument("--embed_all",     action="store_true")
    parser.add_argument("--embedding_model", default="firqaaa/indo-sentence-bert-base")
    args = parser.parse_args()

    if args.create_tables:
        create_tables()
    if args.seed_sample:
        seed_sample_data()
    if args.embed_all:
        embed_all_signs(args.embedding_model)

    if not any([args.create_tables, args.seed_sample, args.embed_all]):
        parser.print_help()
