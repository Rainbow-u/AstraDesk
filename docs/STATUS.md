# 项目状态（STATUS）

## 当前阶段
- 阶段：**T00–T02 完成**（A 布局基线骨架）；另执行**「识别提升与识别信息自然语言化」专项方案**（D008/D009/D010）：Phase 1 微调+评测、Phase 2 开放词表融合、Phase 3 facts-first 自然语言层；**「识别细化与物体属性增强」专项方案（Phase 4，D011/D012）**：阶段 A 类别细化、阶段 B 确定性属性+语义预留。
- 专项方案进度：**Phase 1（微调+Track1 评测+适配器接入）done**（val mAP50=0.848，pen recall 0→0.793、monitor 0.643→0.929，real 适配器已用微调权重）；**Phase 2（开放词表融合）done**（CPU+GPU 冒烟，6GB GPU 可行性已确认，峰值 0.732GiB、热启 0.025s/图）；**Phase 3（facts-first NL + interpret API + 前端展示）done**。**delivery-reviewer 三阶段评审整改 done**（第一轮：严重项 S1/S2/S3 + 证据缺口 G1/G2 + 警告 W3/W7/W8；第二轮复核：“有条件通过、三阶段可进入验收”，W-new-1/2/3 + W8 收尾 4 项非阻塞条件全部处理，全量单测 **113 绿**、前端 tsc exit 0）。**Phase 4 阶段 A（类别细化 9→23 训练类+other）done**：category_map v2、build_desk 泛化重建 data/desk_fine(1549/97,0丢弃)、desk_fine 重训(100ep/3407s/GPU_mem峰值2.01G)、Track1b 评测(val97 mAP50=0.747/mAP50-95=0.555，父类聚合 cup召回−0.022/bottle召回+0.018 未显著掉总召回)、适配器+契约+scene_facts/render_nl 全接入24类、real 端到端冒烟(细类 cable/charger/headphones/lamp/thermos_cup/tissue 真实检出)、全量单测 **128 绿**；delivery-reviewer 阶段 A 只读评审**「通过」**（无严重项；W1 样例 v2 索引/源、W2 全量显存 2.01G 仓内证据两条非阻塞警告已处理，复跑仍 128 绿）。**Phase 4 阶段 B（确定性属性+语义预留）done**：新增 object_attributes.py（颜色需原图取像素、几何由 bbox_desk 派生，纯函数确定性免训练无新依赖）、scene_facts 每物体附 attributes（SceneObject.bbox_image + compute_scene_facts image 参数）、service._load_interpret_image 从 detect job 原图取像素、scene_facts.schema 扩展 attributes（color/几何 + semantic 预留块恒 blocked、additionalProperties 受控）、render_nl 融入“X色+竖放/横放+大/中/小号”（语义 blocked 不生成推断词）、vl_interpreter.apply_semantic_attributes 预留接口（H01 护栏）、前端 api.ts/App.tsx 展示色块+颜色+几何；全量单测 **176 绿**（新增 object_attributes 30 + scene_facts 6 + contracts 3 + interpret_flow 2 + render_nl 3 + vl_interpreter 4）、前端 tsc+vite build exit 0；real desk_fine 端到端取色冒烟（4 val 图取色非 unknown、几何齐全、semantic 全 blocked、deterministic、过 schema）。Track2（用户冻结集）外部阻塞。
- 已通过门槛：**G0 可运行环境**、**G1 契约稳定**（新增 scene_facts/vl_relations 契约与样例可校验）。
- 当前阻塞：远端 VL/生成凭据未提供（阻塞 B 与 VL 真实路径）；**用户冻结评测集照片未入 `data/eval_raw/`**（阻塞 Phase 2 Track2）；git init/首次提交待用户授权。
- 下个任务：**Phase 4 完成**（阶段 A 类别细化 + 阶段 B 确定性属性均 done）；等待用户照片→ Track2（凌乱桌面冻结集评测）；或 VL 凭据到位→ 接通语义属性（apply_semantic_attributes 已预留）；或负责人指定下一 T 编号任务。

## 任务进度总览
| 任务 | 状态 | 备注 |
| --- | --- | --- |
| T00 范围与环境 | done | 环境已实测记录，A/B 范围已明确 |
| T01 模型技术验证 | in_progress | 检测子项 **verified**（YOLOv10n 真实图 7 框）；VL/生成子项 blocked（缺远端凭据） |
| T02 契约与骨架 | done | 前后端启动、健康检查通过、契约样例可校验；桌面识别端到端（mock+real）跑通；G0/G1 达成 |
| T03–T13 | not-started | 按依赖推进 |

---

## 完成报告

```text
任务 ID：T00
状态：done（含 blocked 前置项）
需求覆盖：FR13（运行模式与能力探测）、WORKFLOW 5.2 T00 行、G0（部分）、章程第一节环境基线
实现说明：
  完成 Windows 与 WSL2 双侧环境实测（Python/Node/Git/GPU/磁盘/密钥/Git状态），
  与用户讨论补全四项环境决策，创建 ENVIRONMENT/DECISIONS/STATUS 记录、
  数据与权重目录及 .gitignore；明确 A 可推进、B 被凭据阻塞。
变更文件：
  docs/ENVIRONMENT.md、docs/DECISIONS.md、docs/STATUS.md、
  .gitignore、data/images/.gitkeep、data/exports/.gitkeep、weights/.gitkeep、
  artifacts/probe_wsl.sh、artifacts/probe_T00_2026-10-11.txt
验证命令：
  python --version; node --version; npm --version; git --version; nvidia-smi（Windows）
  wsl -d Ubuntu-24.04 -- bash artifacts/probe_wsl.sh（WSL：lsb_release/python3/pip/venv/node/nvidia-smi/nvcc/df）
  python3 -m venv /tmp/t00_venvtest（WSL：验证 ensurepip 可用性）
  Get-ChildItem env:（密钥名匹配）、Test-Path .git、文件树枚举
验证结果：
  通过：环境项实测 9 项均取得确定值；数据/权重目录创建成功；.gitignore 生效；无密钥值输出。
  失败：0。
  未执行/blocked：
    - WSL venv 创建失败 → ensurepip 不可用，需 `sudo apt install python3.12-venv python3-pip`（未执行 sudo，待授权）。
    - torch.cuda 实测未执行（PyTorch 未安装，属 T01）。
    - 模型真实推理未执行（无权重/凭据/照片，属 T01）。
真实运行：
  无模型真实推理（T00 不含）；探测原始输出见 artifacts/probe_T00_2026-10-11.txt。
剩余限制：
  - Python 依赖链在 ensurepip 补全前无法安装。
  - B 阶段真实 VL/生成在用户提供远端凭据前无法验收。
  - 真实照片未到位，T01 真实检测验证与 T13 验收阻塞。
下一任务：T01 模型技术验证
  所需输入：(1) 授权执行 apt 安装 python3.12-venv/pip；(2) 安装 PyTorch(CUDA) 并实测 torch.cuda；
           (3) 下载 YOLOv10 小尺寸权重 + 至少 1 张授权桌面照片；(4) 远端 VL/生成凭据（B 相关，可延后）。
```

---

## 阶段性报告（T01 进行中）

```text
任务 ID：T01（检测子项完成；VL/生成子项 blocked）
状态：in_progress（检测 verified；VL/生成 blocked）
需求覆盖：WORKFLOW 5.2 T01、FR03（真实检测）、G3 前置、章程第一节 GPU 硬边界
实现说明：
  解除 ensurepip；建 WSL venv；装 torch 2.6.0+cu124 并实测 GPU；获取 YOLO-DeskDataset（CC BY 4.0）；
  下载 yolov10n.pt（v8.3.0）并装 ultralytics 8.4.175；在真实 val 图上 GPU 跑通检测并保存标注图+JSON。
变更文件：
  docs/ENVIRONMENT.md、docs/DECISIONS.md（D005/D006）、docs/DATASET.md、docs/STATUS.md、
  artifacts/probe_torch_cuda.py、artifacts/probe_torch_cuda_result.json、
  artifacts/run_t01_detection.py、artifacts/run_t01.sh、artifacts/t01_detection/（result.json + 标注图）、
  weights/yolov10n.pt、data/YOLO-DeskDataset/（gitignore，不入库）
验证命令：
  sudo apt-get install -y python3.12-venv python3-pip
  python3 -m venv ~/venvs/astradesk；pip install torch torchvision --index-url .../cu124；pip install ultralytics
  ~/venvs/astradesk/bin/python artifacts/probe_torch_cuda.py
  bash artifacts/run_t01.sh（内部 timeout 240 跑 run_t01_detection.py）
  git clone（Windows 侧代理）获取数据集；curl（Windows 侧代理）下载 yolov10n.pt
验证结果：
  通过：ensurepip；venv；torch.cuda（1024×1024 矩乘）；数据集 1646 图+标签配对；
        真实检测 7 框（laptop0.94/mouse0.89/bottle/book/teddy bear），首次含加载 2.27s，显存峰值 56.64MiB。
  失败：0。
  未执行/blocked：Qwen-VL 与生成后端验证（缺远端凭据）——T01 剩余子项，如实标 blocked。
真实运行：
  检测为真实 GPU 推理（非 mock）：输入 data/YOLO-DeskDataset/dataset/val/images/img (1).jpg（1441×1080），
  模型 yolov10n.pt（sha256 11287ed0…c16b6f），输出 artifacts/t01_detection/（result.json + 标注图）。
  尚无 VL/生成真实运行（缺凭据）。
剩余限制：
  - yolov10n 为 COCO 预训练，与数据集 80 桌面类别不同；桌面类别精度待 T14 微调后评测。
  - YOLOv10/ultralytics 为 AGPL-3.0，闭源/商用分发需许可评估。
  - 6GB 显存硬边界；远端 VL/生成为确定路线（D003）。
下一步：
  T02 契约与骨架（不依赖真实模型，可立即推进）；VL/生成验证待用户提供凭据后补 T01 剩余子项。
```

---

## 完成报告（T02）

```text
任务 ID：T02
状态：done
需求覆盖：WORKFLOW 5.2 T02、FR01（上传校验）、FR03（真实检测）、FR13（运行模式与错误）、
          PRD 5.2（坐标契约）、PRD 8.2/8.3（核心对象/API 基线/统一错误）、G0、G1、H01（ID 守恒接口层）
实现说明：
  建立后端（FastAPI + SQLAlchemy + Pydantic）与前端（React+TS+Vite）骨架；定义运行模式
  （real/mock，real 缺权重报 MODEL_UNAVAILABLE 不静默回退）；实现桌面识别端到端：
  创建项目→上传（EXIF 校正/去元数据/magic bytes 校验/服务端生成路径）→检测任务（202+后台执行）
  →坐标归一化还原→结果查询；写 contracts JSON Schema 与合法/非法样例；坐标往返转换模块。
变更文件：
  pyproject.toml、README.md、locks/python.lock.txt、
  packages/__init__.py、packages/vision/{__init__,detector,preprocess}.py、packages/layout/{__init__,coordinates}.py、packages/generation/__init__.py、
  services/api/{__init__,app,routes,service,config,schemas,errors,db,storage}.py、services/worker/{__init__,__main__,runner}.py、
  contracts/{README.md,detection_result.schema.json,error.schema.json}、contracts/samples/{detection_result.valid,detection_result.invalid,error.valid,error.invalid}.json、
  apps/web/{package.json,vite.config.ts,tsconfig.json,index.html}、apps/web/src/{main.tsx,App.tsx,api.ts,styles.css}、
  tests/{conftest,test_coordinates,test_contracts,test_detection_flow}.py、
  artifacts/{run_t02_real_detect.py,run_t02.sh,run_t02_api.sh}、artifacts/t02_detect/（result.json + 叠框图）、
  docs/{STATUS,ENVIRONMENT,DECISIONS}.md
验证命令：
  ~/venvs/astradesk/bin/pip install -e '.[dev]'
  ASTRADESK_RUN_MODE=mock ~/venvs/astradesk/bin/python -m pytest -q
  bash artifacts/run_t02.sh        # real 模式经完整 API 栈跑真实检测
  bash artifacts/run_t02_api.sh    # uvicorn 启动 + /health + /capabilities + openapi 路由清单
  cd apps/web; npm install; npm run build
验证结果：
  通过：pytest 16/16（契约合法/非法样例、坐标往返与边界、检测端到端 mock、real 缺权重不回退、
        伪装/不支持格式被拒、资产读取）；uvicorn 启动 /health→200、/capabilities 正常、8 条路由注册；
        前端 npm run build 通过（tsc 无类型错误，产出 dist/）。
  失败：0。
  未执行/blocked：git init 与首次提交（待用户授权）；远端 VL/生成相关接口（缺凭据，本任务不涉及）。
真实运行：
  real 模式经完整 API 栈（路由→服务→真实 YOLOv10 GPU）对数据集真实 val 图检测：
  输入 data/YOLO-DeskDataset/dataset/val/images/（首张 jpg），模型 yolov10n.pt，run_mode=real，
  status=succeeded，6 个框（laptop0.939/mouse0.893/bottle0.403/teddy bear×2/book0.250），首次含加载 3.92s；
  证据 artifacts/t02_detect/result.json 与叠框图（图片不入库）。
剩余限制：
  - yolov10n 为 COCO 预训练，未映射到 PRD 10 桌面类（T04 建 configs/category_map.yaml）。
  - worker 仅最小轮询；租约/心跳/重启过期置 failed 属 T06–T07。
  - 仅实现检测链；项目删除级联/分页、revision/坐标推导落库属 T03/T05。
  - device 字段在 real 运行时报告为 auto（未影响 GPU 推理，T01 已证 CUDA），待后续精确化。
下一任务：T03 图片与项目
  所需输入：无外部阻塞；在现有骨架上补项目 CRUD/列表分页/删除级联（取消任务+删文件+防迟到输出复活）、
           上传校验边界用例（超 10MB/超 2500 万像素/损坏图）与尺寸一致性测试。
```

---

## 完成报告（识别提升方案 Phase 1：数据修复 + 微调 + Track1 评测 + 适配器接入）

```text
任务 ID：识别提升方案 Phase 1（微调提前，C/T14）
状态：done
需求覆盖：FR03（真实检测+可追溯 source）、FR13（能力探测）、PRD 5.1（9 产品类）、D008
实现说明：
  数据修复 tools/build_desk9.py（标签 int/float 归一、按 configs/category_map.yaml 重映射为 9 产品类、
  原始 80 类旁挂 labels_raw 追溯、images 符号链接）→ data/desk9（train1490/val93）+ data9.yaml；
  微调 tools/train_desk9.py（起始 yolov10n.pt、imgsz=640、batch=8、AMP、patience=20、100 epoch、凌乱鲁棒增强），
  setsid nohup 脱离会话后台跑→ best.pt 复制为 weights/yolov10_desk9.pt；
  适配器接入 detector.py（detect_real 每框 source=yolov10:<stem>）+ config.py（real 默认权重→yolov10_desk9.pt，缺权重仍报 DetectorUnavailable 不回退）；
  Track1 评测 tools/eval_detect.py（基线 COCO yolov10n vs 微调 desk9，同一 GT 映射 9 产品类算每类 P/R）。
变更文件：
  configs/category_map.yaml、tools/{build_desk9,train_desk9,eval_detect}.py、packages/vision/{detector,category_map}.py、
  services/api/config.py、data/desk9/（gitignore）、weights/yolov10_desk9.pt（gitignore）、
  artifacts/t_finetune/{train_report.json,eval_track1.json,smoke_real_desk9.json,train_gpu_mem_evidence.txt}、artifacts/{smoke_real_desk9.py,extract_train_gpumem.py}、
  docs/{DECISIONS(D008),DATASET(§7),ENVIRONMENT,STATUS}.md
验证命令：
  ~/venvs/astradesk/bin/python tools/build_desk9.py
  setsid nohup ~/venvs/astradesk/bin/python tools/train_desk9.py > /tmp/train_desk9.log（脱离会话）
  ~/venvs/astradesk/bin/python tools/eval_detect.py
  ASTRADESK_RUN_MODE=real ~/venvs/astradesk/bin/python artifacts/smoke_real_desk9.py
  ~/venvs/astradesk/bin/python -m pytest -q
验证结果：
  通过：微调训练完成（elapsed 4023.5s≈67min wall；日志记 100 epoch 训练 1.061h，全程峰值 GPU_mem **1.91G 十进制≈1.78GiB** 无 OOM，证据 artifacts/t_finetune/train_gpu_mem_evidence.txt）；
        微调 val(93) mAP50=0.848 / mAP50-95=0.650 / P=0.929 / R=0.795；
        **词表缺口被补上（Track1 每类 recall 基线→微调）**：pen 0.0→0.793（COCO tp=0/fn=29→微调 tp=23）、
        monitor 0.643→0.929（P 0.545→0.963）、book 0.155→0.732、cup 0.222→0.815、bottle 0.31→0.637、
        mobile_phone 0.125→0.625（P 0.333→1.0）、laptop 0.591→0.894、keyboard 0.755→0.939、mouse 0.716→0.925；
        适配器 real 模式冒烟（artifacts/smoke_real_desk9.py）：model_name=yolov10_desk9、run_mode=real、
        检出含 pen(5)/book(4)/cup(6)/laptop(0)/mouse(3)、all_names_in_product_vocab=true、all_source_finetuned=true；
        pytest 全绿（注：109 为三阶段+评审整改后统一复跑的全量数；Phase 1 完成时点用例数少于此、当时亦全绿。三份报告在方案末尾一并定稿，未在各阶段分别冻结计数）。
  失败：0。
  未执行/blocked：无（Phase 1 内部无外部阻塞；凌乱桌面召回结论属 Phase 2 Track2，依赖用户照片）。
真实运行：
  均为真实 GPU 推理（非 mock）：训练 device=0（RTX 4050 6GB）；Track1 在 desk9 val(93) 真实推理；
  适配器冒烟输入 data/desk9/val/images 前 3 图，模型 weights/yolov10_desk9.pt，run_mode=real，
  证据 artifacts/t_finetune/{train_report.json,eval_track1.json,smoke_real_desk9.json}。
剩余限制（诚实标注）：
  - val 仅 93 图 + 数据集干净桌面偏置 + 无会话元数据可能连拍泄漏 → Track1 数字仅供**相对比较**，非泛化终值；
    凌乱桌面真实召回以用户冻结集人工复核（Phase 2 Track2）为准。
  - bottle（P 0.686）/mobile_phone（R 0.625）仍偏低；mobile_phone 样本少（val 仅 16 实例）。
  - 冒烟将全图当桌面（无用户标定桌面框）为近似；真实使用时应传 desk_bbox_image。
  - YOLOv10/ultralytics 为 AGPL-3.0，商用需许可评估。
下一任务：Phase 2 Track2（待用户照片入 data/eval_raw）；各阶段 delivery-reviewer 评审。
```

---

## 完成报告（识别提升方案 Phase 2：开放词表融合）

```text
任务 ID：识别提升方案 Phase 2（YOLO-World 开放词表融合）
状态：done（Track2 评测 blocked—外部依赖用户照片）
需求覆盖：FR03（可追溯 source）、FR04（人工补框前置）、FR13（能力探测）、D009
实现说明：
  新增 packages/vision/open_vocab.py（YOLOWorld + set_classes，提示词=9 产品类+常见桌面物归 other）
  与 fusion.py（主检测全保留，补检测映射产品类后类无关 NMS 抑制，IoU≥fusion_iou 才保留并打 source=yolo-world）；
  接入 service.process_detect_job（real+openvocab_enabled 时融合，缺权重报 MODEL_UNAVAILABLE 不回退）、
  config.py（ASTRADESK_OPENVOCAB_* / FUSION_IOU，默认关闭且带默认值）、routes.py（capabilities 报 open_vocab）；
  契约 detection_result.schema.json 的 class_id/class_name 枚举收窄为 9 产品类+other，detection 加 source 字段。
变更文件：
  packages/vision/{open_vocab,fusion,detector}.py、services/api/{config,service,routes,schemas}.py、
  contracts/detection_result.schema.json、contracts/samples/detection_result.{valid,invalid}.json、
  tests/test_openvocab_service.py、artifacts/smoke_openvocab.py、locks/python.lock.txt、docs/DECISIONS.md(D009)
验证命令：
  ~/venvs/astradesk/bin/python -m pytest -q（全量）
  ASTRADESK_RUN_MODE=real 下 CPU 冒烟：python artifacts/smoke_openvocab.py
  GPU 6GB 可行性：python artifacts/smoke_openvocab_gpu.py
验证结果：
  通过：pytest 全绿（注：109 为三阶段+评审整改后统一复跑的全量数，Phase 2 完成时点用例数少于此、当时亦全绿）（含 test_openvocab_service 3 个 monkeypatch：融合合并、MODEL_UNAVAILABLE 不回退、mock 跳过开放词表）；
        开放词表冒烟跑通（**真实主检测 desk9 2 框 + YOLO-World 22 raw → 融合 20 框，18 框由开放词表新增**；映射正确：pen→5/cup→6/bottle→7/book→4/mouse→3，非产品物归 other(9)——**归 other 者其原始提示词名由 `raw_class_name` 保留(FR03)，在 `smoke.json`/`smoke_cpu.json` 的 `fused`/`added_by_openvocab` 条目可直读为 lamp/power bank/tissue**；speaker 原始检出(0.2509)被类无关 NMS 抑制、未进 fused，其→other 映射改由 `test_fusion` 参数化用例覆盖，非 smoke 直读）；
        **重叠抑制以真实主检测框验证**：open-vocab laptop(0.9478) 被真实主检测 laptop(0.9338) 抑制（IoU≥0.5、主检测优先），未进入 added_by_openvocab；主检测为真实 detect_real（payload.primary_is_synthetic=false，非合成框）；
        **6GB GPU 可行性已实测确认**（device=0 峰值 reserved 0.732 GiB / allocated 0.682 GiB，远小于 6GB；GPU 热启 0.025s/图、冷启 8.2s，22 raw 检出）。
  失败：0。
  未执行/blocked：Track2（tools/eval_messy.py 用户冻结集人工复核）—用户照片未入 data/eval_raw/，外部阻塞。
真实运行：
  开放词表为真实 YOLO-World 推理（非 mock）、主检测为真实 detect_real(yolov10_desk9.pt)（非合成框）：权重 weights/yolov8s-world.pt（27.2MB），首运行自动装 clip(git)+ftfy/regex/tqdm/wcwidth 并下 338MB CLIP 权重；
  **CPU 冷启 526s 为一次性历史观测**（含首次 pip 装 clip 依赖 + 下 338MB CLIP，依赖已缓存后不可复现）；依赖缓存后本轮重跑 CPU 开放词表推理热启 **~6.0s/图**（证据 `smoke_cpu.json` 的 `elapsed_seconds=6.013`，device=cpu，2 primary+21 raw→20 fused/18 新增）；GPU（cuda:0）冷启 8.2s、热启 0.025s/图，峰值 reserved 0.732 GiB；证据 artifacts/t_openvocab/{smoke.json(GPU),smoke_cpu.json(CPU),smoke_cached.json,gpu_feasibility.json}。
剩余限制：
  - 开放词表默认关闭（ASTRADESK_OPENVOCAB_ENABLED=false）；6GB GPU 已确认可行，启用时建议走 GPU（热启 0.025s/图）。
  - 凌乱桌面召回提升的定量结论需 Track2（用户冻结集）佐证，当前未得。
  - ultralytics/YOLO-World 为 AGPL-3.0，商用需许可评估。
下一任务：Phase 2 Track2（待用户照片）；或 Phase 1 训练完后的 Track1 评测。
```

---

## 完成报告（识别提升方案 Phase 3：facts-first 自然语言层）

```text
任务 ID：识别提升方案 Phase 3（scene_facts + render_nl + vl_interpreter + interpret API + 前端）
状态：done（VL 真实路径 blocked—缺远端凭据）
需求覆盖：H01（事实清单不被改写）、H07（杯瓶-电子设备距离）、PRD 6.2（软目标）、FR02/FR06（非法不静默修正）、D010
实现说明：
  新增 packages/understanding/：scene_facts.py（确定性几何事实：分区/九宫格占用留白/最大连续空闲矩形/
  聚类/对齐/取用便利/H07 距离，单一事实来源）、render_nl.py（模板中文渲染绑定 6.2 软目标）、
  vl_interpreter.py（B 阶段 blocked 接口，护栏：只引用已有 object_id/不改事实/schema 校验/版本化 prompt/有界重试/缺凭据显式报错）；
  新增 contracts/scene_facts.schema.json + vl_relations.schema.json + 样例、prompts/vl_interpret.md；
  API 新增 interpret 任务全链路（db.Job.request_json 幂等迁移、schemas InterpretJobIn/InterpretObjectIn、
  service create/process_interpret_job—bbox_desk 后端推导、routes POST .../jobs/interpret + capabilities features 加 interpret）；
  前端 api.ts 加 source/interpret 类型与 createInterpretJob，App.tsx 检测成功后自动触发 interpret 并展示场景描述/维度/H07 告警，styles.css 配套。
变更文件：
  packages/understanding/{__init__,scene_facts,render_nl,vl_interpreter}.py、
  contracts/{scene_facts,vl_relations}.schema.json、contracts/samples/scene_facts.{valid,invalid}.json、prompts/vl_interpret.md、
  services/api/{db,schemas,service,routes}.py、apps/web/src/{api.ts,App.tsx,styles.css}、
  tests/{test_scene_facts,test_render_nl,test_vl_interpreter,test_interpret_flow,test_contracts}.py、artifacts/gen_scene_facts_sample.py、docs/DECISIONS.md(D010)
验证命令：
  ~/venvs/astradesk/bin/python -m pytest -q（全量）
  cd apps/web; npx tsc --noEmit（前端类型检查）
验证结果：
  通过：pytest 全量 109 用例全绿（Phase 3 新增 scene_facts 17 + render_nl 8 + vl_interpreter 8 + interpret E2E 6 + 契约 scene_facts valid/invalid；评审整改再补 W7 能力探测 1 + vl_relations 契约 valid/invalid 2 → 共 109）；
        前端 tsc --noEmit 无类型错误。interpret E2E 覆盖：显式 objects（内嵌 scene_facts 过契约校验+description.text 非空+vl.enabled False）、
        detect_job_id 来源、无来源 400 INVALID_REQUEST、跨项目 404 JOB_NOT_FOUND、非法类 tv→failed SCHEMA_INVALID。
  失败：0。
  未执行/blocked：vl_interpreter 真实 VL 调用—缺远端凭据，接口显式 VLUnavailable（B-stage blocked），单测用 mock backend 验证护栏与有界重试。
真实运行：
  interpret 任务经完整 API 栈（路由→服务→确定性 facts→模板 NL）在 mock 检测上跑通：bbox_image→bbox_desk 后端推导（约定3），
  输出 count/scene_facts/description/vl（enabled=False, reason=B-stage blocked）；证据由 tests/test_interpret_flow.py 内嵌契约校验。
剩余限制：
  - movement_saving（减少移动）为规划期指标，场景描述阶段标 N/A（需目标布局）。
  - 所有距离/面积为桌面归一化图像空间相对量，非厘米物理量（未经相机标定）。
  - VL 关系增强真实路径待远端凭据（B 阶段）；当前 interpret 不调 VL。
下一任务：Phase 1 Track1 评测（待训练完）；各阶段 delivery-reviewer 评审。
```

---

## 评审整改报告（delivery-reviewer 三阶段评审，2026-10-12）

```text
任务 ID：识别提升方案 三阶段 delivery-reviewer 评审整改
状态：done（严重项 S1/S2/S3 与证据缺口 G1/G2、警告 W3/W7/W8 已修；其余警告记为局限）
需求覆盖：交付真实性（约定1 mock/fixture 显式标识、不静默回退）、FR03 可追溯、H01 事实不被改写、章程红线1/7（不过度声称）
整改说明（逐项）：
  S1（严重·合成主检测混入“真实运行”证据）：重写 artifacts/smoke_openvocab.py，主检测改为真实
     detector.detect_real(yolov10_desk9.pt)（payload.primary_is_synthetic=false）；GPU 重生成 smoke.json/smoke_cached.json。
     证据：2 真实主检测(laptop 0.9338/book 0.8045) + 22 raw 开放词表 → 融合 20 框（18 新增）；
     **重叠抑制以真实框验证**：open-vocab laptop(0.9478) 被真实主检测 laptop(0.9338) 抑制（IoU≥0.5、主检测优先）。
     STATUS Phase 2 与 D009 措辞同步更正（原“21 raw→20 fused”→真实主检测版本）。
  S2（严重·“106 全绿”回填）：Phase 1/2 报告标注 109 为三阶段+评审整改后统一复跑的全量数、
     各阶段完成时点用例数少于此（当时亦全绿），不再声称各阶段当场跑满 106/109。
  S3（严重·数据划分虚假声明）：DATASET §7 与 D008 第5条原称“从原 train 随机留 ~4% 作训练期 val”，
     与 build_desk9.py 实际（沿用数据集自带 train/val、仅丢弃无有效框图）不符；已改为事实描述并补记
     “未按方案做 10-15% 内部随机留出”为偏离/局限（同源泄漏风险由数据集原划分决定、非本仓库可控）。
  G1（训练 GPU_mem 无仓内证据 + 数值口误）：新增 artifacts/extract_train_gpumem.py 从训练日志提取逐 epoch 峰值，
     产 artifacts/t_finetune/train_gpu_mem_evidence.txt；实测峰值 **1.91G 十进制≈1.78GiB**（非早期所写 1.89GiB），
     STATUS Phase 1 / ENVIRONMENT 两处数值与单位已更正并引证据。
  G2（权重 sha256 无 manifest）：新增 tools/weights_manifest.py → artifacts/weights_sha256.json（含 desk9/world/v10n/CLIP 四权重哈希+字节+来源）；
     yolov10n.pt 哈希与 T01 所记一致。ENVIRONMENT 已引用。
  W3（vl_relations 无样例/README/契约测试）：补 contracts/samples/vl_relations.{valid,invalid}.json（invalid 含未知谓词/空 subject_id/缺 explanation/额外 rewritten_facts 以验 H01）、
     test_contracts.py 新增 valid 通过/invalid 被拒两测、contracts/README.md 补 scene_facts/vl_relations 条目。
  W7（能力探测）：routes.capabilities 改为仅在 openvocab_enabled **且** 权重存在时才 advertise open_vocab 特性（启用但缺权重会使检测 MODEL_UNAVAILABLE，不当可用能力上报）；新增 test_capabilities_open_vocab_only_advertised_when_weights_exist。
  W8（speaker 映射证据）：added_by_openvocab 现记录映射后 class_id（other=9/pen=5/cup=6/bottle=7/book=4/mouse=3）；归 other 者其原始提示词名由 `raw_class_name` 保留（见第二轮 W-new-3），在 smoke.json/smoke_cpu.json 的 fused.other 可直读为 lamp/power bank/tissue；speaker 原始检出(0.2509)被类无关 NMS 抑制、未进 fused，其→other 映射改由 test_fusion 参数化用例覆盖（非 smoke 直读）。
变更文件：
  artifacts/{smoke_openvocab.py,extract_train_gpumem.py}、artifacts/t_openvocab/{smoke.json,smoke_cached.json}、
  artifacts/t_finetune/train_gpu_mem_evidence.txt、artifacts/weights_sha256.json、tools/weights_manifest.py、
  services/api/routes.py、tests/{test_openvocab_service.py,test_contracts.py}、contracts/samples/vl_relations.{valid,invalid}.json、contracts/README.md、
  docs/{STATUS,DECISIONS,DATASET,ENVIRONMENT}.md
验证命令：
  ASTRADESK_RUN_MODE=real ~/venvs/astradesk/bin/python artifacts/smoke_openvocab.py --device 0（重生成真实主检测融合证据）
  ~/venvs/astradesk/bin/python artifacts/extract_train_gpumem.py --log /tmp/train_desk9.log
  ~/venvs/astradesk/bin/python tools/weights_manifest.py
  ASTRADESK_RUN_MODE=mock ~/venvs/astradesk/bin/python -m pytest -q
验证结果：
  通过：pytest 全量 **109** 用例全绿（exit 0，无 F/E/skip；较评审前 106 新增 W7 能力探测 1 + vl_relations 契约 valid/invalid 2）；
        smoke.json 重生成后 primary_is_synthetic=false、主检测为真实 detect_real、重叠抑制以真实框生效。
  失败：0。
  未执行/blocked：Track2（用户照片未入 data/eval_raw）与 VL 真实路径（缺凭据）仍外部阻塞，未因整改而变。
剩余限制（评审其余警告，如实记录、本轮未改代码）：
  - 训练仍为单次运行、无多种子重复；Track1 val 仅 93 图且干净偏置，数字仅供相对比较。
  - 开放词表提示词表为人工拟定，未做提示词消融/调优（不面向用户照片调参）。
  - scene_facts 几何量为桌面归一化图像空间相对量，非厘米物理量（未经相机标定）。
  - 前端 interpret 展示仅在检测成功且 capabilities.features 含 interpret 时触发；未做独立上传入口。
下一任务：等待用户照片 → Phase 2 Track2（tools/eval_messy.py 人工复核）；或负责人指定下一 T 编号任务。
```

---

## 评审整改报告·第二轮（delivery-reviewer 复核后整改，2026-10-12）

```text
任务 ID：识别提升方案 第二轮复核整改（W-new-1/2/3 + W8 收尾）
状态：done（复核结论“有条件通过、三阶段可进入验收”的 4 项非阻塞条件全部处理）
需求覆盖：FR03 可追溯（原始类名+桌面矩形基准）、约定3（bbox_desk 后端推导）、章程红线7（不过度声称）
整改说明（逐项）：
  W-new-3（融合保留开放词表原始类名，满足 FR03）：Detection 加 raw_class_name 字段（detector.py）；
     fusion.fuse 对补检测 replace 时写 raw_class_name=映射前提示词名（归 other 后仍可知“原本是什么”）；
     全链路打通：db.py（Detection 列 + _migrate 幂等补列）、service.py（_persist_detections 落库 + job_to_dict 序列化 + interpret）、
     schemas.py（DetectionOut 加 raw_class_name，修复响应层丢字段的根因）、contracts/detection_result.schema.json + samples、
     前端 api.ts（Detection.raw_class_name?）+ App.tsx（与 class_name 不同时以 (raw) 显示）+ styles.css(.raw)。
     测试：test_fusion 3 处加 raw_class_name 断言 + 新增 test_secondary_to_other_preserves_raw_class_name(speaker)；
     test_openvocab_service 加 API 回写断言（pen→"pen"、主检测 laptop→None/""）。
  W-new-2（interpret 结果回写桌面矩形与“全图假设”标记）：service.process_interpret_job 记 desk_provided，
     result_json 回写 desk_bbox_image 与 desk_assumed_full_image（未标定桌面时为 true，全图当桌面）；
     前端 api.ts InterpretResult 加两字段。测试：test_interpret_flow 两用例分别断言显式桌面框(False)与 detect_job 来源(True)。
  W-new-1（CPU 冒烟无仓内证据）：新增 artifacts/t_openvocab/smoke_cpu.json（device=cpu，2 primary+21 raw→20 fused/18 新增，
     elapsed_seconds=6.013）；smoke_openvocab.py payload 的 fused/added_by_openvocab 加 raw_class_name 后重生成 GPU smoke.json。
     STATUS/ENVIRONMENT/D009 三处把“CPU 冷启 526s”显式标注为**一次性历史观测**（含首次 pip 装 clip+下 338MB CLIP，依赖缓存后不可复现），
     并以 smoke_cpu.json 实测热启 ~6.0s/图为据（GPU/CPU 比由 ~1000× 更正为 ~240×）。
  W8（收尾）：见第一轮报告 W8 行——措辞改为 raw_class_name 可直读 lamp/power bank/tissue，speaker 被 NMS 抑制改由单测覆盖。
变更文件：
  packages/vision/{detector,fusion}.py、services/api/{db,service,schemas}.py、contracts/detection_result.schema.json、
  contracts/samples/detection_result.valid.json、artifacts/{smoke_openvocab.py,t_openvocab/{smoke.json,smoke_cpu.json}}、
  tests/{test_fusion.py,test_openvocab_service.py,test_interpret_flow.py}、apps/web/src/{api.ts,App.tsx,styles.css}、
  docs/{STATUS,DECISIONS,ENVIRONMENT}.md
验证命令：
  ASTRADESK_RUN_MODE=real ~/venvs/astradesk/bin/python artifacts/smoke_openvocab.py --device 0（GPU 证据重生成含 raw_class_name）
  ASTRADESK_RUN_MODE=real ~/venvs/astradesk/bin/python artifacts/smoke_openvocab.py --device cpu --out artifacts/t_openvocab/smoke_cpu.json（CPU 证据）
  ASTRADESK_RUN_MODE=mock ~/venvs/astradesk/bin/python -m pytest（全量）
  cd apps/web; npx tsc --noEmit（前端类型）
验证结果：
  通过：pytest 全量 **113** 用例全绿（较第一轮 109 新增 4：test_secondary_to_other_preserves_raw_class_name 1 + test_fusion 参数化 speaker/lamp/tissue 3）；
        前端 tsc --noEmit exit 0；smoke.json/smoke_cpu.json 的 fused.other 条目 raw_class_name 可直读为 lamp/power bank/tissue。
  失败：0。
  未执行/blocked：Track2（用户照片未入 data/eval_raw）与 VL 真实路径（缺凭据）仍外部阻塞，未因整改而变。
剩余限制（第二轮复核提出、本轮未改代码，如实记录）：
  - W-new-4：packages.understanding 未登记 pyproject packages（当前靠 sys.path/根目录导入生效，打包发布前需补）。
  - W-new-5：render_nl.py 方位描述硬编码 user_side=bottom，top/left/right 时可能错轴，测试未覆盖这些方位。
  - W-new-6：interpret 结果暂无独立契约 schema（内嵌 scene_facts 已过 scene_facts.schema.json 校验）。
下一任务：等待用户照片 → Phase 2 Track2（tools/eval_messy.py 人工复核）；或负责人指定下一 T 编号任务。
```

---

## 完成报告·Phase 4 阶段 A（识别细化：词表 9→23 训练类+other，2026-10-13）

```text
任务 ID：Phase 4 阶段 A（A1–A7：类别细化）
状态：done（delivery-reviewer 阶段 A 只读评审结论「通过」；W1/W2 非阻塞一致性项已处理）
需求覆盖：FR01/FR03（可追溯原始类名+source）、PRD 5.1（产品词表，实质范围变化已授权 D011）、
          H01（事实清单不被改写）、坐标约定3（bbox_desk 后端推导）、章程红线1/7（无真实测量不编数字）
实现说明：
  将产品检测词表由 9 具体类细化为 23 训练类(0–22)+other(23)：拆 cup→4 杯型、bottle→5 瓶罐，
  将 cable/charger/tissue/paper/lamp/headphones/mouse_pad 等 other 高频物转正。细分标注全部现成
  （原始 80 类即独立类），零标注成本；泛化重建脚本+重训即得。全链路适配器/契约/事实层/渲染层已接入 24 类。
变更文件：
  configs/category_map.yaml（version 2）、tools/build_desk.py（新，泛化）、tools/train_desk_fine.py（新）、
  tools/eval_track1b.py（新）、tools/weights_manifest.py（新权重 note）、
  data/desk_fine/**（重建，未改原始数据集）、weights/yolov10_desk_fine.pt（训练产物，gitignore）、
  services/api/config.py:54、packages/vision/open_vocab.py、packages/understanding/{scene_facts,render_nl}.py、
  contracts/{detection_result,scene_facts}.schema.json、contracts/samples/detection_result.valid.json、
  tests/{test_category_map,test_fusion,test_scene_facts,test_contracts,test_openvocab_service}.py、
  artifacts/{run_train_desk_fine.sh,run_trial_desk_fine.sh,smoke_real_desk_fine.py}、
  artifacts/t_finetune/{train_report_desk_fine.json,eval_track1b.json,smoke_real_desk_fine.json,desk_fine_class_counts.json,train_desk_fine_gpu_mem_evidence.txt,train_desk_fine_full_gpu_mem_evidence.txt}、
  artifacts/weights_sha256.json、docs/{DECISIONS(D011),DATASET(§8),ENVIRONMENT,STATUS}.md
  W1/W2 收尾：artifacts/gen_scene_facts_sample.py（class_id→v2、source→desk_fine）+ 重生成 contracts/samples/scene_facts.valid.json；
  artifacts/extract_train_gpumem.py（结论注去除 Phase1 专有口误、泛化）→ 生成 train_desk_fine_full_gpu_mem_evidence.txt（全量峰值 2.01G 仓内证据）；
  artifacts/smoke_real_desk9.py（加历史脚本说明：默认权重已改 desk_fine，重跑须显式 ASTRADESK_YOLO_WEIGHTS=yolov10_desk9.pt）。
验证命令（仅列已执行）：
  ~/venvs/astradesk/bin/python tools/build_desk.py（重建 data/desk_fine）
  ASTRADESK_TRIAL=1 ~/venvs/astradesk/bin/python tools/train_desk_fine.py（2ep 试跑验 6GB 显存）
  ~/venvs/astradesk/bin/python tools/train_desk_fine.py（100ep 全量重训，后台终端）
  ~/venvs/astradesk/bin/python tools/eval_track1b.py（Track1b：desk9 vs desk_fine）
  ~/venvs/astradesk/bin/python tools/weights_manifest.py（sha256 留档）
  ASTRADESK_RUN_MODE=real ~/venvs/astradesk/bin/python artifacts/smoke_real_desk_fine.py（real 端到端）
  ASTRADESK_RUN_MODE=mock ~/venvs/astradesk/bin/python -m pytest -q（全量）
验证结果：
  通过：pytest 全量 **128** 用例全绿（exit 0；较 Phase 3 的 113 新增/扩充 category_map v2、fusion 细类、
        scene_facts 一致性、契约 24 类枚举等用例）。real 端到端冒烟 EXIT=0，4 图均 all_source_finetuned=true、
        all_names_in_product_vocab=true，细类真实检出 cable/charger/headphones/lamp/thermos_cup/tissue。
  失败：0。
  未执行/blocked：Track2（用户照片未入 data/eval_raw）仍外部阻塞；阶段 B 属性单测尚未实现（下一阶段）。
真实运行：
  模型 yolov10_desk_fine.pt（sha256 93ed28bf…d6208521）；real 模式 GPU device=auto；
  样本 data/desk_fine/val 前 4 图（img (1)/(10)/(11)/(114).jpg）；热启 0.015–0.081s/图（首图含加载 2.29s）；
  证据 artifacts/t_finetune/smoke_real_desk_fine.json。NL 渲染正确输出细类中文名（保温杯/耳机/充电器/数据线/台灯/纸巾）。
评测（Track1b，证据 artifacts/t_finetune/eval_track1b.json）：
  desk_fine 原生 val(97,23类)：mAP50=0.747 / mAP50-95=0.555 / P=0.864 / R=0.665（默认 conf，与 Phase1 desk9 mAP50=0.848 同口径）。
  保留 7 类强势：laptop mAP50=0.984、mouse=0.979、monitor=0.956、keyboard=0.949。
  转正新类（之前归 other 不可检）：mouse_pad=0.932、headphones=0.859、cup=0.883、thermos_cup=0.848、
    lamp=0.783、tissue=0.760、cable=0.732、paper=0.708、charger=0.663——7 种新物体现可检出（主要收益）。
  长尾类（val support 极小，噪声大）：can P0.431/R0.333(support 3)、waterpot P1.0/R0.344(5)、
    disposable_cup P0.644/R0.5(6)、plastic_cup P0.758/R0.5(10)。
  父类聚合对比（desk9 val 93 共同基准，conf=0.25，两模型同口径；desk9 侧精确复现 Phase1 数字）：
    cup：desk9 P0.84/R0.815 → desk_fine P0.843/R0.793（召回 −0.022，tp 110→107）；
    bottle：desk9 P0.686/R0.637 → desk_fine P0.592/R0.655（召回 +0.018，tp 72→74；精度 −0.094，细瓶罐互检致 fp 33→51）。
    结论：**细化未显著掉总召回**（cup −2.2pt、bottle +1.8pt），验收标准达成；bottle 父类精度下降为如实局限。
  家族内混淆：错误以 background(FN 漏检) 为主，跨类误分有限（cup→thermos_cup 仅 2、bottle↔plastic_bottle 4+1），
    说明细类确实分化而非块块互混。
剩余限制（诚实标注）：
  - val 干净桌面偏置、无会话分组、可能泄漏；细类 val support 极小（can/waterpot/disposable_cup 个位数），每类 P/R 仅供相对比较。
  - 总 mAP50 0.848→0.747 为词表 9→23 类、任务变难所致（含长尾），非退步；应看每类（保留类持平/提升、新增 7 转正类从不可检→可检）。
  - bottle 父类聚合精度 −0.094（细瓶罐间互检产生额外 fp）；类别不平衡（cable 1272 vs disposable_cup 140）可能偏向高频类。
  - 训练为单次运行、无多种子重复；凌乱桌面结论仍待用户冻结集（Track2 blocked）。
评审结论（delivery-reviewer 只读评审）：
  **通过**——全部核心验收标准达成（细类成功分化有混淆矩阵佐证、父类聚合不掉总召回 cup−0.022/bottle+0.018、
  适配器 real 用新权重 source 佐证、pytest 全绿 128），无严重项。两条非阻塞一致性警告已处理：
  - W1（scene_facts.valid.json class_id 为 v1 旧索引、source 仍 desk9）：已修 gen_scene_facts_sample.py 并重生成（cup 6→7、book 4→5、pen 5→6、desk9→desk_fine；cup/pen 保留 yolo-world 演示开放词表混源路径）。
  - W2（全量训练峰值 2.01G 缺仓内独立提取证据）：已用 extract_train_gpumem.py 从 /tmp/train_desk_fine.log 提取生成 train_desk_fine_full_gpu_mem_evidence.txt（逐 epoch 峰值，peak 2.01G@epoch24，自包含仓内证据）。
  - 建议项：smoke_real_desk9.py 已加历史脚本说明（避免重跑断言失败困惑）。
  处理后 pytest 全量复跑仍 **128 绿**（errors=0/failures=0/skipped=0，junitxml 核验）。
下一任务：Phase 4 阶段 B（B1 object_attributes.py 确定性颜色+几何属性，免训练）。
```

## 完成报告·Phase 4 阶段 B（确定性属性 + 语义属性预留，2026-10-13）

```text
任务 ID：Phase 4 阶段 B（B1–B5：确定性属性 + 语义预留）
状态：done（delivery-reviewer 阶段 B 只读评审结论「通过、无严重项」；W1/W2 非阻塞项已处理，S1 建议已采纳）
需求覆盖：FR06（VL 增强护栏）、H01（事实清单不被改写）、坐标约定3（bbox_desk 后端推导、bbox_image/bbox_desk 不混用）、
          章程红线1/7（无真实测量不编数字：语义属性恒 blocked、颜色 unknown 不编造）、约定7（资源归属校验）
实现说明：
  新增确定性免训练属性：object_attributes.py（纯函数、离线、可复现）——颜色从原图 bbox_image 区取量化直方图
  峰值代表色→ 12 中文基本色名+rgb/hsv（无原图→unknown，不编造）；几何从 bbox_desk 派生 aspect_ratio/orientation/size_class（恒可算）。
  scene_facts 每物体附 attributes（SceneObject.bbox_image + compute_scene_facts image 参数）；service 经 _load_interpret_image
  从 detect job 原图取像素（仅 detect_job 路径；显式 objects 无图→unknown）。schema 扩 attributes（color/几何 + semantic 预留块恒
  blocked、additionalProperties 受控、object_fact 必填）；render_nl 融入“X色+竖放/横放+大/中/小号”（语义 blocked 不生成推断词）；
  vl_interpreter.apply_semantic_attributes 为纯函数预留接口（同等护栏）；前端 api.ts/App.tsx 展示色块+颜色+几何。
变更文件：
  packages/understanding/object_attributes.py（新）、packages/understanding/{scene_facts,render_nl,vl_interpreter}.py、
  services/api/service.py（_load_interpret_image + project_id 归属校验）、
  contracts/scene_facts.schema.json、contracts/samples/scene_facts.valid.json（重生成，含真实色值）、
  artifacts/gen_scene_facts_sample.py（重写：合成纯色分区图，显式标识）、artifacts/smoke_attributes_desk_fine.py（新）、
  artifacts/t_finetune/smoke_attributes_desk_fine.json（新证据）、
  apps/web/src/{api.ts,App.tsx,styles.css}、
  tests/{test_object_attributes.py（新）,test_scene_facts.py,test_contracts.py,test_interpret_flow.py,test_render_nl.py,test_vl_interpreter.py}、
  docs/{DECISIONS(D012),ENVIRONMENT,STATUS}.md。无新依赖（locks/python.lock.txt 不变）。
验证命令（仅列已执行）：
  ~/venvs/astradesk/bin/python -m pytest -q --junitxml=...（全量，多次）
  cd apps/web; npm run build（tsc && vite build）
  ASTRADESK_RUN_MODE=real ~/venvs/astradesk/bin/python artifacts/smoke_attributes_desk_fine.py（real 端到端取色）
验证结果：
  通过：pytest 全量 **176** 用例全绿（errors=0/failures=0/skipped=0，junitxml 核验；较阶段 A 的 128 新增 48：
        object_attributes 30 + scene_facts 6（含5属性+1坐标不混用回归）+ contracts 3 + interpret_flow 2 + render_nl 3 + vl_interpreter 4）。
        前端 npm run build exit 0（tsc 无类型错、vite 构建成功）。real 端到端取色冒烟 EXIT=0。
  失败：0。
  未执行/blocked：语义属性真实 VL 后端验证（凭据未到位，apply_semantic_attributes 仅单测覆盖）；Track2（用户照片未入 data/eval_raw）仍外部阻塞。
真实运行：
  模型 yolov10_desk_fine.pt（sha256 93ed28bf…d6208521）；real 模式 GPU device=auto；样本 data/desk_fine/val 前 4 图；
  证据 artifacts/t_finetune/smoke_attributes_desk_fine.json。结果：4 图 colors_non_unknown 均>0（每图取色均非 unknown）、
  all_geometry_present=true、all_semantic_blocked=true、deterministic=true（同图同框两次一致）、schema_valid=true；
  NL 描述真实融入颜色+几何+细类名（例：“黑色保温杯(左·中,小号)、青色笔记本电脑(中·中,横放,中号)”）。
剩余限制（诚实标注）：
  - 颜色为**受光照/白平衡影响的主色近似**，非精确材质色；量化直方图对多色物体只取峰值代表色（近黑色物体色名处阈值边界，S2）。
  - 语义属性（材质/开合/空满/精确朝向）**全程 blocked**，待 VL 凭据到位；apply_semantic_attributes 无真实后端验证。
  - 冒烟以全图当桌面（desk=[0,0,1,1]）为近似；带标定桌面框的真实场景取色仍待用户照片（Track2 blocked）。
评审结论（delivery-reviewer 只读评审）：
  **通过、无严重项**——五类实质问题（模拟替代/H01/坐标混用/无界重试/未执行测试）逐项核查均通过：属性为真实像素运算、
  apply_semantic_attributes 深拷贝仅改 semantic 块、颜色走 bbox_image 几何走 bbox_desk 结构性分离、MAX_ATTEMPTS=2 保持且预留接口不被生产调用、语义恒 blocked 不编造。两条非阻塞警告+建议已处理：
  - W1（STATUS 缺阶段 B 结构化报告块）：已补本报告块（本段）。
  - W2（_load_interpret_image 的 image_asset_id 分支缺项目归属校验，当前不可经 API 触发）：已加固——传入 job.project_id，detect job 与 asset 均校验 project_id 一致，不一致降级 None（跨项目资源不读取）。
  - S1（缺 bbox_image≠bbox_desk 专项回归）：已补 test_attributes_color_uses_bbox_image_geometry_uses_bbox_desk（左红右蓝原图，颜色取 bbox_image 左半=红、几何取 bbox_desk=landscape，证坐标不混用）。
  - S2/S3（近黑色色名边界 / 冒烟桌面近似）：已归入“剩余限制”如实标注（非编造，rgb 真实）。
  处理后 pytest 全量复跑仍 **176 绿**（errors=0/failures=0/skipped=0）。
下一任务：Phase 4 完成；等待用户照片→Track2（凌乱桌面冻结集）；或 VL 凭据到位→接通语义属性（apply_semantic_attributes 已预留）；或负责人指定下一 T 编号任务。
```
