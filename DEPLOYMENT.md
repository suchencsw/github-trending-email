# 部署与维护

此版本在 GitHub Actions 中运行，每天北京时间 08:17 发送，08:47 补跑。GitHub 的定时任务可能延迟。发送成功后记录日期，补跑会跳过当天已发送的邮件。

## 邮箱配置

在仓库的 Settings → Secrets and variables → Actions 中设置：

| Secret | 内容 |
| --- | --- |
| `SMTP_USERNAME` | 发信邮箱地址 |
| `SMTP_PASSWORD` | 邮箱的 SMTP 授权码或应用专用密码 |
| `SMTP_TO` | 收件邮箱地址 |
| `SILICONFLOW_API_KEY` | 硅基流动模型接口密钥 |

QQ 邮箱使用 `smtp.qq.com`、端口 `465`、`SMTP_SSL=true`、`SMTP_STARTTLS=false`。授权码需要先在 QQ 邮箱设置中开启 SMTP 服务后生成，不能使用邮箱登录密码。邮箱地址与凭据均保存在 Secrets 中。

## 定时任务与数据来源

在同一设置页面的 Variables 中配置：

| Variable | 当前配置或默认值 | 用途 |
| --- | --- | --- |
| `DIGEST_ENABLED` | `false`，首次发送测试成功后改为 `true` | 开启每天自动发送 |
| `SMTP_HOST` | 当前为 `smtp.qq.com` | 发信服务器；代码默认 `smtp.gmail.com` |
| `SMTP_PORT` | `465` | SMTP 端口 |
| `SMTP_SSL` | `true` | 启用直接 TLS 连接 |
| `SMTP_STARTTLS` | `false` | 需要 STARTTLS 的服务商才开启，同时关闭 SMTP_SSL |
| `DIGEST_LANGUAGES` | `[]` | GitHub 热榜的语言范围；例如 `["python","c++"]`，空列表表示全部 |
| `DIGEST_DATE_RANGE` | `daily` | GitHub 热榜周期：daily / weekly / monthly |
| `ENABLE_HUGGINGFACE` | `true` | 收集模型 |
| `ENABLE_HACKER_NEWS` | `true` | 收集技术新闻 |
| `ENABLE_AI_PAPERS` | `true` | 收集论文 |
| `ENABLE_DEV_TO` | `false` | 原项目的 Dev.to 来源 |
| `DIGEST_ITEM_LIMIT` | 当前为 `20` | 原项目各可选来源的候选数；最终数量由兴趣配置限制 |
| `LLM_MODEL` | `deepseek-ai/DeepSeek-V4.1-Flash` | 硅基流动中用于项目分析的模型 |

个性化筛选使用 GitHub 官方搜索接口补充领域项目，使用工作流自动提供的 GitHub 令牌。热榜收集与领域搜索分别标注来源，只有热榜提供时才显示当天新增星标。

## 大模型阅读与筛选

工作流先按每个领域的名额加倍粗筛，九组各最多 10 个候选，合计最多 90 个；交替读取不同领域的公开 README 和仓库内相关文档片段，交给硅基流动分析。读取内容有长度限制，未阅读整个工程，也不安装、执行项目代码。

模型先用一两句中文介绍项目功能，再结合研究兴趣给出科研接入方式、条件与限制，并引用实际读取文档中的原文。最终每组最多 5 项，九组合计最多 45 项；模型须判定适合且相关性评分至少 70，无法验证文档引用的项目不会入选。没有最低条数，不为填满名额降低标准。论文、模型和新闻栏目仍由元数据筛选，各最多 5 条。

`scripts/summarize_papers.py` 在项目筛选后用同一硅基流动模型整理论文中文摘要解读，写入 `output/digest.json` 供邮件使用。输入为原题与来源提供的摘要（最多 8000 字符），不下载全文；正文简要介绍研究问题、方法与作者报告的结果，不补造实验结论。缺少摘要时注明仅标题概述；失败显示中文提示和原文链接。原题、作者、日期与链接保留，模型和新闻的介绍暂保留原文。每期至多调用 5 篇，最多 2 并发、输出有长度上限，按原题、摘要、模型和兴趣配置缓存 7 天；使用现有 `SILICONFLOW_API_KEY`，不需要新增密钥。

模型接口遵循硅基流动官方地址 `https://api.siliconflow.cn/v1/chat/completions`，使用 `SILICONFLOW_API_KEY`。公开项目资料与兴趣配置会发送给该服务，不发送邮箱凭据或 GitHub 令牌。模型不能调用工具或执行仓库中的指令。

分析缓存通过 GitHub Actions Cache 保存，文档内容、模型或兴趣配置改变时重新分析；缓存最长复用 7 天。预览也可能产生模型用量。每个项目有输入长度和输出 token 限制，最多并发 2 个分析；精确费用以硅基流动账单为准。

部分项目分析失败时，仅从成功分析的项目中选取；所有分析失败或没有合适项目则任务中止。邮件中的文档分析不能替代实际运行验证。

## 修改兴趣

编辑 [config/interests.json](config/interests.json) 中的类别、关键词、搜索条件和数量限制。语言条件只影响热榜候选；兴趣类别决定项目的相关性和邮件分组。

默认设九个项目分组：科研效率与知识工具；AI 编程、Skills、MCP 与插件；大模型、多模态与推理；视觉、导航与三维；具身智能、机器人与无人机；Blender、UE、CAD 与仿真；FPGA、电路芯片与嵌入式；光电、精密测量与信号；深空探测与多模态仿真。最后一组关注 Cesium 类地月火星/地形场景、AirSim / ProjectAirSim 类传感器与多模态数据集，以及 Basilisk、GMAT 类航天器与轨道动力学仿真。通用工具只说明文档支持的可复用能力，不把潜在用途当成已有深空功能。`researchGoal` 描述实际研究用途偏好；邮件展示文档分析和来源依据。

## 首次运行与故障排查

1. 配置 `SILICONFLOW_API_KEY`。打开 Actions → GitHub Trending Email → Run workflow，保留 `preview_only=true`。此操作生成预览，不需要 SMTP 授权码，但会按需调用模型。
2. 在成功运行的 Artifacts 中下载 `digest-preview`，查看邮件内容。
3. 配好邮箱 Secrets 后，以 `preview_only=false` 运行一次，检查发信结果和收件箱。
4. 将 `DIGEST_ENABLED` 改为 `true`，启用每日发送。

只有发送成功后才更新当天记录和项目去重记录。预览不会改变记录。默认七天内已发送的项目不重复推荐；`force_send=true` 可强制当天再次发送，但仍按兴趣和去重规则筛选。

某个外部来源暂时不可用时，会尽量使用其余来源并在邮件中说明。如果没有筛选出相关 GitHub 项目，任务会失败，避免发送空日报。失败时可查看 Actions 日志中的错误，再手动预览或补发。

GitHub 对长期没有活动的公开仓库可能暂停定时工作流，收到停用通知后需要在 Actions 页面重新启用。每天成功发送产生的记录提交也能帮助保持仓库活动。
