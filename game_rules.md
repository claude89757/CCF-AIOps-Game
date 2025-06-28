# 大赛报名

所有参赛选手通过国际AIOps挑战赛官网进行报名和组队，参赛选手请仔细阅读并严格遵守《AIOps挑战赛选手报名协议》，违反相关规定将取消参赛资格。

**报名时间**：2025年5月31日-6月26日 18:00

**报名流程**：参赛选手在官网（https://challenge.aiops.cn/）进行注册，按照提示填写账户资料、绑定手机号、进行实名认证，实名认证经审核通过后，即可点击"参加比赛"报名。

1. 若队伍成员为海外选手，实名认证选择"其他"，上传相应证件照片。
2. 高校学生参与报名，所在单位及职位请填写所在学校及专业年级。
3. 请如实填写信息，否则可能取消参赛资格和成绩。

# 创建队伍

选手报名后自动创建团队，可邀请其他成员加入，组队完成后由队长确认"确认组队完成"。

1. 参赛队伍人数不限，可以单人组队，也可以自由组队。
2. 每名选手限参加1支参赛队伍。
3. 队长需在挑战赛官网"确认组队完成"（单人参赛也需要完成"确认组队"），锁定队伍成员和队伍名称。最晚请于6月26日20:00前完成组队。
4. 资源申请：
   > **注**：填写问卷前，请在挑战赛官网完成"确认组队"，方可申请。发放资源前，会核实组队完成信息。资源审核通过后会以邮件方式通知
   
   - **服务器资源**：请以团队为单位填写资源分配问卷：https://www.wjx.top/vm/tUFzNJC.aspx，组委会将会统一分配资源。
   - **大模型Token申请**：请团队队长访问链接获取大模型Token：https://uni-api.cstcloud.cn，在申请名称或说明中注明2025 AIOps挑战赛，即可顺利通过审核。

# 参考范例

## 输入

1. 故障案例的uuid以及对应的一段自然语言查询（如："The system experienced an anomaly from 2025-04-30T19:10:15Z to 2025-04-30T19:40:15Z. Please infer the possible cause."）
2. 与之关联的运行数据，包括：
   - **监控指标（Metrics）**：如 CPU 使用率、磁盘 I/O 等
   - **服务日志（Logs）**：组件产生的结构化或半结构化日志
   - **调用链数据（Traces）**：服务之间的依赖与请求路径

## 输出

结构化 JSON 格式的根因结果（字段组合视任务而定）：

```json
{
  "uuid": "33c11d00-2",
  "component": "checkoutservice",
  "reason": "disk IO overload",
  "time": "2025-04-21 12:18:00",
  "reasoning_trace": [
    {
      "step": 1,
      "action": "LoadMetrics(checkoutservice)",
      "observation": "disk_read_latency spike"
    },
    {
      "step": 2,
      "action": "TraceAnalysis('frontend -> checkoutservice')",
      "observation": "checkoutservice self-loop spans"
    },
    {
      "step": 3,
      "action": "LogSearch(checkoutservice)",
      "observation": "IOError in 3 logs"
    }
  ]
}
```

## 字段说明

| 字段名 | 类型 | 是否必须 | 说明 |
|--------|------|----------|------|
| uuid | string | 是 | 该条返回结果所对应的故障案例的uuid |
| component | string | 是 | 根因组件的名称，每条样本只评估一个根因组件，若提交多个组件，仅评估 JSON 中首个出现的 component 字段，类型需为 string。 |
| reason | string | 是 | 故障发生的原因或类型 |
| time | string(ISO) | 是 | 根因事件对应的时间点，用于任务对齐与人工验证，不参与自动评分。建议精度在分钟级别，并尽量贴近指标或日志异常的时间点。 |
| reasoning_trace | object[] | 是 | 完整推理轨迹，包含每步 action/observation 等，其中observation 超出 100 字将被截断，仅保留前 100 字参与评分 |

> **注1**：当前任务为单根因故障定位，每条样本仅包含一个 ground truth component 与 reason。评估系统仅采纳提交结果中的首个 component 和 reason 字段。

> **注2**：字段格式说明：
> - "time" 字段推荐格式为 "YYYY-MM-DD HH:mm:ss"，例如 "2025-04-21 12:18:00"
> - "reasoning_trace" 为包含多个 step 对象的数组，每个对象应包含以下字段：
>   - **step**：整数，表示推理步骤编号（从 1 开始）
>   - **action**：字符串，描述该步调用或操作
>   - **observation**：字符串，描述该步观察到的结果，建议控制在 100 字内
> - 所有字段名建议使用 snake_case 命名风格，避免大小写混用。

**提交答案的脚本详见**：https://www.aiops.cn/gitlab/aiops-live-benchmark/aiopschallenge2025-submission

# 赛事环境

中国科学院计算机网络信息中心将为赛事提供服务器算力及大模型接口支持，资源由中国科技云（大模型接口）和云网融合技术创新与试验平台（算力服务器）分别提供。

# 评分标准

为全面评估大语言模型在根因定位任务中的综合能力，当前赛题统一采用如下评分标准

## 一、评分维度与分值构成（总分：1.00）

| 维度 | 权重（初始设定） | 说明 |
|------|------------------|------|
| 组件准确率 LA | 0.40 | 是否准确识别出根因组件（component 字段） |
| 原因准确率 TA | 0.40 | 是否准确识别出根因类型/诱因（reason 字段） |
| 推理效率 Efficiency | 0.10 | 推理路径是否紧凑，步数越少得分越高（根据平均推理步数 APL 评估） |
| 推理可解释性 Explainability | 0.10 | 推理链条是否覆盖关键证据，逻辑完整性是否良好（基于结构化轨迹评估） |

> 📌 **注**：各评分维度的权重可能根据比赛进展情况进行动态调整，如有调整将通过赛事公告进行说明。

## 二、评分细则

### 1. 组件准确率（LA）

该评分项用于衡量模型是否准确识别出导致故障的根因组件（component 字段）。在微服务架构中，定位到出问题的服务节点是根因分析的关键前提，因而该指标是最核心的评估维度之一。

**评分公式**：

$$LA = \frac{L_c}{L_t}$$

其中：
- $L_c$：正确预测的组件数量，即选手提交的 component 与 ground_truth中component 完全相同的样本数
- $L_t$：总的评估样本数量（即赛题中需要评估的任务条目数）

> **注**：当前任务为单组件根因定位，故每条样本最多有一个标注组件，选手提交的第一个 component 字段将作为评估对象，多报、错报不计入。

### 2. 原因准确率（TA）

该评分项用于评估模型是否准确识别出导致故障的原因或类型（reason 字段），即对诱因的理解能力。在实际场景中，只有明确了触发故障的机制，才能实现进一步修复或预防。

**评分公式**：

$$TA = \frac{T_c}{T_t}$$

其中：
- $T_c$：选手提交的reason是否和ground truth中的reason是否相同，该项将通过基于关键词匹配 + 语义相似度的方法进行评估
- $T_t$：总的评估样本数量

> **注**：当前任务为单因果场景，reason 仅评估第一条，允许"语义相近"情况获得部分得分，但泛化表述如 "high latency" 可能无法命中精确标签 "disk IO overload"。

### 3. 推理效率（Efficiency）

该评分项用于衡量模型在推理过程中的路径紧凑性与效率。在真实故障排查中，过长的推理路径往往意味着推理冗余或方向偏离，而过短可能表明推理流程被简化，遗漏关键信息。因此，本项鼓励构建信息充分且逻辑紧凑的推理链。

Efficiency 仅基于根因组件（component）和故障原因（reason）均预测正确的样本进行统计。从这些样本中提取其推理路径长度，计算平均推理步数（APL, Average Path Length），并据此评分：

**评分公式**：

$$Efficiency = \exp\left(-\frac{APL-5}{5}\right)$$

其中：
- APL = 所有正确结果的平均的推理步骤数
- Efficiency 得分最大值为 1.00（超过部分将被截断）

**示例得分情况**：

| APL | Efficiency 得分 |
|-----|----------------|
| 4步 | 1.22 → 截断为 1.00 |
| 5步 | 1.00 |
| 10步 | 0.37 |
| 15步 | 0.13 |
| 20步 | 0.05 |

### 4. 推理可解释性（Explainability）

推理可解释性评分用于衡量选手提交的推理链是否具备充分的证据支持其根因结论。每个故障样本预定义若干关键证据点，评分计算的是这些证据点在 reasoning_trace 中被覆盖的比例。

**推理可解释性得分计算公式**：

$$Explainability = \frac{E_m}{E_t}$$

其中：
- $E_m$ = 选手在每个样本提交的 reasoning_trace[].observation 中命中关键证据点的总数
- $E_t$ = 样本总共定义的关键证据点数量

**各类数据证据点命中的判断依据**：

| 类型 | 子类 | 命中判断依据 |
|------|------|-------------|
| 指标 | 指标名称命中 | 在 observation 中提到预期 KPI 名称（模糊匹配可接受，如 fs_read ≈ disk_read_latency） |
| 日志 | 日志内容提及 | 提到有日志检索行为，并出现关键组件名即可视为命中，不要求匹配精确错误码 |
| 调用链 | trace 节点命中 | 推理链中提到的组件应位于 trace 路径上（caller / callee 均可），例如："调用链中 checkoutservice 多次自调用" |

> **注**：reasoning_trace 中每步 observation 可超过 100 字，但评分系统仅使用前 100 字参与关键证据点的命中判断。为确保得分有效，建议选手将关键指标、调用链信息或日志异常等关键信息置于 observation 的前 100 字内。此规则旨在抑制无效关键词堆砌，鼓励选手提交结构清晰、重点突出的推理过程。

### 最终得分

$$\text{Final Score} = (0.40 \times LA + 0.40 \times TA + 0.10 \times Efficiency + 0.10 \times Explainability) \times 100$$

> **注**：推理可解释性得分评估推理链条的合理性与完整性，但不直接保证最终根因组件（component）和故障原因（reason）的准确性，二者独立计分。

# 用例说明

## 组委会提供 - 参考答案

```json
{
  "uuid": "33c11d00-2",
  "component": "checkoutservice",
  "reason": "disk IO overload",
  "time": "2025-04-21 12:18:00",
  "reasoning_trace": [
    {
      "step": 1,
      "action": "LoadMetrics(checkoutservice)",
      "observation": "disk_read_latency spike observed at 12:18"
    },
    {
      "step": 2,
      "action": "TraceAnalysis('frontend -> checkoutservice')",
      "observation": "checkoutservice appears multiple times in self-loop spans"
    },
    {
      "step": 3,
      "action": "LogSearch(checkoutservice)",
      "observation": "IOError found in 3 log entries"
    }
  ]
}
```

## 选手提交答案 - 评测示例1 ✅答案正确

```json
{
  "uuid": "33c11d00-2",
  "component": "checkoutservice",
  "reason": "disk IO overload",
  "time": "2025-04-21 12:18:00",
  "reasoning_trace": [
    {
      "step": 1,
      "action": "QueryMetric(checkoutservice)",
      "observation": "I/O latency peak at 12:18"
    },
    {
      "step": 2,
      "action": "TraceCheck",
      "observation": "checkoutservice is on a self-loop chain"
    },
    {
      "step": 3,
      "action": "LogInspection",
      "observation": "multiple IOError records"
    }
  ]
}
```

**评分解释**：

- ✅ 根因组件正确 → LA = 0.40
- ✅ 故障类型正确 → TA = 0.40
- ✅ Reasoning_trace 共 3 步，推理紧凑 → Efficiency = 1.00 × 0.10 = 0.10
- ✅ 命中 3 个关键证据点（指标、日志、调用链） → Explainability = 0.10

🔢 **总分**：0.40 + 0.40 + 0.10 + 0.10 = 1.00

## 选手提交答案 - 评测示例2 ⚠️答案部分正确

```json
{
  "uuid": "33c11d00-2",
  "component": "checkoutservice",
  "reason": "high latency",
  "time": "2025-04-21 12:18:00",
  "reasoning_trace": [
    {
      "step": 1,
      "action": "FetchMetrics(checkoutservice)",
      "observation": "latency spikes detected"
    },
    {
      "step": 2,
      "action": "LogScan(checkoutservice)",
      "observation": "error logs detected"
    }
  ]
}
```

**评分解释**：

- ✅ 根因组件正确 → LA = 0.40
- ❌ 原因未命中 → TA = 0.00
- ❌ 未完全命中（仅组件正确），Efficiency 不参与计算 → Efficiency = 0.00
- ✅ 命中 2 个关键证据点（指标 + 日志），共 3 个 → Explainability = 2/3 × 0.10 ≈ 0.067

🔢 **总分**：0.40 + 0.00 + 0.00 + 0.067 = 0.467

## 选手提交答案 - 评测示例3 ❌答案错误

```json
{
  "uuid": "33c11d00-2",
  "component": "frontend",
  "reason": "network congestion",
  "time": "2025-04-21 12:10:00",
  "reasoning_trace": [
    {
      "step": 1,
      "action": "LoadMetrics(frontend)",
      "observation": "CPU usage stable"
    },
    {
      "step": 2,
      "action": "CheckTraces",
      "observation": "normal communication"
    }
  ]
}
```

**评分解释**：

- ❌ 根因组件错误 → LA = 0.00
- ❌ 原因错误 → TA = 0.00
- ❌ 根因未命中 → Efficiency = 0.00（未进入效率评分）
- ❌ 未命中任何有效证据（指标正常、调用链正常，均无关键异常） → Explainability = 0.00

🔢 **总分**：0.00 + 0.00 + 0.00 + 0.00 = 0.00

# 技术要求与实现建议

## 必须满足

1. 根因定位核心推理任务必须由大语言模型（LLM）驱动完成
2. 系统需具备解析多模态数据（指标、日志、调用链）的能力
3. 模型需能理解自然语言查询，并输出结构化结果
4. 提交结果需支持复现，附带推理日志或说明文档
5. 主办方统一提供大语言模型调用接口，参赛队伍仅可使用以下模型：
   - QWQ-LLaMA API（国内部署版本）
   - DeepSeek-LLM API（对话+代码支持）
6. 所有参赛系统需通过主办方提供的认证接口统一调用，禁止绕过 API 或私自调用第三方模型服务。

## 推荐实现方式

为提高系统的推理效率与可解释性，鼓励选手采用多智能体架构（Multi-Agent System）完成根因分析任务。

**典型组件可包括**：

- **Controller Agent**：控制流程、规划任务顺序
- **Tool Agent / Code Agent**：调用分析工具或执行脚本
- **Judge Agent**：判断是否已定位根因
- **Log/Trace/Metric Agent**：各类数据分析模块

> **注**：是否采用多智能体实现不会直接影响评分，评分仅基于提交结果中的字段内容进行评估。

## 明确禁止

| 违规行为 | 后果 |
|----------|------|
| 使用纯规则/脚本推理替代模型 | 准确率项记为 0 分 |
| 人工标注结果后提交 | 成绩取消 |
| 硬编码答案或组件结果 | 全部不得分 |
| 模型仅用于格式包装，不参与决策 | 视为无效使用 |

> **注**：上述"仅用于格式包装"的判定指未将大语言模型用于实际推理过程中的信息提取、因果判断或决策环节，仅将模型用于将已有答案包装为 JSON 格式等场景。
> 
> 系统中存在辅助模块（如规则过滤、指标选择等）并不视为违规，前提是模型在流程中实际参与了根因相关的分析与判断任务。

# FAQ

**2025 CCF国际AIOps挑战赛FAQ常见问题**：

## Q1: 是否必须使用多智能体架构？

**A1**: 没有限制。单模型方案（如 ReAct、Chain-of-Thought）亦可，只要能够生成结构化 reasoning_trace 且满足推理完整性要求即可。

## Q2: 模型可以使用外部知识或预设规则吗？

**A2**: 不可使用硬编码规则代替模型判断，但允许将 SOP、组件属性、故障类型等信息嵌入 prompt，前提是推理由 LLM 驱动。

## Q3: 是否可以使用缓存或预处理数据？

**A3**: 允许对原始监控数据进行预处理，但判断、决策、因果分析必须由 LLM 实时完成。

## Q4: 如果预测结果中多报了组件，会怎样处理？

**A4**: 当前评测仅采纳提交结果中的第一个根因（按 JSON 字段顺序），忽略后续条目。

## Q5: reasoning_trace 中是否可以合并多步为一步？

**A5**: 不建议。每步应保持"action–observation"结构，反映真实推理流程，否则会影响可解释性得分。

## Q7: 是否支持语言模型调用外部代码工具？

**A7**: 支持在执行代码模式下调用外部工具模块（如 Python 执行环境），但这些调用需由 LLM 决策控制，不能脱离语言模型主导。

## Q8: 可以使用外部知识库或训练数据优化模型吗？

**A8**: 允许在不违反公平性前提下使用公开资料和通用知识来增强模型推理能力，但需满足以下要求：

- ✅ 可使用通用公开数据集、行业技术文档等构建提示模板（prompt）或规则框架
- ✅ 如使用外部知识库，请在提交文档中注明来源与用途，供评委核查
- ❌ 严禁通过人工标注方式或硬编码答案绕过模型决策，否则视为违规处理