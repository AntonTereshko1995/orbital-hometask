export interface Conversation {
	id: string;
	title: string;
	created_at: string;
	updated_at: string;
	has_document: boolean;
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
	conversation_id: string;
	filename: string;
	page_count: number;
	created_at: string;
}

export interface ConversationDetail extends Conversation {
	documents: UploadedDocument[];
}
