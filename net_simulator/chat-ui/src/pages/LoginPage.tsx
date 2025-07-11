import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { LogIn, Loader2 } from 'lucide-react';
import { useUser } from '@/contexts';
import { v4 as uuidv4 } from 'uuid'; // 用于生成唯一的用户ID

import { config } from '@/config';
import axios from 'axios';
import { toast } from 'sonner';
import { uniqueNamesGenerator } from 'unique-names-generator';

/**
 * 登录页面组件
 * 功能：
 * 1. 展示一个居中的登录卡片。
 * 2. 点击按钮后，模拟一个异步登录过程。
 * 3. 登录成功后，跳转到主页面 ('/main')。
 */
export function LoginPage() {
    // 用于控制按钮的加载状态，提供更好的用户体验
    const [isLoading, setIsLoading] = useState(false);

    // 从 react-router-dom 获取页面导航函数
    const navigate = useNavigate();

    // user login
    const { login } = useUser();

    //处理登录按钮点击事件的函数
    const handleLogin = async () => {
        setIsLoading(true);

        const newUserId = uuidv4(); // <-- 生成一个模拟用户ID
        console.log(`✅ Generated new User ID: ${newUserId}`);

        const newUserName = uniqueNamesGenerator(config.userNameGenConfig);
        console.log(`✅ Generated new User Name: ${newUserName}`);

        const userServerUrl = `http://localhost:${config.userServer.port}`;
        const data = { user_id: newUserId, user_name: newUserName };

        let success = true;

        try {
            const response = await axios.post(`${userServerUrl}/user/register`, data);
            if (response.status !== 200) {
                toast.error(`Failed to register: ${response.status} - ${response.statusText}`);
                success = false;
            }

            const responseJson = JSON.stringify(response.data);
            if (responseJson['status'] === 'error') {
                toast.error(`Failed to register: ${responseJson['message']}`);
                success = false;
            }
        } catch (error) {
            console.error(error);
            toast.error(`Failed to register: ${error instanceof Error ? error.message : 'Unknown error'}`);
            success = false;
        }

        if (!success) {
            setIsLoading(false);
            return;
        }


        login(newUserId, newUserName); // <-- 通过 Context 设置当前用户ID

        setIsLoading(false);

        // 核心改动：导航到包含 userId 的新 URL
        navigate(`/user/${newUserId}/main`);
    };

    return (
        <div className="flex items-center justify-center min-h-screen bg-background">
            <Card className="w-full max-w-sm">
                <CardHeader className="text-center">
                    <CardTitle className="text-3xl font-bold">
                        Join Agent Network
                    </CardTitle>
                    <CardDescription>
                        Press the button to register and enter the network.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <Button
                        onClick={handleLogin}
                        disabled={isLoading}
                        className="w-full"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Connecting...
                            </>
                        ) : (
                            <>
                                <LogIn className="mr-2 h-4 w-4" />
                                Connect & Enter
                            </>
                        )}
                    </Button>
                </CardContent>
            </Card>
        </div>
    );
}
