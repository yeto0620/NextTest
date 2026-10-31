# NextTest — 下一次，先验证什么？

**面向有限试验预算的实验决策智能体工作台。**

NextTest 不只预测一个结果，而是从尚未揭示的历史方案中提出“下一次最值得验证什么”，先封存预测，人工确认后再揭示历史实测，并把模型、SHA 和证据链一起更新。

[▶ 1 分 44 秒功能演示（中文配音 + 字幕）](https://github.com/yeto0620/NextTest/releases/download/v3.0.0/NextTest_Demo.mp4) · [快速开始](#下载与快速开始) · [DeepSeek 配置](#deepseek-配置) · [使用说明](docs/DOWNLOAD_AND_USE_CN.md)


> **普通访客请先看这里：** 不要直接点 `Code → Download ZIP` 后运行，源码包需要 Node/npm 构建。最简单的使用方式是下载下面 Release 里的 `Install_NextTest.cmd`，双击即可，不需要命令行、Node 或 cd。

## 普通用户：3 步使用

完整图文步骤见 [安装与使用教程](docs/INSTALL_TUTORIAL_CN.md)。

1. 打开 [Releases](https://github.com/yeto0620/NextTest/releases/tag/v3.0.0)，下载 `Install_NextTest.cmd`。
2. 双击它；Windows 提示时选择“更多信息 → 仍要运行”。
3. 等安装窗口自动下载、安装依赖并启动；浏览器会打开工作台。
4. 以后直接双击桌面的 **NextTest** 再次打开。
5. 需要 DeepSeek 时，先双击 **NextTest DeepSeek Config** 配置 Key，再双击 **NextTest DeepSeek** 启动。

不需要 Node/npm，不需要 `cd frontend`，也不要在 Desktop 下手动运行 `npm ci`。

安装完成后会自动创建桌面和开始菜单快捷方式：

```text
NextTest                    普通打开
NextTest DeepSeek           使用 DeepSeek 打开
NextTest DeepSeek Config    配置或更换 DeepSeek Key
```

## 不想用命令行？

直接下载并双击：

[Install_NextTest.cmd](https://github.com/yeto0620/NextTest/releases/download/v3.0.0/Install_NextTest.cmd)

它会自动下载 ReadyToRun 包、解压到 `%USERPROFILE%\NextTest`、安装 Python 依赖并启动。**不需要 Node/npm，也不需要手动 cd。**

## 这是什么

NextTest 是一个可本地运行的 Web 工作台，用公开历史数据做可复核的实验决策回放：

- 先看已知记录和候选，再决定下一次验证；
- 预测与实测分离，候选标签只在人工确认后揭示；
- 研究模式服务科研审查，科普模式服务公众理解，两者共享同一事实源；
- 所有推荐、误差和证据摘要来自固定数据与确定性计算。

## 能做什么

### 01 研究模式

观测、候选、实验、策略、证据、档案、数据七个入口。首屏直接呈现候选表格、预测、模型分歧和审计信息。

### 02 科普模式

导览、航图、体验、故事四个入口，用同一套候选和历史回放解释“为什么下一次要这样选”。

### 03 实验台

选择候选 → 封存预测 → 人工确认 → 揭示一条历史实测 → 更新模型和证据链。关键动作可只读恢复。

### 04 数据坞

导入本地 CSV，检查字段角色、缺失、重复和泄漏风险，确认后冻结只读数据护照；原始文件留在本机。

### 05 策略观测台

固定协议、固定种子，对照随机、预测最优和模型分歧三种策略，查看预算轨迹、运行矩阵和失败单元。

### 06 项目库与证据包

把项目变成可复核证据：项目卡片、来源/切分可比性检查、确定性 JSON/Markdown 证据包、公开 SHA 和已揭示历史。

### 07 科研智能体

DeepSeek 解释白名单公开证据；没有 Key 时自动使用本地规则。LLM 不参与选点、排序、训练、阈值或科研数字生成。

### 08 新手引导与亮色主题

首次进入会自动打开 4 步新手引导；顶栏的 ✦ 可随时重开。顶栏太阳/月亮按钮切换亮色/深色主题，选择会保存在本机。


## 创新点

1. **从“预测结果”推进到“决定下一次验证”**
   把有限预算花在最值得验证的一步，而不是只追求一个预测值。

2. **先封存，后揭示**
   候选选择阶段不读取隐藏结果，人工确认后才释放一条历史实测，降低数据泄漏和事后改答案风险。

3. **研究 / 科普共享同一事实源**
   专业用户看字段、单位、模型、SHA 和审计；公众看导览、航图和故事，底层候选与证据完全一致。

4. **可审计的证据闭环**
   项目编号、事件记录、模型 SHA、只读恢复、证据包和项目库，让每次判断可以复盘。

## 下载与快速开始

### 最快方式：ReadyToRun

1. 下载 [NextTest_V3_ReadyToRun.zip](https://github.com/yeto0620/NextTest/releases/download/v3.0.0/NextTest_V3_ReadyToRun.zip)（已包含前端构建，不需要 Node/npm）。
2. **解压**到本地目录，不要直接在压缩包里运行。
3. 进入解压后的文件夹，确认能看到 `setup_nexttest.cmd`、`start_nexttest.cmd`、`frontend`。
4. 双击 `setup_nexttest.cmd`。

首次会自动安装 Python 依赖并启动；浏览器打开 `127.0.0.1:8501–8510`。

### 从 GitHub 源码运行

需要 Python 3.13 和 Node.js LTS：

```powershell
python -m pip install -r requirements-web.txt
python -m pip install -r requirements-compute.txt
cd frontend
npm ci
npm run build
cd ..
.\setup_nexttest.cmd
```

### 常见错误

**`npm` 不是内部或外部命令**

说明 Node.js 没有安装或没有进入 PATH。安装 Node.js LTS 后，**关闭并重新打开 PowerShell**，再运行 `npm -v`。如果不想安装 Node，请使用 ReadyToRun 压缩包。

**`cd frontend` 找不到路径**

说明当前目录不是解压后的 NextTest 根目录。请先 `cd` 到包含 `start_nexttest.cmd` 的文件夹，或在文件资源管理器中进入该文件夹后再打开 PowerShell。

**不要这样做**

不要在自己的 `Desktop` 目录直接运行 `npm ci` 或 `cd frontend`；要先解压并进入项目根目录。

### 启动

普通本地模式：

```powershell
.\start_nexttest.cmd
```

DeepSeek 模式：

```powershell
.\configure_nexttest_llm.cmd
.\start_nexttest_with_llm.cmd
```

启动后浏览器打开 `127.0.0.1:8501–8510` 中自动选择的端口。

完整下载、安装、数据和故障排查说明见 [INSTALL_TUTORIAL_CN.md](docs/INSTALL_TUTORIAL_CN.md)；技术环境说明见 [DOWNLOAD_AND_USE_CN.md](docs/DOWNLOAD_AND_USE_CN.md)。

## DeepSeek 配置

当前版本已接入 DeepSeek，真实请求已通过 HTTP 200 验收。

- 首次配置输入 Key 时使用遮罩；
- 只有 DeepSeek 返回 HTTP 200 才保存；
- 使用 Windows current-user DPAPI 加密，保存在仓库外的 `%LOCALAPPDATA%\NextTest\secrets\deepseek.key`；
- 不会写入 `.env`、日志、测试或 Git；
- 默认使用本地规则解释，配置 Key 后使用 `deepseek-chat`；
- 换电脑后重新运行 `configure_nexttest_llm.cmd` 即可。

## 技术结构

```text
frontend/          React + Vite + Three.js 工作台
nexttest/          FastAPI、历史回放、数据坞、策略、项目库、证据包
scripts/           一键启动、UI worker、公开门禁
tests/             核心、API、UI 合同和公开发布测试
docs/              产品、契约、下载与使用说明
```

固定示例：UCI Concrete，252 条训练、89 条候选、84 条独立留出，固定 28 天龄期。

## 验证

```text
Python 测试：80 passed
前端构建：通过
公开门禁：release_ready=true，errors=[]
浏览器：1280 / 1440 / 1920 无横向溢出，console errors=[]
DeepSeek：HTTP 200，deepseek-chat 调用成功
```

## 文档

- [下载与使用说明](docs/DOWNLOAD_AND_USE_CN.md)
- [Windows 快速启动](docs/WINDOWS_QUICKSTART.md)
- [证据包契约](docs/EVIDENCE_PACKAGE_CONTRACT.md)
- [项目库契约](docs/PROJECT_LIBRARY_CONTRACT.md)
- [公开版检查清单](docs/GITHUB_RELEASE_CHECKLIST.md)
- [项目方案（详细版）](docs/NextTest_项目方案_详细版.docx)
- [最终交付报告](docs/FINAL_RELEASE_REPORT.md)

## 适用范围

NextTest 适合有限预算的历史数据回放、实验决策教学、科研流程审查和公众科普。推荐、预测和证据摘要用于复盘与讨论；真实实验需要领域专家结合实验条件复核。

## 版权与使用

Copyright © 2026 Wu Yetao. All rights reserved.

本仓库用于项目展示、学术交流与竞赛评审。未经作者书面许可，不得复制、修改、再发布、商业使用或将本项目及其衍生版本用于其他竞赛申报。

第三方依赖分别遵循其原始许可证。本声明不改变第三方组件的许可条件。
