import { Viewer, Worker, SpecialZoomLevel } from "@react-pdf-viewer/core";
import { defaultLayoutPlugin } from "@react-pdf-viewer/default-layout";
import { AnimatePresence, motion } from "framer-motion";
import {
	AlertCircle,
	BookOpen,
	CheckCircle2,
	Eye,
	Loader2,
	MessageSquarePlus,
	MoreHorizontal,
	Trash2,
	Upload,
	X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { getDocumentUrl } from "../lib/api";
import type { UploadSummary } from "../hooks/use-library";
import type { UploadedDocument } from "../types";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";

const WORKER_URL = new URL(
	"pdfjs-dist/build/pdf.worker.min.js",
	import.meta.url,
).toString();

function PDFPreview({ pdfUrl }: { pdfUrl: string }) {
	const plugin = defaultLayoutPlugin();
	return (
		<Viewer
			fileUrl={pdfUrl}
			plugins={[plugin]}
			defaultScale={SpecialZoomLevel.PageWidth}
		/>
	);
}

interface DocumentPreviewModalProps {
	doc: UploadedDocument;
	onClose: () => void;
	onCreateChat: (id: string) => void;
}

function DocumentPreviewModal({ doc, onClose, onCreateChat }: DocumentPreviewModalProps) {
	const pdfUrl = getDocumentUrl(doc.id);

	// Close on Escape
	useEffect(() => {
		const handler = (e: KeyboardEvent) => {
			if (e.key === "Escape") onClose();
		};
		document.addEventListener("keydown", handler);
		return () => document.removeEventListener("keydown", handler);
	}, [onClose]);

	return createPortal(
		<div
			className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-6"
			onClick={onClose}
		>
			<div
				className="flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
				onClick={(e) => e.stopPropagation()}
			>
				<div className="flex flex-shrink-0 items-center justify-between border-b border-neutral-100 px-4 py-3">
					<div className="min-w-0">
						<p className="truncate text-sm font-medium text-neutral-800">
							{doc.filename}
						</p>
						<p className="text-xs text-neutral-400">
							{doc.page_count} page{doc.page_count !== 1 ? "s" : ""}
						</p>
					</div>
					<div className="ml-4 flex flex-shrink-0 items-center gap-2">
						<Button
							size="sm"
							className="gap-1.5 text-xs"
							onClick={() => {
								onCreateChat(doc.id);
								onClose();
							}}
						>
							<MessageSquarePlus className="h-3.5 w-3.5" />
							Start chat
						</Button>
						<Button variant="ghost" size="icon" onClick={onClose}>
							<X className="h-4 w-4" />
						</Button>
					</div>
				</div>
				<div className="flex-1 overflow-hidden">
					<Worker workerUrl={WORKER_URL}>
						<PDFPreview pdfUrl={pdfUrl} />
					</Worker>
				</div>
			</div>
		</div>,
		document.body,
	);
}

interface LibraryPanelProps {
	open: boolean;
	documents: UploadedDocument[];
	loading: boolean;
	error: string | null;
	uploading: boolean;
	uploadProgress: { done: number; total: number } | null;
	uploadSummary: UploadSummary | null;
	onClose: () => void;
	onDelete: (id: string) => void;
	onUpload: (files: File[]) => void;
	onCreateChat: (id: string) => void;
}

export function LibraryPanel({
	open,
	documents,
	loading,
	error,
	uploading,
	uploadProgress,
	uploadSummary,
	onClose,
	onDelete,
	onUpload,
	onCreateChat,
}: LibraryPanelProps) {
	const fileInputRef = useRef<HTMLInputElement>(null);
	const [openMenuId, setOpenMenuId] = useState<string | null>(null);
	const [previewDoc, setPreviewDoc] = useState<UploadedDocument | null>(null);

	useEffect(() => {
		if (!openMenuId) return;
		const close = () => setOpenMenuId(null);
		document.addEventListener("click", close);
		return () => document.removeEventListener("click", close);
	}, [openMenuId]);

	if (!open) return null;

	const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const files = Array.from(e.target.files ?? []);
		if (files.length > 0) onUpload(files);
		e.target.value = "";
	};

	const summaryParts: string[] = [];
	if (uploadSummary) {
		if (uploadSummary.added > 0)
			summaryParts.push(`${uploadSummary.added} added`);
		if (uploadSummary.duplicates > 0)
			summaryParts.push(`${uploadSummary.duplicates} already in library`);
		if (uploadSummary.failed > 0)
			summaryParts.push(`${uploadSummary.failed} failed`);
	}

	return (
		<>
			{previewDoc && (
				<DocumentPreviewModal
					doc={previewDoc}
					onClose={() => setPreviewDoc(null)}
					onCreateChat={onCreateChat}
				/>
			)}

			<div className="flex h-full w-[280px] flex-shrink-0 flex-col border-l border-neutral-200 bg-white">
				<div className="flex items-center justify-between border-b border-neutral-100 p-3">
					<div className="flex items-center gap-2">
						<BookOpen className="h-4 w-4 text-neutral-500" />
						<span className="text-sm font-semibold text-neutral-700">
							Library
						</span>
					</div>
					<Button variant="ghost" size="icon" onClick={onClose}>
						<X className="h-4 w-4" />
					</Button>
				</div>

				<div className="border-b border-neutral-100 p-3">
					<input
						ref={fileInputRef}
						type="file"
						accept=".pdf,application/pdf"
						multiple
						className="hidden"
						onChange={handleFileChange}
					/>
					<Button
						variant="secondary"
						size="sm"
						className="w-full gap-2 text-xs"
						disabled={uploading}
						onClick={() => fileInputRef.current?.click()}
					>
						{uploading ? (
							<Loader2 className="h-3.5 w-3.5 animate-spin" />
						) : (
							<Upload className="h-3.5 w-3.5" />
						)}
						{uploading
							? uploadProgress
								? `Uploading ${uploadProgress.done}/${uploadProgress.total}…`
								: "Uploading…"
							: "Upload documents"}
					</Button>

					{uploadSummary && (
						<div
							className={`mt-2 flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs ${
								uploadSummary.failed > 0 &&
								uploadSummary.added === 0 &&
								uploadSummary.duplicates === 0
									? "bg-red-50 text-red-600"
									: uploadSummary.failed > 0
										? "bg-amber-50 text-amber-700"
										: uploadSummary.duplicates > 0 && uploadSummary.added === 0
											? "bg-amber-50 text-amber-700"
											: "bg-green-50 text-green-700"
							}`}
						>
							{uploadSummary.failed > 0 &&
							uploadSummary.added === 0 &&
							uploadSummary.duplicates === 0 ? (
								<AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
							) : (
								<CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0" />
							)}
							{summaryParts.join(" · ")}
						</div>
					)}
				</div>

				{error && (
					<div className="mx-3 mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
						{error}
					</div>
				)}

				<ScrollArea className="flex-1">
					<div className="p-2">
						{loading && documents.length === 0 && (
							<div className="flex items-center justify-center py-10">
								<Loader2 className="h-5 w-5 animate-spin text-neutral-400" />
							</div>
						)}

						{!loading && documents.length === 0 && (
							<div className="flex flex-col items-center py-10 text-center">
								<BookOpen className="mb-3 h-8 w-8 text-neutral-300" />
								<p className="text-xs text-neutral-400">No documents yet</p>
								<p className="mt-1 text-xs text-neutral-400">
									Upload PDFs to get started
								</p>
							</div>
						)}

						<AnimatePresence initial={false}>
							{documents.map((doc) => (
								<motion.div
									key={doc.id}
									initial={{ opacity: 0, height: 0 }}
									animate={{ opacity: 1, height: "auto" }}
									exit={{ opacity: 0, height: 0 }}
									transition={{ duration: 0.15 }}
									className="group grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 rounded-lg px-3 py-2.5 hover:bg-neutral-50 transition-colors"
								>
									<div className="flex h-7 w-7 items-center justify-center rounded-lg bg-neutral-100">
										<BookOpen className="h-3.5 w-3.5 text-neutral-500" />
									</div>
									<div className="min-w-0">
										<p className="truncate text-xs font-medium text-neutral-800">
											{doc.filename}
										</p>
										<p className="text-xs text-neutral-400">
											{doc.page_count} page
											{doc.page_count !== 1 ? "s" : ""}
										</p>
									</div>
									<div className="relative">
										<button
											type="button"
											onClick={(e) => {
												e.stopPropagation();
												setOpenMenuId(openMenuId === doc.id ? null : doc.id);
											}}
											className="rounded p-1 text-neutral-300 opacity-0 transition-all hover:bg-neutral-100 hover:text-neutral-600 group-hover:opacity-100"
										>
											<MoreHorizontal className="h-3.5 w-3.5" />
										</button>
										{openMenuId === doc.id && (
											<div className="absolute right-0 top-full z-50 mt-1 min-w-[148px] rounded-lg border border-neutral-200 bg-white py-1 shadow-lg">
												<button
													type="button"
													onClick={() => {
														setPreviewDoc(doc);
														setOpenMenuId(null);
													}}
													className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-neutral-700 hover:bg-neutral-50"
												>
													<Eye className="h-3.5 w-3.5" />
													View
												</button>
												<button
													type="button"
													onClick={() => {
														onCreateChat(doc.id);
														setOpenMenuId(null);
													}}
													className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-neutral-700 hover:bg-neutral-50"
												>
													<MessageSquarePlus className="h-3.5 w-3.5" />
													Create chat
												</button>
												<div className="my-1 border-t border-neutral-100" />
												<button
													type="button"
													onClick={() => {
														onDelete(doc.id);
														setOpenMenuId(null);
													}}
													className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-red-500 hover:bg-red-50"
												>
													<Trash2 className="h-3.5 w-3.5" />
													Delete
												</button>
											</div>
										)}
									</div>
								</motion.div>
							))}
						</AnimatePresence>
					</div>
				</ScrollArea>
			</div>
		</>
	);
}
