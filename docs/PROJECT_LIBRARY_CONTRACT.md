# NextTest 只读项目证据库契约（P5-C）

本契约定义只读项目索引、项目卡片和两两可比性检查。证据库不是排行榜，不做策略排名、胜率、p 值、推荐或聚合结论。

## 端点

```text
GET  /api/library
GET  /api/library/{project_id}/card
POST /api/library/compare
```

## 读取顺序

1. 只枚举既有 `p2_` / `p3_` 项目目录。
2. 每个项目先走既有 `inspect` 和只读审计。
3. 审计通过后，基于 P5-B evidence package 的公开字段派生 card/summary。
4. 审计失败的项目不返回部分事实：library 排除；card/compare 返回 503。

不写项目、不写缓存、不写包文件、不训练模型、不调用 LLM、不创建新 Evidence Run。

## `GET /api/library`

```json
{
  "schema_version": "nexttest_project_library_v1",
  "count": 2,
  "items": []
}
```

- `items` 按 `project_id` 升序稳定排序。
- 最多 100 项；`count` 是实际返回项数。
- 审计失败项目不加入 `items`。

### item 白名单

```text
project_id
dataset_id
dataset_display_name
dataset_short_id
status
goal
strategy
budget
revealed_count
observed_count
candidate_count
historical_replay
source_sha256_short
split_sha256_short
test_sha256_short
model_sha256_short
audit_status
event_chain_sha256_short
```

短指纹取 SHA-256 前 12 个十六进制字符。`audit_status="passed"` 表示已通过既有只读审计。

不返回：路径、pending、候选池、未揭示标签、test 行/标签、CSV、环境变量、Key、完整事件、完整 audit 文件。

## `GET /api/library/{project_id}/card`

```json
{
  "schema_version": "nexttest_project_card_v1",
  "project_id": "...",
  "summary": {},
  "dataset_public_metadata": {},
  "snapshot_public": {},
  "audit_public": {},
  "defense_brief": {},
  "limitations": [],
  "package_payload_sha256": "..."
}
```

- card 完全由 P5-B evidence package 的公开字段派生。
- 不复制原始项目文件、完整事件、历史 CSV 或原始 audit。
- `summary` 与 library item 同白名单。
- `defense_brief` 使用 P5-B 的确定性统计；没有 reveal 时 MAE/max 为 `null`。

## `POST /api/library/compare`

请求严格只允许：

```json
{
  "left_project_id": "p2_...",
  "right_project_id": "p3_..."
}
```

额外字段、非法 ID 返回 422；任一侧审计失败返回 503，不返回部分 `left`/`right`。

响应严格为：

```json
{
  "schema_version": "nexttest_project_comparability_v1",
  "left": {},
  "right": {},
  "comparability": "comparable_same_source_and_split",
  "shared_facts": {},
  "differences": {},
  "limitations": []
}
```

### `comparability`

```text
comparable_same_source_and_split
same_dataset_but_different_split
different_dataset
audit_failed
```

- 只有 source SHA **和** split SHA 均一致，才输出 `comparable_same_source_and_split`。
- 同一 dataset_id、但 source/split 不一致时输出 `same_dataset_but_different_split`。
- dataset_id 不同输出 `different_dataset`。
- 审计失败时 HTTP 503，错误详情包含 `comparability="audit_failed"`；不产生部分比较对象。

### `left` / `right`

```text
project_id, dataset_id, dataset_display_name, dataset_short_id,
status, goal, strategy, budget, revealed_count, observed_count,
candidate_count, historical_replay, source_sha256_short,
split_sha256_short, test_sha256_short, model_sha256_short,
event_chain_sha256_short, audit_status, mae, max_error
```

### `shared_facts`

```text
same_dataset, same_source_sha256, same_split_sha256,
same_source_and_split, same_goal, same_strategy, same_budget,
disclaimer, comparison_note
```

固定声明：

> 描述性比较，不构成策略优越、显著性、因果、成本节省、工业有效性或泛化结论。

### `differences`

只包含两侧不同的公开字段，形式为：

```json
{"field": {"left": "...", "right": "..."}}
```

### `limitations`

固定声明加两侧包的限制说明，去重并保持稳定顺序。

## 不做的事

- 不计算跨项目排名、胜率、p 值、显著性、因果、成本节省、工业有效性或泛化。
- 不推荐项目、策略或候选。
- 不调用 LLM。
- 不返回 pending target、test 标签、原始 CSV、路径、环境变量或 Key。
- 不修改项目目录；调用前后项目 tree SHA 必须不变。
