import { useState } from "react";
import * as api from "../lib/api";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";

interface ShareDialogProps {
	conversationId: string;
	isShared: boolean;
	shareToken: string | null;
	onClose: () => void;
	onShareChange: () => void;
}

export function ShareDialog({
	conversationId,
	isShared: initialShared,
	shareToken: initialToken,
	onClose,
	onShareChange,
}: ShareDialogProps) {
	const [isShared, setIsShared] = useState(initialShared);
	const [shareToken, setShareToken] = useState(initialToken);
	const [loading, setLoading] = useState(false);
	const [copying, setCopying] = useState(false);

	const shareUrl = shareToken
		? `${window.location.origin}/shared/${shareToken}`
		: null;

	async function handleEnable() {
		setLoading(true);
		try {
			const result = await api.shareConversation(conversationId);
			setIsShared(result.is_shared);
			setShareToken(result.share_token);
		} finally {
			setLoading(false);
		}
	}

	async function handleDisable() {
		setLoading(true);
		try {
			await api.unshareConversation(conversationId);
			setIsShared(false);
			onShareChange();
		} finally {
			setLoading(false);
		}
	}

	function handleCopy() {
		if (!shareUrl) return;
		navigator.clipboard.writeText(shareUrl);
		setCopying(true);
		setTimeout(() => setCopying(false), 2000);
	}

	return (
		<Dialog open onOpenChange={(open) => !open && onClose()}>
			<DialogContent className="max-w-sm">
				<DialogHeader>
					<DialogTitle>Share conversation</DialogTitle>
				</DialogHeader>

				{!isShared ? (
					<div className="space-y-3">
						<p className="text-sm text-neutral-500">
							Create a read-only link that anyone can view.
						</p>
						<Button
							onClick={handleEnable}
							disabled={loading}
							className="w-full"
						>
							{loading ? "Creating link…" : "Create share link"}
						</Button>
					</div>
				) : (
					<div className="space-y-3">
						<p className="text-sm text-neutral-500">
							Anyone with this link can view this conversation (read-only).
						</p>
						<div className="flex gap-2">
							<input
								readOnly
								value={shareUrl ?? ""}
								className="min-w-0 flex-1 truncate rounded-md border border-neutral-200 px-3 py-2 text-xs text-neutral-600 outline-none"
							/>
							<Button size="sm" onClick={handleCopy}>
								{copying ? "Copied!" : "Copy"}
							</Button>
						</div>
						<Button
							variant="ghost"
							size="sm"
							onClick={handleDisable}
							disabled={loading}
							className="w-full text-red-600 hover:bg-red-50 hover:text-red-600"
						>
							{loading ? "Disabling…" : "Disable sharing"}
						</Button>
					</div>
				)}
			</DialogContent>
		</Dialog>
	);
}
