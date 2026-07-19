// ============================================================
// TeacherPanel.tsx
// Panel umpan balik real-time untuk guru
// Komponen BARU — tidak ada di repo kevinjosethomas
//
// Fitur:
//   - Feed kartu feedback BISINDO ↔ SIBI berdasarkan TeacherFeedbackEvent
//   - Counter per severity
//   - Tombol session summary + export
//   - Indikator koneksi
// ============================================================

import { useState, useCallback, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { TeacherFeedbackEvent, SessionSummary } from "../types/bisindo";
import { useBISINDOSocket } from "../hooks/useBISINDOSocket";
import SIBIFeedback from "./SIBIFeedback";

interface FeedbackEntry extends TeacherFeedbackEvent {
  id: string;
}

interface TeacherPanelProps {
  sessionId?: string;
}

export default function TeacherPanel({ sessionId: propSessionId }: TeacherPanelProps) {
  const sessionId = propSessionId ?? uuidv4();

  const [feedbackQueue, setFeedbackQueue] = useState<FeedbackEntry[]>([]);
  const [sessionSummary, setSessionSummary] = useState<SessionSummary | null>(null);
  const [showSummary, setShowSummary] = useState(false);

  // Counters per severity
  const [counts, setCounts] = useState({ info: 0, minor: 0, significant: 0 });

  // Kata yang terdeteksi (histori sesi)
  const [wordHistory, setWordHistory] = useState<string[]>([]);

  const handleFeedback = useCallback((event: TeacherFeedbackEvent) => {
    const entry: FeedbackEntry = { ...event, id: uuidv4() };

    setFeedbackQueue((prev) => [entry, ...prev].slice(0, 20)); // max 20 kartu
    setCounts((prev) => ({
      ...prev,
      [event.severity]: prev[event.severity] + 1,
    }));
    setWordHistory((prev) => [event.detected_word, ...prev].slice(0, 50));
  }, []);

  const { connected, latency } = useBISINDOSocket({
    room: "teacher_room",
    sessionId,
    onTeacherFeedback: handleFeedback,
  });

  const dismissFeedback = useCallback((id: string) => {
    setFeedbackQueue((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const exportSummary = () => {
    if (!sessionSummary) return;
    const blob = new Blob([JSON.stringify(sessionSummary, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bisindo-sesi-${sessionId.slice(0, 8)}.json`;
    a.click();
  };

  // Buat summary dari state lokal
  const buildSummary = (): SessionSummary => ({
    session_id: sessionId,
    total_words: wordHistory.length,
    words_with_sibi_diff: counts.minor + counts.significant,
    feedback_items: feedbackQueue,
    started_at: new Date().toISOString(),
    duration_minutes: 0,
  });

  return (
    <div className="flex flex-col h-full bg-transparent">
      {/* ─── Header ─── */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/5 bg-white/5">
        <div className="flex items-center gap-3">
          <span className="text-lg">👩‍🏫</span>
          <div>
            <h2 className="text-sm font-semibold">Panel Guru</h2>
            <p className="text-[10px] text-white/40">BISINDO ↔ SIBI real-time</p>
          </div>
        </div>

        {/* Status koneksi */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/20 border border-white/5">
          <div
            className={`w-1.5 h-1.5 rounded-full ${
              connected ? "bg-green-500 animate-pulse" : "bg-red-500"
            }`}
          />
          <span className="text-[10px] text-white/50">
            {connected ? `${latency ?? "—"}ms` : "Terputus"}
          </span>
        </div>
      </div>

      {/* ─── Counter badges ─── */}
      <div className="flex gap-2 px-5 py-3 border-b border-white/5 bg-black/10">
        <CountBadge label="Info" count={counts.info} color="blue" />
        <CountBadge label="Minor" count={counts.minor} color="amber" />
        <CountBadge label="Perlu koreksi" count={counts.significant} color="red" />
        <div className="ml-auto text-[10px] text-white/30">
          {wordHistory.length} kata terdeteksi
        </div>
      </div>

      {/* ─── Feedback feed ─── */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 custom-scrollbar">
        {feedbackQueue.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-center animate-fade-in opacity-60">
            <p className="text-3xl mb-3 drop-shadow-lg">🤟</p>
            <p className="text-sm text-white/40">Menunggu isyarat siswa…</p>
            <p className="text-[10px] text-white/25 mt-1">
              Umpan balik BISINDO ↔ SIBI akan muncul di sini
            </p>
          </div>
        ) : (
          feedbackQueue.map((fb) => (
            <SIBIFeedback
              key={fb.id}
              feedback={fb}
              onDismiss={() => dismissFeedback(fb.id)}
            />
          ))
        )}
      </div>

      {/* ─── Footer actions ─── */}
      <div className="flex gap-3 px-4 py-4 border-t border-white/5 bg-white/5">
        <button
          onClick={() => {
            setSessionSummary(buildSummary());
            setShowSummary(true);
          }}
          className="glass-button flex-1 text-xs py-2.5 rounded-xl text-white/80 font-medium tracking-wide flex items-center justify-center gap-2"
        >
          📊 Ringkasan Sesi
        </button>
        <button
          onClick={() => {
            setFeedbackQueue([]);
            setCounts({ info: 0, minor: 0, significant: 0 });
            setWordHistory([]);
          }}
          className="text-xs px-4 py-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20
                     text-rose-400 hover:text-rose-300 transition-all duration-300 border border-rose-500/20"
        >
          Reset
        </button>
      </div>

      {/* ─── Session Summary Modal ─── */}
      {showSummary && sessionSummary && (
        <SessionSummaryModal
          summary={sessionSummary}
          onClose={() => setShowSummary(false)}
          onExport={exportSummary}
        />
      )}
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────

function CountBadge({
  label,
  count,
  color,
}: {
  label: string;
  count: number;
  color: "blue" | "amber" | "red";
}) {
  const colors = {
    blue: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30 shadow-indigo-500/10",
    amber: "bg-amber-500/20 text-amber-300 border-amber-500/30 shadow-amber-500/10",
    red: "bg-rose-500/20 text-rose-300 border-rose-500/30 shadow-rose-500/10",
  };

  return (
    <div
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px]
                  border shadow-sm font-medium tracking-wide ${colors[color]}`}
    >
      <span className="font-bold tabular-nums">{count}</span>
      <span className="opacity-70">{label}</span>
    </div>
  );
}

function SessionSummaryModal({
  summary,
  onClose,
  onExport,
}: {
  summary: SessionSummary;
  onClose: () => void;
  onExport: () => void;
}) {
  const diffRate =
    summary.total_words > 0
      ? ((summary.words_with_sibi_diff / summary.total_words) * 100).toFixed(1)
      : "0.0";

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
      <div className="bg-slate-900/90 rounded-2xl border border-white/10 shadow-2xl shadow-indigo-500/10 w-full max-w-sm p-6 space-y-5 animate-slide-up">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm">Ringkasan sesi</h3>
          <button
            onClick={onClose}
            className="text-white/30 hover:text-white transition-colors text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-3">
          <StatCard label="Kata terdeteksi" value={summary.total_words} />
          <StatCard
            label="Perbedaan BISINDO↔SIBI"
            value={summary.words_with_sibi_diff}
            highlight
          />
          <StatCard label="Tingkat perbedaan" value={`${diffRate}%`} />
          <StatCard
            label="Perlu koreksi"
            value={
              summary.feedback_items.filter((f) => f.severity === "significant").length
            }
          />
        </div>

        {/* Top words dengan perbedaan */}
        {summary.feedback_items.filter((f) => f.is_different).length > 0 && (
          <div>
            <p className="text-[10px] text-white/40 uppercase tracking-wide mb-2">
              Kata dengan perbedaan SIBI
            </p>
            <div className="flex flex-wrap gap-1.5">
              {[
                ...new Set(
                  summary.feedback_items
                    .filter((f) => f.is_different)
                    .map((f) => f.detected_word)
                ),
              ]
                .slice(0, 10)
                .map((word) => (
                  <span
                    key={word}
                    className="px-2 py-0.5 rounded-full bg-amber-900/40 text-amber-300
                               text-[10px] border border-amber-700/30"
                  >
                    {word}
                  </span>
                ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            onClick={onExport}
            className="flex-1 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 shadow-lg shadow-indigo-500/20
                       text-white text-xs font-semibold tracking-wide transition-all duration-300"
          >
            Export JSON
          </button>
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl glass-button text-white/80 text-xs font-medium"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string | number;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl p-3 border ${
        highlight
          ? "bg-amber-900/30 border-amber-700/30"
          : "bg-white/5 border-white/10"
      }`}
    >
      <p className={`text-[10px] mb-1 ${highlight ? "text-amber-400/70" : "text-white/40"}`}>
        {label}
      </p>
      <p
        className={`text-xl font-bold tabular-nums ${
          highlight ? "text-amber-300" : "text-white"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
