import { config } from './config'; 
import { Todo, TodosResponse } from "./types";

function getAuthHeader(): string {                                                                                                                                                                  
    const sessionTokens = JSON.parse(localStorage.getItem('sessionTokens')!);                                                                                                                       
    return sessionTokens.IdToken.jwtToken;                                                                                                                                                          
}

                                                                                                                                                                                                      
async function apiFetch<T>(url: string, options: RequestInit = {}): Promise<T | null> {                                                                                                             
    try {                                                                                                                                                                                           
        const res = await fetch(url, {                                                                                                                                                              
            ...options,                                                                                                                                                                             
            headers: {                                                                                                                                                                            
                'Authorization': getAuthHeader(),
                ...options.headers                                                                                                                                                                  
            }
        });                                                                                                                                                                                         
                                                                                                                                                                                                
        if (res.status === 401) {
            window.location.href = './index.html';
            return null;                                                                                                                                                                            
        }
                                                                                                                                                                                                    
        return res.json() as Promise<T>;                                                                                                                                                          
    } catch (err) {
        console.error('API call failed:', err);
        return null;                                                                                                                                                                                
    }
}

export async function getTodos(callback: (todos: Todo[]) => void): Promise<void> {                                                                                                                  
    const userID = localStorage.getItem('userID');                                                                                                                                                  
    const url = `${config.todoApiEndpoint}${userID}/todos`;                                                                                                                                         
                                                                                                                                                                                                    
    const data = await apiFetch<TodosResponse>(url);                                                                                                                                                
    if (data) {                                                                                                                                                                                     
        console.log('successfully loaded todos for ', userID);                                                                                                                                   
        callback(data.todos);                                                                                                                                                                       
    }
}

export async function getTodo(todoID: string, callback: (todo: Todo) => void): Promise<void> {
    const userID = localStorage.getItem('userID');                                                                                                                                                  
    const url = `${config.todoApiEndpoint}${userID}/todos/${todoID}`;  

    const data = await apiFetch<Todo>(url);
    if (data) {                                                                                                                                                                                     
        console.log('successfully loaded todo:', todoID);                                                                                                                                   
        callback(data);                                                                                                                                                                       
    }
}

export async function addTodo(dateDue: string, title: string, description: string): Promise<void> {
    const userID = localStorage.getItem('userID');                                                                                                                                                  
    const url = `${config.todoApiEndpoint}${userID}/todos/add`;
    
    const todo = {
        title,                                                                                                                                                                                      
        description,                                                                                                                                                                              
        dateDue,
    };

    const options = {
        headers: { 'Content-Type': 'application/json' },
        method: 'POST',
        body: JSON.stringify(todo)
    }

    const data = await apiFetch<void>(url, options);
    if (data !== null) {
        window.location.reload();
    }
}

export async function completeTodo(todoID: string): Promise<void> {
    const userID = localStorage.getItem('userID');                                                                                                                                                  
    const url = `${config.todoApiEndpoint}${userID}/todos/${todoID}/complete`;

    await apiFetch<void>(url);
}

export async function deleteTodo(todoID: string): Promise<void> {
    const userID = localStorage.getItem('userID');                                                                                                                                                  
    const url = `${config.todoApiEndpoint}${userID}/todos/${todoID}/delete`;

    await apiFetch<void>(url);
    window.location.reload();
    
}

export async function addTodoNotes(todoID: string, notes: string): Promise<void> {
    const userID = localStorage.getItem('userID');                                                                                                                                                  
    const url = `${config.todoApiEndpoint}${userID}/todos/${todoID}/addnotes`;

    const payload = { notes };

    const options = {
        headers: { 'Content-Type': 'application/json' },
        method: 'POST',
        body: JSON.stringify(payload)
    }

    await apiFetch<void>(url, options);
    
}
