"""
holistic_detector.py
====================
Adaptasi dari repo kevinjosethomas/sign-language-processing.

PERUBAHAN dari repo asli:
  - Repo asli: mp.solutions.hands → hanya 21 titik tangan (63 koordinat)
  - BISINDO-LLM: mp.solutions.holistic → 33 pose + 2×21 tangan = 75 titik (225 koordinat)

Alasan: BISINDO Jawa Timur menggunakan gerakan tubuh bagian atas (bahu, siku,
pergelangan tangan) sebagai bagian integral dari isyarat — berbeda dengan ASL
fingerspelling yang didominasi gerakan jari. MediaPipe Holistic menangkap semua
ini dalam satu inferensi yang efisien.

Koordinat output (225 float per frame):
  [0:99]   → 33 titik pose tubuh (x, y, z per titik)
  [99:162] → 21 titik tangan kiri (x, y, z per titik)
  [162:225]→ 21 titik tangan kanan (x, y, z per titik)
"""

import cv2
import mediapipe as mp
import numpy as np
from typing import Optional


# ── Konstanta dimensi ──────────────────────────────────────────────────────────
N_POSE   = 33   # MediaPipe Pose landmark count
N_HAND   = 21   # MediaPipe Hand landmark count per tangan
DIM_POSE = N_POSE * 3           # 99
DIM_HAND = N_HAND * 3           # 63
DIM_TOTAL = DIM_POSE + DIM_HAND * 2  # 225

# Indeks pose yang relevan (bahu, siku, pergelangan, pinggul atas)
# Digunakan untuk normalisasi relatif terhadap tubuh penanda
SHOULDER_LEFT  = 11
SHOULDER_RIGHT = 12
HIP_LEFT       = 23
HIP_RIGHT      = 24


class BISINDOHolisticDetector:
    """
    Detektor landmark holistic untuk pengenalan BISINDO secara real-time.

    Contoh pemakaian:
        detector = BISINDOHolisticDetector()
        frame = ...  # numpy array BGR dari kamera
        coords, vis_frame = detector.process_frame(frame)
        if coords is not None:
            # coords.shape == (225,)  ← siap masuk ke PointNet
    """

    def __init__(
        self,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.6,
        smooth_landmarks: bool = True,
    ):
        self.mp_holistic = mp.solutions.holistic
        self.mp_drawing  = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        self.holistic = self.mp_holistic.Holistic(
            static_image_mode=False,
            model_complexity=1,               # 0=lite, 1=full, 2=heavy
            smooth_landmarks=smooth_landmarks,
            enable_segmentation=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        # Buffer frame untuk temporal smoothing (lihat bisindo_synthesizer.py)
        self._frame_buffer: list[np.ndarray] = []

    # ── API utama ──────────────────────────────────────────────────────────────

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        draw_landmarks: bool = True,
    ) -> tuple[Optional[np.ndarray], np.ndarray]:
        """
        Proses satu frame kamera.

        Parameters
        ----------
        frame_bgr : np.ndarray
            Frame BGR dari cv2 / browser.
        draw_landmarks : bool
            Jika True, gambar landmark pada frame untuk visualisasi.

        Returns
        -------
        coords : np.ndarray | None
            Array 225 float yang dinormalisasi, atau None jika tidak terdeteksi.
        vis_frame : np.ndarray
            Frame dengan anotasi landmark (untuk tampilan kamera browser).
        """
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False

        results = self.holistic.process(frame_rgb)

        frame_rgb.flags.writeable = True
        vis_frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        if draw_landmarks:
            self._draw(vis_frame, results)

        coords = self._extract_and_normalize(results)
        return coords, vis_frame

    def close(self):
        self.holistic.close()

    # ── Ekstraksi & normalisasi ────────────────────────────────────────────────

    def _extract_and_normalize(
        self, results
    ) -> Optional[np.ndarray]:
        """
        Ekstrak koordinat dari hasil MediaPipe dan normalisasi.

        Normalisasi dilakukan relatif terhadap pusat bahu (midpoint antara
        bahu kiri dan kanan) dan jarak antar-bahu sebagai skala referensi.
        Ini memastikan model tidak bergantung pada:
          - Jarak signer ke kamera
          - Posisi horizontal/vertikal di frame
          - Tinggi badan signer
        """
        pose_coords = self._extract_pose(results.pose_landmarks)
        left_coords  = self._extract_hand(results.left_hand_landmarks)
        right_coords = self._extract_hand(results.right_hand_landmarks)

        # Minimal harus ada pose tubuh agar kita bisa normalisasi
        if pose_coords is None:
            return None

        # Pakai zero-vector jika tangan tidak terdeteksi
        if left_coords is None:
            left_coords = np.zeros(DIM_HAND, dtype=np.float32)
        if right_coords is None:
            right_coords = np.zeros(DIM_HAND, dtype=np.float32)

        # Normalisasi relatif bahu
        pose_coords, scale = self._normalize_pose(pose_coords)
        left_coords  = self._normalize_hand(left_coords, pose_coords, scale)
        right_coords = self._normalize_hand(right_coords, pose_coords, scale)

        coords = np.concatenate([pose_coords, left_coords, right_coords])
        assert coords.shape == (DIM_TOTAL,), f"Dimensi salah: {coords.shape}"
        return coords.astype(np.float32)

    def _extract_pose(self, landmarks) -> Optional[np.ndarray]:
        if landmarks is None:
            return None
        return np.array(
            [[lm.x, lm.y, lm.z] for lm in landmarks.landmark],
            dtype=np.float32,
        ).flatten()  # (99,)

    def _extract_hand(self, landmarks) -> Optional[np.ndarray]:
        if landmarks is None:
            return None
        return np.array(
            [[lm.x, lm.y, lm.z] for lm in landmarks.landmark],
            dtype=np.float32,
        ).flatten()  # (63,)

    def _normalize_pose(
        self, pose: np.ndarray
    ) -> tuple[np.ndarray, float]:
        """
        Normalisasi koordinat pose relatif terhadap pusat bahu.
        Mengembalikan (pose_normalized, scale) agar tangan bisa dinormalisasi
        dengan skala yang sama.
        """
        pts = pose.reshape(N_POSE, 3)

        # Pusat bahu sebagai origin
        shoulder_l = pts[SHOULDER_LEFT]
        shoulder_r = pts[SHOULDER_RIGHT]
        origin = (shoulder_l + shoulder_r) / 2.0

        # Jarak antar-bahu sebagai skala
        scale = float(np.linalg.norm(shoulder_r - shoulder_l))
        if scale < 1e-6:
            scale = 1.0  # hindari pembagian nol

        pts_normalized = (pts - origin) / scale
        return pts_normalized.flatten(), scale

    def _normalize_hand(
        self,
        hand: np.ndarray,
        normalized_pose: np.ndarray,
        scale: float,
    ) -> np.ndarray:
        """
        Normalisasi koordinat tangan menggunakan skala yang sama dengan pose.
        """
        if np.all(hand == 0):
            return hand  # tangan tidak terdeteksi, biarkan zero

        pts = hand.reshape(N_HAND, 3)
        pose_pts = normalized_pose.reshape(N_POSE, 3)

        # Origin: pergelangan tangan dari pose (titik ke-15 = kiri, ke-16 = kanan)
        # Ini memastikan tangan dan pose berada dalam sistem koordinat yang sama
        wrist_pose = pose_pts[15]  # gunakan pergelangan kiri sebagai fallback
        pts_normalized = (pts - wrist_pose) / scale
        return pts_normalized.flatten()

    # ── Visualisasi ───────────────────────────────────────────────────────────

    def _draw(self, frame: np.ndarray, results) -> None:
        """Gambar koneksi landmark pada frame untuk keperluan debug/demo."""
        # Pose skeleton
        if results.pose_landmarks:
            self.mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                self.mp_holistic.POSE_CONNECTIONS,
                landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style(),
            )

        # Tangan kiri
        if results.left_hand_landmarks:
            self.mp_drawing.draw_landmarks(
                frame,
                results.left_hand_landmarks,
                self.mp_holistic.HAND_CONNECTIONS,
                self.mp_drawing_styles.get_default_hand_landmarks_style(),
                self.mp_drawing_styles.get_default_hand_connections_style(),
            )

        # Tangan kanan
        if results.right_hand_landmarks:
            self.mp_drawing.draw_landmarks(
                frame,
                results.right_hand_landmarks,
                self.mp_holistic.HAND_CONNECTIONS,
                self.mp_drawing_styles.get_default_hand_landmarks_style(),
                self.mp_drawing_styles.get_default_hand_connections_style(),
            )


# ── Utilitas frame ─────────────────────────────────────────────────────────────

def decode_frame_bytes(frame_bytes: bytes) -> np.ndarray:
    """
    Decode bytes dari browser (via SocketIO / WebSocket) menjadi numpy BGR frame.
    Digunakan di server.py saat menerima frame dari kamera browser.
    """
    arr = np.frombuffer(frame_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Gagal decode frame: data tidak valid")
    return frame


if __name__ == "__main__":
    # ── Quick test dengan webcam lokal ────────────────────────────────────────
    detector = BISINDOHolisticDetector()
    cap = cv2.VideoCapture(0)

    print(f"Output shape per frame: ({DIM_TOTAL},) = "
          f"{DIM_POSE} pose + {DIM_HAND} tangan-kiri + {DIM_HAND} tangan-kanan")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        coords, vis = detector.process_frame(frame)
        if coords is not None:
            print(f"  coords[:6] = {coords[:6].round(4)}", end="\r")

        cv2.imshow("BISINDO Holistic Detector", vis)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    detector.close()
