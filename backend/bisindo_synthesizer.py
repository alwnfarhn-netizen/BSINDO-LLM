"""
bisindo_synthesizer.py
======================
Adaptasi dari logika synthesis di repo kevinjosethomas/sign-language-processing.

PERUBAHAN dari repo asli:
  - Repo asli: error-correction hardcoded per huruf ASL (A-T-M-N-S dll)
               + neuspell untuk koreksi ejaan English
  - BISINDO-LLM: PointNet mengklasifikasikan KATA (bukan huruf), dengan
                 temporal sliding window + confidence thresholding.
                 LLM menghasilkan kalimat Bahasa Indonesia (bukan English).
                 NeuSpell diganti pipeline spell-check Bahasa Indonesia.

Alur kerja:
  Frame buffer (30 frame) → PointNet → label + confidence
  → temporal voting → kata yang stabil
  → akumulasi kata → LLM synthesis → kalimat BI
"""

import time
import numpy as np
from collections import deque, Counter
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


# ── Konstanta ──────────────────────────────────────────────────────────────────
WINDOW_SIZE       = 30    # frame per window (≈1 detik @ 30fps)
CONFIDENCE_THRESH = 0.75  # minimum confidence untuk menerima prediksi
MIN_STABLE_FRAMES = 10    # frame berturut-turut prediksi sama sebelum diterima
SILENCE_TIMEOUT   = 2.0   # detik diam sebelum trigger LLM synthesis
MAX_WORDS_BUFFER  = 20    # maks kata sebelum force synthesis


# ── LLM System Prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT_BI = """Kamu adalah asisten sintesis kalimat Bahasa Indonesia untuk sistem penerjemah \
Bahasa Isyarat Indonesia (BISINDO). Tugasmu adalah mengubah urutan kata (gloss BISINDO) menjadi \
kalimat Bahasa Indonesia yang natural, gramatikal, dan kontekstual.

Aturan:
1. Hasilkan HANYA kalimat Bahasa Indonesia yang natural. Jangan tambahkan penjelasan.
2. BISINDO memiliki tata bahasa berbeda dari Bahasa Indonesia — urutan kata bisa berbeda.
3. Pertahankan makna asli. Jangan tambahkan informasi yang tidak ada.
4. Jika kata tidak jelas, gunakan konteks untuk memilih interpretasi paling masuk akal.
5. Gunakan ragam formal-netral yang sesuai untuk konteks ruang kelas inklusif.

Contoh:
  Input gloss: "BUKU MANA KAMU"
  Output: "Di mana bukumu?" atau "Kamu mau buku yang mana?"

  Input gloss: "SAYA TIDAK MENGERTI GURU JELASKAN"
  Output: "Saya tidak mengerti penjelasan guru."
"""


class BISINDOSynthesizer:
    """
    Mengkonversi stream koordinat Holistic menjadi kalimat Bahasa Indonesia.

    Contoh pemakaian:
        synth = BISINDOSynthesizer(model=pointnet_model, label_encoder=le)

        # Dipanggil setiap frame dari server.py
        result = synth.feed_frame(coords)  # coords: np.ndarray (225,)

        if result["type"] == "word":
            # Kata baru terdeteksi stabil
            emit("word_detected", result["word"])

        elif result["type"] == "sentence":
            # LLM menghasilkan kalimat lengkap
            emit("sentence", result["sentence"])
    """

    def __init__(
        self,
        model,           # Keras PointNet model (bisindo_pointnet.h5)
        label_encoder,   # sklearn LabelEncoder yang di-fit dengan label BISINDO
        openai_api_key: str = "",
        llm_model: str = "gpt-4o-mini",
        window_size: int = WINDOW_SIZE,
        confidence_thresh: float = CONFIDENCE_THRESH,
        min_stable_frames: int = MIN_STABLE_FRAMES,
    ):
        self.model          = model
        self.label_encoder  = label_encoder
        self.window_size    = window_size
        self.conf_thresh    = confidence_thresh
        self.min_stable     = min_stable_frames

        # Buffer sliding window frame koordinat
        self._frame_window: deque = deque(maxlen=window_size)

        # Tracking prediksi stabil
        self._last_label: Optional[str] = None
        self._stable_count: int = 0
        self._last_emit_time: float = time.time()

        # Akumulasi kata untuk dirangkai jadi kalimat
        self._word_buffer: list[str] = []
        self._last_word_time: float = time.time()

        # LLM
        self._llm = ChatOpenAI(
            model=llm_model,
            api_key=openai_api_key,
            temperature=0.3,
        ) if openai_api_key else None

    # ── API utama ──────────────────────────────────────────────────────────────

    def feed_frame(self, coords: Optional[np.ndarray]) -> dict:
        """
        Masukkan satu frame koordinat (225,). Mengembalikan dict hasil.

        Returns
        -------
        dict dengan key:
          "type": "none" | "word" | "sentence"
          "word": str (jika type == "word")
          "sentence": str (jika type == "sentence")
          "confidence": float
          "word_buffer": list[str]
        """
        now = time.time()

        # Jika tangan/pose tidak terdeteksi
        if coords is None:
            self._stable_count = 0
            # Cek apakah sudah waktunya synthesis (silence timeout)
            if (self._word_buffer and
                    now - self._last_word_time > SILENCE_TIMEOUT):
                return self._trigger_synthesis()
            return {"type": "none", "word_buffer": self._word_buffer, "confidence": 0.0}

        self._frame_window.append(coords)

        # Butuh window penuh sebelum inferensi
        if len(self._frame_window) < self.window_size:
            return {"type": "none", "word_buffer": self._word_buffer, "confidence": 0.0}

        # ── Inferensi PointNet ─────────────────────────────────────────────
        label, confidence = self._predict()

        if label is None or confidence < self.conf_thresh:
            self._stable_count = 0
            return {"type": "none", "word_buffer": self._word_buffer,
                    "confidence": float(confidence or 0)}

        # ── Temporal voting: perlu N frame stabil berturut-turut ──────────
        if label == self._last_label:
            self._stable_count += 1
        else:
            self._last_label  = label
            self._stable_count = 1

        if self._stable_count < self.min_stable:
            return {"type": "none", "word_buffer": self._word_buffer,
                    "confidence": float(confidence)}

        # Kata stabil — cegah pengulangan langsung
        if self._word_buffer and self._word_buffer[-1] == label:
            return {"type": "none", "word_buffer": self._word_buffer,
                    "confidence": float(confidence)}

        # ── Kata baru terdeteksi ───────────────────────────────────────────
        self._word_buffer.append(label)
        self._last_word_time = now
        self._stable_count = 0

        # Force synthesis jika buffer penuh
        if len(self._word_buffer) >= MAX_WORDS_BUFFER:
            return self._trigger_synthesis()

        return {
            "type": "word",
            "word": label,
            "confidence": float(confidence),
            "word_buffer": list(self._word_buffer),
        }

    def force_synthesis(self) -> dict:
        """Dipanggil secara eksplisit dari client (misal: tombol 'Selesai')."""
        return self._trigger_synthesis()

    def reset(self):
        """Reset semua state — dipanggil saat sesi baru dimulai."""
        self._frame_window.clear()
        self._word_buffer.clear()
        self._last_label = None
        self._stable_count = 0
        self._last_word_time = time.time()

    # ── Inferensi ─────────────────────────────────────────────────────────────

    def _predict(self) -> tuple[Optional[str], float]:
        """
        Jalankan PointNet pada window saat ini.

        Model BISINDO menerima input shape: (1, window_size, 225)
        Output: softmax probabilities atas semua kelas BISINDO
        """
        window = np.array(self._frame_window)  # (30, 225)
        window = window[np.newaxis, ...]        # (1, 30, 225)

        probs = self.model.predict(window, verbose=0)[0]  # (n_classes,)
        idx = int(np.argmax(probs))
        confidence = float(probs[idx])

        label = self.label_encoder.inverse_transform([idx])[0]
        return label, confidence

    # ── Synthesis LLM ─────────────────────────────────────────────────────────

    def _trigger_synthesis(self) -> dict:
        """
        Kirim buffer kata ke LLM dan hasilkan kalimat Bahasa Indonesia.
        """
        if not self._word_buffer:
            return {"type": "none", "word_buffer": [], "confidence": 0.0}

        gloss = " ".join(self._word_buffer)
        sentence = self._llm_synthesize(gloss)

        result = {
            "type": "sentence",
            "gloss": gloss,
            "sentence": sentence,
            "word_buffer": list(self._word_buffer),
            "confidence": 1.0,
        }

        self._word_buffer.clear()
        return result

    def _llm_synthesize(self, gloss: str) -> str:
        """
        Gunakan LLM untuk mengubah gloss BISINDO menjadi kalimat BI natural.
        Fallback ke gloss mentah jika LLM tidak tersedia.
        """
        if self._llm is None:
            # Fallback sederhana: capitalize + titik
            return gloss.lower().capitalize() + "."

        messages = [
            SystemMessage(content=SYSTEM_PROMPT_BI),
            HumanMessage(content=f"Gloss BISINDO: {gloss}"),
        ]

        try:
            response = self._llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            print(f"[Synthesizer] LLM error: {e}")
            return gloss.lower().capitalize() + "."

    # ── Utilitas ──────────────────────────────────────────────────────────────

    def get_word_buffer(self) -> list[str]:
        return list(self._word_buffer)

    @property
    def has_pending_words(self) -> bool:
        return len(self._word_buffer) > 0


# ── Factory function ───────────────────────────────────────────────────────────

def load_synthesizer(
    model_path: str,
    label_encoder_path: str,
    openai_api_key: str = "",
) -> BISINDOSynthesizer:
    """
    Load model PointNet dan label encoder dari disk, kembalikan synthesizer siap pakai.

    Parameters
    ----------
    model_path : str
        Path ke file .h5 (misal: "model/bisindo_pointnet.h5")
    label_encoder_path : str
        Path ke file .pkl LabelEncoder
    """
    import pickle
    import tensorflow as tf

    print(f"[Synthesizer] Loading model dari {model_path}...")
    model = tf.keras.models.load_model(model_path)

    print(f"[Synthesizer] Loading label encoder dari {label_encoder_path}...")
    with open(label_encoder_path, "rb") as f:
        label_encoder = pickle.load(f)

    n_classes = len(label_encoder.classes_)
    print(f"[Synthesizer] Siap. {n_classes} kelas BISINDO.")

    return BISINDOSynthesizer(
        model=model,
        label_encoder=label_encoder,
        openai_api_key=openai_api_key,
    )
