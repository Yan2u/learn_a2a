/* eslint-disable @typescript-eslint/no-unused-vars */
import { useParams } from 'react-router-dom';
import { mockConversations } from '@/lib/mock-data';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Paperclip, Send } from 'lucide-react';
import { ChatMessage } from '@/types';
import { Skeleton } from '@/components/ui/skeleton';
import { useUser } from '@/contexts';
import { useEffect, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid'; // 用于生成唯一的消息ID
import axios from 'axios';
import { config } from '@/config';

import userSvg from "@/assets/user.svg"
import servantSvg from "@/assets/servant.svg";
import { toast } from 'sonner';
import Markdown from 'react-markdown';
import { useInterval } from 'ahooks';

// 加载动画组件
function AssistantLoading({ annotation }: { annotation?: string }) {
    if (!annotation) {
        annotation = 'Loading...';
    }
    return (
        <div className="flex flex-col items-start space-x-2 space-y-2 py-4">
            <div className="flex items-center space-x-3">
                <Avatar className="h-8 w-8">
                    <AvatarImage src={servantSvg} />
                    <AvatarFallback>A</AvatarFallback>
                </Avatar>
                <div className="flex flex-col">
                    <span className="font-semibold">Assistant</span>
                    <span className="text-xs text-muted-foreground">
                        {annotation}
                    </span>
                </div>
            </div>
            <Skeleton className="h-4 w-48 rounded-lg" />
            <Skeleton className="h-4 w-48 rounded-lg" />
            <Skeleton className="h-4 w-48 rounded-lg" />
        </div>
    )
}

// 单条消息的渲染组件
function Message({ msg }: { msg: ChatMessage }) {
    const isUser = msg.role === 'user';

    // 只渲染 user 和 assistant 的消息
    if (msg.role !== 'user' && msg.role !== 'assistant') {
        return null;
    }

    // 简化布局，根据 isUser 决定左右对齐
    const alignment = isUser ? 'items-end' : 'items-start';
    const name = isUser ? 'User' : 'Assistant';
    const avatarSrc = isUser ? userSvg : servantSvg; // 假设你有头像图片

    return (
        <div className={`flex flex-col space-y-2 py-4 ${alignment}`}>
            <div className="flex items-center space-x-3">
                <Avatar className="h-8 w-8">
                    <AvatarImage src={avatarSrc} />
                    <AvatarFallback>{name.charAt(0)}</AvatarFallback>
                </Avatar>
                <div className="flex flex-col">
                    <span className="font-semibold">{name}</span>
                    {msg.annotations && (
                        <span className="text-xs text-muted-foreground">
                            {msg.annotations.join(', ')}
                        </span>
                    )}
                </div>
            </div>
            <div className="max-w-prose rounded-lg bg-muted p-3 text-base whitespace-normal break-words">
                <Markdown>
                    {msg.content.map((part, index) => part.type === 'text' ? part.text?.trim() : null).join('\n')}
                </Markdown>
            </div>
        </div>
    )
}

export function ConversationPage() {
    const { conversationId } = useParams<{ conversationId: string }>();
    const { userId, userData, addMessage } = useUser();

    const [input, setInput] = useState('');
    const [isReplying, setIsReplying] = useState(false);

    const [enableLoadingAnnotation, setEnableLoadingAnnotation] = useState(false);
    const [loadingAnnotation, setLoadingAnnotation] = useState<string | null>(null);

    const scrollViewportRef = useRef<HTMLDivElement>(null);

    const conversation = userData?.conversations.find(c => c.id === conversationId);

    // 自动滚动到底部的函数
    const scrollToBottom = () => {
        if (scrollViewportRef.current) {
            const contentDiv = scrollViewportRef.current;
            // 查找 ScrollArea 的 viewport 元素
            const viewport = contentDiv.closest('[data-radix-scroll-area-viewport]') as HTMLElement;

            if (viewport) {
                // 使用 requestAnimationFrame 确保 DOM 更新完成后再滚动
                requestAnimationFrame(() => {
                    viewport.scrollTop = viewport.scrollHeight;
                });
            } else {
                // 如果找不到 viewport，直接在当前元素的父容器中滚动
                const parent = contentDiv.parentElement;
                if (parent) {
                    requestAnimationFrame(() => {
                        parent.scrollTop = parent.scrollHeight;
                    });
                }
            }
        }
    };

    useInterval(() => {
        if (!enableLoadingAnnotation || !(conversation?.messages?.length > 0)) {
            setLoadingAnnotation(null);
            return;
        }

        axios.get(`http://localhost:${config.userServer.port}/interactions/user/${userId}`, { timeout: 250 })
            .then(response => {
                if (response.status === 200 && response.data.status === 'success') {
                    const names = response.data.content.map(([, y]) => y);
                    if (names.length > 0) {
                        setLoadingAnnotation(`Calling ${names.join(', ')}`);
                    } else {
                        setLoadingAnnotation(null);
                    }
                } else {
                    setLoadingAnnotation(null);
                }
            }).catch(() => { setLoadingAnnotation(null); });

    }, 500)

    const handleSendMessage = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || !conversationId) return;

        // 1. 创建并添加用户消息
        const userMessage: ChatMessage = {
            id: uuidv4(),
            role: 'user',
            content: [{ type: 'text', text: input }],
            annotations: [userId]
        };
        addMessage(conversationId, userMessage);
        const userInput = input; // 保存用户输入用于回复
        setInput(''); // 清空输入框


        // 2. 显示加载动画并等待
        setIsReplying(true);
        setEnableLoadingAnnotation(true);

        scrollToBottom();
        let success = true;
        // await new Promise(resolve => setTimeout(resolve, 2000));
        try {
            const userServerUrl = `http://localhost:${config.userServer.port}`;
            const data = {
                user_id: userId,
                conversation_id: conversationId,
                message: input,
            }

            const response = await axios.post(`${userServerUrl}/user/chat`, data, { timeout: 1800000 });

            if (response.status !== 200) {
                toast.error(`Failed to send message: ${response.status} - ${response.statusText}`);
                success = false;
            } else {
                const responseJson = response.data;
                if (responseJson.status === 'error') {
                    console.error("Error response from server:", responseJson);
                    toast.error(`Failed to send message: ${responseJson.message}`);
                    success = false;
                } else {
                    const message = responseJson.content;
                    const assistantMessage: ChatMessage = {
                        id: uuidv4(),
                        role: 'assistant',
                        content: [{ type: 'text', text: message }],
                    };
                    addMessage(conversationId, assistantMessage);
                    // 收到回复后滚动到底部
                    scrollToBottom();
                }
            }
        } catch (error) {
            console.error("Error sending message:", error);
            toast.error(`Failed to send message: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }

        setIsReplying(false); // 隐藏加载动画
        setEnableLoadingAnnotation(false);
    };

    if (!conversation) {
        return <div className="p-16">Select a conversation to start.</div>;
    }

    return (
        <div className="flex h-full flex-col">
            <ScrollArea className="flex-1 p-4 h-100 ">
                <div
                    ref={scrollViewportRef}
                    className="p-4"
                >
                    {conversation.messages.map((msg) => <Message key={msg.id} msg={msg} />)}
                    {isReplying && <AssistantLoading annotation={loadingAnnotation} />} {/* <-- 显示加载动画 */}
                </div>
            </ScrollArea>
            <form onSubmit={handleSendMessage} className="border-t p-4"> {/* <-- 使用 form 标签 */}
                <div className="relative">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Type your message..."
                        className="pr-20 resize-none block w-full rounded-md border bg-transparent px-3 py-2 text-base shadow-xs transition-[color,box-shadow] outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] min-h-[40px] max-h-40 disabled:opacity-50"
                        disabled={isReplying}
                        rows={2}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !(e.ctrlKey || e.metaKey)) {
                                // 普通回车插入换行
                                e.stopPropagation();
                                return;
                            }
                            if ((e.key === 'Enter' && (e.ctrlKey || e.metaKey))) {
                                // Ctrl+Enter 或 Cmd+Enter 发送
                                e.preventDefault();
                                const form = e.currentTarget.form;
                                if (form) {
                                    form.requestSubmit();
                                }
                            }
                        }}
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex space-x-1">
                        <Button type="button" variant="ghost" size="icon" disabled={isReplying}>
                            <Paperclip className="h-4 w-4" />
                        </Button>
                        <Button type="submit" size="icon" disabled={isReplying || !input.trim()}>
                            <Send className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </form>
        </div>
    );
}