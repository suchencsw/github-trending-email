# AI 科研与工程生产力日报

基于 [Talljack/github-trending-email](https://github.com/Talljack/github-trending-email) 的个人部署，重点发现能提高科研效率和工程生产力的 AI 开源项目。

## 关注方向

- AI / 大模型、编程助手、Agent Skills、MCP、插件与科研工作流。
- 计算机视觉、匹配、导航、三维重建与生成。
- 具身智能、机器人、无人机与仿真。
- Unreal Engine、Blender、动画、CAD / SolidWorks 与三维设计工具。
- FPGA、芯片与电路设计、嵌入式软硬件、光电和精密信号测量工具。

GitHub 热榜与领域搜索先筛出候选项目，再由硅基流动的 `deepseek-ai/DeepSeek-V4.1-Flash` 阅读项目 README 和仓库内文档，判断对科研工作的实际用途。每封邮件按方向分组，展示中文用途、科研接入方式、使用条件、局限和可核对的原文依据，同时附少量相关论文、模型与科技新闻。

这是根据文档进行分析，不代表已经安装或运行验证项目。论文、模型、新闻栏目仍依据来源元数据筛选，保留原文。

## 每日推送

- 计划北京时间 **08:17** 运行，**08:47** 备用检查；GitHub Actions 调度可能延迟。
- 每封最多 18 个项目、5 篇论文、4 个模型、5 条新闻，实际以相关内容为准。
- 先按兴趣相关性、热度与活跃度粗筛最多 36 个项目，再阅读文档并按科研价值筛选，为不同研究方向保留名额；不会为凑数量保留模型判为不合适的项目。
- 读取的仓库资料和研究兴趣配置会提交给硅基流动分析。模型接口密钥单独保存在 GitHub Secrets，不进入代码、邮件或文档。
- 最近 7 天已发项目不重复推荐。发送成功后才保存记录；预览不会影响下次推送。
- 手机与桌面邮箱均可阅读，发送与收件地址保存在 GitHub Secrets 中。

## 调整兴趣

编辑 [config/interests.json](config/interests.json) 可以修改关键词、主题、搜索条件和分组名额。邮箱、可选来源等设置见 [部署说明](DEPLOYMENT.md)。

本部署保留上游采集功能，并增加领域搜索、大模型文档分析、中文分组、安全预览和通用 SMTP 配置。原项目说明请查看[上游 README](https://github.com/Talljack/github-trending-email#readme)。

## 手动预览与发送

在 **Actions → GitHub Trending Email → Run workflow** 中：

- `preview_only=true`：只生成 `digest-preview` 预览文件，不发邮件。
- `preview_only=false`：发送到配置好的收件邮箱。
- `force_send=true`：允许同一天再次发送，通常保持关闭。

每日自动发送由仓库变量 `DIGEST_ENABLED=true` 启用。首次部署先运行预览和一次发送验证。

预览也会调用模型接口。相同文档、模型和兴趣配置的分析结果可缓存复用，减少重复调用。模型失败时不会把关键词初筛伪装成 AI 分析；所有模型分析失败或没有合适项目时停止发送。

## 验证

```text
python -m unittest discover -s tests -p "test_*.py"
```

来源：GitHub Trending / GitHub Search API、Hugging Face、Hacker News。部分可选来源暂时不可用时，邮件会简短说明。

MIT License。原项目版权与许可见 [LICENSE](LICENSE)。
