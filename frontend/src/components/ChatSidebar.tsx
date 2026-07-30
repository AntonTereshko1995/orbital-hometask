import { AnimatePresence, motion } from "framer-motion";
import {
	BookOpen,
	Link,
	MessageSquarePlus,
	MoreHorizontal,
	Pencil,
	Pin,
	PinOff,
	Share2,
	Trash2,
} from "lucide-react";
import { useState } from "react";
import { relativeTime } from "../lib/utils";
import type { Conversation } from "../types";
import { ShareDialog } from "./ShareDialog";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { ScrollArea } from "./ui/scroll-area";

interface ChatSidebarProps {
	conversations: Conversation[];
	selectedId: string | null;
	loading: boolean;
	libraryOpen: boolean;
	onSelect: (id: string) => void;
	onCreate: () => void;
	onDelete: (id: string) => void;
	onRename: (id: string, title: string) => void;
	onPin: (id: string) => void;
	onToggleLibrary: () => void;
	onShareChange: () => void;
}

export function ChatSidebar({
	conversations,
	selectedId,
	loading,
	libraryOpen,
	onSelect,
	onCreate,
	onDelete,
	onRename,
	onPin,
	onToggleLibrary,
	onShareChange,
}: ChatSidebarProps) {
	const [hoveredId, setHoveredId] = useState<string | null>(null);
	const [openMenuId, setOpenMenuId] = useState<string | null>(null);
	const [renamingId, setRenamingId] = useState<string | null>(null);
	const [renameValue, setRenameValue] = useState("");
	const [shareDialogConvId, setShareDialogConvId] = useState<string | null>(
		null,
	);

	const pinned = conversations.filter((c) => c.is_pinned);
	const unpinned = conversations.filter((c) => !c.is_pinned);
	const hasPinned = pinned.length > 0;

	function handleRenameSubmit() {
		if (!renamingId || !renameValue.trim()) return;
		onRename(renamingId, renameValue.trim());
		setRenamingId(null);
	}

	function renderConversation(conversation: Conversation) {
		return (
			<motion.div
				key={conversation.id}
				initial={{ opacity: 0, height: 0 }}
				animate={{ opacity: 1, height: "auto" }}
				exit={{ opacity: 0, height: 0 }}
				transition={{ duration: 0.15 }}
			>
				<button
					type="button"
					className={`group grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-lg px-3 py-2.5 text-left transition-colors ${
						selectedId === conversation.id
							? "bg-neutral-100"
							: "hover:bg-neutral-50"
					}`}
					onClick={() => onSelect(conversation.id)}
					onMouseEnter={() => setHoveredId(conversation.id)}
					onMouseLeave={() => setHoveredId(null)}
				>
					<div className="min-w-0 overflow-hidden">
						<div className="flex items-center gap-1">
							{conversation.is_pinned && (
								<Pin className="h-3 w-3 flex-shrink-0 text-blue-500" />
							)}
							{conversation.is_shared && (
								<Link className="h-3 w-3 flex-shrink-0 text-green-500" />
							)}
							<p className="truncate text-sm font-medium text-neutral-800">
								{conversation.title}
							</p>
						</div>
						<p className="mt-0.5 truncate text-xs text-neutral-400">
							{relativeTime(conversation.updated_at)}
						</p>
					</div>

					<div className="w-6 flex-shrink-0">
						{/* Always mounted — conditional unmounting breaks Radix focus-return */}
						<DropdownMenu
							onOpenChange={(open) =>
								setOpenMenuId(open ? conversation.id : null)
							}
						>
							<DropdownMenuTrigger asChild>
								<button
									type="button"
									className={`rounded p-1 text-neutral-400 hover:bg-neutral-200 hover:text-neutral-600 transition-opacity ${
										hoveredId === conversation.id ||
										openMenuId === conversation.id
											? "opacity-100"
											: "pointer-events-none opacity-0"
									}`}
									onClick={(e) => e.stopPropagation()}
									title="More options"
								>
									<MoreHorizontal className="h-3.5 w-3.5" />
								</button>
							</DropdownMenuTrigger>
							<DropdownMenuContent side="right" align="start">
								<DropdownMenuItem
									onSelect={() => {
										// setTimeout defers dialog open until after DropdownMenu's
										// DismissableLayer has fully processed its close event,
										// preventing the Dialog from closing immediately.
										setTimeout(() => {
											setRenamingId(conversation.id);
											setRenameValue(conversation.title);
										}, 0);
									}}
								>
									<Pencil className="h-3.5 w-3.5" />
									Rename
								</DropdownMenuItem>
								<DropdownMenuItem onSelect={() => onPin(conversation.id)}>
									{conversation.is_pinned ? (
										<PinOff className="h-3.5 w-3.5" />
									) : (
										<Pin className="h-3.5 w-3.5" />
									)}
									{conversation.is_pinned ? "Unpin" : "Pin"}
								</DropdownMenuItem>
								<DropdownMenuItem
									onSelect={() => {
										setTimeout(() => {
											setShareDialogConvId(conversation.id);
										}, 0);
									}}
								>
									<Share2 className="h-3.5 w-3.5" />
									Share
								</DropdownMenuItem>
								<DropdownMenuSeparator />
								<DropdownMenuItem
									destructive
									onSelect={() => onDelete(conversation.id)}
								>
									<Trash2 className="h-3.5 w-3.5" />
									Delete
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
					</div>
				</button>
			</motion.div>
		);
	}

	return (
		<>
			<div className="flex h-full w-[250px] flex-shrink-0 flex-col border-r border-neutral-200 bg-white">
				<div className="flex items-center justify-between border-b border-neutral-100 p-3">
					<span className="text-sm font-semibold text-neutral-700">Chats</span>
					<div className="flex items-center gap-1">
						<Button
							variant="ghost"
							size="icon"
							onClick={onToggleLibrary}
							title="Document library"
							className={libraryOpen ? "bg-neutral-100" : ""}
						>
							<BookOpen className="h-4 w-4" />
						</Button>
						<Button
							variant="ghost"
							size="icon"
							onClick={onCreate}
							title="New chat"
						>
							<MessageSquarePlus className="h-4 w-4" />
						</Button>
					</div>
				</div>

				<ScrollArea className="flex-1">
					<div className="p-2">
						{loading && conversations.length === 0 && (
							<div className="space-y-2 p-2">
								{[1, 2, 3].map((i) => (
									<div key={i} className="animate-pulse space-y-1">
										<div className="h-4 w-3/4 rounded bg-neutral-100" />
										<div className="h-3 w-1/2 rounded bg-neutral-50" />
									</div>
								))}
							</div>
						)}

						{!loading && conversations.length === 0 && (
							<p className="px-2 py-8 text-center text-xs text-neutral-400">
								No conversations yet
							</p>
						)}

						{hasPinned && (
							<>
								<p className="mb-1 px-3 pt-1 text-[10px] font-semibold uppercase tracking-wider text-neutral-400">
									Pinned
								</p>
								<AnimatePresence initial={false}>
									{pinned.map(renderConversation)}
								</AnimatePresence>
								{unpinned.length > 0 && (
									<p className="mb-1 mt-3 px-3 text-[10px] font-semibold uppercase tracking-wider text-neutral-400">
										Recent
									</p>
								)}
							</>
						)}

						<AnimatePresence initial={false}>
							{unpinned.map(renderConversation)}
						</AnimatePresence>
					</div>
				</ScrollArea>
			</div>

			{/* Rename dialog — rendered outside the sidebar to avoid z-index conflicts */}
			<Dialog
				open={renamingId !== null}
				onOpenChange={(open) => !open && setRenamingId(null)}
			>
				<DialogContent className="max-w-sm">
					<DialogHeader>
						<DialogTitle>Rename conversation</DialogTitle>
					</DialogHeader>
					<input
						className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm outline-none focus:border-neutral-400"
						value={renameValue}
						onChange={(e) => setRenameValue(e.target.value)}
						// biome-ignore lint/a11y/noAutofocus: intentional focus for rename dialog
						autoFocus
						onKeyDown={(e) => {
							if (e.key === "Enter") handleRenameSubmit();
							if (e.key === "Escape") setRenamingId(null);
						}}
					/>
					<div className="flex justify-end gap-2">
						<Button
							variant="ghost"
							size="sm"
							onClick={() => setRenamingId(null)}
						>
							Cancel
						</Button>
						<Button
							size="sm"
							disabled={
								!renameValue.trim() ||
								renameValue.trim() ===
									conversations.find((c) => c.id === renamingId)?.title
							}
							onClick={handleRenameSubmit}
						>
							Rename
						</Button>
					</div>
				</DialogContent>
			</Dialog>

			{/* Share dialog — rendered outside the sidebar to avoid z-index conflicts */}
			{shareDialogConvId !== null &&
				(() => {
					const conv = conversations.find((c) => c.id === shareDialogConvId);
					if (!conv) return null;
					return (
						<ShareDialog
							conversationId={conv.id}
							isShared={conv.is_shared}
							shareToken={conv.share_token}
							onClose={() => setShareDialogConvId(null)}
							onShareChange={() => {
								onShareChange();
								setShareDialogConvId(null);
							}}
						/>
					);
				})()}
		</>
	);
}
