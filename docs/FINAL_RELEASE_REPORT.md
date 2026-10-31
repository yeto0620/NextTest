# NextTest V3 最终交付报告

## 1. 产品定位

NextTest 是一个面向有限试验预算的**历史数据回放平台**：用已知记录训练轻量模型，从尚未揭示结果的历史方案中提出下一次验证建议；用户确认后才揭示历史实测值并更新判断。

它不是新物理实验平台、自动实验室、工业部署系统或临床工具，也不是已经打包好的 Tauri/Electron 桌面应用。

## 2. 已完成核心功能

- 研究 / 科普双模式，入口、导航、默认工作区、组件和信息密度均不同。
- 历史回放闭环：候选选择、预测封存、人工确认、单条历史揭示、模型更新、事件记录、只读恢复。
- Data Dock 本地数据入舱：字段角色、显示名、单位、质量警告、数据闸门和只读数据护照。
- Strategy Observatory：固定协议下的三策略、固定 seeds、公平约束、Run Matrix、审计和比较包。
- 项目库与可比性检查：只读项目索引、项目卡片、source/split 可比性检查。
- 证据包：确定性 JSON/Markdown、公开 SHA、已揭示历史和防御摘要。
- 科研智能体：本地规则优先，DeepSeek 只解释白名单公开证据，不参与选点、排序、训练或生成科研数字。
- 一键本地 Web 启动、doctor、公开门禁和 CI 合同测试。

## 3. 研究 / 科普模式差异

### 研究模式（默认）

- 初始 `mode = research`；初始 `viewMode = table`；刷新后仍以研究模式进入。
- 顶栏：`观测 / 候选 / 实验 / 策略 / 证据 / 档案 / 数据`。
- 默认显示 `ResearchCockpit` 和候选表格，研究专属入口包括科研智能体、数据坞、项目库、策略比较、证据审计。
- 控制量完整，research density 样式生效；说明通过标题、tooltip、drawer 或展开区承载，默认页面不展开大段解释。

### 科普模式

- 顶栏：`导览 / 航图 / 体验 / 故事`。
- 默认切换到导览叙事，使用 `MissionDeck`、引导抽屉和演示模式。
- 保留教学解释、步骤化和简化控制量；隐藏研究专属的智能体、数据坞、项目库、完整审计入口。
- 两个模式共享同一事实源、同一候选选择和同一历史回放状态，但组件、导航、默认工作区和展示密度明显不同。

浏览器实测：初始研究模式、研究 7 个导航、科普 4 个导航；刷新后仍为研究模式；研究/科普无横向溢出；console errors 为空。

## 4. 历史回放闭环

固定数据切分 → 候选推荐 → 保存预测 → 用户确认 → 揭示单条历史实测 → 更新模型 → 写入审计事件。历史 target、test 标签和原始 CSV 不进入前端或模型上下文。

## 5. 数据坞

本地 CSV 导入、编码/重复列/缺失/泄漏检查、字段角色、单位、质量确认、冻结数据护照和只读数据集。用户数据只在本机处理。

## 6. 策略比较

同一数据、切分、模型 seed 和预算下比较 random、greedy_prediction、max_disagreement；固定 seeds 使用 3 × 10 × 2 的 Evidence Run。该比较是描述性历史回放，不是新实验，不做策略排名。

## 7. 项目库

`GET /api/library`、项目卡片和 `POST /api/library/compare`；只读、稳定排序、最多 100 项、审计失败 fail-closed。可比性只区分 same source+split、same dataset 不同 split、不同 dataset 和 audit failed。

## 8. 证据包

`schema_version = nexttest_evidence_package_v1`。只包含公开数据集元数据、公开快照/审计摘要、已揭示历史、确定性 defense_brief、固定 limitations、payload SHA 和 Markdown。不含 pending target、test 标签、原始 CSV、路径、环境变量、Key、完整事件或原始 audit。

## 9. 科研智能体

- 无有效 Key：`local_rules`，本地证据解释仍可用，不发起网络请求。
- 有有效 Key：`deepseek-chat`，只解释白名单公开证据。
- LLM 不参与推荐、排序、训练、阈值或记录修改；证据不足时明确说不足；失败 fail-closed。
- 浏览器实测无 Key 时显示“本地引擎可用”，没有假装 DeepSeek 已连接。

## 10. DeepSeek 永久配置机制

- `configure_nexttest_llm.cmd` → `scripts/configure_nexttest_llm.ps1`。
- 输入使用 `Read-Host -AsSecureString` 遮罩。
- 先向 DeepSeek 做最小验证，只有 HTTP 200 才覆盖凭据。
- 401/402/网络错误或非 200 时不覆盖旧文件。
- 使用 Windows current-user DPAPI 加密，写入 `%LOCALAPPDATA%\NextTest\secrets\deepseek.key`，在仓库外。
- `start_nexttest_with_llm.cmd` 支持 `-Port`、`-NoBrowser`，启动时解密到当前进程环境，退出后清理环境变量和 BSTR/明文引用，不打印 Key。

### 当前真实状态

**当前 DPAPI 凭据已通过 HTTP 200 验证。** 直接验证返回 200，随后启动本地服务并调用 `POST /api/copilot/explain`，返回：

```text
provider=deepseek
model=deepseek-chat
disclaimer=AI 解释，不是新增科研证据
answer_length=83
```

回答内容只解释公开证据和历史回放边界，没有输出、记录或提交 Key。真实 DeepSeek 解释链路已验收通过。

如果 Key 被撤销或过期，配置器不会覆盖旧文件；重新运行：

```text
configure_nexttest_llm.cmd
```

有效后使用：

```text
start_nexttest_with_llm.cmd
```

## 11. 一键启动

- 无 LLM：双击 `start_nexttest.cmd`，本地 Web 工作台在 `127.0.0.1:8501–8510` 打开。
- 有 DPAPI Key：双击 `start_nexttest_with_llm.cmd`。
- 启动前执行只读 doctor；缺前端构建、依赖、端口或 Key 配置时明确失败。
- 不称其为原生桌面应用；Tauri/Electron 不作为本次交付。

## 12. 测试与浏览器结果

```text
python -m pytest -q tests/test_nexttest_llm_copilot.py `
  tests/test_nexttest_web_api.py tests/test_nexttest_ui_worker.py `
  tests/test_nexttest_p2_ui_contract.py tests/test_nexttest_p3_ui_contract.py `
  tests/test_nexttest_p4a_ui_contract.py tests/test_nexttest_project_library.py `
  tests/test_nexttest_evidence_package.py tests/test_nexttest_public_release.py `
  tests/test_nexttest_desktop_readiness.py tests/test_nexttest_ui_mode_closure.py

80 passed
```

```text
cd frontend
npm run build
exit 0，2171 modules transformed
```

```text
python scripts/nexttest_doctor.py --check
exit 0，ready_to_launch=true

python scripts/verify_public_release.py --check
exit 0，release_ready=true
```

浏览器检查：

- 1280 / 1440 / 1920 宽度均无横向溢出。
- 首屏默认研究模式；刷新后仍为研究模式。
- 研究导航 7 项；科普导航 4 项。
- 研究/科普组件和结构不同，不是只换文案。
- 科研智能体无 Key 时显示本地解释。
- console errors = `[]`。
- 页面无 `None` / `undefined`。
- 所有禁用按钮均有可见原因（例如未创建项目时“导出当前项目”禁用并显示 title）。

## 13. Git 提交状态

- 本地代码提交 SHA：`f4de1ac47069756f6646ffeaa8f590ca61d0c7ad`
- commit message：`feat: complete NextTest research-first competition release`
- remote：`https://github.com/yeto0620/NextTest.git`
- 已推送分支：`main`
- 推送时远端 HEAD：`cd102150d16b1f7966b11175217fb7f01ec34a11`
- push：已成功；本地 `main` 已跟踪 `origin/main`，重复的 `master` 分支已删除
- 本报告另作为文档提交追加到代码提交之后。

## 14. 科学边界

- 历史回放不是新物理实验，也不是新的测量。
- 模型预测不是实测值；候选在揭示前没有真实 target。
- 模型分歧不是概率、置信区间或统计不确定性保证；IQR 不是 95% CI。
- 不做 p 值、显著性、跨项目排名或胜率。
- 不声称策略优越、因果、成本节省、工业/临床有效性或跨数据集泛化。
- 单次或固定 seeds 的历史回放不证明外部有效性。
- SHA、doctor、公开门禁和审计是软件完整性证据，不是科学有效性证明。
- 本项目不包含原始数据、运行产物、未揭示标签或私有项目记录。

## 15. 版权与使用

**未采用开源许可证，保留全部权利。**

Copyright © 2026 Wu Yetao. All rights reserved.

本仓库用于项目展示、学术交流与竞赛评审。未经作者书面许可，不得复制、修改、再发布、商业使用或将本项目及其衍生版本用于其他竞赛申报。

第三方依赖分别遵循其原始许可证。本声明不改变第三方组件的许可条件。

本仓库不是开源软件；公开可查看不等于授予开源许可。GitHub 可以正常提交、展示和评审，不添加 LICENSE 不构成发布阻碍。

仍待用户处理：

- GitHub 仓库地址和账号由项目负责人配置。
- DeepSeek Key 已通过 HTTP 200 验证；如以后被撤销，重新运行配置器即可，不需要改代码。
- 科学边界与数据许可见前文。
