import { Button } from "@/components/ui/button";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { ListTodo, Network, PersonStanding, Text } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

export default function DashboardPage() {
    return (
        <ResizablePanelGroup direction="horizontal" className="h-screen w-full bg-gray-100 dark:bg-gray-900">
            <ResizablePanel defaultSize={10} minSize={10} maxSize={20}>
                <aside className="w-64 flex-shrink-0 h-full">
                    <div className="flex h-full flex-col px-4 py-6">
                        <div className="mb-6">
                            <h2 className="text-xl font-semibold tracking-tight">Dashboard</h2>
                        </div>
                        <nav className="flex flex-col gap-2">
                            {/* 使用 shadcn/ui 的 Button 作为导航项 */}
                            <Button variant="ghost" className="justify-start gap-2" asChild>
                                <NavLink to='/dashboard/network' key='network'>
                                    <Network className="h-4 w-4" />
                                    Network
                                </NavLink>
                            </Button>
                            {/* 你可以在这里添加更多导航项 */}
                            <Button variant="ghost" className="justify-start gap-2" asChild>
                                <NavLink to='/dashboard/tasks' key='tasks'>
                                    <ListTodo className="h-4 w-4" />
                                    Tasks
                                </NavLink>
                            </Button>
                            <Button variant="ghost" className="justify-start gap-2" asChild>
                                <NavLink to='/dashboard/artifacts' key='artifacts'>
                                    <Text className="h-4 w-4" />
                                    Artifacts
                                </NavLink>
                            </Button>
                            <Button variant="ghost" className="justify-start gap-2" asChild>
                                <NavLink to='/dashboard/agents' key='agents'>
                                    <PersonStanding className="h-4 w-4" />
                                    Agents
                                </NavLink>
                            </Button>
                        </nav>
                    </div>

                </aside>
            </ResizablePanel>
            <ResizableHandle withHandle />
            <ResizablePanel defaultSize={90}>
                <div className="flex h-screen bg-gray-100 dark:bg-gray-900">
                    <Outlet />
                </div>
            </ResizablePanel>
        </ResizablePanelGroup>

    )
}