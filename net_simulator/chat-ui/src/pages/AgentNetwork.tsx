// src/components/AgentNetwork.js
import { useInterval } from 'ahooks';
import React, { useState, useEffect } from 'react';
import VisGraph, {
    GraphData,
} from 'react-vis-graph-wrapper';

// 初始 Agent 数据定义
const initialAgents = [
    // Public Agents - 内部环
    { level: 0, id: 'search_summary', type: 'public', task_count: 2, label: 'S&S Agent' },
    { level: 0, id: 'stock', type: 'public', task_count: 0, label: 'Stock Analyzer' },
    { level: 0, id: 'essay', type: 'public', task_count: 5, label: 'Essay Writer' },
    { level: 0, id: 'doctor', type: 'public', task_count: 0, label: 'Doctor Agent' },
    // User Agents - 外部环
    { level: 1, id: 'user1', type: 'user', label: 'User 1' },
    { level: 1, id: 'user2', type: 'user', label: 'User 2' },
    { level: 1, id: 'user3', type: 'user', label: 'User 3' },
    { level: 1, id: 'user4', type: 'user', label: 'User 4' },
    { level: 1, id: 'user5', type: 'user', label: 'User 5' },
    { level: 1, id: 'user6', type: 'user', label: 'User 6' },
];

// 模拟的互动信息
const initialInteractions = [
    { from: 'user1', to: 'search_summary' },
    { from: 'user2', to: 'search_summary' },
    { from: 'user3', to: 'essay' },
    { from: 'user4', to: 'doctor' },
];

function AgentNetwork() {
    const [agents, setAgents] = useState(initialAgents);
    const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
    const [interactions, setInteractions] = useState(initialInteractions);

    // vis-network 图表的配置选项
    const options = {
        // 自动布局算法
        layout: {
            hierarchical: {
                enabled: false, // 启用层级布局
            }
        },
        // 节点默认样式
        nodes: {
            shape: 'dot',
            size: 20,
            font: {
                size: 14,
                color: '#ffffff'
            },
            borderWidth: 2,
        },
        // 连线默认样式
        edges: {
            width: 2,
            color: { inherit: 'from' },
        },
        // 物理引擎配置
        physics: {
            enabled: false, // 初始时启用物理引擎来展开节点
            solver: 'barnesHut', // 使用 Barnes-Hut 算法
            barnesHut: {
                gravitationalConstant: -8000, // 调整引力（负数为斥力），可以控制整体的紧密程度
                centralGravity: 0.3, // 中心引力，防止图形无限扩散
                springLength: 200, // 边的理想长度
                springConstant: 0.04, // 边的“弹性系数”
                damping: 0.5, // 阻尼系数，帮助网络更快稳定
                avoidOverlap: 0 // 避免重叠的因子，我们用 nodeDistance 来控制
            },
        },
        // 交互配置
        interaction: {
            dragNodes: true, // 允许拖动节点
            zoomView: true,
            dragView: true,
        },
        height: '100%',
        width: '100%',
    };

    // useEffect 用于在组件挂载后处理数据和模拟后端更新
    useEffect(() => {
        // --- 数据处理和样式定义 ---
        const updateGraph = (currentAgents, currentInteractions) => {
            const interactingAgents = new Set();
            currentInteractions.forEach(i => {
                interactingAgents.add(i.from);
                interactingAgents.add(i.to);
            });

            // 1. 定义节点 (Nodes)
            const publicAgents = currentAgents.filter(x => x.type === 'public');
            const userAgents = currentAgents.filter(x => x.type === 'user');
            const publicAgentNodes = publicAgents.map((agent, index) => {
                const isWorking = agent.task_count > 0;
                const radius = 300;
                const angle = (index / publicAgents.length) * 2 * Math.PI; // 均匀分布在圆周上

                return {
                    ...agent,
                    shape: 'box',
                    label: agent.task_count > 0 ? `${agent.label}\n(${agent.task_count})` : agent.label,
                    color: {
                        border: isWorking ? '#219ebc' : '#6a994e', // 紫色边框表示工作中，靛蓝色表示空闲
                        background: isWorking ? '#8ecae6' : '#a7c957', // 浅紫色背景表示工作中
                    },
                    size: 30,
                    font: {
                        size: 30,
                        color: '#264653', // 字体颜色
                    },
                    x: radius * Math.cos(angle), // 手动设定位置
                    y: radius * Math.sin(angle), // 手动设定位置
                }
            });

            const userAgentNodes = userAgents.map((agent, index) => {
                const isWorking = interactingAgents.has(agent.id);
                const radius = 600;
                const angle = (index / userAgents.length) * 2 * Math.PI; //

                return {
                    ...agent,
                    shape: 'circle',
                    label: agent.label,
                    color: {
                        border: isWorking ? '#219ebc' : '#6a994e', // 紫色边框表示工作中，靛蓝色表示空闲
                        background: isWorking ? '#8ecae6' : '#a7c957', // 浅紫色背景表示工作中
                    },
                    size: 20,
                    font: {
                        size: 30,
                        color: '#264653', // 字体颜色
                    },
                    x: radius * Math.cos(angle), // 手动设定位置
                    y: radius * Math.sin(angle), // 手动设定位置
                }
            });

            const nodes = [...publicAgentNodes, ...userAgentNodes];

            // 2. 定义连线 (Edges)
            const allEdges = [];
            let edgeId = 0;

            // 公共节点之间互相连接
            const n = nodes.length;
            for (let i = 0; i < n; i++) {
                for (let j = i + 1; j < n; j++) {
                    let isInteracting = false;
                    for (let k = 0; k < currentInteractions.length; k++) {
                        if ((currentInteractions[k].from === nodes[i].id && currentInteractions[k].to === nodes[j].id) ||
                            (currentInteractions[k].from === nodes[j].id && currentInteractions[k].to === nodes[i].id)) {
                            allEdges.push({
                                id: ++edgeId,
                                from: nodes[i].id,
                                to: nodes[j].id,
                                dashes: false, // 实线
                                width: 3,
                                color: '#F87171', // 红色高亮
                            });
                            isInteracting = true;
                        }
                    }
                    if (!isInteracting) {
                        if (nodes[i].type === 'public' && nodes[j].type === 'public') {
                            allEdges.push({
                                id: ++edgeId,
                                from: nodes[i].id,
                                to: nodes[j].id,
                                dashes: true, // 默认虚线
                                width: 3,
                                color: '#dedbd2', // 默认颜色
                            });
                        }
                    }
                }
            }

            return { nodes, edges: allEdges };
        };

        // 初始化图表数据
        setGraph(updateGraph(agents, interactions));
    }, [agents]); // 当 agents 数据变化时，重新计算图表

    function getRandomInt(max) {
        return Math.floor(Math.random() * max);
    }

    useInterval(() => {
        if (Math.random() < 0.5) {
            return;
        }
        setAgents(prevAgents => {
            const newAgents = [...prevAgents];
            newAgents.filter(agent => agent.type === 'public').forEach(agent => {
                // 模拟任务数量变化
                agent.task_count = Math.floor(Math.random() * 6); // 0-5 之间的随机数
            });
            // 模拟用户与公共代理的互动
            return newAgents;
        });
        const n = agents.length;
        const newInteractions = [];
        for (let i = 0; i < 6; ++i) {
            const srcIdx = getRandomInt(n);
            let dstIdx = getRandomInt(n);
            while (srcIdx === dstIdx) {
                dstIdx = getRandomInt(n);
            }

            newInteractions.push({
                from: agents[srcIdx].id,
                to: agents[dstIdx].id
            })
        }

        setInteractions(newInteractions);

    }, 1000, { immediate: true })

    return (
        <VisGraph
            graph={graph}
            options={options}
        />
    );
}

export default AgentNetwork;