import { Worker } from "@react-pdf-viewer/core";
import { useCallback, useRef, useState } from "react";
import { ChatSidebar } from "./components/ChatSidebar";
import { ChatWindow } from "./components/ChatWindow";
import { DocumentViewer } from "./components/DocumentViewer";
import { LibraryPanel } from "./components/LibraryPanel";
import { TooltipProvider } from "./components/ui/tooltip";
import { useConversations } from "./hooks/use-conversations";
import { useDocument } from "./hooks/use-document";
import { useLibrary } from "./hooks/use-library";
import { useMessages } from "./hooks/use-messages";
import * as api from "./lib/api";

const WORKER_URL = new URL(
	"pdfjs-dist/build/pdf.worker.min.js",
	import.meta.url,
).toString();

// Document pane width as percentage of the main content area (sidebar excluded).
// Clamped between 40% and 80% via the drag handle.
const DOC_WIDTH_DEFAULT = 62;
const DOC_WIDTH_MIN = 40;
const DOC_WIDTH_MAX = 80;

export default function App() {
	const [libraryOpen, setLibraryOpen] = useState(false);
	const [docWidthPercent, setDocWidthPercent] = useState(DOC_WIDTH_DEFAULT);
	const [isDragging, setIsDragging] = useState(false);
	const mainRef = useRef<HTMLDivElement>(null);

	const {
		conversations,
		selectedId,
		loading: conversationsLoading,
		create,
		createQuiet,
		select,
		remove,
		rename,
		togglePin,
		refresh: refreshConversations,
	} = useConversations();

	const {
		messages,
		loading: messagesLoading,
		error: messagesError,
		streaming,
		streamingContent,
		send,
	} = useMessages(selectedId);

	const {
		documents,
		uploading,
		upload,
		refresh: refreshDocument,
	} = useDocument(selectedId);

	const {
		documents: libraryDocuments,
		loading: libraryLoading,
		error: libraryError,
		refresh: refreshLibrary,
		remove: removeFromLibrary,
		upload: uploadToLibrary,
		uploading: libraryUploading,
		uploadProgress: libraryUploadProgress,
		uploadSummary: libraryUploadSummary,
	} = useLibrary();

	const handleSend = useCallback(
		async (content: string) => {
			await send(content);
			refreshConversations();
		},
		[send, refreshConversations],
	);

	const handleUpload = useCallback(
		async (files: File[]) => {
			await upload(files);
			refreshDocument();
			refreshConversations();
			refreshLibrary();
		},
		[upload, refreshDocument, refreshConversations, refreshLibrary],
	);

	const handleAttachFromLibrary = useCallback(
		async (documentId: string) => {
			if (!selectedId) return;
			await api.attachFromLibrary(selectedId, documentId);
			refreshDocument();
			refreshConversations();
		},
		[selectedId, refreshDocument, refreshConversations],
	);

	const handleDeleteFromLibrary = useCallback(
		async (id: string) => {
			await removeFromLibrary(id);
			refreshDocument();
		},
		[removeFromLibrary, refreshDocument],
	);

	const handleLibraryUpload = useCallback(
		async (files: File[]) => {
			await uploadToLibrary(files);
		},
		[uploadToLibrary],
	);

	const handleCreateChatFromLibrary = useCallback(
		async (documentId: string) => {
			const conv = await createQuiet();
			if (!conv) return;
			await api.attachFromLibrary(conv.id, documentId);
			select(conv.id);
			refreshConversations();
			setLibraryOpen(false);
		},
		[createQuiet, select, refreshConversations],
	);

	// Drag handler for the split-pane divider between document and chat.
	// Captures the container bounds at drag-start so calculations stay accurate
	// even if the container shifts during the drag.
	const handleSplitDrag = useCallback((e: React.MouseEvent) => {
		e.preventDefault();
		const container = mainRef.current;
		if (!container) return;

		setIsDragging(true);
		const rect = container.getBoundingClientRect();

		const handleMouseMove = (moveEvent: MouseEvent) => {
			const relX = moveEvent.clientX - rect.left;
			const percent = (relX / rect.width) * 100;
			setDocWidthPercent(
				Math.min(DOC_WIDTH_MAX, Math.max(DOC_WIDTH_MIN, percent)),
			);
		};

		const handleMouseUp = () => {
			setIsDragging(false);
			window.removeEventListener("mousemove", handleMouseMove);
			window.removeEventListener("mouseup", handleMouseUp);
		};

		window.addEventListener("mousemove", handleMouseMove);
		window.addEventListener("mouseup", handleMouseUp);
	}, []);

	return (
		<Worker workerUrl={WORKER_URL}>
			<TooltipProvider delayDuration={200}>
				<div
					className="flex h-screen bg-neutral-50"
					// Prevent text selection while dragging the divider
					style={isDragging ? { userSelect: "none", cursor: "col-resize" } : {}}
				>
					<ChatSidebar
						conversations={conversations}
						selectedId={selectedId}
						loading={conversationsLoading}
						libraryOpen={libraryOpen}
						onSelect={select}
						onCreate={create}
						onDelete={remove}
						onRename={rename}
						onPin={togglePin}
						onToggleLibrary={() => setLibraryOpen((v) => !v)}
						onShareChange={refreshConversations}
					/>

					{/* Main content area: document pane + divider + chat pane */}
					<div ref={mainRef} className="relative flex flex-1 overflow-hidden">
						{/* Document pane — primary, wider */}
						<div
							style={{ width: `${docWidthPercent}%` }}
							className="flex flex-col overflow-hidden"
						>
							<DocumentViewer documents={documents} />
						</div>

						{/* Drag handle — vertical divider between document and chat */}
						<div
							className="absolute top-0 z-10 h-full w-1 -translate-x-1/2 cursor-col-resize transition-colors hover:bg-blue-400"
							style={{ left: `${docWidthPercent}%` }}
							onMouseDown={handleSplitDrag}
						/>

						{/* Chat pane — secondary, narrower */}
						<div
							style={{ width: `${100 - docWidthPercent}%` }}
							className="flex flex-col overflow-hidden border-l border-neutral-200"
						>
							<ChatWindow
								messages={messages}
								loading={messagesLoading}
								error={messagesError}
								streaming={streaming}
								streamingContent={streamingContent}
								hasDocument={documents.length > 0}
								uploading={uploading}
								conversationId={selectedId}
								libraryDocuments={libraryDocuments}
								onSend={handleSend}
								onUpload={handleUpload}
								onAttachFromLibrary={handleAttachFromLibrary}
							/>
						</div>
					</div>

					<LibraryPanel
						open={libraryOpen}
						documents={libraryDocuments}
						loading={libraryLoading}
						error={libraryError}
						uploading={libraryUploading}
						uploadProgress={libraryUploadProgress}
						uploadSummary={libraryUploadSummary}
						onClose={() => setLibraryOpen(false)}
						onDelete={handleDeleteFromLibrary}
						onUpload={handleLibraryUpload}
						onCreateChat={handleCreateChatFromLibrary}
					/>
				</div>
			</TooltipProvider>
		</Worker>
	);
}
