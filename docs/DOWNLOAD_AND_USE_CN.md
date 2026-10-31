# NextTest 下载与使用说明

## 1. 获取方式

推荐下载 **ReadyToRun** 包，已包含前端构建，不需要安装 Node。

最省事：下载并双击 [Install_NextTest.cmd](https://github.com/yeto0620/NextTest/releases/download/v3.0.0/Install_NextTest.cmd)，它会自动下载、解压到 `%LOCALAPPDATA%\NextTest` 并启动。

或手动下载：

- [NextTest_V3_ReadyToRun.zip](https://github.com/yeto0620/NextTest/releases/download/v3.0.0/NextTest_V3_ReadyToRun.zip)

如果使用源码包：

- `NextTest_V3_GitHub_Source.zip`
- 解压到任意中文或英文路径，不要放在系统受保护目录。
- 也可以将解压后的内容直接导入 GitHub：GitHub → New repository → Upload an existing file，或使用 Git 推送到仓库。

源码压缩包只包含公开源代码、测试、文档和配置模板；不包含原始 CSV、运行产物、`.env`、DPAPI 凭据、API Key、`node_modules/` 或 `frontend/dist/`。

## 2. 环境要求

ReadyToRun 包：

- Windows 10/11；
- Python 3.13；
- 不需要 Node.js。

源码包：

- Windows 10/11；
- Python 3.13；
- Node.js LTS + npm；
- 首次运行前端需要安装依赖并构建。

## 3. 首次安装

### 最快方式

1. 解压 **ReadyToRun** 包。
2. 进入解压后的文件夹，确认能看到 `setup_nexttest.cmd`、`start_nexttest.cmd` 和 `frontend`。
3. 双击 `setup_nexttest.cmd`。

脚本会检查 Python、安装依赖，并在需要时构建前端，然后启动工作台。

### 源码方式

在解压后的项目根目录打开 PowerShell：

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

**`npm` 无法识别**

Node.js 未安装或未进入 PATH。安装 [Node.js LTS](https://nodejs.org/) 后，关闭并重新打开 PowerShell，运行 `npm -v` 确认。如果不想安装 Node，请使用 ReadyToRun 包。

**`cd frontend` 找不到路径**

当前目录不是项目根目录。先 `cd` 到包含 `start_nexttest.cmd` 的文件夹，或直接在解压后的文件夹中打开 PowerShell。

**不要在 Desktop 直接运行**

必须先解压，再进入解压后的项目根目录；不要在桌面目录直接执行 `npm ci` 或 `cd frontend`。

## 4. 启动

### 普通本地模式（无 DeepSeek Key）

```powershell
.\start_nexttest.cmd
```

浏览器会打开本地地址，通常是 `http://127.0.0.1:8501`。如果没有自动打开，复制窗口中的 `127.0.0.1` 地址到浏览器。

### 永久 DeepSeek 模式（可选）

首次配置：

```powershell
.\configure_nexttest_llm.cmd
```

- 输入会遮罩；
- 只有 DeepSeek 返回 HTTP 200 才保存；
- Key 使用当前 Windows 用户 DPAPI 加密，保存于仓库外的 `%LOCALAPPDATA%\NextTest\secrets\deepseek.key`；
- 不写入 `.env`、日志、测试或 Git。

配置成功后：

```powershell
.\start_nexttest_with_llm.cmd
```

如果 Key 无效或网络失败，启动器/助手会 fail-closed；可重新运行配置器。

## 5. 数据使用

仓库不附带原始数据。示例数据需从 UCI Concrete Compressive Strength 数据集自行获取，并通过 Data Dock 的：

1. 字段角色确认；
2. 缺失/重复/泄漏检查；
3. 质量警告确认；
4. 只读数据护照冻结。

不要把原始 CSV、`runs/`、`artifacts/` 或私有项目记录提交到 GitHub。

## 6. 功能入口

- **研究模式（默认）**：观测、候选、实验、策略、证据、档案、数据；包含科研智能体、数据坞、项目库、审计和完整控制量。
- **科普模式**：导览、航图、体验、故事；包含引导、教学解释、演示模式和简化控制量。
- 两模式共享同一事实源和候选选择，但组件、导航和信息密度不同。

## 7. 停止

回到启动窗口，按 `Ctrl+C`，或关闭窗口。启动器只清理本次启动的本地服务。

## 8. 验证

```powershell
python scripts/nexttest_doctor.py --check
python -m pytest -q tests/test_nexttest_llm_copilot.py tests/test_nexttest_web_api.py tests/test_nexttest_ui_worker.py tests/test_nexttest_p2_ui_contract.py tests/test_nexttest_p3_ui_contract.py tests/test_nexttest_p4a_ui_contract.py tests/test_nexttest_project_library.py tests/test_nexttest_evidence_package.py tests/test_nexttest_public_release.py tests/test_nexttest_desktop_readiness.py tests/test_nexttest_ui_mode_closure.py
```

## 9. 边界

- 本项目是**历史数据回放平台**，不是新物理实验。
- 模型预测不是测量；模型分歧不是概率或置信区间。
- 不声称策略优越、因果、成本节省、工业/临床有效性或泛化。
- 不是原生桌面安装包，不提供 Electron/Tauri 安装程序。
- 未采用开源许可证，保留全部权利；公开可查看不等于授予开源许可。

## 10. 常见问题

**浏览器没有自动打开？** 手动访问启动窗口显示的 `127.0.0.1` 地址。

**端口被占用？** 启动器会自动选择 8501–8510 中可用端口，不要杀已有服务。

**前端页面 503？** 在 `frontend` 目录运行 `npm ci` 和 `npm run build`。

**DeepSeek 未配置？** 使用普通启动模式；或运行 `configure_nexttest_llm.cmd` 配置有效 Key。

**Python 依赖错误？** 确认使用 Python 3.13，并安装 `requirements-web.txt` 与 `requirements-compute.txt`。
