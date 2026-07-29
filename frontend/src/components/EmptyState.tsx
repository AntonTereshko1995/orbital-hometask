import { BookOpen, FileSearch } from "lucide-react";
import { useState } from "react";
import type { UploadedDocument } from "../types";
import { DocumentSourceDialog } from "./DocumentSourceDialog";
import { Button } from "./ui/button";

interface EmptyStateProps {
	onUpload: (files: File[]) => void;
	onAttachFromLibrary: (documentId: string) => void;
	libraryDocuments: UploadedDocument[];
	uploading?: boolean;
}

export function EmptyState({
	onUpload,
	onAttachFromLibrary,
	libraryDocuments,
	uploading,
}: EmptyStateProps) {
	const [dialogOpen, setDialogOpen] = useState(false);

	return (
		<div className="flex flex-col items-center px-4">
			<DocumentSourceDialog
				open={dialogOpen}
				onOpenChange={setDialogOpen}
				uploading={uploading ?? false}
				libraryDocuments={libraryDocuments}
				onUpload={onUpload}
				onAttachFromLibrary={onAttachFromLibrary}
			/>

			<div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-neutral-900">
				<FileSearch className="h-7 w-7 text-white" />
			</div>
			<h2 className="mb-2 text-lg font-semibold text-neutral-800">
				Upload documents to get started
			</h2>
			<p className="mb-8 max-w-sm text-center text-sm text-neutral-500">
				Ask questions about leases, title reports, contracts, and other legal
				documents
			</p>
			<Button
				onClick={() => setDialogOpen(true)}
				className="flex items-center gap-2"
			>
				<BookOpen className="h-4 w-4" />
				Add document
			</Button>
		</div>
	);
}
