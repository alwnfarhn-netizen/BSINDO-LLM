// ============================================================
// App.tsx
// Root component BISINDO-LLM
// Layout: Receptive kiri | Avatar 3D tengah | Teacher Panel kanan
// ============================================================

import { useState, useRef, useCallback, useEffect } from "react";
import Webcam from "react-webcam";
import { v4 as uuidv4 } from "uuid";
import { useBISINDOSocket } from "./hooks/useBISINDOSocket";
import Avatar3D from "./components/Avatar3D";
import TeacherPanel from "./components/TeacherPanel";
import {
  WordDetectedEvent,
  SentenceEvent,
  SignAnimationEvent,
} from "./types/bisindo";

const SESSION_ID = uuidv4();
const CAPTURE_FPS = 15; // frame per detik yang dikirim ke server

export default function App() {
  const webcamRef = useRef<Webcam>(null);
  const captureIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [isCapturing, setIsCapturing] = useState(false);
  const [latestWord, setLatestWord] = useState<WordDetectedEvent | null>(null);
  const [sentences, setSentences] = useState<string[]>([]);
  const [currentAnimation, setCurrentAnimation] = useState<SignAnimationEvent | null>(null);
  const [isAvatarPlaying, setIsAvatarPlaying] = useState(false);

  // Expressive: antrian kata untuk diperagakan avatar
  const [speakInput, setSpeakInput] = useState("");
  const animQueueRef = useRef<SignAnimationEvent[]>([]);

  // ---------- WebSocket (student_room) ----------
  const { connected, sendFrame, sendSpeak, forceSynthesis, resetSession } =
    useBISINDOSocket({
      room: "student_room",
      sessionId: SESSION_ID,

      onWordDetected: (e) => setLatestWord(e),

      onSentence: (e: SentenceEvent) => {
        setSentences((prev) => [e.sentence, ...prev].slice(0, 20));
      },

      onSignAnimation: (e: SignAnimationEvent) => {
        animQueueRef.current.push(e);
        if (!isAvatarPlaying) playNextInQueue();
      },
    });

  // ---------- Capture loop ----------
  const startCapture = useCallback(() => {
    if (captureIntervalRef.current) return;
    setIsCapturing(true);
    captureIntervalRef.current = setInterval(() => {
      const imageSrc = webcamRef.current?.getScreenshot();
      if (imageSrc) {
        // Kirim hanya bagian base64 tanpa header "data:image/..."
        sendFrame(imageSrc.split(",")[1]);
      }
    }, 1000 / CAPTURE_FPS);
  }, [sendFrame]);

  const stopCapture = useCallback(() => {
    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current);
      captureIntervalRef.current = null;
    }
    setIsCapturing(false);
    forceSynthesis(); // flush buffer kata
  }, [forceSynthesis]);

  useEffect(() => {
    return () => {
      if (captureIntervalRef.current) clearInterval(captureIntervalRef.current);
    };
  }, []);

  // ---------- Avatar queue ----------
  const playNextInQueue = useCallback(() => {
    const next = animQueueRef.current.shift();
    if (!next) {
      setIsAvatarPlaying(false);
      setCurrentAnimation(null);
      return;
    }
    setCurrentAnimation(next);
    setIsAvatarPlaying(true);
  }, []);

  const handleAnimationEnd = useCallback(() => {
    playNextInQueue();
  }, [playNextInQueue]);

  // ---------- Expressive: kirim teks ----------
  const handleSpeak = () => {
    if (!speakInput.trim()) return;
    sendSpeak(speakInput.trim());
    setSpeakInput("");
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden font-sans">
      {/* ─── Top bar ─── */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-slate-900/30 backdrop-blur-md shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xl">🤟</span>
          <span className="font-bold text-sm tracking-wide">BISINDO-LLM</span>
          <span className="text-[10px] text-white/30 ml-1">Jawa Timur</span>
        </div>

        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1.5 text-[10px] ${connected ? "text-green-400" : "text-red-400"}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
            {connected ? "Terhubung" : "Terputus"}
          </div>
          <button
            onClick={resetSession}
            className="text-[10px] text-white/30 hover:text-white/60 transition-colors"
          >
            Reset sesi
          </button>
        </div>
      </header>

      {/* ─── Main layout: 3 columns with breathing room ─── */}
      <main className="flex-1 p-4 grid grid-cols-[320px_1fr_300px] gap-4 overflow-hidden">

        {/* ── LEFT: Receptive (Siswa) ── */}
        <section className="glass-panel rounded-2xl flex flex-col overflow-hidden animate-slide-up" style={{ animationDelay: '0.1s' }}>
          <div className="px-4 py-3 text-[10px] font-bold text-indigo-300/80 uppercase tracking-widest border-b border-white/5 bg-white/5">
            📷 Receptive — Isyarat BISINDO
          </div>

          {/* Webcam */}
          <div className="relative bg-black/50 aspect-video shrink-0 border-b border-white/5">
            <Webcam
              ref={webcamRef}
              audio={false}
              screenshotFormat="image/jpeg"
              screenshotQuality={0.7}
              videoConstraints={{ width: 640, height: 480, facingMode: "user" }}
              className="w-full h-full object-cover opacity-90"
            />
            {isCapturing && (
              <div className="absolute top-2 right-2 flex items-center gap-1.5
                              bg-red-600 rounded-full px-2 py-0.5">
                <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                <span className="text-[9px] font-medium">LIVE</span>
              </div>
            )}
            {latestWord && isCapturing && (
              <div className="absolute bottom-2 left-2 right-2 text-center
                              bg-black/70 backdrop-blur rounded-lg py-1.5">
                <span className="font-bold text-sm">{latestWord.word}</span>
                <span className="text-[10px] text-white/50 ml-2">
                  {(latestWord.confidence * 100).toFixed(0)}%
                </span>
              </div>
            )}
          </div>

          {/* Capture control */}
          <div className="px-4 py-3 border-b border-white/5 bg-white/5">
            <button
              onClick={isCapturing ? stopCapture : startCapture}
              disabled={!connected}
              className={`w-full py-2.5 rounded-xl text-xs font-semibold tracking-wide transition-all duration-300 shadow-lg
                ${isCapturing
                  ? "bg-rose-500/80 hover:bg-rose-500 text-white shadow-rose-500/20"
                  : "bg-indigo-500/80 hover:bg-indigo-500 text-white disabled:opacity-40 shadow-indigo-500/20"
                }`}
            >
              {isCapturing ? "⏹ Stop Perekaman" : "▶ Mulai Merekam"}
            </button>
          </div>

          {/* Kalimat output */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
            <div className="text-[10px] text-white/30 mb-2">Kalimat hasil translasi:</div>
            {sentences.length === 0 ? (
              <p className="text-[11px] text-white/20 italic">
                Belum ada kalimat. Mulai berisyarat di depan kamera.
              </p>
            ) : (
              sentences.map((s, i) => (
                <div
                  key={i}
                  className="text-sm text-white/80 bg-white/5 rounded-xl px-3 py-2 leading-relaxed"
                >
                  {s}
                </div>
              ))
            )}
          </div>
        </section>

        {/* ── CENTER: Avatar 3D ── */}
        <section className="glass-panel rounded-2xl flex flex-col overflow-hidden animate-slide-up" style={{ animationDelay: '0.2s' }}>
          <div className="px-4 py-3 text-[10px] font-bold text-indigo-300/80 uppercase tracking-widest border-b border-white/5 bg-white/5">
            🤟 Avatar 3D — BISINDO Expressive
          </div>

          {/* Avatar */}
          <div className="flex-1 p-3">
            <Avatar3D
              animation={currentAnimation}
              isPlaying={isAvatarPlaying}
              onAnimationEnd={handleAnimationEnd}
            />
          </div>

          {/* Input teks untuk expressive */}
          <div className="px-4 py-4 border-t border-white/5 bg-white/5 space-y-3">
            <div className="text-[11px] text-white/50 tracking-wide">
              Ketik teks Bahasa Indonesia → Avatar akan memperagakan isyarat BISINDO:
            </div>
            <div className="flex gap-2">
              <input
                value={speakInput}
                onChange={(e) => setSpeakInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSpeak()}
                placeholder="Contoh: selamat pagi"
                className="flex-1 bg-black/20 border border-white/10 rounded-xl
                           px-4 py-2.5 text-sm text-white placeholder-white/30
                           focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all duration-300"
              />
              <button
                onClick={handleSpeak}
                disabled={!connected || !speakInput.trim()}
                className="px-5 py-2.5 bg-indigo-600/90 hover:bg-indigo-500 disabled:opacity-40 shadow-lg shadow-indigo-500/20
                           rounded-xl text-xs font-semibold tracking-wide transition-all duration-300"
              >
                Peragakan
              </button>
            </div>
          </div>
        </section>

        {/* ── RIGHT: Teacher Panel ── */}
        <section className="glass-panel rounded-2xl overflow-hidden animate-slide-up" style={{ animationDelay: '0.3s' }}>
          <TeacherPanel sessionId={SESSION_ID} />
        </section>

      </main>
    </div>
  );
}
