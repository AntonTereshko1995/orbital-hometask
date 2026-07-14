import type { Message } from "../types";

export type SseEvent =
	| { type: "content"; content: string }
	| { type: "message"; message: Message }
	| { type: "done"; sources_cited: number; message_id: string };

/**
 * Parse a single SSE line into a typed event.
 * Returns null for empty lines, comments, or invalid JSON.
 */
export function parseSseLine(line: string): SseEvent | null {
	const trimmed = line.trim();
	if (!trimmed.startsWith("data: ")) return null;
	const raw = trimmed.slice(6);
	if (raw === "[DONE]") return null;
	try {
		return JSON.parse(raw) as SseEvent;
	} catch {
		return null;
	}
}
