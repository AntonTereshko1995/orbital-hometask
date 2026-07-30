import { Viewer } from "@react-pdf-viewer/core";
import "@react-pdf-viewer/core/lib/styles/index.css";
import { defaultLayoutPlugin } from "@react-pdf-viewer/default-layout";
import "@react-pdf-viewer/default-layout/lib/styles/index.css";
import { SpecialZoomLevel } from "@react-pdf-viewer/core";
import { FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { getDocumentUrl } from "../lib/api";
import type { UploadedDocument } from "../types";

interface DocumentViewerProps {
	documents: UploadedDocument[];
}

// PDFView is keyed by document ID so React fully remounts it when switching
// documents, ensuring a fresh plugin instance and clean viewer state.
function PDFView({ pdfUrl }: { pdfUrl: string }) {
	const defaultLayoutPluginInstance = defaultLayoutPlugin();
	return (
		<Viewer
			fileUrl={pdfUrl}
			plugins={[defaultLayoutPluginInstance]}
			defaultScale={SpecialZoomLevel.PageWidth}
		/>
	);
}

interface DocumentTabBarProps {
	documents: UploadedDocument[];
	selectedId: string | null;
	onSelect: (id: string) => void;
}

function DocumentTabBar({
	documents,
	selectedId,
	onSelect,
}: DocumentTabBarProps) {
	return (
		<div className="flex gap-1 overflow-x-auto border-b border-neutral-100 px-2 pt-2 flex-shrink-0 bg-white">
			{documents.map((doc) => {
				const isActive = doc.id === selectedId;
				const displayName =
					doc.filename.length > 28
						? `${doc.filename.slice(0, 28)}…`
						: doc.filename;
				return (
					<button
						key={doc.id}
						type="button"
						className={`whitespace-nowrap rounded-t-md px-3 py-1.5 text-xs flex-shrink-0 transition-colors ${
							isActive
								? "border border-b-white border-neutral-200 bg-white font-medium text-neutral-800"
								: "text-neutral-400 hover:text-neutral-600"
						}`}
						onClick={() => onSelect(doc.id)}
						title={doc.filename}
					>
						{displayName}
					</button>
				);
			})}
		</div>
	);
}

export function DocumentViewer({ documents }: DocumentViewerProps) {
	const [selectedId, setSelectedId] = useState<string | null>(null);

	// Auto-select first document when list changes; clear when list is empty
	useEffect(() => {
		if (documents.length === 0) {
			setSelectedId(null);
			return;
		}
		if (!documents.find((d) => d.id === selectedId)) {
			setSelectedId(documents[0]?.id ?? null);
		}
	}, [documents, selectedId]);

	const selectedDoc =
		documents.find((d) => d.id === selectedId) ?? documents[0] ?? null;

	if (documents.length === 0) {
		return (
			<div className="flex h-full flex-col items-center justify-center bg-neutral-50">
				<FileText className="mb-3 h-10 w-10 text-neutral-300" />
				<p className="text-sm text-neutral-400">No documents uploaded</p>
			</div>
		);
	}

	const pdfUrl = selectedDoc ? getDocumentUrl(selectedDoc.id) : null;

	return (
		<div className="flex h-full flex-col bg-white">
			{/* Tab bar — only shown when there are 2+ documents */}
			{documents.length > 1 && (
				<DocumentTabBar
					documents={documents}
					selectedId={selectedDoc?.id ?? null}
					onSelect={setSelectedId}
				/>
			)}

			{/* Single-document header */}
			{selectedDoc && documents.length === 1 && (
				<div className="flex items-center border-b border-neutral-100 px-4 py-2.5 flex-shrink-0">
					<div className="min-w-0">
						<p className="truncate text-sm font-medium text-neutral-800">
							{selectedDoc.filename}
						</p>
						<p className="text-xs text-neutral-400">
							{selectedDoc.page_count} page
							{selectedDoc.page_count !== 1 ? "s" : ""}
						</p>
					</div>
				</div>
			)}

			{/* PDF Viewer — Worker stays mounted; only PDFView remounts on tab switch */}
			{pdfUrl && selectedDoc && (
				<div className="flex-1 overflow-hidden">
					<PDFView key={selectedDoc.id} pdfUrl={pdfUrl} />
				</div>
			)}
		</div>
	);
}
