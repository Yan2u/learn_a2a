import { useState, ReactNode, useEffect } from 'react';
import { ChatMessage, UserData } from '@/types';
import { UserContext } from './UserContext';
import { v4 as uuidv4 } from 'uuid'; // 用于生成唯一的 conversation ID

// --- Helper Functions for localStorage ---
// Map 不能直接被 JSON.stringify，需要转换
const serializeMap = (map: Map<string, UserData>) => JSON.stringify(Array.from(map.entries()));
const deserializeMap = (jsonStr: string): Map<string, UserData> => new Map(JSON.parse(jsonStr));

export function UserProvider({ children }: { children: ReactNode }) {
    const [userId, setUserId] = useState<string | null>(null);
    // 使用一个 Map 来存储所有用户的数据，key 是 userId
    // 核心改动：从 localStorage 初始化 state
    const [allUsersData, setAllUsersData] = useState<Map<string, UserData>>(() => {
        try {
            const savedData = localStorage.getItem('agentNetUserData');
            return savedData ? deserializeMap(savedData) : new Map();
        } catch (error) {
            console.error("Failed to parse user data from localStorage", error);
            return new Map();
        }
    });

    const login = (id: string, name: string | null) => {
        setUserId(id);
        // 如果是新用户，为他创建一个空的初始数据结构
        if (!allUsersData.has(id)) {
            setAllUsersData(prevData => {
                const newData = new Map(prevData);
                // newData.set(id, mockUserData)
                newData.set(id, { conversations: [], tasks: [], events: [], name: name });
                return newData;
            });
        }
    };

    useEffect(() => {
        try {
            localStorage.setItem('agentNetUserData', serializeMap(allUsersData));
        } catch (error) {
            console.error("Failed to save user data to localStorage", error);
        }
    }, [allUsersData]);

    const logout = () => {
        setUserId(null);
    };

    const addMessage = (conversationId: string, message: ChatMessage) => {
        if (!userId) return;

        setAllUsersData(prevAllData => {
            const newAllData = new Map(prevAllData);
            const currentUserData = newAllData.get(userId);

            if (currentUserData) {
                const updatedConversations = currentUserData.conversations.map(convo => {
                    if (convo.id === conversationId) {
                        // 返回一个更新了 messages 的新 conversation 对象
                        return { ...convo, messages: [...convo.messages, message] };
                    }
                    return convo;
                });
                // 更新该用户的数据
                newAllData.set(userId, { ...currentUserData, conversations: updatedConversations });
            }
            return newAllData;
        });
    };

    const addConversation = (title: string) => {
        const newAllData = new Map(allUsersData);
        const currentUserData = newAllData.get(userId);
        if (currentUserData) {
            const newConversation = {
                id: uuidv4(),
                title: title,
                messages: [],
            };
            const updatedConversations = [...currentUserData.conversations, newConversation];
            newAllData.set(userId, { ...currentUserData, conversations: updatedConversations });
            setAllUsersData(newAllData);
        }
    };

    const value = {
        userId,
        userData: userId ? allUsersData.get(userId) || null : null,
        login,
        logout,
        addMessage,
        addConversation
    };

    return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

