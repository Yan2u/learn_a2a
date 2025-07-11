import { Task } from '@a2a-js/sdk'

export interface AgentInteraction {
    dst_id: string;
    message: string;
}

export interface AgentNetNode {
    interactions: AgentInteraction[];
    kind: 'public' | 'user';
    name: string;
    category: string;
}

export interface PublicAgentNode extends AgentNetNode {
    kind: 'public';
    task_count: number;
    url: string;
    lastseen: number;
}

export interface UserAgentNode extends AgentNetNode {
    kind: 'user';
    conversations: Record<string, Record<string, unknown>[]>;
    tasks: Record<string, Task>;
}

export type AgentNetGraphNode = PublicAgentNode | UserAgentNode;