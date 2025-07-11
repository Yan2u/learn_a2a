import { useEffect, useRef, useState } from 'react';
import { useInterval } from 'ahooks';
import { config } from '@/config';
import { AgentNetGraphNode } from '@/types';
import axios from 'axios';
import { toast } from 'sonner';
import { GraphCanvas, GraphEdge, GraphNode, InternalGraphEdge, useSelection } from 'reagraph';
import { useDialog } from '@/contexts';
import { Button } from '@/components/ui/button';
import { ChevronsUpDown, Info, List, Pause, Play, StopCircle } from 'lucide-react';
import { Alert, AlertTitle } from '@/components/ui/alert';
import { Command, CommandEmpty, CommandGroup, CommandItem, CommandList } from '@/components/ui/command';
import { ButtonGroup } from '@/components/buttongroup';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

function AgentNetPage() {

    const [nodeData, setNodeData] = useState<Record<string, AgentNetGraphNode>>({});
    const canvasRef = useRef(null);
    const [nodes, setNodes] = useState<GraphNode[]>([]);
    const [edges, setEdges] = useState<GraphEdge[]>([]);
    const { showMessageDialog } = useDialog();

    const [isRecording, setIsRecording] = useState(false);
    const [isReplaying, setIsReplaying] = useState(false);
    const [statusMessage, setStatusMessage] = useState<string>("Realtime graph...");

    // record
    const [recordNodes, setRecordNodes] = useState<GraphNode[][]>([]);
    const [recordEdges, setRecordEdges] = useState<GraphEdge[][]>([]);
    const [recordSelections, setRecordSelections] = useState<string[][]>([]);
    const [replayIndex, setReplayIndex] = useState(0);

    // record select
    const [recordSelectionOpen, setRecordSelectionOpen] = useState(false);
    const [recordSelection, setRecordSelection] = useState<string>("");

    const {
        selections, setSelections, actives
    } = useSelection({
        ref: canvasRef,
        nodes: nodes,
        edges: edges,
        pathSelectionType: "all",
        type: "multi"
    })

    // useEffect 用于在组件挂载后处理数据和模拟后端更新
    useEffect(() => {
        if (isReplaying) {
            return;
        }

        const interactingAgents: string[] = [];
        const items = Object.entries(nodeData);
        const currentEdges: GraphEdge[] = [];

        items.forEach(([id, node]) => {
            if (node.interactions.length > 0) {
                if (interactingAgents.findIndex(x => x === id) === -1) {
                    interactingAgents.push(id);
                }
            }
            node.interactions.forEach(interaction => {
                if (interactingAgents.findIndex(x => x === interaction.dst_id) === -1) {
                    interactingAgents.push(interaction.dst_id);
                }
                currentEdges.push({
                    source: id,
                    target: interaction.dst_id,
                    label: interaction.message.substring(0, 100) + (interaction.message.length > 100 ? '...' : ''),
                    id: `${id}_${interaction}`,
                    data: {
                        message: interaction.message,
                    }
                })
            })
        });

        setNodes(items.map(([id, node]) => {
            return {
                id: id,
                label: node.name,
                data: {
                    category: node.category,
                }
            }
        }));

        setEdges(currentEdges);
        setSelections(interactingAgents);

        if (isRecording) {
            setRecordNodes(prev => [...prev, nodes]);
            setRecordEdges(prev => [...prev, currentEdges]);
            setRecordSelections(prev => [...prev, interactingAgents]);
            setStatusMessage(`${recordEdges.length + 1} frames recorded...`);
        }

    }, [nodeData, setSelections]);

    useInterval(() => {
        if (isReplaying) {
            return;
        }
        axios.get(`http://localhost:${config.userServer.port}/graph`, { timeout: 500 })
            .then(response => {
                if (response.status === 200) {
                    const graph: Record<string, AgentNetGraphNode> = response.data.content;
                    setNodeData(graph);
                } else {
                    console.error("Failed to fetch graph data:", response.statusText);
                    toast.error("Failed to fetch graph data. Please check the server status.");
                }
            }).catch(error => {
                console.error("Error fetching graph data:", error);
                toast.error("Failed to fetch graph data. Please check the server status.");
            })

    }, config.graphUpdateInterval, { immediate: true })

    useInterval(() => {
        if (!isReplaying) { return; }
        if (replayIndex >= recordNodes.length) {
            setIsReplaying(false);
            setReplayIndex(0);
            setStatusMessage("Replay finished.");
            return;
        }
        setNodes(recordNodes[replayIndex]);
        setEdges(recordEdges[replayIndex]);
        setSelections(recordSelections[replayIndex]);
        setStatusMessage(`Replaying frame ${replayIndex + 1}/${recordNodes.length}...`);
        setReplayIndex(replayIndex + 1);
    }, config.graphUpdateInterval)

    const edgeOnClick = (edge: InternalGraphEdge) => {
        showMessageDialog(
            `${nodeData[edge.source].name} ==> ${nodeData[edge.target].name}`,
            edge.data.message,
            true,
            null
        );
    }

    const handleToogleRecording = (value: boolean) => {
        if (value) {
            setRecordEdges([]);
            setRecordNodes([]);
            setRecordSelections([]);
        } else {
            const newRecordName = `rec_${new Date().toLocaleString().replace(' ', '_')}`;
            const recordsStr = localStorage.getItem('records');
            const records = recordsStr ? JSON.parse(recordsStr) : {};
            records[newRecordName] = {
                nodes: recordNodes,
                edges: recordEdges,
                selections: recordSelections
            };
            localStorage.setItem('records', JSON.stringify(records));
            setStatusMessage(`Recording saved as ${newRecordName} (${recordNodes.length} frames).`);
        }

        setIsRecording(value);
    }

    const handleToggleReplay = (value: 'start' | 'stop' | 'pause') => {
        if (value === 'start') {
            if (isRecording) {
                toast.error("Please stop recording before starting replay.");
                return;
            }

            if (!recordSelection) {
                toast.error("Please select a record to replay.");
                return;
            }

            const recordData = JSON.parse(localStorage.getItem('records'))[recordSelection];
            setRecordNodes(recordData.nodes);
            setRecordEdges(recordData.edges);
            setRecordSelections(recordData.selections);
        }
        if (value === 'stop' || value === 'pause') {
            setIsReplaying(false);
            setStatusMessage("Replay stopped.");
            if (value === 'stop') {
                setReplayIndex(0);
            }
            return;
        } else {
            if (recordNodes.length === 0) {
                toast.error("No recorded frames to replay.");
                return;
            }
            // setReplayIndex(0);
            setIsReplaying(true);
        }

        if (value === 'start') {
            setIsReplaying(true);
        } else {
            setIsReplaying(false);
        }
    }

    return (
        <div className="flex-1 flex flex-col p-6 gap-3">

            <div className='flex flex-row gap-3 items-center'>
                <span> Recording </span>
                <ButtonGroup>
                    <Button variant='outline' disabled={isRecording} onClick={() => handleToogleRecording(true)}> <Play /> </Button>
                    <Button variant='outline' disabled={!isRecording} onClick={() => handleToogleRecording(false)}> <StopCircle /> </Button>
                </ButtonGroup>

                <span> Replay </span>
                <ButtonGroup>
                    <Button variant='outline' disabled={isReplaying} onClick={() => handleToggleReplay('start')}> <Play /> </Button>
                    <Button variant='outline' disabled={!isReplaying} onClick={() => handleToggleReplay('pause')}> <Pause /> </Button>
                    <Button variant='outline' disabled={!isReplaying} onClick={() => handleToggleReplay('stop')}> <StopCircle /> </Button>
                </ButtonGroup>

                <span> Select </span>
                <Popover open={recordSelectionOpen} onOpenChange={setRecordSelectionOpen}>
                    <PopoverTrigger asChild>
                        <Button variant='outline' role='combobox' aria-expanded={recordSelectionOpen} className='w-[200px] justify-between'>
                            {recordSelection || "Select Record"}
                            <ChevronsUpDown className="opacity-50" />
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="p-0">
                        <Command>
                            <CommandList>
                                <CommandEmpty>No records</CommandEmpty>
                                <CommandGroup>
                                    {
                                        (localStorage.getItem('records') ? Object.keys(JSON.parse(localStorage.getItem('records'))) : []).map(
                                            name =>
                                                <>
                                                    <CommandItem key={name} value={name} onSelect={v => { setRecordSelection(v); setRecordSelectionOpen(false) }} className='px-2'>
                                                        <List />
                                                        {name}
                                                    </CommandItem>
                                                </>
                                        )
                                    }
                                </CommandGroup>
                            </CommandList>
                        </Command>
                    </PopoverContent>
                </Popover>

                <Alert variant='default' className='flex-1 shadow-sm py-2'>
                    <Info />
                    <AlertTitle>{statusMessage}</AlertTitle>
                </Alert>
            </div>

            <div className="flex-1 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-1 shadow-sm relative">
                <GraphCanvas ref={canvasRef} nodes={nodes} edges={edges}
                    selections={selections} clusterAttribute='category' draggable
                    edgeInterpolation='curved' actives={actives} defaultNodeSize={7} minNodeSize={5} maxNodeSize={10}
                    onEdgeClick={edgeOnClick} labelType="all" />
            </div>

        </div>
    )
}

export default AgentNetPage;