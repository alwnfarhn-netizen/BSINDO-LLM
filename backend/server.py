"""
server.py
=========
Adaptasi dari src/server/server.py repo kevinjosethomas/sign-language-processing.

PERUBAHAN utama dari repo asli:
  1. Tambah SocketIO "rooms": room guru terpisah dari room siswa
  2. Integrasi BISINDOHolisticDetector (ganti hand-only detector)
  3. Integrasi BISINDOSynthesizer (ganti ASL synthesizer)
  4. Tambah TeacherAssistant (modul baru)
  5. Embedding model IndoBERT untuk expressive (ganti MiniLM English)
  6. Endpoint /expressive menghasilkan isyarat BISINDO (bukan ASL)

Jalankan:
  source venv/bin/activate
  cd src/server
  python3 server.py
"""

import os
import base64
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import Flask, request
from flask_socketio import SocketIO, join_room, leave_room, emit

from holistic_detector import BISINDOHolisticDetector, decode_frame_bytes
from bisindo_synthesizer import load_synthesizer, BISINDOSynthesizer
from teacher_assistant import create_teacher_assistant, TeacherAssistant

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
DB_HOST        = os.environ.get("DB_HOST", "localhost")
DB_PORT        = int(os.environ.get("DB_PORT", 5432))
DB_NAME        = os.environ.get("DB_NAME", "bisindo_llm")
DB_USER        = os.environ.get("DB_USER", "postgres")
DB_PASS        = os.environ.get("DB_PASS", "")
MODEL_PATH     = os.environ.get("MODEL_PATH", "../../model/bisindo_pointnet.h5")
LABEL_ENC_PATH = os.environ.get("LABEL_ENC_PATH", "../../model/label_encoder.pkl")

# Embedding model IndoBERT (ganti MiniLM dari repo asli)
EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL",
    "firqaaa/indo-sentence-bert-base",   # IndoBERT fine-tuned untuk sentence similarity
)

# ── App init ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    max_http_buffer_size=10 * 1024 * 1024,  # 10MB untuk frame kamera
)

# ── Globals (di-init saat startup) ───────────────────────────────────────────
detector:   BISINDOHolisticDetector  | None = None
synthesizer: BISINDOSynthesizer      | None = None
teacher_assistant: TeacherAssistant  | None = None
db_conn                                     = None
embedding_model                             = None

# Mapping session_id → room info
# { sid: {"room_id": str, "role": "student"|"teacher"} }
sessions: dict[str, dict] = {}

# Synthesizer per ruangan agar state tidak tercampur antar kelas
# { room_id: BISINDOSynthesizer }
room_synthesizers: dict[str, BISINDOSynthesizer] = {}


# ── Startup ───────────────────────────────────────────────────────────────────

@app.before_request
def startup():
    """
    Inisialisasi semua komponen saat pertama kali request masuk.
    (Gunakan proper startup hook di production.)
    """
    global detector, synthesizer, teacher_assistant, db_conn, embedding_model

    if detector is not None:
        return  # sudah di-init

    print("[Server] Menginisialisasi BISINDO-LLM server...")

    # Detector holistic
    detector = BISINDOHolisticDetector(
        min_detection_confidence=0.7,
        min_tracking_confidence=0.6,
    )
    print("[Server] ✓ BISINDOHolisticDetector siap")

    # PointNet synthesizer (hanya jika model file tersedia)
    if os.path.exists(MODEL_PATH):
        synthesizer = load_synthesizer(
            model_path=MODEL_PATH,
            label_encoder_path=LABEL_ENC_PATH,
            openai_api_key=OPENAI_API_KEY,
        )
        print("[Server] ✓ BISINDOSynthesizer siap")
    else:
        print(f"[Server] ⚠ Model belum ada di {MODEL_PATH}. Jalankan training dulu.")

    # Database
    try:
        db_conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            dbname=DB_NAME, user=DB_USER, password=DB_PASS
        )
        print("[Server] ✓ Database terhubung")
    except Exception as e:
        print(f"[Server] ✗ Database gagal: {e}")

    # Teacher assistant
    teacher_assistant = create_teacher_assistant(openai_api_key=OPENAI_API_KEY)
    print("[Server] ✓ TeacherAssistant siap")

    # Embedding model untuk expressive (IndoBERT)
    try:
        from sentence_transformers import SentenceTransformer
        embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"[Server] ✓ Embedding model '{EMBEDDING_MODEL}' siap")
    except Exception as e:
        print(f"[Server] ⚠ Embedding model gagal dimuat: {e}")


# ── HTTP endpoints ────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": synthesizer is not None,
        "db_connected": db_conn is not None,
    }


# ── SocketIO: Manajemen room ──────────────────────────────────────────────────
#
# Berbeda dari repo asli yang menggunakan satu namespace global,
# BISINDO-LLM memisahkan siswa dan guru dalam "room" berbeda.
#
# Flow:
#   Siswa join room "kelas-A" sebagai role "student"
#   Guru join room "kelas-A" sebagai role "teacher"
#   Frame dari siswa diproses → hasilnya dikirim ke guru di room yang sama

@socketio.on("join_room")
def handle_join(data: dict):
    """
    Client bergabung ke ruangan kelas.

    data: { "room_id": "kelas-A", "role": "student"|"teacher" }
    """
    room_id = data.get("room_id", "default")
    role    = data.get("role", "student")
    sid     = request.sid

    join_room(room_id)
    sessions[sid] = {"room_id": room_id, "role": role}

    # Buat synthesizer per ruangan jika belum ada
    if room_id not in room_synthesizers and synthesizer is not None:
        import copy
        room_synthesizers[room_id] = copy.deepcopy(synthesizer)

    print(f"[Server] {sid[:8]} bergabung ke room '{room_id}' sebagai {role}")
    emit("room_joined", {"room_id": room_id, "role": role})


@socketio.on("leave_room")
def handle_leave(data: dict):
    sid     = request.sid
    room_id = sessions.pop(sid, {}).get("room_id", "default")
    leave_room(room_id)

    # Kirim summary sesi ke guru saat meninggalkan room
    if teacher_assistant:
        summary = teacher_assistant.get_session_summary()
        emit("session_summary", summary, room=room_id)

    print(f"[Server] {sid[:8]} meninggalkan room '{room_id}'")


# ── SocketIO: Receptive (BISINDO → Teks BI) ──────────────────────────────────

@socketio.on("frame")
def handle_frame(data: dict):
    """
    Terima frame kamera dari browser, proses, kirim hasil ke room.

    data: {
      "frame": bytes | base64str,   # frame kamera
      "room_id": str                # room target (opsional, fallback ke session)
    }

    Emit balik ke room:
      "word_detected"  → { word, confidence, word_buffer }
      "sentence"       → { gloss, sentence, word_buffer }
      "teacher_feedback" → TeacherFeedback.to_dict()  (ke guru saja)
    """
    sid     = request.sid
    session = sessions.get(sid, {})
    room_id = session.get("room_id") or data.get("room_id", "default")

    # Decode frame
    try:
        raw = data.get("frame")
        if isinstance(raw, str):
            raw = base64.b64decode(raw)
        frame_bgr = decode_frame_bytes(raw)
    except Exception as e:
        emit("error", {"message": f"Frame decode error: {e}"})
        return

    # Deteksi holistic
    coords, _ = detector.process_frame(frame_bgr, draw_landmarks=False)

    # Synthesizer untuk room ini
    room_synth = room_synthesizers.get(room_id, synthesizer)
    if room_synth is None:
        emit("error", {"message": "Model belum dimuat. Hubungi admin."})
        return

    # Feed ke synthesizer
    result = room_synth.feed_frame(coords)

    # Kirim kata baru ke semua di room
    if result["type"] == "word":
        word = result["word"]
        socketio.emit("word_detected", result, room=room_id)

        # Cek perbedaan BISINDO-SIBI → kirim ke guru
        if teacher_assistant:
            feedback = teacher_assistant.check_word(word)
            if feedback and feedback.is_different:
                socketio.emit(
                    "teacher_feedback",
                    feedback.to_dict(),
                    room=room_id,
                )

    # Kirim kalimat lengkap ke semua di room
    elif result["type"] == "sentence":
        socketio.emit("sentence", result, room=room_id)


@socketio.on("force_synthesis")
def handle_force_synthesis(data: dict):
    """Guru atau siswa menekan tombol 'Selesai' → paksa LLM synthesis."""
    sid     = request.sid
    room_id = sessions.get(sid, {}).get("room_id", "default")
    room_synth = room_synthesizers.get(room_id, synthesizer)

    if room_synth:
        result = room_synth.force_synthesis()
        socketio.emit("sentence", result, room=room_id)


# ── SocketIO: Expressive (Teks BI → Isyarat BISINDO) ─────────────────────────
#
# Alur sama dengan repo asli, perbedaan:
#   - Embedding: MiniLM (en) → IndoBERT (id)
#   - Database: tabel ASL signs → tabel bisindo_signs
#   - pgvector dim: 384 → 768

@socketio.on("speak")
def handle_speak(data: dict):
    """
    Terima teks Bahasa Indonesia dari guru/siswa, kembalikan animasi BISINDO.

    data: { "text": "Selamat pagi semua", "room_id": str }

    Emit: "sign_animation" → { words: [{ word, pose_frames }] }
    """
    text    = data.get("text", "").strip()
    sid     = request.sid
    room_id = sessions.get(sid, {}).get("room_id") or data.get("room_id", "default")

    if not text:
        return

    if embedding_model is None or db_conn is None:
        emit("error", {"message": "Expressive module belum siap."})
        return

    words = text.split()
    animations = []

    for word in words:
        pose_data = _fetch_bisindo_sign(word)
        animations.append({
            "word": word,
            "pose_frames": pose_data,
            "found": pose_data is not None,
        })

    socketio.emit("sign_animation", {"words": animations}, room=room_id)


def _fetch_bisindo_sign(word: str) -> list | None:
    """
    Cari animasi pose BISINDO untuk satu kata menggunakan cosine similarity.

    Berbeda dari repo asli:
      - Embedding 768-dim (IndoBERT) bukan 384-dim (MiniLM)
      - Query ke tabel bisindo_signs bukan ASL signs
      - Threshold similarity lebih ketat (0.75) karena bahasa lebih spesifik

    Returns list of pose frames atau None jika tidak ditemukan.
    """
    try:
        # Buat embedding IndoBERT untuk kata ini
        emb = embedding_model.encode(word, normalize_embeddings=True)
        emb_list = emb.tolist()

        with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    gloss_bisindo,
                    pose_frames,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM bisindo_signs
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT 1
                """,
                (emb_list, emb_list),
            )
            row = cur.fetchone()

            if row is None or row["similarity"] < 0.75:
                # Fallback: ejaan huruf demi huruf (sama dengan repo asli)
                return _fingerspell_fallback(word)

            return row["pose_frames"]

    except Exception as e:
        print(f"[Server] Expressive error untuk '{word}': {e}")
        return None


def _fingerspell_fallback(word: str) -> list:
    """
    Fallback: jika kata tidak ada di database, eja huruf per huruf.
    Logika sama dengan repo asli (ASL fingerspelling) tapi untuk abjad BISINDO.
    """
    # TODO: Implementasi abjad BISINDO per huruf
    # Placeholder: kembalikan list kosong sementara database abjad dibangun
    print(f"[Server] Fingerspell fallback untuk: {word}")
    return []


# ── SocketIO: Utility ─────────────────────────────────────────────────────────

@socketio.on("reset_session")
def handle_reset(data: dict):
    sid     = request.sid
    room_id = sessions.get(sid, {}).get("room_id", "default")
    room_synth = room_synthesizers.get(room_id)
    if room_synth:
        room_synth.reset()
    if teacher_assistant:
        teacher_assistant.reset_session()
    emit("session_reset", {"room_id": room_id})


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    sessions.pop(sid, None)
    print(f"[Server] {sid[:8]} disconnect")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  BISINDO-LLM Server")
    print("  http://localhost:5001")
    print("=" * 50)
    socketio.run(app, host="0.0.0.0", port=5001, debug=False)
