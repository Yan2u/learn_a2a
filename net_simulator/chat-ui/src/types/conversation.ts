// src/types/conversation.ts

/**
 * @description 消息发送者的角色类型。
 * 你的后端可能返回更多类型，但我们在类型定义中全部列出以保持严谨。
 */
export type MessageRole = 'user' | 'assistant' | 'system' | 'tool';

/**
 * @description 多模态消息中的文本部分。
 */
export interface TextContentPart {
    type: 'text';
    text: string;
}

/**
 * @description 多模态消息中的图像部分。
 * 我们存储图像的URL，这个URL可能是上传后后端返回的地址，或者是本地的Blob URL。
 */
export interface ImageContentPart {
    type: 'image';
    imageUrl: string;
}

/**
 * @description 多模态消息中的音频部分。
 * 我们存储音频的URL和相关元数据。
 */
export interface AudioContentPart {
    type: 'audio';
    audioUrl: string;
    mediaType: string; // 例如 'audio/wav', 'audio/mp3'
    duration?: number; // 音频时长（秒）
    fileName?: string; // 原始文件名
}

/**
 * @description 一条完整的对话消息。
 * content 设计为数组是为了支持图文混排等多模态输入。
 */
export interface ChatMessage {
    id: string; // 每条消息的唯一ID，用于React的key
    role: MessageRole;
    content: (TextContentPart | ImageContentPart | AudioContentPart)[];
    annotations?: string[]; // 可选的标注信息，如 "创建了任务T-101"
}

/**
 * @description 代表一个完整的对话会话。
 */
export interface ConversationSession {
    id: string; // 会话的唯一ID
    title: string; // 会话的标题，用于在侧边栏显示
    messages: ChatMessage[];
}