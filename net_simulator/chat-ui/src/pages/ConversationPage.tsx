/* eslint-disable @typescript-eslint/no-unused-vars */
import { useParams } from 'react-router-dom';
import { mockConversations } from '@/lib/mock-data';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Paperclip, Send, X, Play, Pause, FileAudio } from 'lucide-react';
import { ChatMessage, TextContentPart, ImageContentPart, AudioContentPart } from '@/types';
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

// 获取音频时长的工具函数
const getAudioDuration = (file: File): Promise<number> => {
    return new Promise((resolve) => {
        const audio = new Audio();
        audio.onloadedmetadata = () => {
            resolve(audio.duration);
        };
        audio.onerror = () => {
            resolve(0); // 如果无法获取时长，返回0
        };
        audio.src = URL.createObjectURL(file);
    });
};

// 格式化时长显示
const formatDuration = (seconds: number): string => {
    if (seconds === 0) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

// 音频卡片组件
function AudioCard({ audio }: { audio: AudioContentPart }) {
    const [isPlaying, setIsPlaying] = useState(false);
    const audioRef = useRef<HTMLAudioElement>(null);

    const togglePlay = () => {
        if (audioRef.current) {
            if (isPlaying) {
                audioRef.current.pause();
            } else {
                audioRef.current.play();
            }
            setIsPlaying(!isPlaying);
        }
    };

    const handleEnded = () => {
        setIsPlaying(false);
    };

    return (
        <div className="flex items-center gap-3 p-3 rounded-lg border bg-muted max-w-xs">
            <button
                onClick={togglePlay}
                className="flex-shrink-0 w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 transition-colors"
            >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <FileAudio className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    <span className="text-sm font-medium truncate">
                        {audio.fileName || 'Audio'}
                    </span>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                    {formatDuration(audio.duration || 0)} • {audio.mediaType.split('/')[1]?.toUpperCase()}
                </div>
            </div>
            <audio
                ref={audioRef}
                src={audio.audioUrl}
                onEnded={handleEnded}
                className="hidden"
            />
        </div>
    );
}

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

    // 分离文本、图片和音频内容
    const textContent = msg.content.filter(part => part.type === 'text') as TextContentPart[];
    const imageContent = msg.content.filter(part => part.type === 'image') as ImageContentPart[];
    const audioContent = msg.content.filter(part => part.type === 'audio') as AudioContentPart[];

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
            {/* 渲染图片内容 */}
            {imageContent.length > 0 && (
                <div className="flex flex-wrap gap-2 max-w-prose">
                    {imageContent.map((img, index) => (
                        <img
                            key={index}
                            src={img.imageUrl}
                            alt={`Image ${index + 1}`}
                            className="max-w-xs max-h-48 rounded-lg object-cover border"
                        />
                    ))}
                </div>
            )}

            {/* 渲染音频内容 */}
            {audioContent.length > 0 && (
                <div className="flex flex-col gap-2 max-w-prose">
                    {audioContent.map((audio, index) => (
                        <AudioCard key={index} audio={audio} />
                    ))}
                </div>
            )}

            {/* 渲染文本内容 */}
            {textContent.length > 0 && (
                <div className="max-w-prose rounded-lg bg-muted p-3 text-base whitespace-normal break-words">
                    <Markdown>
                        {textContent.map(part => part.text?.trim()).join('\n')}
                    </Markdown>
                </div>
            )}
        </div>
    )
}

export function ConversationPage() {
    const { conversationId } = useParams<{ conversationId: string }>();
    const { userId, userData, addMessage } = useUser();

    const [input, setInput] = useState('');
    const [isReplying, setIsReplying] = useState(false);
    const [uploadedImages, setUploadedImages] = useState<ImageContentPart[]>([]);
    const [uploadedAudios, setUploadedAudios] = useState<AudioContentPart[]>([]);

    const [enableLoadingAnnotation, setEnableLoadingAnnotation] = useState(false);
    const [loadingAnnotation, setLoadingAnnotation] = useState<string | null>(null);

    const scrollViewportRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

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

    // 处理文件上传（图片和音频）
    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (!files) return;

        for (const file of Array.from(files)) {
            if (file.type.startsWith('image/')) {
                // 处理图片文件
                const reader = new FileReader();
                reader.onload = (e) => {
                    const result = e.target?.result as string;
                    const newImage: ImageContentPart = {
                        type: 'image',
                        imageUrl: result
                    };
                    setUploadedImages(prev => [...prev, newImage]);
                };
                reader.readAsDataURL(file);
            } else if (file.type.startsWith('audio/')) {
                // 处理音频文件
                const reader = new FileReader();
                reader.onload = async (e) => {
                    const result = e.target?.result as string;
                    const duration = await getAudioDuration(file);
                    const newAudio: AudioContentPart = {
                        type: 'audio',
                        audioUrl: result,
                        mediaType: file.type,
                        duration: duration,
                        fileName: file.name
                    };
                    setUploadedAudios(prev => [...prev, newAudio]);
                };
                reader.readAsDataURL(file);
            }
        }

        // 清空文件输入
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    // 移除已上传的图片
    const removeImage = (index: number) => {
        setUploadedImages(prev => prev.filter((_, i) => i !== index));
    };

    // 移除已上传的音频
    const removeAudio = (index: number) => {
        setUploadedAudios(prev => prev.filter((_, i) => i !== index));
    };

    const handleSendMessage = async (e: React.FormEvent) => {
        e.preventDefault();
        if ((!input.trim() && uploadedImages.length === 0 && uploadedAudios.length === 0) || !conversationId) return;

        // 1. 创建消息内容，包含文本、图片和音频
        const messageContent: (TextContentPart | ImageContentPart | AudioContentPart)[] = [];

        // 添加文本内容
        if (input.trim()) {
            messageContent.push({
                type: 'text',
                text: input
            });
        }

        // 添加图片和音频内容
        messageContent.push(...uploadedImages, ...uploadedAudios);

        // 创建用户消息
        const userMessage: ChatMessage = {
            id: uuidv4(),
            role: 'user',
            content: messageContent,
            annotations: [userId]
        };
        addMessage(conversationId, userMessage);

        const userInput = input; // 保存用户输入用于回复
        setInput(''); // 清空输入框
        setUploadedImages([]); // 清空上传的图片
        setUploadedAudios([]); // 清空上传的音频


        // 2. 显示加载动画并等待
        setIsReplying(true);
        setEnableLoadingAnnotation(true);

        scrollToBottom();
        let success = true;
        // await new Promise(resolve => setTimeout(resolve, 2000));
        try {
            const userServerUrl = `http://localhost:${config.userServer.port}`;

            // 构建新的消息格式
            const messageArray = [];

            // 添加文本消息
            if (userInput.trim()) {
                messageArray.push({
                    'kind': 'text',
                    'text': userInput
                });
            }

            // 添加图片消息
            uploadedImages.forEach(img => {
                // 从完整的 data URL 中提取 base64 部分和 MIME 类型
                const match = img.imageUrl.match(/^data:([^;]+);base64,(.+)$/);
                if (match) {
                    const mimeType = match[1];
                    const base64Data = match[2];
                    messageArray.push({
                        'kind': 'file',
                        'file': {
                            'bytes': base64Data,
                            'mimeType': mimeType
                        }
                    });
                }
            });

            // 添加音频消息
            uploadedAudios.forEach(audio => {
                // 从完整的 data URL 中提取 base64 部分和 MIME 类型
                const match = audio.audioUrl.match(/^data:([^;]+);base64,(.+)$/);
                if (match) {
                    const mimeType = match[1];
                    const base64Data = match[2];
                    messageArray.push({
                        'kind': 'file',
                        'file': {
                            'bytes': base64Data,
                            'mimeType': mimeType.replace('mpeg', 'mp3')
                        }
                    });
                }
            });

            console.log(messageArray);

            const data = {
                user_id: userId,
                conversation_id: conversationId,
                message: messageArray,
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
            <form onSubmit={handleSendMessage} className="border-t p-4">
                {/* 文件预览区域 */}
                {(uploadedImages.length > 0 || uploadedAudios.length > 0) && (
                    <div className="mb-3 flex flex-col gap-3">
                        {/* 图片预览 */}
                        {(uploadedImages.length > 0 || uploadedAudios.length > 0) && (
                            <div className="flex flex-wrap gap-2">
                                {uploadedImages.map((img, index) => (
                                    <div key={index} className="relative group">
                                        <img
                                            src={img.imageUrl}
                                            alt={`Upload ${index + 1}`}
                                            className="w-20 h-20 rounded-lg object-cover border"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => removeImage(index)}
                                            className="absolute -top-2 -right-2 bg-destructive text-destructive-foreground rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                                        >
                                            <X className="w-3 h-3" />
                                        </button>
                                    </div>
                                ))}
                                {uploadedAudios.map((audio, index) => (
                                    <div key={index + uploadedImages.length} className="relative group">
                                        <AudioCard audio={audio} />
                                        <button
                                            type="button"
                                            onClick={() => removeAudio(index)}
                                            className="absolute -top-2 -right-2 bg-destructive text-destructive-foreground rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                                        >
                                            <X className="w-3 h-3" />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

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
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/jpg,image/jpeg,image/png,audio/wav,audio/mp3"
                            multiple
                            onChange={handleFileUpload}
                            className="hidden"
                        />
                        <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            disabled={isReplying}
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <Paperclip className="h-4 w-4" />
                        </Button>
                        <Button type="submit" size="icon" disabled={isReplying || (!input.trim() && uploadedImages.length === 0 && uploadedAudios.length === 0)}>
                            <Send className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </form>
        </div>
    );
}