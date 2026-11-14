# 部署与维护

此版本在 GitHub Actions 中运行，每天北京时间 08:17 发送，08:47 补跑。GitHub 的定时任务可能延迟。发送成功后记录日期，补跑会跳过当天已发送的邮件。

## 邮箱配置

在仓库的 Settings → Secrets and variables → Actions 中设置：

| Secret | 内容 |
| --- | --- |
| `SMTP_USERNAME` | 发信邮箱地址 |
| `SMTP_PASSWORD` | 邮箱的 SMTP 授权码或应用专用密码 |
| `SMTP_TO` | 收件邮箱地址 |

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

个性化筛选还会使用 GitHub 官方搜索接口补充领域项目，使用工作流自动提供的 GitHub 令牌，无需另购 AI 接口。热榜收集与领域搜索分别标注来源，只有热榜提供时才显示当天新增星标。

## 修改兴趣

编辑 [config/interests.json](config/interests.json) 中的类别、关键词、搜索条件和数量限制。语言条件只影响热榜候选；兴趣类别决定项目的相关性和邮件分组。

默认关注 AI 科研工具、大模型与开发工具、视觉与三维、机器人与仿真、硬件与嵌入式、精密测量等方向。邮件展示筛选理由；项目说明保留来源原文。

## 首次运行与故障排查

1. 打开 Actions → GitHub Trending Email → Run workflow，保留 `preview_only=true`。此操作生成预览，不需要 SMTP 授权码。
2. 在成功运行的 Artifacts 中下载 `digest-preview`，查看邮件内容。
3. 配好邮箱 Secrets 后，以 `preview_only=false` 运行一次，检查发信结果和收件箱。
4. 将 `DIGEST_ENABLED` 改为 `true`，启用每日发送。

只有发送成功后才更新当天记录和项目去重记录。预览不会改变记录。默认七天内已发送的项目不重复推荐；`force_send=true` 可强制当天再次发送，但仍按兴趣和去重规则筛选。

某个外部来源暂时不可用时，会尽量使用其余来源并在邮件中说明。如果没有筛选出相关 GitHub 项目，任务会失败，避免发送空日报。失败时可查看 Actions 日志中的错误，再手动预览或补发。

GitHub 对长期没有活动的公开仓库可能暂停定时工作流，收到停用通知后需要在 Actions 页面重新启用。每天成功发送产生的记录提交也能帮助保持仓库活动。
