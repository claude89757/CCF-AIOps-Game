# 赛题答案提交说明

参赛者需使用主办方提供的 Python 提交流程脚本，具体流程可访问以下仓库查看：
https://www.aiops.cn/gitlab/aiops-live-benchmark/aiopschallenge2025-submission/-/tree/main

提交的核心输出为 `answer.json` 文件，包含所有待评估任务的推理结果。提交内容需通过容器构建环境复现，确保可在评委本地复现评分。

## 输出稳定性要求

鉴于赛题需使用大语言模型完成自动推理，为确保结果的可复现性，选手有责任控制模型输出的稳定性，避免由于温度参数设置不当或缺乏固定随机种子等原因造成结果随机波动。若多次运行同一推理流程输出结果不一致，主办方有权要求选手解释差异来源。如被认定为未做有效控制或存在显著漂移，可能视为不符合提交规范，影响评审结果或晋级资格。

**建议：**

- 设置 `temperature=0` 或较低值
- 明确使用的 prompt 模板、固定参数
- 对可能含随机采样的组件进行显式控制或缓存机制设计

## 提交轮次数限制说明

比赛平台支持多轮答题结果（`answer.json`）提交，但仅以选手最后一次提交的答案为准参与最终评审与排名。

为保障平台资源与评审效率，每支队伍的提交次数每日限制为 **10次**，总共提交次数上限为 **350次**。超过限制将不再接受新提交，届时以最后一次提交为准进行评分和排名。

答案提交后不可撤回，请选手确认无误后提交，并确保其可通过后续代码流程正确复现。

---

# 选手代码评审说明

为了保证复现环境的一致性，我们使用 Docker 对选手的代码进行复现，要求如下：

## 复现流程

我们会根据选手提交的压缩包以及启动指令在本地进行镜像的构建，然后运行答案生成过程。具体来说复现时评委会运行选手给出的 `run.sh` 文件，在经过镜像构建和回答生成后，最终会得到一个名为 `answer.json` 的答案文件。

## 答案一致性审查

为确保提交结果的真实性与公平性，主办方将通过选手提交的代码与运行环境对 `answer.json` 的生成过程进行审查。

我们将对选手提交的代码执行流程与最终提交结果进行比对，验证 `answer.json` 是否由所提供流程自动生成。如果发现复现实验生成的结果与正式提交结果差异显著，**该提交将被判定为无效代码，取消晋级资格**。

建议选手避免通过手工构造或脱离流程的方式生成 `answer.json`，确保所有逻辑均可通过 `run.sh` 和容器内代码自动复现。

## 代码提交格式要求

### 1. 打包要求

将包含 Dockerfile 和启动复现环境的 shell 脚本打包为 zip 格式，并命名为 **"队伍名称+队长手机号"**

### 2. 上传方式

将打包好的压缩包上传到给定的网盘地址

**云盘链接：** [提交地址后续更新]

### 3. 目录结构

最终的压缩包内结构如下：

```
teamname-phone.zip
├── README.md        # 代码文档
├── domain.conf      # 需要访问的外网域名及对应域名的功能
├── src/             # 复现需要代码等
├── data/            # 使用到的数据文件/数据集
├── Dockerfile       # 用于构建Docker镜像
└── run.sh           # 构建和启动docker使用的命令
```

> **特别注意：** 代码文档中需要包含复现过程中可能会遇到的问题以及解决方案

### 4. 参考示例

可参考以下仓库查看提交样例及运行模板：
[提交Demo仓库占位链接] (待补充)

## 特别说明

- 所有推理过程需由语言模型实际参与生成，**禁止仅用脚本包装答案**
- 提交中如存在外部调用需求，需在 `domain.conf` 中说明
- **评审过程中若无法复现 `answer.json`，该提交将视为无效**