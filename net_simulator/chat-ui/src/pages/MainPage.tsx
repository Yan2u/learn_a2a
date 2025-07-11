import { useEffect } from 'react';
import { Outlet, useParams } from 'react-router-dom';
import { useUser } from '@/contexts';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import { Sidebar } from './Sidebar';

export function MainPage() {
    // 从 URL 中提取 userId 参数
    const { userId } = useParams<{ userId: string }>();
    const { login, userData } = useUser();

    // 使用 useEffect，在组件加载时执行
    useEffect(() => {
        // 如果 URL 中有 userId，就通过 context 的 login 函数设置当前用户
        // 这确保了在刷新页面时，应用能够从 URL 恢复用户状态
        if (userId) {
            login(userId, userData.name);
        }
    }, [userId, login]); // 依赖项数组确保这个 effect 只在 userId 变化时运行

    return (
        <ResizablePanelGroup direction="horizontal" className="h-screen w-full">
            <ResizablePanel defaultSize={20} minSize={15} maxSize={25}>
                <Sidebar />
            </ResizablePanel>
            <ResizableHandle withHandle />
            <ResizablePanel defaultSize={80}>
                <Outlet />
            </ResizablePanel>
        </ResizablePanelGroup>

    );
}