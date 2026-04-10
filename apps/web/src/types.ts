export interface Todo {
	todoID: string;
	title: string;
	description: string;
	dateDue: string;
	dateCreated: string;
	completed: boolean;
	notes?: string;
}

export interface TodoFile {
	fileID: string;
	todoID: string;
	fileName: string;
	filePath: string;
}

export interface Chatmessage {
	action: string;
	userID: string;
	humain: string;
}

export interface TodosResponse {
	todos: Todo[];
}

export interface FilesResponse {
	files: TodoFile[];
}