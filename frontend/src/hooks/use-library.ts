import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../lib/api";
import type { UploadedDocument } from "../types";

export interface UploadSummary {
	added: number;
	duplicates: number;
	failed: number;
}

export function useLibrary() {
	const [documents, setDocuments] = useState<UploadedDocument[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const [uploading, setUploading] = useState(false);
	const [uploadProgress, setUploadProgress] = useState<{
		done: number;
		total: number;
	} | null>(null);
	const [uploadSummary, setUploadSummary] = useState<UploadSummary | null>(
		null,
	);
	const summaryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	const refresh = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const docs = await api.fetchLibrary();
			setDocuments(docs);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load library");
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		refresh();
	}, [refresh]);

	const remove = useCallback(
		async (id: string) => {
			try {
				await api.deleteDocument(id);
				await refresh();
			} catch (err) {
				setError(
					err instanceof Error ? err.message : "Failed to delete document",
				);
			}
		},
		[refresh],
	);

	const upload = useCallback(
		async (files: File[]) => {
			if (files.length === 0) return;

			setUploading(true);
			setUploadSummary(null);
			setUploadProgress({ done: 0, total: files.length });
			if (summaryTimerRef.current) clearTimeout(summaryTimerRef.current);

			let added = 0;
			let duplicates = 0;
			let failed = 0;

			await Promise.allSettled(
				files.map(async (file) => {
					try {
						const doc = await api.uploadToLibrary(file);
						if (doc.reused_from_library) {
							duplicates++;
						} else {
							added++;
						}
					} catch {
						failed++;
					} finally {
						setUploadProgress((prev) =>
							prev ? { ...prev, done: prev.done + 1 } : null,
						);
					}
				}),
			);

			await refresh();

			setUploading(false);
			setUploadProgress(null);
			setUploadSummary({ added, duplicates, failed });
			summaryTimerRef.current = setTimeout(() => setUploadSummary(null), 5000);
		},
		[refresh],
	);

	return {
		documents,
		loading,
		error,
		refresh,
		remove,
		upload,
		uploading,
		uploadProgress,
		uploadSummary,
	};
}
