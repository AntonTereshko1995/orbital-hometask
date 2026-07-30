import { useEffect, useState } from "react";
import * as api from "../lib/api";
import type { Message, SharedConversation } from "../types";
import { DocumentViewer } from "./DocumentViewer";
import { MessageBubble } from "./MessageBubble";
import { ScrollArea } from "./ui/scroll-area";

export function SharedConversationView() {
	const token =
		window.location.pathname.split("/shared/")[1]?.split("/")[0] ?? "";

	const [conversation, setConversation] = useState<SharedConversation | null>(
		null,
	);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (!token) {
			setError("Invalid share link.");
			setLoading(false);
			return;
		}
		api
			.fetchSharedConversation(token)
			.then(setConversation)
			.catch(() =>
				setError(
					"This conversation is no longer shared or the link is invalid.",
				),
			)
			.finally(() => setLoading(false));
	}, [token]);

	if (loading) {
		return (
			<div className="flex h-screen items-center justify-center bg-neutral-50">
				<div className="space-y-3 text-center">
					<div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-700" />
					<p className="text-sm text-neutral-400">Loading conversation…</p>
				</div>
			</div>
		);
	}

	if (error || !conversation) {
		return (
			<div className="flex h-screen items-center justify-center bg-neutral-50">
				<div className="max-w-sm space-y-2 text-center">
					<p className="text-sm font-medium text-neutral-700">
						Conversation not available
					</p>
					<p className="text-xs text-neutral-400">
						{error ?? "This link is no longer active."}
					</p>
				</div>
			</div>
		);
	}

	// SharedMessage has the same shape as Message — cast for MessageBubble
	const messages = conversation.messages as unknown as Message[];

	return (
		<div className="flex h-screen flex-col bg-neutral-50">
			{/* Header */}
			<header className="flex flex-shrink-0 items-center gap-3 border-b border-neutral-200 bg-white px-6 py-3">
				<h1 className="min-w-0 truncate text-sm font-semibold text-neutral-800">
					{conversation.title}
				</h1>
				<span className="flex-shrink-0 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600">
					Shared
				</span>
			</header>

			{/* Split pane */}
			<div className="flex min-h-0 flex-1">
				{/* Document pane — 62% */}
				<div
					style={{ width: "62%" }}
					className="overflow-hidden border-r border-neutral-200"
				>
					<DocumentViewer documents={conversation.documents} />
				</div>

				{/* Messages pane — 38% */}
				<div style={{ width: "38%" }} className="flex flex-col overflow-hidden">
					<div className="flex-shrink-0 border-b border-neutral-100 px-4 py-2.5 text-xs text-neutral-400">
						Read-only view
					</div>
					<ScrollArea className="flex-1">
						<div className="px-4 py-4">
							{messages.map((m) => (
								<MessageBubble key={m.id} message={m} />
							))}
							{messages.length === 0 && (
								<p className="py-8 text-center text-xs text-neutral-400">
									No messages yet
								</p>
							)}
						</div>
					</ScrollArea>
				</div>
			</div>
		</div>
	);
}
