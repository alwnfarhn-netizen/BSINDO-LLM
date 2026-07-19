"""
collect_bisindo_data.py
=======================
Script pengumpulan dataset BISINDO dari video kamera.

Tidak ada padanannya di repo asli — repo Kevin menggunakan dataset Kaggle yang sudah jadi.
BISINDO-LLM harus merekam datanya sendiri bersama komunitas Tuli Jawa Timur.

Cara pakai (2 mode):

MODE 1 — Rekam langsung dari kamera:
  python3 collect_bisindo_data.py record \
    --gloss MAKAN \
    --signer signer01 \
    --region Surabaya \
    --takes 5

MODE 2 — Proses video yang sudah direkam:
  python3 collect_bisindo_data.py process \
    --video_dir raw_videos/MAKAN \
    --gloss MAKAN

Output:
  data/point_clouds/MAKAN/signer01_take01.npy   # shape (n_frames, 225)
  data/annotations.json                          # metadata
"""

import argparse
import json
import os
import time
import cv2
import numpy as np
import sys

from holistic_detector import BISINDOHolisticDetector, N_FRAMES


# ── Konstanta ──────────────────────────────────────────────────────────────────
DATA_DIR        = "data"
POINT_CLOUD_DIR = os.path.join(DATA_DIR, "point_clouds")
RAW_VIDEO_DIR   = os.path.join(DATA_DIR, "raw_videos")
ANNOTATIONS_PATH = os.path.join(DATA_DIR, "annotations.json")

RECORD_COUNTDOWN = 3    # detik hitungan mundur sebelum rekam
RECORD_DURATION  = 2    # detik durasi rekam per take
FPS_TARGET       = 30


# ── Load / simpan annotations ──────────────────────────────────────────────────

def load_annotations() -> dict:
    if os.path.exists(ANNOTATIONS_PATH):
        with open(ANNOTATIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_annotations(annotations: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ANNOTATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(annotations, f, ensure_ascii=False, indent=2)


# ── MODE 1: Rekam dari kamera ──────────────────────────────────────────────────

def record_mode(args):
    """
    Rekam video langsung dari kamera dan simpan point cloud secara real-time.
    Tampilkan landmark di layar agar signer tahu pose terdeteksi.
    """
    gloss   = args.gloss.upper()
    signer  = args.signer
    region  = args.region
    n_takes = args.takes

    detector = BISINDOHolisticDetector(min_detection_confidence=0.6)
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FPS, FPS_TARGET)

    out_dir = os.path.join(POINT_CLOUD_DIR, gloss)
    os.makedirs(out_dir, exist_ok=True)

    annotations = load_annotations()

    print(f"\n{'='*50}")
    print(f"  Rekam BISINDO: [{gloss}]")
    print(f"  Signer: {signer} | Region: {region}")
    print(f"  {n_takes} take × {RECORD_DURATION} detik")
    print(f"{'='*50}")
    print("Tekan [SPACE] untuk mulai take | [Q] untuk keluar\n")

    take_num = _next_take_number(out_dir, signer)

    for take_idx in range(n_takes):
        current_take = take_num + take_idx
        filename = f"{signer}_take{current_take:02d}.npy"
        rel_path = f"{gloss}/{filename}"
        out_path = os.path.join(out_dir, filename)

        # Tunggu SPACE
        print(f"Take {current_take}/{take_num + n_takes - 1} — tekan SPACE untuk mulai...")
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            coords, vis = detector.process_frame(frame)
            _draw_ui(vis, f"[{gloss}] Take {current_take} — SPACE untuk mulai", coords)
            cv2.imshow("BISINDO Data Collector", vis)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                break
            if key == ord("q"):
                cap.release()
                detector.close()
                cv2.destroyAllWindows()
                return

        # Countdown
        for count in range(RECORD_COUNTDOWN, 0, -1):
            ret, frame = cap.read()
            coords, vis = detector.process_frame(frame)
            _draw_ui(vis, f"Mulai dalam {count}...", coords, color=(0, 165, 255))
            cv2.imshow("BISINDO Data Collector", vis)
            cv2.waitKey(1000)

        # Rekam
        print(f"  REKAM! ({RECORD_DURATION}s)")
        frames_recorded = []
        start_time = time.time()

        while time.time() - start_time < RECORD_DURATION:
            ret, frame = cap.read()
            if not ret:
                break
            coords, vis = detector.process_frame(frame)
            _draw_ui(vis, f"● REKAM [{gloss}]", coords, color=(0, 0, 220))
            cv2.imshow("BISINDO Data Collector", vis)
            cv2.waitKey(1)

            if coords is not None:
                frames_recorded.append(coords)

        print(f"  Selesai. {len(frames_recorded)} frame terdeteksi.")

        if len(frames_recorded) < 10:
            print(f"  ⚠ Terlalu sedikit frame ({len(frames_recorded)}). Pose tidak terdeteksi?")
            print(f"    Take ini dilewati. Coba lagi dengan pose lebih jelas.\n")
            continue

        # Simpan .npy
        arr = np.array(frames_recorded, dtype=np.float32)
        np.save(out_path, arr)
        print(f"  ✓ Disimpan: {out_path}  shape={arr.shape}")

        # Update annotations
        annotations[rel_path] = {
            "gloss": gloss,
            "signer_id": signer,
            "regional_tag": region,
            "n_frames": len(frames_recorded),
            "validated": False,    # harus divalidasi komunitas Tuli dulu
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        save_annotations(annotations)
        print(f"  ✓ Annotations diperbarui\n")

    cap.release()
    detector.close()
    cv2.destroyAllWindows()
    print(f"\n✓ Selesai merekam {n_takes} take untuk [{gloss}]")
    print(f"  Total dataset: {len(annotations)} sequences")


def _next_take_number(out_dir: str, signer: str) -> int:
    """Cari nomor take berikutnya agar tidak overwrite."""
    existing = [
        f for f in os.listdir(out_dir)
        if f.startswith(signer) and f.endswith(".npy")
    ]
    if not existing:
        return 1
    nums = []
    for f in existing:
        try:
            n = int(f.split("take")[1].replace(".npy", ""))
            nums.append(n)
        except Exception:
            pass
    return max(nums) + 1 if nums else 1


def _draw_ui(frame, text: str, coords, color=(50, 200, 50)):
    """Tampilkan teks dan status deteksi di frame."""
    h, w = frame.shape[:2]
    # Background semi-transparan untuk teks
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - 50), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)

    cv2.putText(frame, text, (10, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

    # Indikator deteksi
    dot_color = (0, 200, 0) if coords is not None else (0, 0, 200)
    status = "TERDETEKSI" if coords is not None else "TIDAK TERDETEKSI"
    cv2.circle(frame, (w - 20, h - 30), 8, dot_color, -1)
    cv2.putText(frame, status, (w - 160, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, dot_color, 1, cv2.LINE_AA)


# ── MODE 2: Proses video yang sudah ada ───────────────────────────────────────

def process_mode(args):
    """
    Proses file video (.mp4/.avi) yang sudah direkam sebelumnya.
    Berguna untuk batch processing video dari sesi rekam lapangan.
    """
    gloss     = args.gloss.upper()
    video_dir = args.video_dir

    detector = BISINDOHolisticDetector(min_detection_confidence=0.6)
    out_dir = os.path.join(POINT_CLOUD_DIR, gloss)
    os.makedirs(out_dir, exist_ok=True)

    annotations = load_annotations()

    video_files = [
        f for f in os.listdir(video_dir)
        if f.lower().endswith((".mp4", ".avi", ".mov"))
    ]

    print(f"Memproses {len(video_files)} video untuk [{gloss}]...")

    for vid_file in sorted(video_files):
        vid_path = os.path.join(video_dir, vid_file)
        out_name = os.path.splitext(vid_file)[0] + ".npy"
        out_path = os.path.join(out_dir, out_name)
        rel_path = f"{gloss}/{out_name}"

        print(f"  {vid_file}...", end=" ")
        cap = cv2.VideoCapture(vid_path)
        frames = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            coords, _ = detector.process_frame(frame, draw_landmarks=False)
            if coords is not None:
                frames.append(coords)

        cap.release()

        if len(frames) < 10:
            print(f"⚠ Dilewati (hanya {len(frames)} frame terdeteksi)")
            continue

        arr = np.array(frames, dtype=np.float32)
        np.save(out_path, arr)
        print(f"✓ {arr.shape}")

        annotations[rel_path] = {
            "gloss": gloss,
            "signer_id": "unknown",
            "regional_tag": args.region,
            "n_frames": len(frames),
            "validated": False,
            "source_video": vid_file,
        }

    save_annotations(annotations)
    detector.close()
    print(f"\n✓ Selesai. Total dataset: {len(annotations)} sequences")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BISINDO Dataset Collector")
    subparsers = parser.add_subparsers(dest="mode")

    # Mode rekam
    rec = subparsers.add_parser("record", help="Rekam langsung dari kamera")
    rec.add_argument("--gloss",   required=True, help="Kata BISINDO (misal: MAKAN)")
    rec.add_argument("--signer",  required=True, help="ID signer (misal: signer01)")
    rec.add_argument("--region",  default="Surabaya", help="Kota asal signer")
    rec.add_argument("--takes",   type=int, default=5, help="Jumlah take per kata")

    # Mode proses video
    proc = subparsers.add_parser("process", help="Proses video yang sudah ada")
    proc.add_argument("--video_dir", required=True)
    proc.add_argument("--gloss",     required=True)
    proc.add_argument("--region",    default="unknown")

    args = parser.parse_args()

    if args.mode == "record":
        record_mode(args)
    elif args.mode == "process":
        process_mode(args)
    else:
        parser.print_help()
