# GitHub 公开版发布检查清单

本清单用于 NextTest 公开版。项目**未采用开源许可证，保留全部权利**；不添加 MIT、Apache、GPL 或自定义开源 LICENSE。公开仓库用于展示、学术交流与竞赛评审，不因公开而授予开源许可。

## 应公开提交

- 后端源代码：`nexttest/`
- 测试：`tests/`
- 文档：`README.md`、`docs/`
- 启动与开发脚本：`scripts/`、`start_nexttest.cmd`、`app.py`
- 依赖声明：`requirements-web.txt`、`requirements-compute.txt`、`requirements-app.txt`
- 前端源代码：`frontend/src/`、`frontend/package.json`、`frontend/package-lock.json` 等源码文件（构建产物除外）
- 配置模板：`.env.example`
- 仓库卫生：`.gitignore`

## 不得提交

- 数据副本、原始 CSV、数据导出或 fixtures 中的受限数据
- `data/`、`artifacts/`、`runs/`、`deliverables/` 中的运行记录、截图、证据包或报告
- `.env`、`.env.*`（`.env.example` 除外）或任何真实 API Key
- `.venv/`、`.venv-ui/`、`__pycache__/`、`node_modules/`、`frontend/dist/`
- `*.log`、临时目录、`.dsh-*` 工作目录
- 个人联系方式、学号或其他未获授权的个人信息
- 未经许可的第三方数据、模型权重或大段外部代码

## 数据来源

- 示例使用公开的 UCI Concrete Compressive Strength 数据（CC BY 4.0）：
  <https://archive.ics.uci.edu/dataset/165/concrete+compressive+strength>
- 仓库不附带数据副本；使用者需自行获取，并遵守原始数据许可与引用要求。
- 用户导入的自有 CSV 只在本机处理，不随仓库发布，也不上传到 LLM。

## 发布前检查

1. 在干净环境安装 `requirements-web.txt`、`requirements-compute.txt`，确认启动与测试命令可运行。
2. 运行证据助手测试；确认未配置 Key 时返回 503 且没有任何真实网络请求。
3. 检查 `.env.example` 不含真实 Key，仓库历史中没有 `.env` 或密钥。
4. 检查仓库不包含 `data/`、`artifacts/`、`runs/`、`deliverables/`、虚拟环境或构建产物。
5. 检查 README、证据助手说明和科学边界与当前实现一致。
6. 保持仓库无开源 LICENSE；版权声明为“未采用开源许可证，保留全部权利”。
7. 发布前由人工复核数据许可、个人信息、第三方代码/模型许可。
