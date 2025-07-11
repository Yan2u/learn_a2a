// src/types/task.ts

/**
 * @description 任务的状态。使用联合类型可以防止出现无效的状态字符串。
 */
export type TaskStatus = 'Pending' | 'In Progress' | 'Completed' | 'Failed';

/**
 * @description 单个任务的数据结构。
 */
export interface Task {
    id: string;
    name: string;
    status: TaskStatus;
}