# 提交脚本使用指南

本指南介绍如何在竞赛中向评测服务器提交答案。该脚本允许您提交一个答案文件，并在操作成功时获得提交 ID。

## 环境要求

在开始之前，请确保您的系统已安装 Python 3。

## 脚本概览

脚本接受一个 JSON Lines 文件（`*.jsonl`），每行是一个单独的 JSON 对象，代表一个问题回答。

## 答案格式

字段说明如下：

| 字段名           | 类型         | 是否必须 | 说明                                                                           |
|----------------|------------|-------------|------------------------------------------------------------------------------|
| component      | string     | 是      | 根据组件的名称，每条样本只评估一个根组件；若提交多个组件，仅评估 JSON 中首个出现的 `component` 字段，类型需为 string。                   |
| reason         | string     | 是      | 故障发生的原因或类型。                                            |
| uuid           | string | 是      | 对应问题的 `uuid`                             |
| reasoning_trace | list   | 是      | 完整推理轨迹，每个推理包含 `step`,`action`,`observation` 三个字段，其中 `observation` 超过 100 字将被截断，仅保留前 100 字参与评分。                         |


**示例**

问题文件：
```
[
    {
        "uuid": "3xxxxx",
        "Anomaly Description": "The system experienced an anomaly from 2025-06-01T16:10:02Z to 2025-06-01T16:31:02Z. Please infer the possible cause."
    },
    {
        "uuid": "4xxxxx",
        "Anomaly Description": "Please analyze the abnormal event between 2025-06-02T17:10:04Z and 2025-06-02T17:33:04Z and provide the root cause."
    }
]
```
提交的答案文件：
```
{"uuid": "3xxxxx", "reason": "high cpu usage", "component": "checkoutservice", "reasoning_trace": [{"step":1, "action":"", "observation":""}]}
{"uuid": "4xxxxx", "reason": "high cpu usage", "component": "checkoutservice", "reasoning_trace": [{"step":1, "action":"", "observation":""}]}
```

注1：答案数量必须和问题保持一致，否则无法成功提交。

注2：答案中的uuid必须与问题的uuid一一对应，否则无法成功提交。

注3：答案的格式必须仅为`uuid`,`reason`,`component`,`reasoning_trace`四个字段，不能增加或缺失字段，类型也必须保持一致，否则无法成功提交。

注4：reasoning_trace 为包含多个 step 对象的数组，每个对象应包含以下字段：
- step：整数，表示推理步骤编号（从 1 开始）；
- action：字符串，描述该步调用或操作；
- observation：字符串，描述该步观察到的结果，建议控制在 100 字内；

## 命令行提交

要从命令行使用该脚本，请切换到该脚本所在目录，用 Python 运行该脚本：

```bash
python submit.py [-h] [-s SERVER] [-c CONTEST] [-k TICKET] [result_path]
```

* `[result_path]`：提交的结果文件路径。如果未指定，默认使用当前目录下的 `result.jsonl`。
* `-s, --server`：指定评测服务器的 URL。如果未提供，将使用脚本中定义的 `JUDGE_SERVER` 变量。
* `-c, --contest`：比赛标识。如果未提供，将使用脚本中定义的 `CONTEST` 变量。
* `-k, --ticket`：团队标识。如果未提供，将使用脚本中定义的 `TICKET` 变量。
* `-i, --submission_id`：提交标识。如果提供，脚本将查询本次提交的评测状态。

## 编程方式提交

您还可以将 `submit` 函数导入到您的 Python 代码中，以便用编程方式提交数据。


1. 导入函数：
    确保提交脚本位于您的项目目录或 Python 路径中。使用以下方式导入 submit 函数：

    ```python3
    from submit import submit
    ```

2. 调用 submit 函数：
    准备您的提交数据为字典列表，每个字典代表一个要提交的问题回答。调用 submit 函数：

    ```python3
    data = [
        {"uuid": "3xxxxx", "reason": "xxx", "component": "", "reasoning_trace": []}
        # 根据需要添加更多项
    ]

    submission_id = submit(data, judge_server='https://judge.aiops.cn', contest='YOUR_CONTEST_ID', ticket='YOUR_TEAM_TICKET')
    if submission_id:
        print("提交成功！提交 ID: ", submission_id)
    else:
        print("提交失败")
    ```
    
    在此示例中，请将 `YOUR_CONTEST_ID` 替换为您参加的**比赛ID**，将 `YOUR_TEAM_TICKET` 替换为您的**团队ID**。
    *  **比赛ID** 在比赛的URL中获得，比如"赛道一（Qwen1.5-14B）：基于检索增强的运维知识问答挑战赛"的URL为https://competition.aiops-challenge.com/home/competition/1771009908746010681 ，比赛ID为1771009908746010681
    *  **团队ID**需要在参加比赛并组队后能获得，具体在比赛详情页-> 团队 -> 团队ID，为一串数字标识。 

3. 调用 check_status 函数
    准备提交ID。调用 check_status 函数：

    ```python3
    submission_id = ""
    status = check_status(submission_id, judge_server='https://judge.aiops.cn', contest='YOUR_CONTEST_ID', ticket='YOUR_TEAM_TICKET')
    if status:
        submission_id = status.get('submission_id')
        score = status.get('score')
        create_time = status.get('create_time')
        judge_time = status.get('judge_time')

        if not judge_time: 
            print("Submission %s is still in queue." % submission_id)
        else:
            print("Submission %s score: %s" % (submission_id, score))
    else:
        print("Failed to check submission status.")
    ```

## 常见错误

1. 状态码 400，Invalid submission format

    提交的答案文件里，答案的字段和规定不符，请重新检查，须严格满足以下要求：

    ```
    uuid: str
    reason: str
    component: str
    reasoning_trace: list
    ```

2. 状态码 400，Submission length mismatch

    提交的答案文件长度和问题长度不匹配。

3. 状态码 400，Submission UUID invalid

    提交的答案文件里，答案uuid和问题uuid没有一一对应。

4. 状态码 401，Ticket not provided

    没有提供团队ID。

5. 状态码 401，Invalid ticket

    提供的团队ID不存在。

6. 状态码 401，Contest not provided

    没有提供比赛ID。

7. 状态码 401，Invalid contest

    提供的比赛ID不存在。

8. 状态码 401，Submission ID not provided

    查询提交状态时，没有提供submission ID。

9. 状态码 403， Quota exceeded

    提交次数超过限额。

10. 状态码 404，Submission not found

    没有找到对应的提交记录。

11. 状态码 429，Too many requests

    提交过于频繁。
