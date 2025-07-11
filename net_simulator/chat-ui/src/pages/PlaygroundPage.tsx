import { useInterval } from "ahooks";
import { useCallback, useRef, useState } from "react";
import { GraphCanvas, useSelection } from 'reagraph'

export default function PlaygroundPage() {
    const [nodes, setNodes] = useState([
        {
            id: "0",
            label: 'General Paritioner Agent',
            kind: 'public',
            fill: '#8ecae6',
            data: {
                type: "medical"
            }
        },
        {
            id: "1",
            label: 'Internist Agent',
            kind: 'public',
            fill: '#8ecae6',
            data: {
                type: "medical"
            }
        },
        {
            id: "2",
            label: 'Cardiologist Agent',
            kind: 'public',
            fill: '#8ecae6',
            data: {
                type: "medical"
            }
        },
        {
            id: "3",
            label: 'Mathmatics Agent',
            kind: 'public',
            fill: '#8ecae6',
            data: {
                type: 'scholar'
            }
        },
        {
            id: "4",
            label: 'Physics Agent',
            kind: 'public',
            fill: '#8ecae6',
            data: {
                type: 'scholar'
            }
        },
        {
            id: "5",
            label: 'Fuzzed Marry',
            kind: 'user',
            fill: '#a7c957',
            data: {
                type: 'user'
            }
        },
        {
            id: "6",
            label: 'Fuzzed John',
            kind: 'user',
            fill: '#a7c957',
            data: {
                type: 'user'
            }
        },
        {
            id: "7",
            label: 'Fuzzed Alice',
            kind: 'user',
            fill: '#a7c957',
            data: {
                type: 'user'
            }
        },
        {
            id: "8",
            label: 'Fuzzed Bob',
            kind: 'user',
            fill: '#a7c957',
            data: {
                type: 'user'
            }
        }
    ]);

    const [edges, setEdges] = useState([])
    const canvasRef = useRef(null);
    const {
        selections, setSelections
    } = useSelection({
        nodes: nodes,
        edges: edges,
        ref: canvasRef,
        type: "multi",
        pathSelectionType: "all"
    });

    useInterval(() => {
        setSelections(nodes.filter(() => Math.random() > 0.5).map(x => x.id));
    }, 2000, { immediate: true });



    return <>
        <GraphCanvas selections={selections} ref={canvasRef} nodes={nodes} edges={[]} clusterAttribute="type" constrainDragging={false} />
    </>;
}