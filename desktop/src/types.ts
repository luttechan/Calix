export type EventItem = {
  key: string;
  course_id: number;
  course_name: string;
  kind: string;
  title: string;
  due_at: string | null;
  completed: boolean;
  url: string;
  note: string;
  type_id: number | null;
  type_name: string;
  type_color: string;
  manual: boolean;
  completion_verified: boolean;
  week: string;
  source_title: string;
  lms_data?: {
    attendance_status?: string;
    feedback_available?: boolean;
    rubric?: { title: string; text: string }[];
    status?: string;
    late?: boolean;
    grade?: string;
    submitted_at?: string;
    comments?: { text: string; author: string; created_at: string | null }[];
  };
};
export type Course = { id: number; name: string };
export type Session = {
  semester: string;
  title: string;
  is_online: number;
  id: number;
  course_id: number;
  day: number;
  start_time: string;
  end_time: string;
  professor: string;
  room: string;
  color: string;
};
export type Task = {
  id: string;
  section_id: number;
  source_key: string | null;
  title: string;
  due_at: string | null;
  category: string;
  role: string;
  professor: string;
  status_id: number;
  status_name: string;
  status_color: string;
  status_kind: string;
  note: string;
};
export type Summary = { id: string; date: string; title: string };
export type Journal = {
  date: string;
  title: string;
  body: string;
  html: string;
};
export type ReminderSettings = {
  enabled: boolean;
  startup: boolean;
  sync: boolean;
  urgent: boolean;
  urgent_minutes: number;
  general: boolean;
  general_days: number;
  assignments: boolean;
  videos: boolean;
  sound: boolean;
  track: string;
  sync_track?: string;
  volume: number;
};
export type ReminderPayload = {
  title: string;
  message: string;
  urgent: boolean;
  theme: Preferences["theme"];
  glass: boolean;
  sound: string;
  volume: number;
  total: number;
  events: Pick<
    EventItem,
    "key" | "title" | "course_name" | "kind" | "due_at"
  >[];
};
export type PaletteColor = "canvas" | "surface" | "accent" | "muted";
export type ThemePalette = Partial<Record<PaletteColor, string>>;
export type Preferences = {
  attendance_visible: boolean;
  attendance_sync: boolean;
  anki_sync?: boolean;
  developer_mode: boolean;
  reminders: ReminderSettings;
  theme: "pink" | "sky" | "mint" | "purple" | "dark" | "peach" | "amber" | "olive" | "lavender";
  theme_palette?: ThemePalette;
  glass: boolean;
  font_mode: string;
  catholic: boolean;
  birthday: boolean;
  avatar: string;
  nickname: string;
  greeting: string;
  onboarding_complete: boolean;
};
export type SecurityState = {
  configured: boolean;
  locked: boolean;
  policy: { main: boolean; timetable: boolean; grades: boolean; idle_minutes: number };
  unlocked: string[];
  retry_after: number;
};
export type Snapshot = {
  security?: SecurityState;
  version: string;
  events: EventItem[];
  courses: Course[];
  types: { id: number; name: string; color: string }[];
  sessions: Session[];
  timetableTerms: { name: string; offDays: number[]; startsOn?: string | null; endsOn?: string | null }[];
  mainTerm: string;
  timetableConfigured: boolean;
  semesterAutomatic?: boolean;
  semesterSeasonal?: boolean;
  sections: { id: number; name: string }[];
  statuses: { id: number; name: string; color: string; kind: string }[];
  tasks: Task[];
  offDays: number[];
  preferences: Preferences;
  lastSync: string;
  syncSummary: string;
  holidays: Record<string, string>;
  specialDates: Record<string, string>;
  journals: Summary[];
};
export type Page =
  | "deadlines"
  | "courses"
  | "grades"
  | "attendance"
  | "study"
  | "home"
  | "calendar"
  | "assignments"
  | "videos"
  | "timetable"
  | "checklist"
  | "diary"
  | "settings";
