# NextTest 公开发布运行手册

本手册面向参赛者和 GitHub 使用者，说明如何检查公开仓库、获取数据、启动本地服务，以及哪些科学结论不能声称。

## 1. 项目是什么

NextTest 是一个**历史数据回放平台**：它用已有记录训练轻量模型，从尚未揭示结果的历史方案中提出下一次验证建议；用户确认后才揭示历史实测值并更新判断。

它不是新的物理实验，不是自动实验室，也不是工业或临床系统。

## 2. 科学边界

- 模型预测不是测量值。
- 模型分歧不是概率、置信区间或统计不确定性保证；IQR 不是 95% CI。
- 历史回放不是新实验，不能证明因果。
- 不做显著性、胜率或跨项目排名。
- 不声称策略优越、成本节省、工业/临床有效性或跨数据集泛化。
- 公开仓库不包含原始数据、私有运行记录或既有项目产物。

## 3. 公开仓库不包含什么

公开仓库不包含：

- 原始 CSV 或数据副本；
- 运行目录、artifacts、deliverables 或历史回放结果；
- 虚拟环境、node_modules、构建产物；
- `.env`、API Key、个人路径或本机配置；
- 真实项目编号、未揭示标签或独立 test 数据。

## 4. 获取数据并走数据闸门

示例数据使用 UCI Concrete Compressive Strength：

<https://archive.ics.uci.edu/dataset/165/concrete+compressive+strength>

请自行从原始来源下载，并遵守 CC BY 4.0 和引用要求。下载后：

1. 通过 Data Dock 导入本地 CSV。
2. 检查字段角色、缺失值、重复列和潜在泄漏。
3. 逐项确认质量警告。
4. 冻结只读数据档案后，才允许创建历史回放项目。
5. 不要把原始数据或冻结产物提交到仓库。

## 5. 创建 `.env`（可选）

证据助手没有配置时仍可离线使用其他功能。需要配置时：

```text
cp .env.example .env
```

然后在启动服务的同一 shell 中设置变量：

```powershell
$env:NEXTEST_LLM_PROVIDER = "deepseek"
$env:NEXTEST_LLM_BASE_URL = "https://api.deepseek.com"
$env:NEXTEST_LLM_MODEL = "deepseek-chat"
$env:NEXTEST_LLM_API_KEY = "<你的 key>"
```

当前服务只读取进程环境变量，不会自动解析 `.env`；`.env` 仅作为个人模板/记录，且绝不能提交。未设置 `NEXTEST_LLM_API_KEY` 时，`POST /api/copilot/explain` 返回 HTTP 503 和 `LLM_NOT_CONFIGURED`，不会发起网络请求。

## 6. 一键公开检查

在仓库根目录运行：

```powershell
python scripts/verify_public_release.py --check
```

输出稳定 JSON。`release_ready=true` 时退出码为 0；否则非 0。检查只读，不写项目目录、不生成 artifacts、不联网。

## 7. 启动 API/UI

在仓库根目录运行：

```powershell
python -m pip install -r requirements-web.txt
python -m pip install -r requirements-compute.txt
python scripts/start_nexttest.py
```

服务只绑定本机 `127.0.0.1`。前端源码开发需要 Node：

```powershell
cd frontend
npm ci
npm run build
```

## 8. 发布前检查清单

- [ ] `python scripts/verify_public_release.py --check` 返回 0。
- [ ] 仓库没有原始 CSV、运行产物、交付物或环境目录。
- [ ] 没有 `.env`、API Key、个人绝对路径或内部项目编号。
- [ ] README、GITHUB_RELEASE_CHECKLIST、证据包契约、证据库契约存在且为 UTF-8。
- [ ] GitHub Actions 的 public-check 通过。
- [ ] 前端 `npm ci` 和 `npm run build` 通过。
- [ ] 证据助手在无 Key 时返回 503，且没有真实网络请求。
- [ ] 许可证由项目负责人决定；不要自行添加 LICENSE。

## 9. 不可声称的结论

公开发布、演示和答辩中，不得声称：

- 某种策略更优越或已获胜；
- 统计显著性、因果效应或置信区间；
- 成本节省；
- 工业、临床或生产有效性；
- 跨数据集泛化；
- 历史回放是新实验或新测量。

如需引用数字，只引用公开的、已经揭示的历史回放描述性统计，并同时说明其边界。
