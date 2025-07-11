import { useContext } from "react";
import { DialogContext } from "./DialogContext";

// 创建一个自定义 Hook，方便在组件中使用 Context
export function useDialog() {
    const context = useContext(DialogContext);
    if (context === undefined) {
        throw new Error('useUser must be used within a UserProvider');
    }
    return context;
}