import { BookOpen, Upload } from "lucide-react";
import { useState } from "react";
import type { UploadedDocument } from "../types";
import { DocumentUpload } from "./DocumentUpload";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

interface DocumentSourceDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	uploading: boolean;
	libraryDocuments: UploadedDocument[];
	onUpload: (files: File[]) => void;
	onAttachFromLibrary: (documentId: string) => void;
}

export function DocumentSourceDialog({
	open,
	onOpenChange,
	uploading,
	libraryDocuments,
	onUpload,
	onAttachFromLibrary,
}: DocumentSourceDialogProps) {
	const [tab, setTab] = useState<"upload" | "library">("upload");

	const handleUpload = (files: File[]) => {
		onUpload(files);
		onOpenChange(false);
	};

	const handleAttach = (id: string) => {
		onAttachFromLibrary(id);
		onOpenChange(false);
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-md">
				<DialogHeader>
					<DialogTitle>Add document</DialogTitle>
				</DialogHeader>

				<div className="flex gap-1 rounded-lg bg-neutral-100 p-1">
					<button
						type="button"
						onClick={() => setTab("upload")}
						className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
							tab === "upload"
								? "bg-white text-neutral-900 shadow-sm"
								: "text-neutral-500 hover:text-neutral-700"
						}`}
					>
						<Upload className="h-3.5 w-3.5" />
						Upload
					</button>
					<button
						type="button"
						onClick={() => setTab("library")}
						className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
							tab === "library"
								? "bg-white text-neutral-900 shadow-sm"
								: "text-neutral-500 hover:text-neutral-700"
						}`}
					>
						<BookOpen className="h-3.5 w-3.5" />
						Library
						{libraryDocuments.length > 0 && (
							<span className="ml-1 rounded-full bg-neutral-200 px-1.5 py-0.5 text-xs leading-none text-neutral-600">
								{libraryDocuments.length}
							</span>
						)}
					</button>
				</div>

				{tab === "upload" && (
					<DocumentUpload onUpload={handleUpload} uploading={uploading} />
				)}

				{tab === "library" && (
					<div className="min-h-[120px]">
						{libraryDocuments.length === 0 ? (
							<div className="flex flex-col items-center justify-center py-10 text-center">
								<BookOpen className="mb-3 h-8 w-8 text-neutral-300" />
								<p className="text-sm text-neutral-500">
									No documents in library yet
								</p>
								<p className="mt-1 text-xs text-neutral-400">
									Upload a document to add it to your library
								</p>
							</div>
						) : (
							<ul className="space-y-1">
								{libraryDocuments.map((doc) => (
									<li key={doc.id}>
										<button
											type="button"
											onClick={() => handleAttach(doc.id)}
											className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-neutral-50"
										>
											<div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-neutral-100">
												<BookOpen className="h-4 w-4 text-neutral-500" />
											</div>
											<div className="min-w-0 flex-1">
												<p className="truncate text-sm font-medium text-neutral-800">
													{doc.filename}
												</p>
												<p className="text-xs text-neutral-400">
													{doc.page_count} page
													{doc.page_count !== 1 ? "s" : ""} &middot;{" "}
													{(doc.file_size / 1024).toFixed(0)} KB
												</p>
											</div>
										</button>
									</li>
								))}
							</ul>
						)}
					</div>
				)}
			</DialogContent>
		</Dialog>
	);
}
