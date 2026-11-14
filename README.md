# AI 科研与工程生产力日报

基于 [Talljack/github-trending-email](https://github.com/Talljack/github-trending-email) 的个人部署，重点发现能提高科研效率和工程生产力的 AI 开源项目。

## 关注方向

- AI / 大模型、编程助手、Agent Skills、MCP、插件与科研工作流。
- 计算机视觉、匹配、导航、三维重建与生成。
- 具身智能、机器人、无人机与仿真。
- Unreal Engine、Blender、动画、CAD / SolidWorks 与三维设计工具。
- FPGA、芯片与电路设计、嵌入式软硬件、光电和精密信号测量工具。

GitHub 热榜与领域搜索结果一起筛选。每封邮件按方向分组，给出项目来源、简介和匹配原因，同时附少量相关论文、模型与科技新闻。规则匹配保留来源原文，不依赖额外的大模型 API 密钥。

## 每日推送

- 计划北京时间 **08:17** 运行，**08:47** 备用检查；GitHub Actions 调度可能延迟。
- 每封最多 18 个项目、5 篇论文、4 个模型、5 条新闻，实际以相关内容为准。
- 项目按兴趣相关性、热度与活跃度筛选，并为不同研究方向保留名额。
- 最近 7 天已发项目不重复推荐。发送成功后才保存记录；预览不会影响下次推送。
- 手机与桌面邮箱均可阅读，发送与收件地址保存在 GitHub Secrets 中。

## 调整兴趣

编辑 [config/interests.json](config/interests.json) 可以修改关键词、主题、搜索条件和分组名额。邮箱、可选来源等设置见 [部署说明](DEPLOYMENT.md)。

本部署保留上游采集功能，并增加领域搜索、相关性筛选、中文分组、安全预览和通用 SMTP 配置。原项目说明请查看[上游 README](https://github.com/Talljack/github-trending-email#readme)。

## 手动预览与发送

在 **Actions → GitHub Trending Email → Run workflow** 中：

- `preview_only=true`：只生成 `digest-preview` 预览文件，不发邮件。
- `preview_only=false`：发送到配置好的收件邮箱。
- `force_send=true`：允许同一天再次发送，通常保持关闭。

每日自动发送由仓库变量 `DIGEST_ENABLED=true` 启用。首次部署先运行预览和一次发送验证。

## 验证

```text
python -m unittest discover -s tests -p "test_*.py"
```

来源：GitHub Trending / GitHub Search API、Hugging Face、Hacker News。部分可选来源暂时不可用时，邮件会简短说明。

MIT License。原项目版权与许可见 [LICENSE](LICENSE)。
