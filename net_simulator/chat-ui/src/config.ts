import { adjectives, names } from "unique-names-generator"

export const config = {
    userServer: {
        port: 8080,
    },
    dataUpdateInterval: 3000,
    graphUpdateInterval: 1000,
    userNameGenConfig: {
        dictionaries: [adjectives, names],
        length: 2,
        separator: ' '
    },
    graphOptions: {
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
    }
}