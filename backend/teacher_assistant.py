"""
teacher_assistant.py
====================
Modul BARU — tidak ada padanannya di repo kevinjosethomas/sign-language-processing.

Fungsi modul ini:
  1. Mendeteksi ketika isyarat BISINDO yang digunakan berbeda dari standar SIBI
  2. Menghasilkan umpan balik kontekstual untuk guru secara real-time
  3. Menyimpan log perbedaan per sesi untuk evaluasi pembelajaran

Latar belakang:
  BISINDO (Bahasa Isyarat Indonesia) berkembang secara organik di komunitas Tuli
  Indonesia dan memiliki variasi regional yang kuat — termasuk di Jawa Timur.
  SIBI (Sistem Isyarat Bahasa Indonesia) adalah standar formal yang ditetapkan
  Kemendikbud dan digunakan dalam buku teks sekolah inklusif.
  Gap antara keduanya menjadi hambatan pembelajaran. Modul ini menjembataninya.

Integrasi dengan server.py:
  Dipanggil setiap kali synthesizer menghasilkan kata baru:
    feedback = teacher_assistant.check_word(detected_word)
    if feedback:
        socketio.emit("teacher_feedback", feedback, room=teacher_room)
"""

import json
import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dataclasses import dataclass, asdict
from typing import Optional


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class TeacherFeedback:
    """Umpan balik yang dikirim ke panel guru."""
    detected_word: str        # kata yang terdeteksi dari BISINDO
    sibi_equivalent: str      # padanan di SIBI standar
    is_different: bool        # apakah berbeda dari SIBI?
    explanation: str          # penjelasan perbedaan dalam Bahasa Indonesia
    suggestion: str           # saran untuk guru
    severity: str             # "info" | "minor" | "significant"
    regional_note: str        # catatan variasi regional Jawa Timur
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.timestamp == 0.0:
            d["timestamp"] = time.time()
        return d


# ── LLM System Prompt Guru ────────────────────────────────────────────────────

TEACHER_SYSTEM_PROMPT = """Kamu adalah asisten linguistik untuk guru di ruang kelas inklusif Indonesia.
Tugasmu adalah membantu guru memahami perbedaan antara BISINDO (Bahasa Isyarat Indonesia, khususnya \
varian Jawa Timur) dan SIBI (Sistem Isyarat Bahasa Indonesia — standar buku teks Kemendikbud).

Saat diberi sebuah kata BISINDO yang terdeteksi, berikan respons JSON dengan format persis:
{
  "sibi_equivalent": "<isyarat SIBI yang setara>",
  "is_different": true|false,
  "explanation": "<penjelasan singkat perbedaan dalam BI, max 2 kalimat>",
  "suggestion": "<saran praktis untuk guru, max 1 kalimat>",
  "severity": "info|minor|significant",
  "regional_note": "<catatan tentang variasi Jawa Timur jika relevan, atau kosong>"
}

Tingkat severity:
- "info": isyarat sama atau sangat mirip, hanya notasi berbeda
- "minor": ada perbedaan tapi masih mudah dipahami antar komunitas
- "significant": perbedaan signifikan yang bisa menyebabkan kesalahpahaman

Contoh respons untuk kata "MAKAN":
{
  "sibi_equivalent": "MAKAN",
  "is_different": false,
  "explanation": "Isyarat MAKAN di BISINDO Jawa Timur sama dengan SIBI standar.",
  "suggestion": "Tidak ada penyesuaian yang diperlukan.",
  "severity": "info",
  "regional_note": ""
}

Berikan HANYA JSON valid, tanpa penjelasan tambahan, tanpa markdown.
"""


class TeacherAssistant:
    """
    Asisten guru untuk menjembatani BISINDO regional dan SIBI standar.

    Contoh pemakaian (di server.py):
        ta = TeacherAssistant(db_conn=conn, openai_api_key=key)

        # Dipanggil setiap kata baru terdeteksi
        feedback = await ta.check_word("PERGI")
        if feedback and feedback.is_different:
            socketio.emit("teacher_feedback", feedback.to_dict(), room=teacher_room)
    """

    def __init__(
        self,
        db_conn,                    # psycopg2 connection
        openai_api_key: str = "",
        llm_model: str = "gpt-4o-mini",
        use_db_cache: bool = True,  # cache hasil DB untuk mengurangi panggilan LLM
    ):
        self._db = db_conn
        self._use_cache = use_db_cache
        self._memory_cache: dict[str, Optional[TeacherFeedback]] = {}

        self._llm = ChatOpenAI(
            model=llm_model,
            api_key=openai_api_key,
            temperature=0.1,    # rendah karena kita butuh konsistensi
        ) if openai_api_key else None

        # Log sesi untuk evaluasi pembelajaran
        self._session_log: list[dict] = []
        self._session_start = time.time()

    # ── API utama ──────────────────────────────────────────────────────────────

    def check_word(self, bisindo_word: str) -> Optional[TeacherFeedback]:
        """
        Periksa satu kata BISINDO dan kembalikan umpan balik untuk guru.

        Returns None jika kata tidak perlu dikomentari (identik dengan SIBI
        dan sudah ada di cache dengan severity "info").
        """
        word_upper = bisindo_word.upper().strip()

        # 1. Cek memory cache
        if word_upper in self._memory_cache:
            return self._memory_cache[word_upper]

        # 2. Cek database (cache persisten dari hasil sebelumnya)
        if self._use_cache:
            db_result = self._query_db(word_upper)
            if db_result is not None:
                self._memory_cache[word_upper] = db_result
                return db_result

        # 3. Tanya LLM
        feedback = self._llm_check(word_upper)
        if feedback:
            self._memory_cache[word_upper] = feedback
            self._save_to_db(feedback)
            self._session_log.append({
                "word": word_upper,
                "is_different": feedback.is_different,
                "severity": feedback.severity,
                "time": time.time() - self._session_start,
            })

        return feedback

    def get_session_summary(self) -> dict:
        """
        Ringkasan akhir sesi untuk laporan guru.
        Berisi statistik perbedaan BISINDO-SIBI yang terdeteksi selama sesi.
        """
        if not self._session_log:
            return {"total_words": 0, "differences": 0, "significant": 0, "log": []}

        diffs = [e for e in self._session_log if e["is_different"]]
        significant = [e for e in diffs if e["severity"] == "significant"]

        return {
            "total_words": len(self._session_log),
            "differences": len(diffs),
            "significant": len(significant),
            "duration_minutes": round((time.time() - self._session_start) / 60, 1),
            "log": self._session_log,
        }

    def reset_session(self):
        self._session_log.clear()
        self._session_start = time.time()

    # ── Database ──────────────────────────────────────────────────────────────

    def _query_db(self, word: str) -> Optional["TeacherFeedback"]:
        """
        Cari hasil sebelumnya di tabel bisindo_signs PostgreSQL.
        Kolom is_sibi_diff dan sibi_explanation ditambahkan khusus untuk BISINDO-LLM.
        """
        try:
            with self._db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        gloss_bisindo,
                        gloss_sibi,
                        is_sibi_diff,
                        sibi_explanation,
                        regional_tag
                    FROM bisindo_signs
                    WHERE gloss_bisindo = %s
                    LIMIT 1
                    """,
                    (word,),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                return TeacherFeedback(
                    detected_word=row["gloss_bisindo"],
                    sibi_equivalent=row["gloss_sibi"] or word,
                    is_different=bool(row["is_sibi_diff"]),
                    explanation=row["sibi_explanation"] or "",
                    suggestion="Lihat penjelasan di atas.",
                    severity="info" if not row["is_sibi_diff"] else "minor",
                    regional_note=row["regional_tag"] or "",
                    timestamp=time.time(),
                )
        except Exception as e:
            print(f"[TeacherAssistant] DB query error: {e}")
            return None

    def _save_to_db(self, feedback: "TeacherFeedback"):
        """
        Simpan hasil LLM ke database untuk digunakan ulang di sesi berikutnya.
        Upsert: update jika sudah ada, insert jika belum.
        """
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bisindo_signs
                        (gloss_bisindo, gloss_sibi, is_sibi_diff, sibi_explanation, regional_tag)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (gloss_bisindo) DO UPDATE SET
                        gloss_sibi = EXCLUDED.gloss_sibi,
                        is_sibi_diff = EXCLUDED.is_sibi_diff,
                        sibi_explanation = EXCLUDED.sibi_explanation,
                        regional_tag = EXCLUDED.regional_tag
                    """,
                    (
                        feedback.detected_word,
                        feedback.sibi_equivalent,
                        feedback.is_different,
                        feedback.explanation,
                        feedback.regional_note,
                    ),
                )
            self._db.commit()
        except Exception as e:
            print(f"[TeacherAssistant] DB save error: {e}")
            self._db.rollback()

    # ── LLM ──────────────────────────────────────────────────────────────────

    def _llm_check(self, word: str) -> Optional["TeacherFeedback"]:
        """
        Minta LLM menganalisis perbedaan BISINDO vs SIBI untuk satu kata.
        """
        if self._llm is None:
            # Fallback tanpa LLM: anggap tidak ada perbedaan
            return TeacherFeedback(
                detected_word=word,
                sibi_equivalent=word,
                is_different=False,
                explanation="Analisis otomatis tidak tersedia (API key belum dikonfigurasi).",
                suggestion="Konsultasikan dengan guru ahli SIBI.",
                severity="info",
                regional_note="",
                timestamp=time.time(),
            )

        messages = [
            SystemMessage(content=TEACHER_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Analisis kata BISINDO berikut (varian Jawa Timur): {word}"
            ),
        ]

        try:
            response = self._llm.invoke(messages)
            raw = response.content.strip()

            # Parse JSON dari LLM
            # Bersihkan jika ada backtick markdown yang tidak perlu
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            data = json.loads(raw)

            return TeacherFeedback(
                detected_word=word,
                sibi_equivalent=data.get("sibi_equivalent", word),
                is_different=bool(data.get("is_different", False)),
                explanation=data.get("explanation", ""),
                suggestion=data.get("suggestion", ""),
                severity=data.get("severity", "info"),
                regional_note=data.get("regional_note", ""),
                timestamp=time.time(),
            )

        except json.JSONDecodeError as e:
            print(f"[TeacherAssistant] JSON parse error untuk '{word}': {e}")
            return None
        except Exception as e:
            print(f"[TeacherAssistant] LLM error untuk '{word}': {e}")
            return None


# ── Factory ───────────────────────────────────────────────────────────────────

def create_teacher_assistant(openai_api_key: str = "") -> TeacherAssistant:
    """
    Buat TeacherAssistant dengan koneksi DB dari environment variables.
    Dipanggil dari server.py saat startup.
    """
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 5432)),
            dbname=os.environ.get("DB_NAME", "bisindo_llm"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASS", ""),
        )
    return TeacherAssistant(db_conn=conn, openai_api_key=openai_api_key)
