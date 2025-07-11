// src/types/user.ts

import { ChatMessage, ConversationSession } from "./conversation";
import { AppEvent } from "./event";
import { Task } from "./task";

/**
 * @description 后端 /login 或 /register 接口成功后的响应体。
 * @property {string} userId - 从服务器获得的唯一用户ID。
 */
export interface LoginResponse {
    userId: string;
}

// 单个用户的所有数据
export interface UserData {
    conversations: ConversationSession[];
    tasks: Task[];
    events: AppEvent[];
    name: string | null;
}

// Context 要提供的值的类型
export interface UserContextType {
    userId: string | null;
    userData: UserData | null;
    login: (id: string, name: string | null) => void;
    logout: () => void;
    addMessage: (conversationId: string, message: ChatMessage) => void;
    addConversation: (name: string) => void;
}