import type {
	Conversation,
	ConversationDetail,
	Message,
	UploadedDocument,
} from "../types";

const BASE = "/api";

async function handleResponse<T>(response: Response): Promise<T> {
	if (!response.ok) {
		const text = await response.text().catch(() => "Unknown error");
		throw new Error(`API error ${response.status}: ${text}`);
	}
	return response.json() as Promise<T>;
}

async function handleEmptyResponse(response: Response): Promise<void> {
	if (!response.ok) {
		const text = await response.text().catch(() => "Unknown error");
		throw new Error(`API error ${response.status}: ${text}`);
	}
}

export async function fetchConversations(): Promise<Conversation[]> {
	const res = await fetch(`${BASE}/conversations`);
	return handleResponse<Conversation[]>(res);
}

export async function createConversation(): Promise<Conversation> {
	const res = await fetch(`${BASE}/conversations`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ title: "New conversation" }),
	});
	return handleResponse<Conversation>(res);
}

export async function deleteConversation(id: string): Promise<void> {
	const res = await fetch(`${BASE}/conversations/${id}`, {
		method: "DELETE",
	});
	await handleEmptyResponse(res);
}

export async function fetchConversation(
	id: string,
): Promise<ConversationDetail> {
	const res = await fetch(`${BASE}/conversations/${id}`);
	return handleResponse<ConversationDetail>(res);
}

export async function fetchMessages(
	conversationId: string,
): Promise<Message[]> {
	const res = await fetch(`${BASE}/conversations/${conversationId}/messages`);
	return handleResponse<Message[]>(res);
}

export async function sendMessage(
	conversationId: string,
	content: string,
): Promise<Response> {
	const res = await fetch(`${BASE}/conversations/${conversationId}/messages`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ content }),
	});
	if (!res.ok) {
		const text = await res.text().catch(() => "Unknown error");
		throw new Error(`API error ${res.status}: ${text}`);
	}
	return res;
}

export async function uploadDocument(
	conversationId: string,
	file: File,
): Promise<UploadedDocument> {
	const formData = new FormData();
	formData.append("file", file);
	const res = await fetch(`${BASE}/conversations/${conversationId}/documents`, {
		method: "POST",
		body: formData,
	});
	return handleResponse<UploadedDocument>(res);
}

export async function attachFromLibrary(
	conversationId: string,
	documentId: string,
): Promise<UploadedDocument> {
	const res = await fetch(
		`${BASE}/conversations/${conversationId}/documents/from-library`,
		{
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ document_id: documentId }),
		},
	);
	return handleResponse<UploadedDocument>(res);
}

export async function fetchLibrary(): Promise<UploadedDocument[]> {
	const res = await fetch(`${BASE}/storage`);
	return handleResponse<UploadedDocument[]>(res);
}

export async function uploadToLibrary(file: File): Promise<UploadedDocument> {
	const formData = new FormData();
	formData.append("file", file);
	const res = await fetch(`${BASE}/storage`, {
		method: "POST",
		body: formData,
	});
	return handleResponse<UploadedDocument>(res);
}

export async function deleteDocument(id: string): Promise<void> {
	const res = await fetch(`${BASE}/documents/${id}`, {
		method: "DELETE",
	});
	await handleEmptyResponse(res);
}

export function getDocumentUrl(documentId: string): string {
	return `${BASE}/documents/${documentId}/content`;
}
