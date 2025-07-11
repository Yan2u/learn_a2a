import { useInterval } from 'ahooks';
import { Message } from '@a2a-js/sdk'

import {
    Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"

import { useUser } from '@/contexts';
import { config } from '@/config';
import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

export function TasksPage({ getAllTasks }: { getAllTasks?: boolean } = { getAllTasks: false }) {
    const { userId } = useUser();
    const [tasks, setTasks] = useState<Record<string, { id: string, status: string, message: Message, timestamp: string, artifacts: (string | null)[] }>>({});

    useInterval(() => {
        // get tasks from system server
        const serverUrl = `http://localhost:${config.userServer.port}/events/get`;
        axios.get(
            getAllTasks ? `${serverUrl}/all_tasks` : `${serverUrl}/tasks/${userId}`,
        ).then(response => {
            if (response.status !== 200) {
                console.error("Failed to fetch tasks:", response.status, response.statusText);
                toast.error(`Failed to fetch tasks: ${response.status} - ${response.statusText}`);
                return;
            }
            const responseJson = response.data;
            if (responseJson.status === 'error') {
                console.error("Error response from server:", responseJson);
                toast.error(`Failed to fetch tasks: ${responseJson.message}`);
                return;
            }

            console.log(responseJson);
            setTasks(responseJson.content);
        }).catch(error => {
            console.error("Failed to fetch tasks:", error);
            toast.error(`Failed to fetch tasks: ${error.message}`);
        })

    }, config.dataUpdateInterval, { immediate: true });

    return (
        <div className="flex h-full w-full flex-col p-8">
            <div className='text-2xl font-bold'> Tasks </div>
            <div className='flex flex-col w-full h-full'>
                <div className='sticky'>
                    <Table>
                        <TableHeader className='table table-fixed'>
                            <TableHead className='w-[150px]'>ID</TableHead>
                            <TableHead className='w-[150px]'>Time</TableHead>
                            <TableHead className='w-[150px]'>Status</TableHead>
                            <TableHead className='w-[150px]'>Artifacts</TableHead>
                            <TableHead>Text</TableHead>
                        </TableHeader>
                    </Table>
                </div>
                <div className='flex-1 overflow-y-auto w-full'>
                    {
                        Object.values(tasks).length > 0
                            ? <Table className='w-full'>
                                <TableBody>
                                    {
                                        Object.values(tasks).map(task =>
                                            <TableRow className='w-100'>
                                                <TableCell className='w-[150px] whitespace-normal'>{task.id}</TableCell>
                                                <TableCell className='w-[150px] whitespace-normal'>{new Date(task.timestamp).toLocaleString()}</TableCell>
                                                <TableCell className='w-[150px] whitespace-normal'>{task.status}</TableCell>
                                                <TableCell className='w-[150px] whitespace-normal break-all'>{task.artifacts.join(', ')}</TableCell>
                                                <TableCell className='whitespace-normal'>{task.message ? task.message.parts.filter(x => x.kind === 'text').map(x => x.text).join('\n') : ''}</TableCell>
                                            </TableRow>)
                                    }
                                </TableBody>
                            </Table>
                            :
                            <div className='flex w-full items-center justify-center p-10'>
                                <p className='text-lg text-muted-foreground'>No Tasks</p>
                            </div>
                    }
                </div>
            </div>
        </div>
    )
}