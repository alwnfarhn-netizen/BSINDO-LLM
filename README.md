<div align="center">

# 🤟 BISINDO-LLM

### Platform AI Multimodal untuk Bahasa Isyarat Indonesia

*Komunikasi dua arah BISINDO ↔ Bahasa Indonesia — real-time, inklusif*

<br/>

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Flask](https://img.shields.io/badge/Flask-SocketIO-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.x-FF6F00?style=flat-square&logo=tensorflow&logoColor=white)](https://tensorflow.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![License](https://img.shields.io/badge/Lisensi-MIT-22C55E?style=flat-square)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/alwnfarhn-netizen/BSINDO-LLM?style=flat-square&color=8B5CF6)](https://github.com/alwnfarhn-netizen/BSINDO-LLM/commits/main)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-F59E0B?style=flat-square)](https://github.com/alwnfarhn-netizen/BSINDO-LLM/pulls)

<br/>

> Adaptasi dan perluasan dari karya [Kevin Jose Thomas — sign-language-processing](https://github.com/kevinjosethomas/sign-language-processing) untuk konteks **Bahasa Isyarat Indonesia (BISINDO) Jawa Timur** dengan tambahan modul **LLM Teacher Assistant** berbasis IndoBERT + RAG.

<br/>

| 📷 Receptive | 🤟 Expressive | 👩‍🏫 Teacher Assistant |
|:---:|:---:|:---:|
| BISINDO → Teks BI | Teks BI → Avatar 3D | Umpan balik BISINDO ↔ SIBI |
| MediaPipe + PointNet | IndoBERT + pgvector | LLM + 3-layer cache |

</div>

---

## Daftar Isi

- [Motivasi](#-motivasi)
- [BISINDO vs SIBI](#-bisindo-vs-sibi)
- [Arsitektur Sistem](#-arsitektur-sistem)
- [Teknologi](#-teknologi)
- [Fitur Utama](#-fitur-utama)
- [Contoh Output](#-contoh-output)
- [Struktur Proyek](#-struktur-proyek)
- [Instalasi & Setup](#-instalasi--setup)
- [Konfigurasi `.env`](#-konfigurasi-env)
- [Roadmap](#-roadmap)
- [Kontribusi](#-kontribusi)
- [Kredit](#-kredit)
- [Lisensi](#-lisensi)

---

## 💡 Motivasi

Komunikasi yang inklusif bukan berarti memaksa komunitas Tuli untuk terus-menerus beradaptasi dengan alat yang hanya mempermudah orang dengar. Kita membutuhkan alat yang benar-benar **menjembatani kesenjangan linguistik** — alat yang memahami bahasa isyarat *sebagai bahasa*, bukan sekadar terjemahan kata per kata dari bahasa lisan.

Proyek **BISINDO-LLM** bertujuan untuk:

- Menghilangkan lapisan ekstra (mengetik atau menerjemahkan manual) dalam komunikasi sehari-hari
- Menyediakan platform belajar interaktif berbasis AI untuk guru dan siswa di SLB (Sekolah Luar Biasa)
- Mendokumentasikan dan melestarikan variasi regional BISINDO Jawa Timur
- Membangun dataset BISINDO terbuka pertama di Indonesia

---

## 🗣️ BISINDO vs SIBI

Di Indonesia, sering terjadi kebingungan antara dua sistem:

| | **BISINDO** | **SIBI** |
|---|---|---|
| Kepanjangan | Bahasa Isyarat Indonesia | Sistem Isyarat Bahasa Indonesia |
| Asal | Berkembang organik di komunitas Tuli | Ciptaan pemerintah (1994) |
| Struktur | Bahasa isyarat alami dengan tata bahasa sendiri | Transliterasi visual bahasa lisan |
| Penggunaan | Percakapan sehari-hari komunitas Tuli | Lingkungan formal/akademik |
| Contoh | Isyarat untuk "TIDAK" berbeda per region | Mengikuti morfologi BI (me-, pe-, -kan) |

**Proyek ini memprioritaskan BISINDO** sebagai bahasa utama, sambil menyediakan modul perbandingan BISINDO ↔ SIBI untuk konteks pendidikan.

---

## 🏗️ Arsitektur Sistem

```mermaid
graph TB
    subgraph CLIENT["🖥️  src/client/  ·  React + TypeScript"]
        CAM["📷 Webcam\nuserMedia"]
        MP["MediaPipe Holistic\n225 titik 3D"]
        WS_C["WebSocket client\nsocket.io-client"]
        AVATAR["Three.js\nAvatar 3D GLB"]
        PANEL["👩‍🏫 Teacher Panel\nSIBIFeedback.tsx"]
        STT["react-speech\nrecognition"]
    end

    subgraph SERVER["⚙️  backend/  ·  Python + Flask-SocketIO"]
        WS_S["WebSocket server\nFlask-SocketIO"]
        HOL["holistic_detector.py\nNormalisasi 225 coords"]
        SYN["bisindo_synthesizer.py\nSliding window 30f"]
        MODEL["BiLSTM + PointNet\nKeras · TensorFlow"]
        TA["teacher_assistant.py\n3-layer cache"]
        LLM["LangChain + LLM\nIndoBERT synthesis"]
    end

    subgraph DB["🗄️  Database  ·  PostgreSQL + pgvector"]
        EMB["BISINDO embeddings\n768-dim IndoBERT"]
        POSE["Pose animation data\n.npy keyframes"]
        SIBI_MAP["BISINDO ↔ SIBI\nmapping table"]
        META["Metadata regional\nJawa Timur"]
    end

    CAM --> MP --> WS_C
    STT --> WS_C
    WS_C <-->|"frame / speak\nvia WebSocket"| WS_S
    WS_S --> HOL --> SYN --> MODEL
    MODEL --> LLM --> WS_S
    WS_S --> TA --> DB
    WS_S -->|"word_detected\nsentence\nteacher_feedback\nsign_animation"| WS_C
    WS_C --> AVATAR
    WS_C --> PANEL

    style CLIENT fill:#1e3a5f,stroke:#2563eb,color:#bfdbfe
    style SERVER fill:#0d2a1a,stroke:#15803d,color:#bbf7d0
    style DB fill:#2a1a0a,stroke:#d97706,color:#fde68a
```

### Alur Pipeline Receptive (BISINDO → Teks BI)

```mermaid
sequenceDiagram
    participant C as Browser (Client)
    participant S as Flask Server
    participant M as BiLSTM Model
    participant L as LLM (IndoBERT)

    C->>C: Capture frame 640×480 @ 15fps
    C->>C: MediaPipe Holistic → 225 pts 3D
    C->>S: emit("frame", base64_bytes)
    S->>S: Normalisasi koordinat
    S->>S: Buffer sliding window 30 frame
    S->>M: Inferensi PointNet BISINDO
    M-->>S: gloss + confidence (0.0–1.0)
    S->>S: Temporal voting → kata stabil
    S-->>C: emit("word_detected", {word, confidence})
    Note over S: Setelah silence 2 detik...
    S->>L: LangChain → kalimat BI natural
    L-->>S: "Selamat pagi, apa kabar?"
    S-->>C: emit("sentence", {sentence, gloss_sequence})
```

### Alur Pipeline Expressive (Teks BI → Avatar 3D)

```mermaid
sequenceDiagram
    participant G as Guru (Client)
    participant S as Flask Server
    participant DB as pgvector DB
    participant A as Three.js Avatar

    G->>S: emit("speak", {text: "selamat pagi"})
    S->>S: Tokenisasi → IndoBERT embedding (768-dim)
    S->>DB: Cosine similarity search
    DB-->>S: keyframes .npy per kata
    S-->>G: emit("sign_animation", {word, frames, fps})
    G->>A: Apply keyframes ke bone hierarchy
    A->>A: Animasi skeletal 3D real-time
```

---

## 🔧 Teknologi

| Layer | Teknologi | Fungsi |
|---|---|---|
| **Frontend** | React 18 + TypeScript + Vite | UI utama |
| **Styling** | TailwindCSS | Komponen responsif |
| **3D Rendering** | Three.js + GLTFLoader | Avatar 3D rigged BISINDO |
| **Computer Vision** | MediaPipe Holistic (WASM) | Deteksi 225 landmark |
| **Real-time** | Flask-SocketIO + socket.io-client | Komunikasi bi-directional |
| **ML Model** | TensorFlow/Keras BiLSTM | Klasifikasi isyarat temporal |
| **Embeddings** | IndoBERT (768-dim) | Representasi semantik BI |
| **Vector DB** | PostgreSQL + pgvector | Cosine similarity search |
| **LLM** | LangChain + OpenAI / Claude | Sintesis kalimat + Teacher feedback |

---

## ✨ Fitur Utama

### 📷 Receptive — BISINDO → Teks Bahasa Indonesia
- Deteksi real-time via webcam dengan **MediaPipe Holistic** (tangan + pose tubuh, 225 titik 3D)
- Klasifikasi isyarat temporal menggunakan **BiLSTM** dengan sliding window 30 frame
- Confidence threshold 0.75, temporal voting untuk stabilitas prediksi
- Sintesis kalimat Bahasa Indonesia natural via **IndoBERT + LangChain**

### 🤟 Expressive — Teks BI → Avatar 3D
- Input teks Bahasa Indonesia → tokenisasi → **IndoBERT embedding**
- Pencarian isyarat terdekat via **cosine similarity** di pgvector (9.500+ kata BISINDO)
- Animasi **avatar 3D rigged** real-time dengan Three.js + SkeletonHelper
- Fallback ke fingerspell BISINDO otomatis jika kata tidak ditemukan di database

### 👩‍🏫 Teacher Assistant *(Fitur Baru)*
- Analisis perbedaan **BISINDO regional Jawa Timur ↔ SIBI standar** per kata
- 3-layer caching: RAM → PostgreSQL → LLM (hemat API cost)
- Badge severity: `info` / `minor` / `significant`
- Panel guru real-time dengan session summary & export JSON
- Saran koreksi kontekstual per kata

---

## 📊 Contoh Output

### 1. Receptive — BISINDO → Teks BI

Siswa melakukan isyarat BISINDO untuk kalimat **"aku mau makan siang"**:

```
Frame 001-030: SAYA     → confidence 0.91 ✓
Frame 031-060: MAU      → confidence 0.87 ✓
Frame 061-090: MAKAN    → confidence 0.93 ✓
Frame 091-120: SIANG    → confidence 0.82 ✓

[Silence 2.1 detik → LLM synthesis]

Output: "Saya ingin makan siang."
Gloss:  [SAYA, MAU, MAKAN, SIANG]
```

### 2. Teacher Feedback — Perbedaan BISINDO ↔ SIBI

```json
{
  "detected_word": "TIDAK",
  "sibi_equivalent": "TIDAK (SIBI)",
  "is_different": true,
  "severity": "significant",
  "explanation": "Isyarat TIDAK dalam BISINDO Jawa Timur menggunakan gerakan kepala menggeleng disertai tangan terbuka ke depan. SIBI menggunakan jari telunjuk disilangkan.",
  "suggestion": "Tunjukkan kedua variasi kepada siswa. Jelaskan bahwa BISINDO adalah bahasa isyarat ibu yang lebih ekspresif.",
  "regional_note": "Variasi Jawa Timur — berbeda dengan BISINDO Jakarta",
  "timestamp": 1721390400
}
```

### 3. Expressive — Input → Avatar

```
Input  : "Selamat datang di sekolah kita"
Tokens : ["selamat", "datang", "di", "sekolah", "kita"]

Lookup pgvector:
  "selamat" → similarity 0.94 → 47 keyframes @ 30fps
  "datang"  → similarity 0.91 → 38 keyframes @ 30fps
  "di"      → similarity 0.88 → 12 keyframes @ 30fps
  "sekolah" → similarity 0.96 → 52 keyframes @ 30fps
  "kita"    → similarity 0.89 → 31 keyframes @ 30fps

Total animasi: 180 frame (~6 detik)
Avatar: 3D GLB rigged, skeletal animation, 30fps
```

### 4. Event WebSocket — Real-time Stream

```javascript
// Server → Client events
socket.on("word_detected", {
  word: "MAKAN",
  confidence: 0.93,
  frame_count: 28
})

socket.on("sentence", {
  sentence: "Saya ingin makan siang.",
  gloss_sequence: ["SAYA", "MAU", "MAKAN", "SIANG"],
  timestamp: 1721390400123
})

socket.on("teacher_feedback", {
  detected_word: "TIDAK",
  severity: "significant",
  is_different: true,
  explanation: "...",
  suggestion: "..."
})

socket.on("sign_animation", {
  word: "selamat",
  frames: [[0.12, -0.43, 0.88, ...], ...],  // 47 frame × 225 coords
  fps: 30,
  fingerspell: false
})
```

---

## 📁 Struktur Proyek

```
BSINDO-LLM/
│
├── src/                          # Frontend React + TypeScript
│   ├── App.tsx                   # Root — layout 3 kolom
│   ├── components/
│   │   ├── Avatar3D.tsx          # Three.js avatar 3D rigged
│   │   ├── TeacherPanel.tsx      # Panel guru real-time
│   │   └── SIBIFeedback.tsx      # Kartu umpan balik BISINDO↔SIBI
│   ├── hooks/
│   │   └── useBISINDOSocket.ts   # Custom hook WebSocket
│   └── types/
│       └── bisindo.ts            # TypeScript interfaces
│
├── backend/                      # Backend Python
│   ├── server.py                 # Flask-SocketIO — entry point
│   ├── holistic_detector.py      # MediaPipe → 225 coords
│   ├── bisindo_synthesizer.py    # Sliding window + LLM synthesis
│   ├── teacher_assistant.py      # LLM BISINDO↔SIBI analysis
│   ├── requirements.txt
│   └── data/
│       └── collect_bisindo_data.py  # Tool rekam dataset
│
├── model/
│   └── training/
│       └── train_bisindo_pointnet.py  # BiLSTM training script
│
├── db_seed_bisindo.py            # DDL + seed PostgreSQL + pgvector
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── .env.example
└── README.md
```

---

## 🚀 Instalasi & Setup

### Prasyarat

- **Node.js** 18+ dan npm/yarn
- **Python** 3.9+
- **PostgreSQL** 14+ dengan ekstensi [pgvector](https://github.com/pgvector/pgvector)
- **OpenAI API Key** (atau API key LLM lain yang kompatibel dengan LangChain)
- Webcam yang terhubung

### 1. Clone repository

```bash
git clone https://github.com/alwnfarhn-netizen/BSINDO-LLM.git
cd BSINDO-LLM
```

### 2. Setup Backend (Python)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

# Setup database
psql -U postgres -c "CREATE DATABASE bisindo_db;"
psql -U postgres -d bisindo_db -c "CREATE EXTENSION vector;"
python ../db_seed_bisindo.py    # Seed tabel + 15 kata contoh
```

### 3. Setup Frontend (React)

```bash
# Di root folder
npm install
```

### 4. Konfigurasi `.env`

```bash
cp .env.example .env
# Edit .env dengan kredensial kamu (lihat bagian Konfigurasi)
```

### 5. Jalankan

```bash
# Terminal 1 — Backend
cd backend && python server.py

# Terminal 2 — Frontend
npm run dev
```

Buka [http://localhost:3000](http://localhost:3000) di browser.

---

## ⚙️ Konfigurasi `.env`

```env
# ── LLM ──────────────────────────────────────────
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini           # atau gpt-4o, claude-3-5-haiku, dll

# ── Database ─────────────────────────────────────
DATABASE_URL=postgresql://postgres:password@localhost:5432/bisindo_db

# ── Model ────────────────────────────────────────
MODEL_PATH=./model/bisindo_pointnet.h5
LABEL_ENCODER_PATH=./model/label_encoder.pkl
CONFIDENCE_THRESHOLD=0.75

# ── Embedding ─────────────────────────────────────
EMBEDDING_MODEL=firqaaa/indo-sentence-bert-base   # IndoBERT 768-dim
SIMILARITY_THRESHOLD=0.75

# ── App ──────────────────────────────────────────
FLASK_ENV=development
FLASK_PORT=5000
FRONTEND_URL=http://localhost:3000
```

---

## 🗺️ Roadmap

```mermaid
gantt
    title Roadmap BISINDO-LLM (18 Bulan)
    dateFormat  YYYY-MM
    axisFormat  %b %Y

    section Fase 1 · Fondasi & Data
    Rekrut 20+ informan Tuli Jawa Timur   :done,    f1a, 2025-01, 2025-02
    Rekam 500+ kosakata BISINDO           :active,  f1b, 2025-02, 2025-04
    Setup MediaPipe pipeline              :done,    f1c, 2025-01, 2025-02

    section Fase 2 · Model & Training
    Training BiLSTM BISINDO               :         f2a, 2025-04, 2025-06
    Avatar 3D GLB rigged                  :         f2b, 2025-05, 2025-07
    Modul Teacher Assistant               :done,    f2c, 2025-03, 2025-05
    Database IndoBERT embeddings          :         f2d, 2025-04, 2025-07

    section Fase 3 · Platform & Uji Coba
    Frontend React lengkap                :done,    f3a, 2025-04, 2025-06
    Pilot 2-3 SLB Jawa Timur              :         f3b, 2025-07, 2025-11

    section Fase 4 · Publikasi
    Submission paper EMNLP/ACL            :         f4a, 2025-11, 2026-02
    Dataset open HuggingFace/Zenodo       :         f4b, 2026-01, 2026-03
    Deployment nasional                   :         f4c, 2026-02, 2026-07
```

**Status saat ini: Fase 2 (Model & Training)**

- [x] Arsitektur sistem lengkap
- [x] Backend Python: `server.py`, `holistic_detector.py`, `bisindo_synthesizer.py`, `teacher_assistant.py`
- [x] Frontend React: `Avatar3D`, `TeacherPanel`, `SIBIFeedback`, `useBISINDOSocket`
- [x] Database schema + pgvector
- [ ] Dataset BISINDO (rekam 500+ kata)
- [ ] Training BiLSTM model
- [ ] File avatar GLB 3D rigged
- [ ] Pilot SLB Jawa Timur

---

## 🤝 Kontribusi

Kontribusi sangat disambut! Terutama dari:

- **Anggota komunitas Tuli** — feedback tentang akurasi BISINDO, variasi regional, konteks budaya
- **Pengembang** — bugfix, fitur baru, optimasi performa
- **Peneliti NLP/CV** — eksperimen model, benchmark, evaluasi

### Cara berkontribusi

```bash
# Fork repo, lalu:
git checkout -b feat/nama-fitur
git commit -m "feat: deskripsi singkat"
git push origin feat/nama-fitur
# Buat Pull Request ke branch main
```

Baca [CONTRIBUTING.md](CONTRIBUTING.md) untuk panduan lengkap.

---

## 🙏 Kredit

- **[Kevin Jose Thomas](https://github.com/kevinjosethomas/sign-language-processing)** — repo ASL asli yang menjadi fondasi proyek ini
- **[MediaPipe](https://mediapipe.dev)** — Google, untuk library deteksi landmark
- **[IndoBERT](https://huggingface.co/firqaaa/indo-sentence-bert-base)** — Firqa Asa Firdaus, untuk model embedding Bahasa Indonesia
- **[pgvector](https://github.com/pgvector/pgvector)** — Andrew Kane, untuk ekstensi vector similarity PostgreSQL
- Komunitas Tuli Jawa Timur — untuk pengetahuan, waktu, dan kepercayaan dalam proyek ini

---

## 📄 Lisensi

Didistribusikan di bawah Lisensi **MIT**. Lihat [`LICENSE`](LICENSE) untuk detail.

---

<div align="center">
