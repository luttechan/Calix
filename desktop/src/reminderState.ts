import type { ReminderPayload } from "./types";
export type ReminderEnvelope = {
  revision: number;
  payload: ReminderPayload | null;
};
export function acceptReminder(
  current: ReminderEnvelope,
  incoming: ReminderEnvelope,
): ReminderEnvelope {
  return Number.isSafeInteger(incoming.revision) &&
    incoming.revision >= current.revision
    ? incoming
    : current;
}
