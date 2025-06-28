数据地址: https://www.aiops.cn/gitlab/aiops-live-benchmark/phaseone/

# 下载归档及完整性校验

本项目包含以下压缩包文件及其 MD5 校验和：

| 文件名                 | MD5 校验和                           |
|-----------------------|--------------------------------------|
| `2025-06-06.tar.gz`   | `214fd850d7b4b42ad2ac713c43133e54`   |
| `2025-06-07.tar.gz`   | `cb57089278ee99f3b83dfa9da19d6e1f`   |
| …                     | …                                    |

可以直接下载本目录下的 [`checksums.md5`](./checksums.md5) 来验证。

## 验证方法

1. 从 Git 仓库 clone 或下载文件：
   ```bash
   git clone https://your.repo.url.git
   cd your-repo
   ```

2. 运行校验命令
   ```bash
   md5sum -c checksums.md5
   ```
   
   如果输出类似：
   ```
   2025-06-06.tar.gz: OK
   2025-06-07.tar.gz: OK
   ```
   说明下载完整且未被篡改。

# 温馨提示

数据文件名中含有的时间为 CST 时区，如 `log_filebeat-server_2025-06-06_00-00-00.parquet` 中的时间，表示北京时间2025年6月6号零点零分。

日志数据中的时间格式为 `2025-06-05T16:00:29.045Z`，为 UTC 时区，表示北京时间2025年6月6号零点零分。

指标数据中的时间格式为 `2025-06-05T16:00:00Z `，为 UTC 时区，表示北京时间2025年6月6号零点零分。

调用链数据中 `startTimeMillis` 的时间格式为 `1749139200377`，为时间戳，单位毫秒。
