import { Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";
import type { Message, UploadedDocument } from "../types";
import { ChatInput } from "./ChatInput";
import { EmptyState } from "./EmptyState";
import { MessageBubble, StreamingBubble } from "./MessageBubble";

interface ChatWindowProps {
	messages: Message[];
	loading: boolean;
	error: string | null;
	streaming: boolean;
	streamingContent: string;
	hasDocument: boolean;
	uploading: boolean;
	conversationId: string | null;
	libraryDocuments: UploadedDocument[];
	onSend: (content: string) => void;
	onUpload: (files: File[]) => void;
	onAttachFromLibrary: (documentId: string) => void;
}

export function ChatWindow({
	messages,
	loading,
	error,
	streaming,
	streamingContent,
	hasDocument,
	uploading,
	conversationId,
	libraryDocuments,
	onSend,
	onUpload,
	onAttachFromLibrary,
}: ChatWindowProps) {
	const scrollRef = useRef<HTMLDivElement>(null);

	// Auto-scroll to bottom when new messages arrive or during streaming
	const messagesLength = messages.length;
	// biome-ignore lint/correctness/useExhaustiveDependencies: messages and streamingContent are intentional triggers for auto-scroll
	useEffect(() => {
		if (scrollRef.current) {
			scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
		}
	}, [messagesLength, streamingContent]);

	// No conversation selected
	if (!conversationId) {
		return (
			<div className="flex flex-1 items-center justify-center bg-neutral-50">
				<div className="text-center">
					<p className="text-sm text-neutral-400">
						Select a conversation or create a new one
					</p>
				</div>
			</div>
		);
	}

	// Loading messages
	if (loading) {
		return (
			<div className="flex flex-1 items-center justify-center bg-white">
				<Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
			</div>
		);
	}

	// Empty conversation - show upload prompt
	if (messages.length === 0 && !streaming) {
		return (
			<div className="flex min-h-0 flex-1 flex-col bg-white">
				<div className="flex flex-1 items-center justify-center">
					{hasDocument ? (
						<div className="text-center">
							<p className="text-sm text-neutral-500">
								Documents uploaded. Ask a question to get started.
							</p>
						</div>
					) : (
						<EmptyState
							onUpload={onUpload}
							onAttachFromLibrary={onAttachFromLibrary}
							libraryDocuments={libraryDocuments}
							uploading={uploading}
						/>
					)}
				</div>
				{hasDocument && (
					<ChatInput
						onSend={onSend}
						onUpload={onUpload}
						onAttachFromLibrary={onAttachFromLibrary}
						libraryDocuments={libraryDocuments}
						uploading={uploading}
						disabled={streaming}
					/>
				)}
			</div>
		);
	}

	return (
		<div className="flex min-h-0 flex-1 flex-col bg-white">
			{error && (
				<div className="mx-4 mt-2 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">
					{error}
				</div>
			)}

			<div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
				<div className="w-full space-y-1">
					{messages.map((message) => (
						<MessageBubble key={message.id} message={message} />
					))}
					{streaming && <StreamingBubble content={streamingContent} />}
				</div>
			</div>

			{hasDocument && (
				<ChatInput
					onSend={onSend}
					onUpload={onUpload}
					onAttachFromLibrary={onAttachFromLibrary}
					libraryDocuments={libraryDocuments}
					uploading={uploading}
					disabled={streaming}
				/>
			)}
		</div>
	);
}
