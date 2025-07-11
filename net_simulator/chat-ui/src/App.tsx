import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from './pages/LoginPage';
import { MainPage } from './pages/MainPage';
import { ConversationPage } from './pages/ConversationPage';
import { DialogProvider, UserProvider } from './contexts';
import { TasksPage } from './pages/TasksPage';
import { ArtifactsPage } from './pages/ArtifactsPage';
import AgentNetPage from './pages/AgentNetPage';
import PlaygroundPage from './pages/PlaygroundPage';
import DashboardPage from './pages/DashboardPage';
import AgentsPage from './pages/AgentsPage';

// 任务和事件的占位页面
// const TaskListPage = () => <div className="p-4">Task List Page Placeholder</div>;
// const EventListPage = () => <div className="p-4">Event List Page Placeholder</div>;

function App() {
  return (
    <UserProvider>
      <DialogProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path='/playground' element={<PlaygroundPage />} />

            {/* 核心改动：为所有主页面路由添加 /user/:userId 前缀 */}
            <Route path="/user/:userId/main" element={<MainPage />}>
              <Route index element={<Navigate to="conversation/conv-1" replace />} />
              <Route path="conversation/:conversationId" element={<ConversationPage />} />
              <Route path="tasks" element={<TasksPage />} />
              <Route path="artifacts" element={<ArtifactsPage />} />
            </Route>

            <Route path="/dashboard" element={<DashboardPage />}>
              <Route index element={<Navigate to="network" replace />} />
              <Route path='network' element={<AgentNetPage />} />
              <Route path='tasks' element={<TasksPage getAllTasks={true} />} />
              <Route path='artifacts' element={<ArtifactsPage getAllArtifacts={true} />} />
              <Route path='agents' element={<AgentsPage />} />
            </Route>

            {/* 根路径重定向到登录页 */}
            <Route path="/" element={<Navigate to="/login" replace />} />
          </Routes>
        </BrowserRouter>
      </DialogProvider>
    </UserProvider>
  );
}

export default App;