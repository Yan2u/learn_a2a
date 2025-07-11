import { useInterval } from 'ahooks';
import { Artifact } from '@a2a-js/sdk'

import {
    Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"

import { useUser } from '@/contexts';
import { config } from '@/config';
import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

export function ArtifactsPage({ getAllArtifacts: getAllArtifacts }: { getAllArtifacts?: boolean } = { getAllArtifacts: false }) {
    const { userId } = useUser();
    const [artifacts, setArtifacts] = useState<Artifact[]>([]);

    useInterval(() => {
        // get tasks from system server
        const serverUrl = `http://localhost:${config.userServer.port}/events/get`;
        axios.get(
            getAllArtifacts ? `${serverUrl}/all_artifacts` : `${serverUrl}/artifacts/${userId}`,
        ).then(response => {
            if (response.status !== 200) {
                console.error("Failed to fetch artifacts:", response.status, response.statusText);
                toast.error(`Failed to fetch artifacts: ${response.status} - ${response.statusText}`);
                return;
            }
            const responseJson = response.data;
            if (responseJson.status === 'error') {
                console.error("Error response from server:", responseJson);
                toast.error(`Failed to fetch artifacts: ${responseJson.message}`);
                return;
            }

            console.log(responseJson);
            setArtifacts(responseJson.content);
        }).catch(error => {
            console.error("Failed to fetch artifacts:", error);
            toast.error(`Failed to fetch artifacts: ${error.message}`);
        })

    }, config.dataUpdateInterval, { immediate: true });

    return (
        <div className="flex h-full bg-gray-100 dark:bg-gray-900 flex-col p-8">
            <div className='text-2xl font-bold'> Artifacts </div>
            <div className='flex flex-col w-full h-full'>
                <div className='sticky'>
                    <Table>
                        <TableHeader className='table table-fixed'>
                            <TableHead className='w-[150px]'>Name</TableHead>
                            <TableHead className='w-[150px]'>ID</TableHead>
                            <TableHead>Text</TableHead>
                        </TableHeader>
                    </Table>
                </div>
                <div className='flex-1 overflow-y-auto'>


                    {
                        artifacts.length > 0
                            ?
                            <Table className='w-full h-full'>
                                <TableBody>
                                    {
                                        artifacts.map(artifact =>
                                            <TableRow className='w-100'>
                                                <TableCell className='w hitespace-normal'>{artifact.name}</TableCell>
                                                <TableCell className='whitespace-normal'>{artifact.artifactId}</TableCell>
                                                <TableCell className='whitespace-normal'>{artifact.parts ? artifact.parts.filter(x => x.kind === 'text').map(x => x.text).join('\n') : ''}</TableCell>
                                            </TableRow>)
                                    }
                                </TableBody>
                            </Table>
                            :
                            <div className='flex w-full items-center justify-center p-10'>
                                <p className='text-lg text-muted-foreground'>No Artifacts</p>
                            </div>

                    }

                </div>
            </div>

        </div>
    )
}