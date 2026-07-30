export interface Conversation {
	id: string;
	title: string;
	created_at: string;
	updated_at: string;
	has_document: boolean;
	is_pinned: boolean;
	is_shared: boolean;
	share_token: string | null;
}

export interface Message {
	id: string;
	conversation_id: string;
	role: "user" | "assistant" | "system";
	content: string;
	sources_cited: number;
	created_at: string;
}

export interface UploadedDocument {
	id: string;
	filename: string;
	file_size: number;
	page_count: number;
	created_at: string;
	reused_from_library?: boolean;
}

export interface ConversationDetail extends Conversation {
	documents: UploadedDocument[];
}

export interface SharedMessage {
	id: string;
	conversation_id: string;
	role: "user" | "assistant";
	content: string;
	sources_cited: number;
	created_at: string;
}

export interface SharedConversation {
	title: string;
	created_at: string;
	documents: UploadedDocument[];
	messages: SharedMessage[];
}
