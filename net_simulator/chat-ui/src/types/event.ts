// src/types/event.ts

/**
 * @description 单个事件的数据结构。
 * 我在你的基础上增加了一些常用字段，让它更具实用性。
 */
export interface AppEvent {
    id: string; // 事件的唯一ID
    type: string; // 事件类型，如 "TaskCreated", "AgentCalled"
    timestamp: string; // 事件发生的时间戳 (ISO 8601 格式字符串)
    description: string; // 对事件的详细描述
}