"""
train_bisindo_pointnet.py
=========================
Script training PointNet untuk klasifikasi isyarat BISINDO.

Adaptasi dari logika training di repo kevinjosethomas/sign-language-processing.

PERUBAHAN dari repo asli:
  - Input shape: (63,) per frame → (30, 225) per sequence
    Repo asli mengklasifikasi HURUF dari 1 frame statis.
    BISINDO-LLM mengklasifikasi KATA dari 30 frame temporal (≈1 detik).
  - Dataset: Kaggle ASL images → video BISINDO yang direkam sendiri
  - Output: kelas kata BISINDO (bukan huruf ASL A-Z)

Arsitektur model:
  Input: (batch, 30 frame, 225 koordinat)
  → LSTM layers untuk menangkap gerakan temporal
  → Dense layers untuk klasifikasi
  (PointNet asli untuk 3D point cloud, BISINDO menggunakan LSTM karena
   urutan temporal sangat penting untuk bahasa isyarat penuh — bukan hanya
   pose statis seperti fingerspelling)

Jalankan:
  python3 model/training/train_bisindo_pointnet.py \
    --data_dir ../../data/point_clouds \
    --annotations ../../data/annotations.json \
    --output_dir ../../model \
    --epochs 100 \
    --batch_size 32
"""

import argparse
import json
import os
import pickle
import numpy as np
import tensorflow as tf
from tensorflow import keras
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix


# ── Konstanta ──────────────────────────────────────────────────────────────────
N_FRAMES    = 30    # frame per sequence (sama dengan WINDOW_SIZE di synthesizer)
N_COORDS    = 225   # koordinat per frame (DIM_TOTAL dari holistic_detector.py)
TRAIN_SPLIT = 0.8
VAL_SPLIT   = 0.1
# TEST_SPLIT = 0.1 (sisanya)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_dataset(
    data_dir: str,
    annotations_path: str,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Load dataset dari file .npy (point cloud sequences) dan annotations.json.

    Struktur data_dir yang diharapkan:
        data/point_clouds/
            MAKAN/
                signer01_take01.npy    # shape: (n_frames, 225)
                signer01_take02.npy
                signer02_take01.npy
            PERGI/
                ...

    annotations.json (metadata per file):
        {
          "MAKAN/signer01_take01.npy": {
            "gloss": "MAKAN",
            "signer_id": "signer01",
            "regional_tag": "Surabaya",
            "validated": true
          },
          ...
        }
    """
    with open(annotations_path, "r", encoding="utf-8") as f:
        annotations = json.load(f)

    X, y = [], []
    skipped = 0

    for rel_path, meta in annotations.items():
        if not meta.get("validated", False):
            continue  # skip yang belum divalidasi komunitas Tuli

        npy_path = os.path.join(data_dir, rel_path)
        if not os.path.exists(npy_path):
            print(f"  ⚠ File tidak ditemukan: {npy_path}")
            skipped += 1
            continue

        frames = np.load(npy_path).astype(np.float32)  # (n_frames, 225)

        # Standarisasi ke N_FRAMES frame dengan interpolasi / truncation
        frames = _standardize_length(frames, N_FRAMES)

        X.append(frames)
        y.append(meta["gloss"].upper())

    print(f"[Dataset] Loaded {len(X)} sequences, skipped {skipped}")
    return np.array(X, dtype=np.float32), np.array(y)


def _standardize_length(frames: np.ndarray, target: int) -> np.ndarray:
    """
    Standarisasi sequence menjadi tepat `target` frame.
    - Jika lebih panjang: ambil frame tengah (crop)
    - Jika lebih pendek: pad dengan frame terakhir (repeat)
    """
    n = len(frames)
    if n == target:
        return frames
    elif n > target:
        start = (n - target) // 2
        return frames[start:start + target]
    else:
        pad = np.repeat(frames[-1:], target - n, axis=0)
        return np.concatenate([frames, pad], axis=0)


def augment_sequence(seq: np.ndarray) -> list[np.ndarray]:
    """
    Augmentasi sederhana untuk memperkaya dataset.
    Menghasilkan 3 variasi dari setiap sequence:
      1. Mirror horizontal (simulasi signer kidal)
      2. Noise kecil (simulasi variasi gerakan)
      3. Time warp ±10% (simulasi perbedaan kecepatan tanda)
    """
    augmented = [seq]

    # 1. Mirror horizontal (flip koordinat x)
    mirrored = seq.copy()
    # Koordinat x ada di indeks 0, 3, 6, ... (setiap 3 angka)
    mirrored[:, 0::3] = -mirrored[:, 0::3]
    augmented.append(mirrored)

    # 2. Gaussian noise
    noisy = seq + np.random.normal(0, 0.01, seq.shape).astype(np.float32)
    augmented.append(noisy)

    return augmented


# ── Model architecture ─────────────────────────────────────────────────────────

def build_bisindo_model(n_classes: int) -> keras.Model:
    """
    Model LSTM untuk klasifikasi isyarat BISINDO temporal.

    Mengapa LSTM bukan PointNet asli?
      PointNet asli dirancang untuk 3D point cloud statis (satu snapshot).
      Isyarat BISINDO adalah gerakan temporal — urutan frame sangat penting.
      LSTM menangkap dependensi temporal yang kritis untuk membedakan kata
      yang memiliki pose mirip tapi gerakan berbeda (misal: DATANG vs PERGI).
    """
    inputs = keras.Input(shape=(N_FRAMES, N_COORDS), name="holistic_sequence")

    # Normalisasi input (layer-level, bukan pre-processing)
    x = keras.layers.LayerNormalization()(inputs)

    # Feature extraction: 1D convolution untuk menangkap pola lokal temporal
    x = keras.layers.Conv1D(64, kernel_size=3, padding="same", activation="relu")(x)
    x = keras.layers.Conv1D(128, kernel_size=3, padding="same", activation="relu")(x)

    # Temporal modeling: Bidirectional LSTM
    x = keras.layers.Bidirectional(
        keras.layers.LSTM(128, return_sequences=True, dropout=0.2)
    )(x)
    x = keras.layers.Bidirectional(
        keras.layers.LSTM(64, return_sequences=False, dropout=0.2)
    )(x)

    # Classification head
    x = keras.layers.Dense(256, activation="relu")(x)
    x = keras.layers.Dropout(0.4)(x)
    x = keras.layers.Dense(128, activation="relu")(x)
    x = keras.layers.Dropout(0.3)(x)

    outputs = keras.layers.Dense(n_classes, activation="softmax", name="predictions")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name="bisindo_classifier")
    return model


# ── Training ──────────────────────────────────────────────────────────────────

def train(args):
    print("=" * 55)
    print("  BISINDO-LLM — Training PointNet/LSTM Classifier")
    print("=" * 55)

    # ── Load data ─────────────────────────────────────────────────────────
    print("\n[1/5] Memuat dataset...")
    X, y_raw = load_dataset(args.data_dir, args.annotations)
    print(f"  Shape X: {X.shape}")
    print(f"  Jumlah kelas: {len(np.unique(y_raw))}")

    # ── Augmentasi ────────────────────────────────────────────────────────
    if args.augment:
        print("\n[2/5] Augmentasi data...")
        X_aug, y_aug = [], []
        for seq, label in zip(X, y_raw):
            for aug_seq in augment_sequence(seq):
                X_aug.append(aug_seq)
                y_aug.append(label)
        X = np.array(X_aug, dtype=np.float32)
        y_raw = np.array(y_aug)
        print(f"  Shape X setelah augmentasi: {X.shape}")

    # ── Encode label ──────────────────────────────────────────────────────
    print("\n[3/5] Encode label...")
    le = LabelEncoder()
    y = le.fit_transform(y_raw)
    n_classes = len(le.classes_)
    print(f"  {n_classes} kelas: {list(le.classes_[:10])}{'...' if n_classes > 10 else ''}")

    # Simpan label encoder
    le_path = os.path.join(args.output_dir, "label_encoder.pkl")
    with open(le_path, "wb") as f:
        pickle.dump(le, f)
    print(f"  Label encoder disimpan ke {le_path}")

    # ── Split dataset ─────────────────────────────────────────────────────
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=(1 - TRAIN_SPLIT), random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )
    print(f"\n  Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    # ── Build model ───────────────────────────────────────────────────────
    print("\n[4/5] Membangun model...")
    model = build_bisindo_model(n_classes)
    model.summary()

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=args.lr),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    # Callbacks
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=15,
            restore_best_weights=True,
            verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=7,
            min_lr=1e-6,
            verbose=1,
        ),
        keras.callbacks.ModelCheckpoint(
            filepath=os.path.join(args.output_dir, "bisindo_pointnet_best.h5"),
            monitor="val_accuracy",
            save_best_only=True,
            verbose=1,
        ),
    ]

    # ── Training loop ─────────────────────────────────────────────────────
    print(f"\n[5/5] Training ({args.epochs} epoch max, batch {args.batch_size})...")
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=callbacks,
        verbose=1,
    )

    # ── Evaluasi ──────────────────────────────────────────────────────────
    print("\n── Evaluasi pada test set ──")
    test_loss, test_acc = model.evaluate(X_test, y_test, verbose=0)
    print(f"  Test accuracy : {test_acc:.4f}")
    print(f"  Test loss     : {test_loss:.4f}")

    y_pred = np.argmax(model.predict(X_test, verbose=0), axis=1)
    print("\n  Classification Report:")
    print(classification_report(
        y_test, y_pred,
        target_names=le.classes_,
        zero_division=0,
    ))

    # ── Simpan model final ────────────────────────────────────────────────
    final_path = os.path.join(args.output_dir, "bisindo_pointnet.h5")
    model.save(final_path)
    print(f"\n✓ Model final disimpan ke: {final_path}")
    print(f"✓ Label encoder    : {le_path}")
    print(f"\nAkurasi test: {test_acc:.2%}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Training BISINDO-LLM Classifier")
    parser.add_argument("--data_dir",    default="../../data/point_clouds")
    parser.add_argument("--annotations", default="../../data/annotations.json")
    parser.add_argument("--output_dir",  default="../../model")
    parser.add_argument("--epochs",      type=int,   default=100)
    parser.add_argument("--batch_size",  type=int,   default=32)
    parser.add_argument("--lr",          type=float, default=1e-3)
    parser.add_argument("--augment",     action="store_true", default=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    train(args)
