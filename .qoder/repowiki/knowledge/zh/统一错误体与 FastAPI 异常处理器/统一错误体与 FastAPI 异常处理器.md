---
kind: error_handling
name: 统一错误体与 FastAPI 异常处理器
category: error_handling
scope:
    - '**'
source_files:
    - contracts/error.schema.json
    - services/api/errors.py
    - services/api/app.py
    - services/api/service.py
    - services/api/schemas.py
    - tests/test_contracts.py
---

## 1. 采用的体系

- **JSON Schema 契约**：`contracts/error.schema.json`（draft-2020-12）定义统一的 `ErrorBody`，强制字段 `code`/`message`/`retryable`/`request_id`，可选 `details`；`code` 为枚举，限定 10 个业务码。
- **Pydantic 模型**：`services/api/schemas.py` 中的 `ErrorBody` 作为序列化载体。
- **FastAPI 异常处理**：`services/api/errors.py` 定义 `ApiError` 异常类与两个 `exception_handler`，在 `app.py` 启动时通过 `register_error_handlers(app)` 注册。
- **Worker 侧错误落库**：`services/api/service.py` 中 `_fail_job` 将错误以 JSON 写入 `Job.error_json`，查询时反序列化为 `error` 字段返回。

## 2. 关键文件

- `contracts/error.schema.json` — 错误体 JSON Schema（权威契约）
- `services/api/errors.py` — `ApiError` 异常 + FastAPI 全局异常处理器
- `services/api/app.py` — 应用装配，调用 `register_error_handlers`
- `services/api/service.py` — 业务层抛出 `ApiError`、捕获下游异常并落库
- `services/api/schemas.py` — Pydantic `ErrorBody` 模型
- `tests/test_contracts.py` — 校验 error.schema.json 的合法/非法样例

## 3. 架构与约定

### 3.1 异常 → HTTP 响应映射

`ApiError` 构造参数：`code: str, message: str, status_code: int=400, retryable: bool=False, details: dict|None=None`。
全局处理器 `_api_error` 将其转为 `JSONResponse(status_code=exc.status_code, content=ErrorBody.model_dump())`。
未捕获的任意 `Exception` 由 `_unhandled` 拦截，固定返回 `{"code": "INTERNAL", "message": "internal server error", "retryable": true}` 且 HTTP 500。

### 3.2 request_id 传播

请求头 `x-request-id` 优先使用，否则生成 `uuid.uuid4().hex`，写入每个 `ErrorBody.request_id`。该值同时用于成功响应的追踪（由路由层注入）。

### 3.3 业务错误码（来自 schema 枚举）

| code | 语义 | 典型状态码 |
|---|---|---|
| `INVALID_IMAGE` | 空文件 / 不支持扩展名 / 预处理失败 | 400 或 415 |
| `TOO_MANY_OBJECTS` | 检测框过多 | 400 |
| `MODEL_UNAVAILABLE` | 真实检测器不可用 | 4xx（由调用方决定） |
| `SCHEMA_INVALID` | 输入 Schema 不合法 | 422 |
| `NO_FEASIBLE_LAYOUT` | 无法推导布局 | 422 |
| `STALE_REVISION` | 版本陈旧 | 409 |
| `GENERATION_TIMEOUT` | 生成超时 | 504 |
| `BUDGET_EXCEEDED` | 预算超限 | 429 |
| `PROJECT_NOT_FOUND` / `ASSET_NOT_FOUND` / `JOB_NOT_FOUND` | 资源不存在 | 404 |
| `INTERNAL` | 未预期异常 | 500 |

### 3.4 业务层抛错模式

- `service.py` 中所有可预期的业务失败均 `raise ApiError(...)`，而非返回 None 或字符串。
- 对第三方异常做显式转换：`PreprocessError` → `ApiError`（按消息内容区分 413/400），`CoordinateError` → `ApiError(…, 422)`，`detector.DetectorUnavailable` → 直接走 `_fail_job` 写库。
- Worker 边界（`process_detect_job`）用 `try/except Exception` 兜底，把任何未捕获异常包装为 `INTERNAL` 并持久化到 `Job.error_json`，避免 worker 进程崩溃。

### 3.5 Worker 错误持久化

`_fail_job(session, job, code, message, retryable)` 设置 `job.status = "failed"`，并将 `json.dumps({"code", "message", "retryable"})` 写入 `error_json`。查询接口 `job_to_dict` 再反序列化为顶层 `error` 字段，供前端展示。

## 4. 约定与约束

- **错误体结构受 JSON Schema 强约束**：`contracts/error.schema.json` 声明 `additionalProperties=false` 且 `required=[code,message,retryable,request_id]`，测试 `tests/test_contracts.py` 用 `error.valid.json` 与 `error.invalid.json` 断言。
- **`code` 仅允许 schema 枚举中的值**：新增错误码需同步修改 `contracts/error.schema.json` 与 `schemas.py` 的 `ErrorBody` 类型。
- **HTTP 状态码由 `ApiError.status_code` 决定**，默认 400；业务层显式指定 404/415/422 等。
- **未捕获异常一律降级为 `INTERNAL` + 500**，不向客户端暴露 Python 堆栈。
- **Worker 内所有异常最终落库为 failed**，不静默吞掉（见 `process_detect_job` 注释“约定1”“约定4”）。
- **`retryable` 字段驱动客户端重试策略**：`INTERNAL` 标记为 `True`，`MODEL_UNAVAILABLE` 等业务错误根据语义设置 `False`。
- **`request_id` 从请求头透传**：若缺失则服务端生成，保证每次请求有唯一追踪 ID。

## 5. 观察到的缺口

- 错误码未在 Python 常量集中统一定义，而是分散在 `errors.py`、`service.py` 和 schema 文件中，存在手写重复风险。
- 没有针对 `ApiError` 的单元测试覆盖（当前测试集中在 routes/schema/detection flow），异常路径依赖集成测试间接验证。
- 非 API 模块（如 `packages/vision`、`packages/layout`）自定义异常（`PreprocessError`、`CoordinateError`）各自定义，尚未统一到 `ApiError` 体系之外形成跨包错误分类。