# NextTest 答辩证据包契约（P5-B）

`schema_version = nexttest_evidence_package_v1`

本契约定义只读、确定性、可核验的答辩证据包。证据包不写文件、不训练模型、不调用 LLM、不产生新实验，也不读取 test 标签或原始 CSV。

## 端点

```text
GET /api/projects/{project_id}/evidence-package
GET /api/custom/projects/{project_id}/evidence-package
```

- 第一条用于 `p2_` 项目，第二条用于 `p3_` 项目。
- 服务端先执行既有项目审计；审计失败时返回 503 或既有错误，不返回部分包。
- 响应 `Content-Type: application/json`，同一项目、同一审计事实应得到相同包。

## 顶层字段

严格为：

```text
schema_version
project_id
dataset_public_metadata
snapshot_public
audit_public
revealed_history_only
defense_brief
limitations
payload_sha256
markdown
```

### `dataset_public_metadata`

只允许公开数据集元数据：

- `dataset_id`、`display_name`、`short_id`
- `target`（名称、显示名、单位）
- `features`（字段名、显示名、角色、单位）
- `units`、`unit_not_verified`
- `counts`（train/candidate/test/groups）
- `gate_status`
- 公开的 `sha256`（input/schema）
- `historical_replay`

P2 使用固定公开的 UCI Concrete 元数据；计数绑定当前项目快照。

### `snapshot_public`

只允许项目快照中的公开字段：

```text
snapshot_version, project_id, status, goal, threshold, budget,
remaining_budget, strategy, seed, revealed_count, observed_count,
candidate_count, test_count, current_model_sha, initial_model_sha,
split_sha256, source_canonical_sha256, observed_row_ids_sha256,
test_sha256, historical_replay, dataset_id, dataset_display_name,
dataset_short_id, user_data_replay
```

### `audit_public`

只允许既有 audit 的公开摘要：

```text
audit_version, project_id, status, event_count, event_chain_sha256,
tree_sha256, project_manifest_sha256, source_canonical_sha256,
split_sha256, test_sha256, observed_count, candidate_count,
test_count, test_unchanged, models_present, historical_replay,
valid, auditor_schema, auditor_version, semantic_replay
```

不返回原始 audit 文件、内部 event payload、模型文件或目录。

### `revealed_history_only`

只包含已经 reveal 的历史记录：

```text
round, row_id, prediction, revealed_target, absolute_error, strategy
```

行按 `(round, row_id)` 稳定排序。没有 reveal 时为空数组。

### `defense_brief`

确定性模板生成，不调用 LLM：

```text
template_version = p5b-defense-v1
revealed_count
mae
max_absolute_error
evidence_status = available | insufficient
summary
boundaries
```

- `revealed_count == 0` 时，`mae`、`max_absolute_error` 为 `null`，`evidence_status = insufficient`，摘要明确写“证据不足”。
- 只根据 `revealed_history_only[].absolute_error` 计算：
  - MAE = 平均绝对误差
  - max = 最大绝对误差
- 不计算显著性、置信区间、排名或策略优劣。

### `limitations`

固定文字，至少包含：

- 历史回放不是新实验，也不是新的物理测量。
- 模型预测不是实测值；候选在揭示前没有真实 target。
- 模型分歧不是概率、置信度或统计不确定性保证；IQR 不是 95% CI。
- 不证明策略优越、因果、成本节省、工业有效性或跨数据集泛化。
- 独立 test 标签、原始 CSV 和任意本机路径不进入本包。
- 单位来自公开或用户声明 metadata，未做独立物理单位验证。

### `payload_sha256`

对去除 `payload_sha256` 后的包对象，按 UTF-8、`sort_keys=True`、紧凑 JSON（`separators=(",", ":")`）计算 SHA-256：

```text
sha256(json.dumps(payload_without_sha, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
```

`markdown` 是同一事实源的确定性派生物，参与哈希；不包含 `payload_sha256` 自身，避免循环。

### `markdown`

由与 JSON 相同的快照、历史、防御统计和 limitations 生成，稳定排序；数字使用与 JSON 一致的序列化值。

## 泄漏黑名单

绝不返回：

- pending candidate 的 target、revealed_target、controls、prediction
- 未揭示候选标签、candidate pool
- 独立 test 行、test 标签、test SHAs 之外的原始 test 内容
- 原始 CSV、上传文件、数据行
- 任意本机路径、环境变量、API key、Authorization
- 完整内部事件、原始 audit 文件、模型文件
- `pending` 对象本身

本包不包含候选池；即使上游 view 带有 pending 数据，也不会被序列化。

## 只读与失败关闭

- 端点只调用既有 inspect/audit 与纯函数构建。
- 构建前后项目树必须不变。
- snapshot/audit 状态不一致、`test_unchanged != true`、`models_present != true`、非历史回放、缺少必要字段时返回 503 `EVIDENCE_PACKAGE_INVALID`。
- 不写缓存、不写包文件、不修改项目。
