# AI 科研与工程生产力日报

基于 [Talljack/github-trending-email](https://github.com/Talljack/github-trending-email) 的个人部署，重点发现能提高科研效率和工程生产力的 AI 开源项目。

## 关注方向

- AI / 大模型、编程助手、Agent Skills、MCP、插件与科研工作流。
- 计算机视觉、匹配、导航、三维重建与生成。
- 具身智能、机器人、无人机与仿真。
- Unreal Engine、Blender、动画、CAD / SolidWorks 与三维设计工具。
- FPGA、芯片与电路设计、嵌入式软硬件、光电和精密信号测量工具。
- 深空探测引擎、地月火星与行星地形场景、多模态传感器和合成数据集、航天器与轨道动力学仿真；包括 Cesium、AirSim / ProjectAirSim、Basilisk、GMAT 及相关插件。

GitHub 热榜与领域搜索先筛出候选项目，再由硅基流动的 `deepseek-ai/DeepSeek-V4.1-Flash` 阅读项目 README 和仓库内文档片段，判断对科研工作的实际用途。每个项目先用一两句中文介绍具体功能，再说明科研接入方式、使用条件、局限和可核对的原文依据，同时附少量相关论文、模型与科技新闻。

这是根据文档进行分析，不代表已经安装或运行验证项目。论文、模型、新闻栏目仍依据来源元数据筛选，保留原文。

## 每日推送

- 计划北京时间 **08:17** 运行，**08:47** 备用检查；GitHub Actions 调度可能延迟。
- 九个项目分组各最多 5 项，合计最多 45 个项目；论文、模型、新闻栏目也各最多 5 条。数量是上限，不设最低条数，缺少合适内容的分组可为空。
- 先按兴趣相关性、热度与活跃度粗筛最多 90 个项目，交替阅读不同领域的文档，再按科研价值筛选。项目须通过文档引用校验、模型判定适合且相关性评分至少 70；宁缺毋滥，不用边缘项目填满名额。
- 读取的仓库资料和研究兴趣配置会提交给硅基流动分析。模型接口密钥单独保存在 GitHub Secrets，不进入代码、邮件或文档。
- 最近 7 天已发项目不重复推荐。发送成功后才保存记录；预览不会影响下次推送。
- 手机与桌面邮箱均可阅读，发送与收件地址保存在 GitHub Secrets 中。
- 长邮件会省去重复的证据引文文字，保留全部项目简介、使用条件和可点击的文档依据。

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
