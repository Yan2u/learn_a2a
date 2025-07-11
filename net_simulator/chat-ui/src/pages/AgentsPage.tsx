import { useInterval } from 'ahooks';

import {
    Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"

import { config } from '@/config';
import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { AgentNetGraphNode, PublicAgentNode } from '@/types';

export default function AgentsPage() {
    const [nodeData, setNodeData] = useState<Record<string, PublicAgentNode>>({});

    useInterval(() => {
        // get tasks from system server
        const serverUrl = `http://localhost:${config.userServer.port}`;
        axios.get(`${serverUrl}/graph`).then(response => {
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
            const graph: Record<string, AgentNetGraphNode> = responseJson.content;
            // filter public nodes
            const publicNodes: Record<string, PublicAgentNode> = Object.fromEntries(
                Object.entries(graph).filter(([, node]) => node.kind === 'public').map(([id, node]) => [id, node as PublicAgentNode])
            );
            setNodeData(publicNodes);
        }).catch(error => {
            console.error("Failed to fetch:", error);
            toast.error(`Failed to fetch: ${error.message}`);
        })

    }, config.dataUpdateInterval, { immediate: true });

    return (
        <div className="flex h-full w-full flex-col p-8">
            <div className='text-2xl font-bold'> Agents </div>
            <div className='flex flex-col w-full h-full'>
                <div className='sticky'>
                    <Table>
                        <TableHeader className='table table-fixed'>
                            <TableHead className='w-[100px]'>URL</TableHead>
                            <TableHead className='w-[150px]'>ID</TableHead>
                            <TableHead className='w-[150px]'>Name</TableHead>
                            <TableHead className='w-[100px]'>Task Count</TableHead>
                            <TableHead className='w-[100px]'>Category</TableHead>
                            <TableHead>Interactions</TableHead>
                        </TableHeader>
                    </Table>
                </div>
                <div className='flex-1 overflow-y-auto w-full'>
                    {
                        Object.values(nodeData).length > 0
                            ? <Table className='w-full'>
                                <TableBody>
                                    {
                                        Object.entries(nodeData).map(([id, node]) =>
                                            <TableRow className='w-100'>
                                                <TableCell className='w-[100px] whitespace-normal break-all'>{node.url}</TableCell>
                                                <TableCell className='w-[150px] whitespace-normal break-all'>{id}</TableCell>
                                                <TableCell className='w-[150px] whitespace-normal'>{node.name}</TableCell>
                                                <TableCell className='w-[100px] whitespace-normal break-all'>{node.task_count}</TableCell>
                                                <TableCell className='w-[100px] whitespace-normal'>{node.category}</TableCell>
                                                <TableCell className='whitespace-normal break-all'>
                                                    {
                                                        node.interactions.length > 0
                                                            ? node.interactions.map(i => nodeData[i.dst_id].name).join(', ')
                                                            : "Empty"
                                                    }
                                                </TableCell>
                                            </TableRow>)
                                    }
                                </TableBody>
                            </Table>
                            :
                            <div className='flex w-full items-center justify-center p-10'>
                                <p className='text-lg text-muted-foreground'>No Agents</p>
                            </div>
                    }
                </div>
            </div>
        </div>
    )
}