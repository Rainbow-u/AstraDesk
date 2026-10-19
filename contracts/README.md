# contracts/ — 契约与样例

前后端共用的 JSON Schema 与合法/非法样例（G1 契约稳定的单一来源）。

- `detection_result.schema.json`：检测任务查询结果（`GET /api/v1/jobs/{id}`）。坐标 `bbox_image=[x1,y1,x2,y2]` 归一化 0-1、左上原点（PRD 5.2）；`class_id`/`class_name` 枚举为 9 产品类+other，每个 detection 带 `source`（FR03 可追溯：`yolov10:<stem>` 或 `yolo-world`）。
- `scene_facts.schema.json`：确定性几何事实（单一事实来源），由 `packages/understanding/scene_facts.py` 从确认后检测+桌面矩形计算；`interpret` 任务内嵌返回。
- `vl_relations.schema.json`：B 阶段 Qwen-VL 在 SceneFacts 之上补充的关系与解释（H01：只能引用已有 `object_id`、不得改写事实清单）；`additionalProperties:false` 确保 VL 输出不携带重写的事实。当前 VL 真实路径 blocked（缺凭据）。
- `error.schema.json`：统一错误对象（PRD 8.3），`code` 限建议错误码集合。
- `samples/`：每个 schema 附一个 `*.valid.json` 与一个 `*.invalid.json`；测试用 `jsonschema` 断言合法样例通过、非法样例被拒。

坐标约定：`bbox_image` 与 `bbox_desk` 显式区分，`bbox_desk` 由后端从原图框与桌面矩形推导，往返转换见 `packages/layout/coordinates.py` 与 `tests/test_coordinates.py`。
