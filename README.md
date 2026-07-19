# 🤟 BISINDO ⭤ Bahasa Indonesia Translation with MediaPipe, PointNet, ThreeJS, and LLM

Bahasa Isyarat Indonesia (BISINDO) adalah bahasa alami yang berkembang secara organik di dalam komunitas Tuli Indonesia, memiliki struktur, tata bahasa, dan budaya yang berbeda dari Bahasa Indonesia lisan (maupun SIBI). Sayangnya, banyak alat bantu "translasi" yang dibangun dari perspektif orang dengar yang menganggap bahasa isyarat sekadar representasi visual dari bahasa lisan.

Proyek ini adalah prototipe yang memfasilitasi komunikasi dua arah antara BISINDO dan Bahasa Indonesia. Dibangun dengan berfokus pada pelestarian BISINDO sebagai bahasa utama, antarmuka aplikasi ini menyediakan fitur:

<table style="width: 100%">
  <tr>
    <th style="width: 50%">Receptive: BISINDO → Bahasa Indonesia</th>
    <th style="width: 50%">Expressive: Bahasa Indonesia → BISINDO</th>
  </tr>
  <tr>
    <td>Menerjemahkan gerakan isyarat BISINDO secara langsung (real-time) melalui kamera menjadi teks Bahasa Indonesia. Membantu Teman Tuli berekspresi secara alami tanpa perlu repot mengetik.</td>
    <td>Menerjemahkan teks Bahasa Indonesia menjadi animasi isyarat BISINDO yang diperagakan oleh Avatar 3D. Membantu orang dengar untuk berkomunikasi secara visual tanpa memaksa Teman Tuli membaca teks panjang.</td>
  </tr>
</table>

> [!NOTE]
> Proyek ini merupakan adaptasi dan lokalisasi untuk **Bahasa Isyarat Indonesia (BISINDO)** berdasarkan karya luar biasa dari [Kevin Jose Thomas (ASL Translation)](https://github.com/kevinjosethomas/sign-language-processing). Repositori ini telah dikembangkan lebih jauh dengan integrasi **Large Language Model (LLM)** sebagai *Teacher Assistant* untuk membantu pengguna mempelajari konteks budaya dan memberikan umpan balik (feedback) saat berlatih.

## Table of Contents
- [Motivation](#motivation)
- [Language (BISINDO vs SIBI)](#language)
- [Technology](#technology)
  - [Receptive (Vision & PointNet)](#receptive)
  - [Expressive (3D Avatar)](#expressive)
  - [AI Teacher Assistant (LLM & RAG)](#teacher-assistant)
- [Project Structure](#project-structure)
- [Installation & Setup](#installation--setup)

---

## Motivation
Komunikasi yang inklusif bukan berarti memaksa komunitas Tuli untuk terus-menerus beradaptasi dengan alat yang hanya mempermudah orang dengar (seperti sekadar Voice-to-Text). Kita membutuhkan alat yang benar-benar menjembatani kesenjangan linguistik—alat yang memahami bahasa isyarat *sebagai bahasa*, bukan sekadar terjemahan kata per kata.

Proyek **BISINDO-LLM** bertujuan untuk menghilangkan lapisan ekstra (mengetik atau menerjemahkan secara manual) dalam komunikasi sehari-hari, sambil menyediakan platform belajar interaktif.

## Language
Di Indonesia, sering kali ada kebingungan antara **BISINDO** (Bahasa Isyarat Indonesia) dan **SIBI** (Sistem Isyarat Bahasa Indonesia). SIBI adalah sistem buatan pemerintah yang secara harfiah menerjemahkan tata bahasa lisan (dengan imbuhan me-, pe-, dll) ke dalam isyarat, yang seringkali kaku dan sulit digunakan dalam percakapan sehari-hari. Sebaliknya, **BISINDO** adalah bahasa isyarat ibu yang kaya ekspresi dan digunakan secara alami oleh komunitas Tuli di Indonesia. Proyek ini memprioritaskan BISINDO.

## Technology

### Receptive
Kami menggunakan **MediaPipe Holistic** untuk mengekstrak titik-titik (landmarks) dari tangan, pose, dan wajah melalui *webcam* pengguna. Titik-titik ini (*point clouds*) kemudian diklasifikasikan secara real-time menggunakan arsitektur **PointNet** (dilatih dengan TensorFlow) untuk mengenali kosakata spesifik BISINDO.

### Expressive
Menerima *input* teks Bahasa Indonesia, lalu memetakannya menjadi urutan animasi (*keyframes*) yang kemudian dirender di browser menggunakan **ThreeJS** dalam bentuk Avatar 3D.

### AI Teacher Assistant (Fitur Baru)
Kami mengintegrasikan **OpenAI LLM** dengan bantuan arsitektur RAG (Retrieval-Augmented Generation) menggunakan **PostgreSQL + pgvector** dan IndoBERT. Asisten ini muncul di UI sebagai panel guru yang memberikan *feedback*, menjelaskan perbedaan isyarat (misalnya BISINDO vs SIBI), dan membimbing pengguna saat mereka berlatih menggunakan kamera.

## Project Structure
Repositori ini dirancang sebagai *Full-stack Web Application*:
- `src/`: Berisi kode *Frontend* berbasis React, Vite, dan TailwindCSS (UI Receptive, Expressive Avatar, Teacher Panel).
- `backend/`: Berisi kode *Backend* berbasis Python (Flask & Socket.IO), model Machine Learning (PointNet), skrip pengumpulan data (`collect_bisindo_data.py`), dan logika LLM LangChain.

## Installation & Setup

**Prasyarat:** Node.js, Python 3.9+, PostgreSQL (dengan pgvector), dan OpenAI API Key.

1. **Clone repository:**
   ```bash
   git clone https://github.com/alwnfarhn-netizen/BSINDO-LLM.git
   cd BSINDO-LLM
   ```
2. **Jalankan Frontend (React):**
   ```bash
   npm install
   npm run dev
   ```
3. **Jalankan Backend (Python):**
   ```bash
   cd backend
   pip install -r requirements.txt
   # (Pastikan .env sudah dikonfigurasi dengan OPENAI_API_KEY)
   python server.py
   ```
