# NextTest — 下一次先试什么

NextTest 是一个面向有限试验预算的**实验决策智能体工作台**：它用已知记录训练轻量模型，从尚未揭示结果的历史方案中提出下一次验证建议；用户确认后，系统才揭示这条历史实测值并更新模型。示例使用公开的 UCI 混凝土抗压强度数据，固定 28 天龄期。

主界面是 React + Three.js 本地工作台，由 FastAPI 提供页面与固定 schema API；支持研究/科普双模式、数据坞、策略观测台、只读项目库、证据包和科研智能体。

## 当前可做的事

- 在桌面工作台查看 252 条**已知训练记录**；三维图不含待选方案或独立留出集的真实强度。
- 导入自己的本地 CSV，检查字段和常见质量问题，确认后保存只读数据档案。
- 从三种探索方法中选择下一组历史配方：随机对照、预测最优、模型分歧最大。
- 先查看推荐与预测，再确认揭示该条历史实测；每次操作保留独立记录，可用项目编号只读恢复，并导出 Markdown/JSON 证据摘要。
- 使用 Strategy Observatory 查看固定种子的配对历史回放；使用 Run Matrix 查看状态、预算和失败单元。
- 查看固定数据切分：252 条训练、89 条待选历史方案、84 条独立留出。

## 可选证据助手

科研智能体是**只读解释层**，支持本地规则解释与 DeepSeek 公开证据解释，不参与推荐、排序、训练、阈值或记录修改：

- 只读取当前候选、已经揭示的历史记录、公开计数和公开 SHA。
- 不读取待揭示 candidate target、独立 test 标签、原始 CSV 全量、任意路径、环境变量或 API Key。
- 默认使用本地规则解释，核心流程无需联网；配置有效 Key 后自动使用 `deepseek-chat` 解释公开证据。
- 返回固定 `disclaimer`：`AI 解释，不是新增科研证据`。
- 模型回答最多 350 汉字；不用于产生新数据、显著性、因果、成本节省或工业有效性结论。

配置只从环境变量读取：

```text
NEXTEST_LLM_PROVIDER=deepseek
NEXTEST_LLM_BASE_URL=https://api.deepseek.com
NEXTEST_LLM_MODEL=deepseek-chat
NEXTEST_LLM_API_KEY=
```

在启动服务的 shell 中设置这些变量；可参考 `.env.example`，真实 `.env` 不进入版本控制。默认配置下所有本地功能照常工作。

## 可核验答辩证据包

已通过只读审计的 `p2_` / `p3_` 项目可以导出确定性证据包：

```text
GET /api/projects/{project_id}/evidence-package
GET /api/custom/projects/{project_id}/evidence-package
```

证据包只包含公开数据集元数据、公开快照/审计摘要、已揭示历史、确定性防御摘要和固定限制；不包含 pending target、test 标签、原始 CSV、路径、环境变量、API Key、完整事件或原始 audit 文件。审计失败时不返回部分包。格式与哈希定义见 [EVIDENCE_PACKAGE_CONTRACT.md](docs/EVIDENCE_PACKAGE_CONTRACT.md)。

## 只读项目证据库

项目库是**只读项目索引与可比性检查**。它列出已通过只读审计的 `p2_` / `p3_` 项目，并支持成对检查是否使用相同 source/split：

```text
GET  /api/library
GET  /api/library/{project_id}/card
POST /api/library/compare
```

项目库提供项目卡片和成对可比性说明，展示各自公开的 revealed_count/MAE/max_error 与数据边界；适合项目复盘和证据审查。格式见 [PROJECT_LIBRARY_CONTRACT.md](docs/PROJECT_LIBRARY_CONTRACT.md)。

## 启动（Windows PowerShell）

首次使用请直接看 [Windows 一键启动](docs/WINDOWS_QUICKSTART.md)。下载、首次安装和功能入口见 [下载与使用说明](docs/DOWNLOAD_AND_USE_CN.md)。

在仓库根目录运行：

```powershell
python -m pip install -r requirements-web.txt
python -m pip install -r requirements-compute.txt
python scripts/start_nexttest.py
```

服务只绑定本机 `127.0.0.1`，自动选择可用端口并打开实际地址。首次载入三维图和首次创建回放项目可能需要数秒。

前端源码开发（可选）：

```powershell
cd frontend
npm ci
npm run build
```

## 测试

在仓库根目录运行：

```powershell
python -m pytest -q tests/test_nexttest_project_library.py tests/test_nexttest_evidence_package.py tests/test_nexttest_llm_copilot.py tests/test_nexttest_web_api.py tests/test_nexttest_ui_worker.py tests/test_nexttest_p1_core.py tests/test_nexttest_p2_experiment_loop.py --basetemp=artifacts/nexttest_web_pytest
```

测试覆盖本地规则、mock transport、证据包和项目库只读路径；真实 DeepSeek 调用单独验收。

## 适用场景

NextTest 适合有限预算的历史数据回放、实验决策教学、科研流程审查与公众科普。系统把候选、预测、证据状态和审计信息放在同一工作台，支持项目复盘、团队讨论和“观察—比较—锁定—揭示—更新”的完整演示。用于真实实验时，由领域专家结合实验条件复核。

## 结果解释

- 历史回放展示已有记录，候选推荐、预测和模型分歧均来自固定数据与确定性计算。
- 证据包、项目库和 SHA 摘要用于软件完整性、可复核性和项目复盘。
- 科研智能体只解释白名单公开证据；科研数字由本地引擎生成。
- 研究/科普双模式共享同一事实源，专业审查与公众理解使用同一套候选和证据。

## GitHub 公开版

公开提交范围、数据来源和发布前检查见 [GITHUB_RELEASE_CHECKLIST.md](docs/GITHUB_RELEASE_CHECKLIST.md)。公开发布操作步骤见 [PUBLIC_RELEASE_RUNBOOK.md](docs/PUBLIC_RELEASE_RUNBOOK.md)。最终验收记录见 [FINAL_RELEASE_REPORT.md](docs/FINAL_RELEASE_REPORT.md)。仓库不包含数据副本、运行记录、环境或密钥。

## 版权与使用

Copyright © 2026 Wu Yetao. All rights reserved.

本仓库用于项目展示、学术交流与竞赛评审。未经作者书面许可，不得复制、修改、再发布、商业使用或将本项目及其衍生版本用于其他竞赛申报。

第三方依赖分别遵循其原始许可证。本声明不改变第三方组件的许可条件。

## 验证

```powershell
python -m pytest -q tests/test_nexttest_llm_copilot.py tests/test_nexttest_web_api.py tests/test_nexttest_ui_worker.py --basetemp=artifacts/nexttest_web_pytest
```

竞赛定位与提交注意事项见 [contest_fit_2026.md](docs/contest_fit_2026.md)。
