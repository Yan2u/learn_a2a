import { NavLink } from 'react-router-dom';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils'; // shadcn/ui 的一个工具函数，用于合并class
import { useDialog, useUser } from '@/contexts';
import { Button } from '@/components/ui/button';

export function Sidebar() {

    const { userData, userId, addConversation } = useUser(); // <-- 从 Context 获取当前用户的数据

    const { showInputDialog: showDialog } = useDialog();

    const handleNewConversation = () => {
        showDialog(
            "New Conversation",
            "Please enter a title for the new conversation.",
            "New Conversation",
            (ok: boolean, value: string) => {
                if (ok && value.trim()) {
                    addConversation(value.trim()); // 添加新对话
                }
            }
        )
    }

    /**
     * NavLink 的 className 可以接收一个函数，
     * 这让我们能根据链接是否处于激活状态 (isActive) 来动态改变样式。
     * @param { isActive: boolean }
     * @returns {string} - 返回对应的 Tailwind CSS 类名
     */
    const getNavLinkClass = ({ isActive }: { isActive: boolean }) => {
        return cn(
            "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
            isActive
                ? "bg-muted text-primary"  // 激活状态：灰色背景，主题色文字
                : "text-muted-foreground hover:bg-muted/50 hover:text-primary" // 普通状态
        );
    };

    return (
        // 使用 padding-right 为 0，让 scrollbar 贴边
        <ScrollArea className="h-full px-4 py-6">
            <div className="space-y-4">
                {/* Operations  */}
                <div>
                    <Button onClick={handleNewConversation}>New Conversation</Button>
                </div>

                {/* Conversations Section */}
                <div>
                    <h4 className="mb-1 rounded-md px-3 text-xs font-semibold text-muted-foreground">
                        Conversations
                    </h4>
                    <div className="flex flex-col space-y-1">
                        {userData?.conversations.map((convo) => (
                            <NavLink
                                to={`/user/${userId}/main/conversation/${convo.id}`}
                                key={convo.id}
                                className={getNavLinkClass}
                            >
                                {convo.title}
                            </NavLink>
                        ))}
                    </div>
                </div>

                {/* System Section */}
                <div>
                    <h4 className="mb-1 rounded-md px-3 text-xs font-semibold text-muted-foreground">
                        System
                    </h4>
                    <div className="flex flex-col space-y-1">
                        <NavLink to={`/user/${userId}/main/tasks`} className={getNavLinkClass}>
                            Tasks
                        </NavLink>
                        <NavLink to={`/user/${userId}/main/artifacts`} className={getNavLinkClass}>
                            Artifacts
                        </NavLink>
                    </div>
                </div>
            </div>
        </ScrollArea>
    );
}