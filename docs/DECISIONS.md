# 决策记录（DECISIONS）

记录选型与需求变更依据。每条含：日期、决策、理由、被否选项、影响范围。

## D001 Python 服务环境策略（2026-10-11，T00）
- 决策：WSL Ubuntu-24.04 内使用 `python3.12 -m venv` 建虚拟环境，依赖以 requirements + lock 管理；Python 服务运行版本锁定 3.12.3。
- 理由：实测 WSL python3=3.12.3 落在章程期望 3.10–3.12 区间；venv 最轻量、贴合"不自建训练平台"取向；Windows 侧 3.14.5 过新不用于服务。
- 被否：Miniconda（体积大、与章程取向略有出入，留待 C 阶段多版本 CUDA 需求出现再评估）。
- 影响：T02 依赖锁方式确定。**前置阻塞**：WSL 缺 ensurepip，需先 `sudo apt install python3.12-venv python3-pip`（待授权）。

## D002 前端 Node 运行位置（2026-10-11，T00）
- 决策：前端开发服务器运行在 Windows 侧 Node v24.19.0；后端服务运行在 WSL。
- 理由：Windows 已有 Node v24.19，避免在 WSL 重复安装；用户选择。
- 被否：WSL 内装 Node LTS（前后端同环境、避免跨系统路径，但用户选择复用 Windows Node）。
- 影响：跨系统联调需注意路径（`/mnt/d` ↔ `D:\`）、换行符（CRLF/LF）与端口经 localhost 转发；前端不直接调用模型、不持有密钥（章程红线8）。

## D003 模型后端路线（2026-10-11，T00）
- 决策：检测走本地 YOLOv10（6GB 显存）；多模态理解与图像生成走远端服务，凭据由用户后续提供。
- 理由：6GB 显存对 Qwen-VL 与布局扩散模型本地推理是硬边界；用户选择本地检测 + 远端 VL/生成。
- 被否：全部本地小权重验证（显存风险高）；全部远端（检测本地更省成本、可离线跑通 A）。
- 影响：A 阶段（本地检测 + 规则规划）无外部阻塞可推进；B 阶段真实 VL/生成在凭据到位前 blocked。凭据仅入服务端 `.env`，不入库、不进前端（章程红线8）。

## D004 授权照片与数据目录（2026-10-11，T00）
- 决策：预先创建 `data/images/`（原始输入）、`data/exports/`（导出）、`weights/`（权重）目录并加 `.gitkeep`；全部纳入 `.gitignore` 不入库。真实照片在需要时（T01 检测验证、T13 验收）向用户索取并记录使用授权。
- 理由：用户要求"先在项目创建图片所在文件位置，需要时再索取"；WORKFLOW 第4节要求 data/weights 本地管理并加入忽略规则。
- 被否：先用公开/合成图打通（用户选择需要时再提供真实照片）。
- 影响：真实照片到位前，T01 真实检测验证与 T13 20 场景验收标 blocked；流程/契约开发可先用明确标识的 fixture 推进（不计入真实推理验收）。

## D005 venv 物理位置与 PyTorch 构建（2026-10-11，T01）
- 决策：项目 Python 虚拟环境创建在 WSL 原生文件系统 `~/venvs/astradesk`（非 `/mnt/d`）；PyTorch 采用 CUDA 12.4 官方索引构建（`--index-url https://download.pytorch.org/whl/cu124`），安装 torch + torchvision。
- 理由：代码在 `/mnt/d`（drvfs，I/O 慢），而 PyTorch+CUDA 体积达数 GB，venv 放 WSL 原生 ext4 可显著加快安装与每次 import；RTX 4050 Laptop 为 Ada 架构（sm_89），cu124 构建支持。venv 位置不影响"从项目根运行入口"（激活 venv 后在 `/mnt/d/AstraDesk` 执行 `python -m ...`）。
- 被否：venv 放 `/mnt/d/AstraDesk/.venv`（drvfs 大 site-packages I/O 慢、符号链接易出问题）；CPU-only 构建（无法实测 torch.cuda，不满足 T01）。
- 影响：ensurepip 缺口已通过 `sudo apt install python3.12-venv python3-pip` 解除（已授权执行）；后续所有 Python 依赖装入该 venv，requirements/lock 在 T02 冻结。

## D006 检测数据集获取与网络路线（2026-10-11，T01）
- 决策：检测数据采用 HuggingFace `hhh134/YOLO-DeskDataset`（CC BY 4.0，sha e53dc4a），落盘 `data/YOLO-DeskDataset/`（gitignore）；详录见 `docs/DATASET.md`。下载在 **Windows 侧经本地代理**（`git clone` + git-lfs）完成。
- 网络约束（实测）：Windows 系统代理为 `127.0.0.1:10808`；直连 huggingface.co 超时；WSL（NAT 模式）无法使用宿主 localhost 代理（连 `172.25.208.1:10808` 也超时，代理仅绑定 localhost）。因此凡需访问 HF 的下载（数据集/权重）均在 Windows 侧设 `HTTP_PROXY/HTTPS_PROXY` 后执行，或后续由用户将代理改为允许局域网/配置 WSL 镜像网络。
- 理由：数据落盘位置在 `/mnt/d`（Windows 与 WSL 共享），在 Windows 侧下载避免 WSL 网络障碍；CC BY 4.0 满足 PRD 11.1 照片授权前提（需署名）。
- 实测差异（已如实记录）：README 宣称 3000+/80-20 划分，实际 1646 图（train1549/val97，约94/6）；以实测为准，不沿用宣传值。
- 影响：解除 T01 检测验证的照片阻塞；后续 T04 需建 `configs/category_map.yaml` 将数据集 80 类映射到 PRD 10 类（映射表见 `docs/DATASET.md` §4）；YOLO 中心点格式 `cx,cy,w,h` 需转为 PRD `[x1,y1,x2,y2]`。

## D007 T02 骨架架构与运行模式（2026-10-11，T02）
- 决策：
  1. **分层**：路由（`services/api/routes.py`）只做协议处理；业务规则集中在应用服务（`services/api/service.py`）；模型经适配器（`packages/vision|layout|generation`）调用（AGENTS.md 模块边界）。
  2. **运行模式**：以 `ASTRADESK_RUN_MODE`（`real`/`mock`，`demo`→`mock`）显式分派；`real` 模式检测缺权重/依赖抛 `DetectorUnavailable`→ 任务置 `failed` 记 `MODEL_UNAVAILABLE`，**不静默回退 mock**（约定1）。默认 `mock`，避免未配置时误触发真实/收费后端。
  3. **异步任务**：`POST .../jobs/detect` 返回 202 + job，检测经 FastAPI `BackgroundTasks` 在请求进程内执行；另提供 `python -m services.worker` 轮询入口用于解耦运行。基于租约/心跳的健壮领取与重启过期置 failed 属 T06–T07，尚未实现（已如实标注）。
  4. **存储**：图片路径由服务端生成（`data/projects/<pid>/`），客户端只拿 `asset_id`，读取经 `GET /assets/{id}` 校验归属（约定7）。上传即做 EXIF 方向校正 + 重存去元数据 + magic bytes 校验（FR01）。
  5. **依赖锁**：Python 用 pyproject + editable 安装，冻结 `locks/python.lock.txt`；前端 npm `package-lock.json`。
- 被否：路由内直接写业务/调模型（违反模块边界）；`real` 缺权重时回退 mock 维持“成功”（违反真实性红线）；客户端传图片路径（违反隐私约定）。
- 影响：G0（API 启动 + 健康检查 + 依赖锁 + 模式明确）、G1（坐标/ID/错误/状态统一，契约样例可校验）达成；桌面识别端到端在 mock 与 real 两模式均跑通。T03 在此骨架上补项目 CRUD/删除级联，T04 补 `configs/category_map.yaml` 与真实桌面类别检测。

## D008 检测微调提前与类别集（2026-10-12，识别提升方案 Phase 1）
- 决策：
  1. **微调提前**：将原属 C/T14 的桌面类别微调提前到当前执行（负责人已授权），起始权重 `yolov10n.pt`（COCO 预训练）迁移学习，产物 `weights/yolov10_desk9.pt`。
  2. **类别集 = 9 具体产品类**（PRD 5.1）：0 laptop,1 monitor,2 keyboard,3 mouse,4 book,5 pen,6 cup,7 bottle,8 mobile_phone；`other`(9) **不参训**，由开放词表(D009)+人工补框(FR04)兜底。
  3. **版本化映射** `configs/category_map.yaml`（version:1）：数据集 80 类 → 9 产品类，声明合并项（cup 合 thermos/plastic/disposable cup；bottle 合 can/waterpot/squeeze bottle；book 仅 18）；原始 80 类 id 旁挂保留以保 FR03 可追溯。
  4. **computer(7) 归 other 不并入 monitor**：目视抽查证据（`artifacts/_tmp_class7/`）显示为台式机机箱/主机（白色机箱+木纹侧板+前置 USB），非显示器；document(19)/paper(39) 为散页纸张非书本，同样归 other。
  5. **数据修复**（`tools/build_desk9.py`）：标签 class_id 整数/浮点混写统一 `int(float(x))`；剔除 0 样本死类与极稀有类(<50)；重映射产物写新目录 `data/desk9/`（不改原始数据集）；**沿用 HF 数据集自带 train/val 划分（原 1549/97），仅丢弃重映射后无有效框的图 → train1490/val93**（未做方案原定的 10-15% 内部随机留出，记为偏离，见局限）。
- 理由：当前 real 模式用 COCO 预训练权重**结构性检不出「笔」、「显示器」只能借 `tv`**，是「识别不达预期」的主因；微调直接补词表缺口。9 类聚焦可靠标注的具体物，other 兜底避免为稀有/模糊类硬凑训练样本。
- 被否：训全部 80 类（大量死类/稀有类、标注语义模糊）；computer(7) 并入 monitor（抽查证伪）；用用户照片参与训练（违反冻结评测集原则，见下）。
- 局限（诚实标注）：HF `YOLO-DeskDataset` 为**干净桌面偏置**，README 自述对凌乱桌面泛化不足；数据集**无会话元数据、无法防连拍泄漏**（WORKFLOW 11.2 在此数据不可满足）；val 仅 93 图 → Track1 定量数字仅供**相对比较**，凌乱桌面结论以用户冻结集人工复核(Track2)为准。**未按方案做 10-15% 内部随机留出**（直接复用数据集自带 val），故 train/val 同源泄漏风险由数据集原划分决定、非本仓库可控。**用户照片 = 冻结评测集，绝不参与训练/调参**。
- 影响：`packages/vision/detector.py` real 默认权重指向 `yolov10_desk9.pt`，每框加 `source=yolov10:<stem>`；`contracts/detection_result.schema.json` class_id/class_name 枚举收窄为 9 产品类+other；A/B 门槛不因微调提前而放宽。

## D009 开放词表融合策略（2026-10-12，识别提升方案 Phase 2）
- 决策：
  1. 引入 **YOLO-World**（`yolov8s-world.pt`，27.2MB）作开放词表补检测（`packages/vision/open_vocab.py`），提示词 = 9 产品类名 + 常见桌面物（headphones/cable/charger/sticky notes/stapler/tissue/plant/tablet/speaker/frame…），后者归 other。
  2. **融合**（`packages/vision/fusion.py`）：主检测(微调 desk9)框**全保留**；补检测(YOLO-World)映射到产品类后与已保留框做类无关抑制（IoU≥`ASTRADESK_FUSION_IOU`，默认 0.5），未被抑制才保留并打 `source=yolo-world`；补检测彼此也 NMS。重叠优先保留可信度更高的主检测。
  3. **配置与不静默**：`ASTRADESK_OPENVOCAB_ENABLED`(默认 false)/`_WEIGHTS`/`_CONF`(0.15)/`ASTRADESK_FUSION_IOU`；启用但权重缺失 → 检测任务 `failed` 报 `MODEL_UNAVAILABLE`（不回退）；关闭 → 仅微调，`GET /capabilities` 明示 `open_vocab.enabled=false`。
- 理由：凌乱桌面召回主要靠开放词表 + 人工补框，不是靠微调（HF 干净偏置）；主检测优先保证可信度，补检测扩召回。
- 被否：仅微调（凌乱桌面漏检严重）；开放词表替换微调（产品类精度不稳）；无 source 标记（违反 FR03 可追溯）。
- 实测（冒烟 `artifacts/smoke_openvocab.py`，证据 `artifacts/t_openvocab/smoke.json`；GPU 可行性 `artifacts/smoke_openvocab_gpu.py`，证据 `gpu_feasibility.json`）：首次运行自动 pip 装 `clip`(git 依赖)+ftfy/regex/tqdm/wcwidth 并下载 338MB CLIP 文本编码器权重；**CPU 冷启 526s 为一次性历史观测**（含首次装依赖+下 CLIP，依赖缓存后不可复现），缓存后重跑 CPU 开放词表推理热启 ~6.0s/图（证据 `smoke_cpu.json` elapsed_seconds=6.013）。冒烟以**真实主检测(desk9)** 为 A 侧、YOLO-World 为 B 侧（`primary_is_synthetic=false`，非合成框）：2 真实主检测(laptop 0.9338/book 0.8045) + 22 raw 开放词表 → 融合 20 框（18 框由开放词表新增），映射正确（pen→5，cup→6，bottle→7，book→4，mouse→3；非产品物归 other(9)，其原始提示词名由 `raw_class_name` 保留以供 FR03 可追溯，在 `smoke.json`/`smoke_cpu.json` 的 fused.other 可直读为 lamp/power bank/tissue；speaker 原始检出 0.2509 被 NMS 抑制未进 fused，其→other 映射由 `test_fusion` 参数化用例覆盖）；**重叠抑制真实框验证**：open-vocab laptop(0.9478) 被真实主检测 laptop(0.9338) 抑制（IoU≥0.5、主检测优先），未进入 added_by_openvocab。**6GB GPU 可行性已实测确认**：device=0 峰值 reserved 0.732 GiB / allocated 0.682 GiB（远小于 6GB），GPU 热启 **0.025s/图**（比 CPU 热启 ~6.0s 快 ~240×）、冷启 8.2s。
- 影响：`locks/python.lock.txt` 记 5 个新依赖；ultralytics/YOLO-World 为 AGPL-3.0，商用需许可评估。Track2（用户冻结集人工复核）待用户照片到位，当前 blocked。

## D010 facts-first 自然语言架构（2026-10-12，识别提升方案 Phase 3）
- 决策：
  1. **确定性事实优先**：`packages/understanding/scene_facts.py` 从确认后的检测（object_id/class/bbox_desk + 桌面矩形 + 靠用户侧 + 偏好）**确定性计算**几何事实：分区(左/中/右×近/中/远)、九宫格占用与留白、最大连续空闲矩形、按类+功能组聚类、边缘对齐偏差、取用便利、杯瓶-电子设备最短距离(H07)。输出结构化 `SceneFacts`（**单一事实来源**），过版本化 `contracts/scene_facts.schema.json`(draft 2020-12)。
  2. **模板 NL**：`packages/understanding/render_nl.py` 把 SceneFacts 渲染为中文场景描述 + 布局解释，**绑定 PRD 6.2 软目标**(continuous_workspace/accessibility/grouping/alignment/movement_saving)——用可测量维度（占比/距离/偏差/评分）描述美学，不用空洞形容词；movement_saving 标注「规划期指标 N/A」；离线、可复现、可测试。
  3. **VL 增强为 B 阶段接口，当前 blocked**：`packages/understanding/vl_interpreter.py` 护栏——**只引用已有 object_id、不得改写事实清单(H01)**、未知实例引用拒绝(UNKNOWN_INSTANCE)、过 `contracts/vl_relations.schema.json` 校验、版本化提示词(`prompts/vl_interpret.md`)、图中文字当数据不当指令(防注入)、有界重试(MAX_ATTEMPTS=2)、缺凭据显式 `VLUnavailable` 不静默回退。
  4. **坐标约定**：interpret 入参为 `bbox_image`，`bbox_desk` **一律由后端 `image_to_desk` 推导**（约定3），前端/客户端不传桌面相对坐标。
  5. **API/前端最小暴露**：新增 `interpret` 任务类型（先跑确定性 facts+模板 NL，不调 VL）；前端检测成功后自动触发 interpret 并展示场景描述文本、维度、H07 告警；`GET /capabilities` features 加 `interpret`。
- 理由：把「识别信息自然语言化」拆成可测试的确定性事实层 + 模板层，VL 仅做受 H01 约束的关系增强，避免不可复现/幻觉污染事实清单。
- 被否：直接让 VL 自由生成描述（不可复现、可能改写事实、无法测试）；在前端计算几何事实（违反单一事实来源与坐标后端推导约定）。
- 影响：新增 `packages/understanding/`、`contracts/scene_facts.schema.json`+`vl_relations.schema.json`+样例、`prompts/vl_interpret.md`；`services/api/{db,schemas,service,routes}.py` 加 interpret 全链路（Job 加 `request_json` 幂等迁移）；单测 scene_facts 17 + render_nl 8 + vl_interpreter 8 + interpret E2E 6，全绿。VL 真实路径待远端凭据（B 阶段）。

## D011 类别细化：词表 9→23 训练类 + other（2026-10-13，识别细化方案 Phase 4 阶段 A）
- 决策：
  1. **词表扩展（PRD 5.1 实质范围变化，负责人已授权）**：产品词表由 9 具体类细化为 **23 训练类(索引 0–22) + other(23) 兜底**。`configs/category_map.yaml` 升 `version:2`。
  2. **杯细分**（原 cup 合 4 类拆回）：7 cup(806) / 8 thermos_cup(562) / 9 plastic_cup(210) / 10 disposable_cup(140)。**瓶罐细分**（原 bottle 合 5 类拆回）：11 bottle(735) / 12 plastic_bottle(479) / 13 squeeze_bottle(265) / 14 can(154) / 15 waterpot(140)。括号为原始数据集 train+val 合计框数（`tools/build_desk.py` 重映射实测）。
  3. **other 高频物转正**（阈值：样本≥300 且桌面整理强相关）：16 cable(1272) / 17 charger(744) / 18 tissue(898) / 19 paper(674) / 20 lamp(427) / 21 headphones(412) / 22 mouse_pad(309)。保留原 7 产品类 0–6（laptop/monitor/keyboard/mouse/mobile_phone/book/pen）。
  4. **转正阈值规则**（写入 category_map.yaml 注释，延续 DATASET §7）：样本≥300 且高频相关→独立类；150–300→候选池（本轮暂归 other）；<50→死类归 other。**候选池**（已有标注、视 A 阶段评测再决定纳入）：tablet(214)/earphones(305)/speaker(155)/phone_holder(214)/pencil_case(228)/fan(226)/eraser(174)/gamepad(167)/document(93)/box(236)/carton(336)/waste_paperball(293)。
  5. **零标注成本**：细分/转正所需标注全部现成——原始 `hhh134/YOLO-DeskDataset` 80 类里 cup/thermos cup/plastic cup/disposable cup、bottle/plastic bottle/squeeze bottle/can/waterpot、cable/charger/tissue/paper/lamp/headphones/mouse pad 均为独立标注类；Phase 1 `build_desk9.py` 已把原始标签旁挂 `labels_raw/`。细化 = 改映射表 + 泛化重建脚本 + 重训，**未新增任何人工标注**。
  6. **泛化重建**：`tools/build_desk9.py`→`tools/build_desk.py`（类数由 category_map 驱动，不再写死 9）；输出 `data/desk_fine/{train,val}/{images,labels,labels_raw}` + `data_fine.yaml`(nc=23)；images 仍符号链接、不改原始数据集；沿用数据集自带 train/val 划分（延续 Phase 1 已记偏离）→ **train 1549 图 / val 97 图，0 丢弃**。
  7. **重训而非续训**：类数变更→检测头重构（`Remapped 6/23 cls head rows`，仅 6 类与 COCO 同名，其余随机初始化），从 `yolov10n.pt`(COCO) 迁移学习重训；沿用 Phase 1 配置（imgsz=640,batch=8,epochs=100,device=0,AMP,patience=20,增强 mosaic/mixup/copy_paste/hsv/degrees/scale,seed=42）。产物 `weights/yolov10_desk_fine.pt`。
- 理由：Phase 1 微调把 Track1 mAP50 拉到 0.848，但**粒度粗**——cup 合 4 杯型、bottle 合 5 瓶罐、20 种桌面物统一归 other，无法支撑「更细致识别 + 桌面整理语义」。细分标注现成，重训即可换取更细词表，收益/成本比高。
- 被否：维持 9 类（粒度不足）；把候选池全部纳入（长尾类 val support 极小、精度不稳）；从 desk9 权重续训（检测头 nc 变更无法续，必须重构）；用用户照片参训（违反冻结评测集原则）。
- 局限（诚实标注）：**val 细类 support 极小**（can=3, waterpot=5, disposable_cup=6, plastic_cup=10, squeeze_bottle=11），其每类 P/R 统计噪声大，Track1b 数字仅供**相对比较**；细杯型(cup vs thermos_cup)视觉相近可能互混；类别不平衡(cable 1272 vs disposable_cup 140)可能偏向高频类；HF val 干净偏置/无会话分组/可能泄漏延续 Phase 1；凌乱桌面结论仍待用户冻结集(Track2 blocked)。**6GB 显存已实测充裕**：23 类头训练 GPU_mem 峰值 1.98G，全卡含基线峰值 ~3.6G（证据 `artifacts/t_finetune/train_desk_fine_gpu_mem_evidence.txt`）。
- 影响：`services/api/config.py` 默认权重与 `packages/vision/detector.py` real 权重指向 `yolov10_desk_fine.pt`（缺权重仍抛 DetectorUnavailable/MODEL_UNAVAILABLE，不静默回退）；`packages/vision/open_vocab.py` PRODUCT_PROMPTS 扩为 23 类英文提示词、EXTRA_PROMPTS 移除已转正项保留候选池、`_PRODUCT_INDEX`/`OTHER_ID` 从 `load_category_map()` 派生（避免索引漂移）；`contracts/detection_result.schema.json` class_id/class_name 枚举扩为 24 类(0–23)、`contracts/scene_facts.schema.json` `$defs/class_name` enum 同步扩为 24 类；`packages/understanding/scene_facts.py`(PRODUCT_CLASSES/FUNCTIONAL_GROUPS/DRINKWARE/ELECTRONICS) 与 `render_nl.py`(CLASS_ZH) 扩为 24 类；`GET /capabilities` 由 `weights_path.stem` 自动派生 model_name=desk_fine。**A/B 门槛不因词表扩展放宽**。

## D012 确定性属性 now + 语义属性 blocked 预留 VL 接口（2026-10-13，识别细化方案 Phase 4 阶段 B）
- 决策：
  1. **只做确定性免训练属性**：新增 `packages/understanding/object_attributes.py`（纯函数、离线、确定性）——`extract_color` 从原图 bbox 区域取量化直方图峰值代表色映射 12 中文基本色名（黑/白/灰/红/橙/黄/绿/青/蓝/紫/棕/粉）+ rgb/hsv；`geometry_attrs` 从 bbox_desk 派生 aspect_ratio / orientation(landscape≥1.2 / portrait≤0.833 / square) / size_class(面积比 <2% small / <10% medium / ≥10% large)。
  2. **颜色需原图，无图不编造**：`scene_facts.compute_scene_facts` 新增 `image` 参数、`SceneObject` 新增 `bbox_image` 字段；`service.process_interpret_job` 经 `_load_interpret_image` 从 detect job 的 image_asset 读原图像素。仅 detect_job 路径能取到图；**显式 objects 路径无关联原图 → color={name:unknown, rgb:null, hsv:null}**，几何仍恒可派生。
  3. **语义属性预留块恒 blocked**：`contracts/scene_facts.schema.json` object.attributes 扩展 `color/aspect_ratio/orientation/size_class` + `semantic{status, material, open_state, fill_level, precise_orientation}`（additionalProperties:false 受控，当前 status=blocked、四字段 null）。`vl_interpreter.apply_semantic_attributes` 为纯函数预留接口：VL 可用时在同等护栏下回填（只引用已有 object_id、深拷贝不改写其他事实 H01、回填后过 semantic_attr schema、字段限 SEMANTIC_FIELDS），真实后端接入前不由 interpret 调用。
  4. **NL 融入颜色/几何、blocked 不生成推断词**：`render_nl._composition_line` 加“X色”前缀（仅取到真实主色时）与 orientation/size 中文标签；语义 blocked → 描述不含材质/开合/空满形容词，收尾注诚实标注“颜色为主色近似、语义属性暂未启用(blocked)”。前端 `apps/web` api.ts 加属性类型、App.tsx 展示色块+颜色+几何，semantic=blocked 时不显示。
- 理由：HF 数据集**无颜色/材质/开合/空满/朝向标注**、VL 凭据未到位。颜色+bbox 几何是**零标注、零训练、可复现**的确定性增量，能立即提升描述信息量；语义属性无真实来源时**只能预留接口并标 blocked**（红线1/7：无真实测量不编数字），待 VL 凭据或标注到位再填充。
- 被否：用 VL 直接生成颜色/材质（凭据未到位，且会引入幻觉与不可复现）；用语义模型推断材质/空满（无标注、无凭据 → 编造）；颜色用 cv2 HSV（H∈[0,180] 需额外换算易错，改用 numpy 量化直方图 + stdlib colorsys，无新依赖）。
- 局限（诚实标注）：颜色为**受光照/白平衡影响的主色近似**，非精确材质色；量化直方图对多色物体只取峰值代表色；语义属性（材质/开合/空满/精确朝向）**全程 blocked**，待 VL 凭据到位；`apply_semantic_attributes` 目前仅单测覆盖，无真实 VL 后端验证。
- 影响：新增 `packages/understanding/object_attributes.py`；`scene_facts.py`(SceneObject.bbox_image / compute_scene_facts image 参数 / per_object attributes)、`scene_facts.schema.json`($defs color_name/color_attr/semantic_attr/object_attributes，attributes 设为 object_fact 必填)、`service.py`(_load_interpret_image)、`render_nl.py`(ORIENT_ZH/SIZE_ZH/颜色前缀/几何标签/blocked 注)、`vl_interpreter.py`(apply_semantic_attributes 预留接口)、`apps/web`(api.ts 类型 + App.tsx 属性展示 + styles.css)。**无新依赖**（numpy/pillow/colorsys 均已在栈内，locks/python.lock.txt 不变）。
