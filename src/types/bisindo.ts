// ============================================================
// BISINDO-LLM — Type Definitions
// Adaptasi dari kevinjosethomas/sign-language-processing
// ============================================================

// --------------- WebSocket Events ---------------

export interface JoinRoomPayload {
  room: "student_room" | "teacher_room";
  session_id: string;
}

export interface FramePayload {
  frame: string;      // base64 JPEG
  timestamp: number;
}

export interface SpeakPayload {
  text: string;
  language?: "id";    // Bahasa Indonesia default
}

// --------------- Server Responses ---------------

export interface WordDetectedEvent {
  word: string;
  confidence: number;
  frame_count: number;
}

export interface SentenceEvent {
  sentence: string;
  gloss_sequence: string[];
  timestamp: number;
}

export interface TeacherFeedbackEvent {
  detected_word: string;
  sibi_equivalent: string | null;
  is_different: boolean;
  explanation: string;
  suggestion: string;
  severity: "info" | "minor" | "significant";
  regional_note: string | null;
  timestamp: number;
}

export interface SignAnimationEvent {
  word: string;
  frames: number[][];       // array of 225-dim keyframes
  fps: number;
  fingerspell: boolean;     // true jika fallback ke fingerspell
}

// --------------- Avatar ---------------

export interface AvatarKeyframe {
  pose: number[];            // 99 coords (33 pts × 3)
  left_hand: number[];       // 63 coords (21 pts × 3)
  right_hand: number[];      // 63 coords (21 pts × 3)
}

// --------------- Teacher Session ---------------

export interface SessionSummary {
  session_id: string;
  total_words: number;
  words_with_sibi_diff: number;
  feedback_items: TeacherFeedbackEvent[];
  started_at: string;
  duration_minutes: number;
}

// --------------- Component Props ---------------

export interface TeacherPanelProps {
  sessionId: string;
  connected: boolean;
}

export interface SIBIFeedbackProps {
  feedback: TeacherFeedbackEvent;
  onDismiss?: () => void;
}

export interface AvatarProps {
  animation: SignAnimationEvent | null;
  isPlaying: boolean;
  onAnimationEnd?: () => void;
}

export interface ReceptiveViewProps {
  onSentence?: (sentence: string) => void;
}

export interface ExpressiveViewProps {
  onAnimationStart?: (word: string) => void;
}
