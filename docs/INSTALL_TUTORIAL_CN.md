# NextTest 安装与使用教程

本教程面向第一次使用 NextTest 的人。**不需要会 Git，不需要 Node/npm，也不需要手动输入安装命令。**

---

## 一、最快方式：下载 Install_NextTest.cmd

### 第 1 步：打开 Releases

打开 GitHub 仓库：

https://github.com/yeto0620/NextTest

在右侧找到 **Releases**，点击：

```text
v3.0.0 · NextTest V3.0 · 可运行发布
```

也可以直接打开：

https://github.com/yeto0620/NextTest/releases/tag/v3.0.0

### 第 2 步：下载 Install_NextTest.cmd

在 Release 的 **Assets** 中找到：

```text
Install_NextTest.cmd
```

点击下载。

> 不要点 `Code → Download ZIP`。
> Code ZIP 是源码，需要 Node/npm 构建；普通使用者请用 Install_NextTest.cmd。

### 第 3 步：双击运行

找到刚下载的 `Install_NextTest.cmd`，双击。

如果 Windows 弹出安全提示：

1. 点击“更多信息”；
2. 点击“仍要运行”。

这是未签名的本地安装脚本，不会修改系统设置，也不会安装后台服务。

### 第 4 步：等待自动安装

会打开一个 PowerShell 窗口，自动执行：

```text
下载 ReadyToRun 包
解压到 %USERPROFILE%\NextTest
检查 Python
安装 Python 依赖
启动 NextTest
```

第一次需要几分钟，取决于网络和 Python 依赖下载速度。

### 第 5 步：浏览器打开工作台

启动成功后，窗口会显示类似：

```text
本地地址：http://127.0.0.1:8501
```

浏览器会自动打开。如果没有自动打开，复制窗口中的地址到浏览器。

看到 NextTest 研究工作台，就说明安装完成。

### 第 6 步：停止

回到启动窗口，按 `Ctrl+C`，或关闭窗口。启动器只停止本次启动的本地服务。

### 第 7 步：以后怎么再次打开

安装完成后，桌面和开始菜单只创建一个快捷方式：

```text
NextTest
```

双击后选择：

```text
Yes = DeepSeek 模式
No  = 普通模式（智能体/小精灵置灰）
```

选择 DeepSeek 且没有 Key 时，会自动打开配置窗口。

以后只需要双击 **NextTest**，不需要再找文件夹、不需要命令行。

如果桌面没有快捷方式，进入安装目录：

```text
%USERPROFILE%\NextTest
```

双击 `start_nexttest.cmd`；或重新运行一次 `setup_nexttest.cmd` 创建快捷方式。

---

## 二、如果电脑没有 Python

安装脚本需要 Python 3.13。

1. 打开：https://www.python.org/downloads/windows/
2. 下载 Python 3.13 Windows installer。
3. 安装时务必勾选：

```text
Add python.exe to PATH
```

4. 安装完成后，重新双击 `Install_NextTest.cmd`。

检查 Python 是否可用：

```powershell
python --version
```

应显示 `Python 3.13.x`。

---

## 三、手动下载 ReadyToRun 包

如果不使用 Install_NextTest.cmd，也可以手动操作：

1. 打开 Release 页面。
2. 下载 `NextTest_V3_ReadyToRun.zip`。
3. 右键 → **全部解压缩**。
4. 进入解压后的文件夹。
5. 双击 `setup_nexttest.cmd`。
6. 等待安装和启动。

这个包已经包含前端构建，**不需要 npm**。

> 不要在“下载”文件夹或 Desktop 里直接运行 `npm ci`。
> 一定要先解压，再进入解压后的文件夹。

---

## 四、开发者：从源码运行

只有需要修改代码时，才使用这种方式。

### 环境

- Python 3.13
- Node.js LTS
- PowerShell

### 安装

```powershell
python -m pip install -r requirements-web.txt
python -m pip install -r requirements-compute.txt
cd frontend
npm ci
npm run build
cd ..
.\setup_nexttest.cmd
```

### 如果 npm 不是命令

说明 Node.js 没有安装或没有进入 PATH：

1. 安装 Node.js LTS：https://nodejs.org/
2. 关闭所有 PowerShell 窗口；
3. 重新打开 PowerShell；
4. 执行：

```powershell
npm -v
```

有版本号后再执行构建。

### 如果 cd frontend 找不到路径

说明当前目录不是项目根目录。请先进入包含以下文件的文件夹：

```text
start_nexttest.cmd
setup_nexttest.cmd
requirements-web.txt
frontend\
```

然后再执行命令。

---

## 五、使用工作台

### 研究模式

默认进入研究模式：

```text
观测 / 候选 / 实验 / 策略 / 证据 / 档案 / 数据
```

可以：

- 查看候选表格和预测；
- 查看模型分歧；
- 选择候选并封存预测；
- 人工确认后揭示一条历史实测；
- 查看事件、SHA 和证据状态；
- 项目库、证据包、数据坞和科研智能体。

### 科普模式

点击右上角“科普”：

```text
导览 / 航图 / 体验 / 故事
```

用导览、航图和故事理解同一套候选与历史回放。

### 数据

仓库不附带原始 CSV。需要用自己的数据时：

1. 打开“数据”；
2. 导入本地 CSV；
3. 确认字段角色；
4. 查看缺失、重复和泄漏检查；
5. 确认并冻结只读数据护照。

---

## 六、配置 DeepSeek

不配置 Key 也能使用普通模式；普通模式下科研智能体和小精灵置灰。

### 首次配置

双击桌面上的：

```text
NextTest
```

在弹窗中选择 **Yes（DeepSeek 模式）**。如果还没有 Key，会自动打开配置器。

输入会遮罩；只有 DeepSeek 返回 HTTP 200 才保存。Key 使用 Windows current-user DPAPI 加密，保存在仓库外。

也可以打开安装目录后运行：

```powershell
.\configure_nexttest_llm.cmd
```

### 使用 DeepSeek 启动

以后双击：

```text
NextTest
```

在弹窗中选择 **Yes** 即可；Key 已保存时不会重复询问。

普通模式选择 **No**，核心回放、数据坞、策略、项目库和证据包仍可用。

### 手动启动
```powershell
.\start_nexttest_with_llm.cmd
```

普通打开仍然双击 `NextTest`，两者使用同一份本地数据。

换电脑后需要重新配置自己的 Key；Key 不在 Git 仓库里。

---

## 七、常见问题

### 1. 双击 Install_NextTest.cmd 后窗口一闪而过

右键该文件 → 以管理员身份运行，或打开 PowerShell 后执行：

```powershell
cd $env:USERPROFILE\Downloads
.\Install_NextTest.cmd
```

如果仍有错误，窗口会保留并显示原因。

### 2. npm 无法识别

普通使用者不需要 npm。请使用 `Install_NextTest.cmd` 或 `NextTest_V3_ReadyToRun.zip`。
开发者请安装 Node.js LTS，并重新打开 PowerShell。

### 3. cd frontend 找不到路径

当前目录不是项目根目录。先进入包含 `start_nexttest.cmd` 的文件夹。

### 4. 浏览器没有自动打开

复制启动窗口里的 `127.0.0.1` 地址，手动粘贴到浏览器。

### 5. 端口被占用

NextTest 会自动选择 `8501–8510` 中可用端口，不需要手动杀进程。

### 6. 页面空白或 503

检查是否完整解压，以及 `frontend\dist\index.html` 是否存在。
ReadyToRun 包已包含该文件；源码包需要执行 `npm run build`。

### 7. 视频打不开

GitHub 代码页不播放 MP4。请使用 Release 里的视频：

https://github.com/yeto0620/NextTest/releases/download/v3.0.0/NextTest_Demo.mp4

---

## 八、更新

以后更新不需要重新配置环境，也不需要重新下载 Python 依赖。

1. 关闭正在运行的 NextTest 窗口；
2. 重新双击 `Install_NextTest.cmd`；
3. 它会自动找到现有的 `NextTest` 或 `NextTest-时间戳` 目录并原地更新；
4. Python 依赖已安装时会跳过，深色/亮色选择、DeepSeek Key 和项目记录保留。

只有安装包本身需要重新下载（约 8 MB），依赖包不会每次重下。

## 九、卸载

NextTest 是便携式本地应用，不写系统服务。

1. 关闭启动窗口；
2. 删除 `%USERPROFILE%\NextTest`；
3. 如需删除 DeepSeek 凭据，运行：

```powershell
.\configure_nexttest_llm.cmd -Remove
```

不会影响其他文件。

---

## 十、版权

Copyright © 2026 Wu Yetao. All rights reserved.

本仓库用于项目展示、学术交流与竞赛评审。未采用开源许可证，保留全部权利。
