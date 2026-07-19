// ============================================================
// App.tsx
// Root component BISINDO-LLM
// Layout: Receptive kiri | Avatar 3D kanan
// ============================================================

import { useState, useRef, useCallback, useEffect } from "react";
import Webcam from "react-webcam";
import { v4 as uuidv4 } from "uuid";
import { useBISINDOSocket } from "./hooks/useBISINDOSocket";
import Avatar3D from "./components/Avatar3D";
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
  const { connected, sendFrame, sendSpeak, forceSynthesis } =
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
    <div className="h-screen w-full bg-[#111111] text-white flex flex-col font-sans overflow-hidden">
      {/* Top Header */}
      <div className="flex border-b border-white/20 shrink-0">
        <div className="w-1/2 text-center py-4 text-lg font-medium border-r border-white/20">
          BISINDO Isyarat → Indonesia
        </div>
        <div className="w-1/2 text-center py-4 text-lg font-medium">
          Indonesia → BISINDO
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* LEFT PANEL */}
        <div className="w-1/2 flex flex-col border-r border-white/20 p-4">
          <div className="relative w-full h-[60%] bg-black rounded overflow-hidden shrink-0">
            <Webcam
              ref={webcamRef}
              audio={false}
              screenshotFormat="image/jpeg"
              screenshotQuality={0.7}
              videoConstraints={{ width: 640, height: 480, facingMode: "user" }}
              className="w-full h-full object-cover"
            />
            {isCapturing && (
              <div className="absolute top-4 right-4 w-3 h-3 rounded-full bg-red-500 animate-pulse" />
            )}
            {latestWord && isCapturing && (
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/60 px-4 py-1 rounded text-white">
                {latestWord.word}
              </div>
            )}
          </div>

          <div className="flex-1 mt-4 relative bg-[#0a0a0a] rounded p-4">
            <div className="absolute inset-0 overflow-y-auto p-4 text-xl">
              {sentences.map((s, i) => (
                <div key={i} className="mb-2">{s}</div>
              ))}
            </div>
          </div>

          <div className="flex justify-between items-center mt-4 text-sm text-gray-300 shrink-0">
            <div className="flex items-center gap-4">
              <button
                onClick={isCapturing ? stopCapture : startCapture}
                disabled={!connected}
                className={`px-4 py-1.5 border border-white/20 rounded hover:bg-white/10 transition-colors ${
                  isCapturing ? "text-red-400 border-red-500/50" : ""
                } disabled:opacity-50`}
              >
                {isCapturing ? "Stop" : "Record"}
              </button>
              {!connected && <span className="text-red-400 text-xs">Disconnected</span>}
            </div>
            
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer hover:text-white">
                <input type="checkbox" className="w-4 h-4 rounded bg-[#222] border-gray-700 accent-blue-500" defaultChecked />
                Autocorrect
              </label>
              <button 
                onClick={() => setSentences([])} 
                className="px-4 py-1.5 border border-white/20 rounded hover:bg-white/10 transition-colors"
              >
                Clear
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT PANEL */}
        <div className="w-1/2 flex flex-col p-4">
          <div className="relative w-full h-[60%] bg-[#1a1a1a] rounded overflow-hidden shrink-0 flex items-center justify-center">
            <Avatar3D
              animation={currentAnimation}
              isPlaying={isAvatarPlaying}
              onAnimationEnd={handleAnimationEnd}
            />
          </div>

          <div className="flex-1 mt-4 relative bg-[#0a0a0a] rounded">
            <textarea
              value={speakInput}
              onChange={(e) => setSpeakInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), handleSpeak())}
              placeholder="Type sentence here..."
              className="absolute inset-0 w-full h-full bg-transparent resize-none outline-none text-xl p-4 text-white placeholder-gray-700"
            />
          </div>

          <div className="flex justify-between items-center mt-4 text-sm text-gray-300 shrink-0">
            <div className="flex items-center gap-4">
              <span>Signing Speed</span>
              <input type="range" className="w-32 accent-blue-500" />
            </div>
            
            <div className="flex items-center gap-4">
              <button
                onClick={handleSpeak}
                disabled={!connected || !speakInput.trim()}
                className="px-6 py-1.5 border border-white/20 rounded hover:bg-white/10 transition-colors disabled:opacity-50"
              >
                Start
              </button>
              <label className="flex items-center gap-2 cursor-pointer hover:text-white">
                <input type="checkbox" className="w-4 h-4 rounded bg-[#222] border-gray-700 accent-blue-500" defaultChecked />
                BISINDO Gloss
              </label>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

