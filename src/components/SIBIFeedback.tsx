// ============================================================
// SIBIFeedback.tsx
// Komponen kartu umpan balik BISINDO ↔ SIBI per kata
// Komponen BARU — tidak ada di repo kevinjosethomas
// ============================================================

import { useEffect, useRef, useState } from "react";
import { SIBIFeedbackProps } from "../types/bisindo";

// Warna berdasarkan severity
const SEVERITY_CONFIG = {
  info: {
    bg: "bg-indigo-900/30 backdrop-blur-md",
    border: "border-indigo-500/20 shadow-lg shadow-indigo-900/20",
    icon: "ℹ️",
    label: "Info",
    labelColor: "text-indigo-300",
    headerBg: "bg-indigo-900/40",
    progressColor: "bg-indigo-500",
    autoHide: 6000,
  },
  minor: {
    bg: "bg-amber-900/30 backdrop-blur-md",
    border: "border-amber-500/20 shadow-lg shadow-amber-900/20",
    icon: "⚠️",
    label: "Perbedaan minor",
    labelColor: "text-amber-300",
    headerBg: "bg-amber-900/40",
    progressColor: "bg-amber-500",
    autoHide: 9000,
  },
  significant: {
    bg: "bg-rose-900/30 backdrop-blur-md",
    border: "border-rose-500/20 shadow-lg shadow-rose-900/20",
    icon: "🔴",
    label: "Perlu koreksi",
    labelColor: "text-rose-300",
    headerBg: "bg-rose-900/40",
    progressColor: "bg-rose-500",
    autoHide: 14000,     // Lebih lama untuk koreksi penting
  },
} as const;

export default function SIBIFeedback({ feedback, onDismiss }: SIBIFeedbackProps) {
  const [visible, setVisible] = useState(true);
  const [progress, setProgress] = useState(100);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startRef = useRef<number>(Date.now());

  const config = SEVERITY_CONFIG[feedback.severity];
  const hideAfter = config.autoHide;

  // Auto-dismiss dengan progress bar
  useEffect(() => {
    startRef.current = Date.now();
    const interval = 50; // update progress setiap 50ms

    timerRef.current = setInterval(() => {
      const elapsed = Date.now() - startRef.current;
      const remaining = Math.max(0, 100 - (elapsed / hideAfter) * 100);
      setProgress(remaining);

      if (elapsed >= hideAfter) {
        clearInterval(timerRef.current!);
        handleDismiss();
      }
    }, interval);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feedback]);

  const handleDismiss = () => {
    setVisible(false);
    setTimeout(() => onDismiss?.(), 300);
  };

  if (!visible) return null;

  return (
    <div
      className={`
        relative rounded-xl border overflow-hidden
        transition-all duration-300 ease-in-out
        ${config.bg} ${config.border}
        animate-slide-in
      `}
      role="alert"
      aria-live="polite"
    >
      {/* Progress bar (auto-dismiss timer) */}
      <div className="absolute top-0 left-0 right-0 h-0.5 bg-white/5">
        <div
          className={`h-full ${config.progressColor} transition-all duration-50 ease-linear`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Header */}
      <div className={`flex items-center justify-between px-3 py-2 ${config.headerBg}`}>
        <div className="flex items-center gap-2">
          <span className="text-base">{config.icon}</span>
          <span className={`text-xs font-semibold ${config.labelColor}`}>
            {config.label}
          </span>
          <span className="text-xs text-white/40">·</span>
          <span className="text-xs text-white/70 font-mono">
            {feedback.detected_word}
          </span>
        </div>
        <button
          onClick={handleDismiss}
          className="text-white/30 hover:text-white/70 transition-colors text-lg leading-none"
          aria-label="Tutup"
        >
          ×
        </button>
      </div>

      {/* Body */}
      <div className="px-4 py-3 space-y-3">
        {/* BISINDO vs SIBI comparison */}
        {feedback.is_different && feedback.sibi_equivalent && (
          <div className="flex items-center gap-3 text-sm">
            <div className="flex-1 rounded-xl bg-black/20 border border-white/5 px-3 py-2.5 shadow-inner">
              <div className="text-[10px] text-white/40 mb-1 uppercase tracking-widest font-semibold">
                BISINDO (dideteksi)
              </div>
              <div className="font-bold text-white text-base tracking-wide">
                {feedback.detected_word}
              </div>
              {feedback.regional_note && (
                <div className="text-[10px] text-indigo-300/70 mt-1">
                  {feedback.regional_note}
                </div>
              )}
            </div>

            <div className="text-white/20 text-xl font-light">→</div>

            <div className="flex-1 rounded-xl bg-black/20 border border-white/5 px-3 py-2.5 shadow-inner">
              <div className="text-[10px] text-white/40 mb-1 uppercase tracking-widest font-semibold">
                SIBI (standar)
              </div>
              <div className="font-bold text-white text-base tracking-wide">
                {feedback.sibi_equivalent}
              </div>
              <div className="text-[10px] text-indigo-300/70 mt-1">
                Buku teks nasional
              </div>
            </div>
          </div>
        )}

        {/* Explanation */}
        <p className="text-xs text-white/80 leading-relaxed font-light">
          {feedback.explanation}
        </p>

        {/* Suggestion (jika ada) */}
        {feedback.suggestion && (
          <div className="flex items-start gap-2.5 rounded-xl bg-white/5 border border-white/5 px-3 py-2.5">
            <span className="text-sm mt-0.5 opacity-80">💡</span>
            <p className="text-xs text-white/90 leading-relaxed font-light">
              {feedback.suggestion}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
