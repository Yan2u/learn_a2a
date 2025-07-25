## Simple Agent Net Simulator

### 后端

#### **简单的 agent 网络**

- 1 个注册节点：存放所有公共 agent 的资料卡；
- 一些公共 agent 节点：底层调用 gpt-4o，添加不同的 system prompt 实现；
- 每个用户专属的 user agent；

#### **公共 agent**

- 搜索&总结 agent：搜索关键词，以给定的结构化数据格式 (json, markdown, csv, ...) 总结搜索结果；
- 股票分析 agent：大盘，某支股票近期走势和分析；
- 论文撰写 agent：根据给出的话题和材料撰写论文；
- 学术 agent：解答特定领域的学术问题；
  - 按学科可细分为数学、物理、生物学等等；
- 诊断 agent：根据输入的病情描述，给出诊断意见，模拟开处方；
- 医生 agent：供诊断 agent 参考的一些 agent，按特定领域划分；

**用户**

- 3 个用户；
- 分别对应不同的需求：撰写论文、分析股票、看病。

#### 前端

##### 基本功能

- Agent Net 可视化；
- 任务过程可视化；

##### **扩展功能**

- 对话式 user agent，用户对话界面；
- 任务管理；
- 多轮对话支持（可以视为任务的一部分，集成到任务管理中，参考 manus）；