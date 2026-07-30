import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { Conversation } from "../types";

function sortConversations(list: Conversation[]): Conversation[] {
	return [...list].sort((a, b) => {
		if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
		return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
	});
}

export function useConversations() {
	const [conversations, setConversations] = useState<Conversation[]>([]);
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const refresh = useCallback(async () => {
		try {
			setError(null);
			const data = await api.fetchConversations();
			setConversations(data);
		} catch (err) {
			setError(
				err instanceof Error ? err.message : "Failed to load conversations",
			);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		refresh();
	}, [refresh]);

	const create = useCallback(async () => {
		try {
			setError(null);
			const conversation = await api.createConversation();
			setConversations((prev) => sortConversations([conversation, ...prev]));
			setSelectedId(conversation.id);
			return conversation;
		} catch (err) {
			setError(
				err instanceof Error ? err.message : "Failed to create conversation",
			);
			return null;
		}
	}, []);

	const createQuiet = useCallback(async () => {
		try {
			setError(null);
			const conversation = await api.createConversation();
			setConversations((prev) => sortConversations([conversation, ...prev]));
			return conversation;
		} catch (err) {
			setError(
				err instanceof Error ? err.message : "Failed to create conversation",
			);
			return null;
		}
	}, []);

	const select = useCallback((id: string | null) => {
		setSelectedId(id);
	}, []);

	const remove = useCallback(
		async (id: string) => {
			try {
				setError(null);
				await api.deleteConversation(id);
				setConversations((prev) => prev.filter((c) => c.id !== id));
				if (selectedId === id) {
					setSelectedId(null);
				}
			} catch (err) {
				setError(
					err instanceof Error ? err.message : "Failed to delete conversation",
				);
			}
		},
		[selectedId],
	);

	const rename = useCallback(
		async (id: string, title: string) => {
			setConversations((prev) =>
				prev.map((c) => (c.id === id ? { ...c, title } : c)),
			);
			try {
				await api.updateConversation(id, { title });
			} catch (err) {
				setError(err instanceof Error ? err.message : "Failed to rename");
				refresh();
			}
		},
		[refresh],
	);

	const togglePin = useCallback(
		async (id: string) => {
			setConversations((prev) => {
				const updated = prev.map((c) =>
					c.id === id ? { ...c, is_pinned: !c.is_pinned } : c,
				);
				return sortConversations(updated);
			});
			const conv = conversations.find((c) => c.id === id);
			if (!conv) return;
			try {
				await api.updateConversation(id, { is_pinned: !conv.is_pinned });
			} catch (err) {
				setError(err instanceof Error ? err.message : "Failed to pin");
				refresh();
			}
		},
		[conversations, refresh],
	);

	const selected = conversations.find((c) => c.id === selectedId) ?? null;

	return {
		conversations,
		selected,
		selectedId,
		loading,
		error,
		create,
		createQuiet,
		select,
		remove,
		rename,
		togglePin,
		refresh,
	};
}
