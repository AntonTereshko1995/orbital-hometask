import { useCallback, useState } from "react";
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

export default function App() {
	const [libraryOpen, setLibraryOpen] = useState(false);

	const {
		conversations,
		selectedId,
		loading: conversationsLoading,
		create,
		select,
		remove,
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

	const handleViewDocument = useCallback((id: string) => {
		window.open(api.getDocumentUrl(id), "_blank");
	}, []);

	const handleCreateChatFromLibrary = useCallback(
		async (documentId: string) => {
			const conv = await create();
			if (!conv) return;
			await api.attachFromLibrary(conv.id, documentId);
			refreshDocument();
			refreshConversations();
			setLibraryOpen(false);
		},
		[create, refreshDocument, refreshConversations],
	);

	return (
		<TooltipProvider delayDuration={200}>
			<div className="flex h-screen bg-neutral-50">
				<ChatSidebar
					conversations={conversations}
					selectedId={selectedId}
					loading={conversationsLoading}
					libraryOpen={libraryOpen}
					onSelect={select}
					onCreate={create}
					onDelete={remove}
					onToggleLibrary={() => setLibraryOpen((v) => !v)}
				/>

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

				<DocumentViewer documents={documents} />

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
					onView={handleViewDocument}
					onCreateChat={handleCreateChatFromLibrary}
				/>
			</div>
		</TooltipProvider>
	);
}
