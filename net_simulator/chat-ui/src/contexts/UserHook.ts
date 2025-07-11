import { useContext } from "react";
import { UserContext } from "./UserContext";

// 创建一个自定义 Hook，方便在组件中使用 Context
export function useUser() {
    const context = useContext(UserContext);
    if (context === undefined) {
        throw new Error('useUser must be used within a UserProvider');
    }
    return context;
}