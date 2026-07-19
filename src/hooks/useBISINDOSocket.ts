// ============================================================
// useBISINDOSocket.ts
// Custom hook — WebSocket connection dengan Flask-SocketIO
// Adaptasi dari kevinjosethomas/sign-language-processing
// Perubahan utama:
//   - multi-room (student_room / teacher_room)
//   - event teacher_feedback (baru)
//   - event sign_animation dengan 225-dim frames
// ============================================================

import { useEffect, useRef, useState, useCallback } from "react";
import { io, Socket } from "socket.io-client";
import {
  TeacherFeedbackEvent,
  SentenceEvent,
  WordDetectedEvent,
  SignAnimationEvent,
} from "../types/bisindo";

const SERVER_URL = import.meta.env.VITE_SERVER_URL ?? "http://localhost:5000";

type RoomType = "student_room" | "teacher_room";

interface BISINDOSocketOptions {
  room: RoomType;
  sessionId: string;
  onWordDetected?: (event: WordDetectedEvent) => void;
  onSentence?: (event: SentenceEvent) => void;
  onTeacherFeedback?: (event: TeacherFeedbackEvent) => void;
  onSignAnimation?: (event: SignAnimationEvent) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export function useBISINDOSocket(options: BISINDOSocketOptions) {
  const {
    room,
    sessionId,
    onWordDetected,
    onSentence,
    onTeacherFeedback,
    onSignAnimation,
    onConnect,
    onDisconnect,
  } = options;

  const socketRef = useRef<Socket | null>(null);
  const [connected, setConnected] = useState(false);
  const [latency, setLatency] = useState<number | null>(null);
  const pingStartRef = useRef<number>(0);

  // ---------- Init socket ----------
  useEffect(() => {
    const socket = io(SERVER_URL, {
      transports: ["websocket"],
      reconnectionDelay: 1000,
      reconnectionAttempts: 10,
    });

    socketRef.current = socket;

    socket.on("connect", () => {
      setConnected(true);
      // Gabung ke room sesuai role
      socket.emit("join_room", { room, session_id: sessionId });
      onConnect?.();
    });

    socket.on("disconnect", () => {
      setConnected(false);
      onDisconnect?.();
    });

    // --------------- Receptive events ---------------
    socket.on("word_detected", (data: WordDetectedEvent) => {
      onWordDetected?.(data);
    });

    socket.on("sentence", (data: SentenceEvent) => {
      onSentence?.(data);
    });

    // --------------- Teacher event (BARU) ---------------
    socket.on("teacher_feedback", (data: TeacherFeedbackEvent) => {
      onTeacherFeedback?.(data);
    });

    // --------------- Expressive event ---------------
    socket.on("sign_animation", (data: SignAnimationEvent) => {
      onSignAnimation?.(data);
    });

    // Latency measurement
    socket.on("pong_bisindo", () => {
      setLatency(Date.now() - pingStartRef.current);
    });

    return () => {
      socket.emit("leave_room", { room, session_id: sessionId });
      socket.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [room, sessionId]);

  // ---------- Send frame (receptive) ----------
  const sendFrame = useCallback((frameBase64: string) => {
    if (!socketRef.current?.connected) return;
    socketRef.current.emit("frame", {
      frame: frameBase64,
      timestamp: Date.now(),
    });
  }, []);

  // ---------- Send text (expressive) ----------
  const sendSpeak = useCallback((text: string) => {
    if (!socketRef.current?.connected) return;
    socketRef.current.emit("speak", { text, language: "id" });
  }, []);

  // ---------- Force synthesis (flush buffer) ----------
  const forceSynthesis = useCallback(() => {
    socketRef.current?.emit("force_synthesis", {});
  }, []);

  // ---------- Reset session ----------
  const resetSession = useCallback(() => {
    socketRef.current?.emit("reset_session", { session_id: sessionId });
  }, [sessionId]);

  // ---------- Ping latency ----------
  const ping = useCallback(() => {
    pingStartRef.current = Date.now();
    socketRef.current?.emit("ping_bisindo", {});
  }, []);

  return {
    connected,
    latency,
    sendFrame,
    sendSpeak,
    forceSynthesis,
    resetSession,
    ping,
  };
}
