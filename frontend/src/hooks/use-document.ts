import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { UploadedDocument } from "../types";

export function useDocument(conversationId: string | null) {
	const [documents, setDocuments] = useState<UploadedDocument[]>([]);
	const [uploading, setUploading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		if (!conversationId) {
			setDocuments([]);
			return;
		}
		try {
			setError(null);
			const detail = await api.fetchConversation(conversationId);
			setDocuments(detail.documents ?? []);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load documents");
		}
	}, [conversationId]);

	useEffect(() => {
		refresh();
	}, [refresh]);

	const upload = useCallback(
		async (files: File[]) => {
			if (!conversationId || files.length === 0) return;
			setUploading(true);
			setError(null);
			try {
				for (const file of files) {
					const doc = await api.uploadDocument(conversationId, file);
					setDocuments((prev) => [...prev, doc]);
				}
			} catch (err) {
				setError(
					err instanceof Error ? err.message : "Failed to upload document",
				);
			} finally {
				setUploading(false);
			}
		},
		[conversationId],
	);

	return {
		documents,
		uploading,
		error,
		upload,
		refresh,
	};
}
