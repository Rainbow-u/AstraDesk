# 环境与模型能力记录（ENVIRONMENT）

本文件由 T00 建立，记录**已实测**的环境与能力状态。探测值不等于锁定值；T02 锁定依赖后升级须记入 `DECISIONS.md`。原始探测输出见 `artifacts/probe_T00_2026-10-11.txt`。最后更新：2026-10-11（T02）。

## 1 已验证环境

| 项 | 实测值 | 位置 | 状态 |
| --- | --- | --- | --- |
| 宿主 OS | Windows 25H2 | Windows | verified（编辑端） |
| WSL 发行版 | Ubuntu 24.04.4 LTS，内核 6.6.87.2-WSL2 | WSL2 | verified（服务运行端） |
| Python（服务） | 3.12.3（/usr/bin/python3） | WSL | verified；落在期望 3.10–3.12 区间 |
| Python venv | `~/venvs/astradesk`（WSL 原生 ext4，pip 26.2.1） | WSL | verified；依赖装入此 venv（见 D005） |
| PyTorch | torch 2.6.0+cu124 / torchvision 0.21.0+cu124 / cuDNN 9.1.0 | WSL venv | **verified**；`torch.cuda.is_available()=true`，1024×1024 GPU 矩乘实测成功（证据 `artifacts/probe_torch_cuda_result.json`） |
| CUDA 运行时 | 12.4（随 torch cu124 轮子）；计算能力 sm_89；可用显存 6.0 GiB | WSL | verified（运行时）；本地编译用 nvcc 仍未装，需要时再装 |
| Python（编辑端） | 3.14.5 | Windows | 仅编辑参考，不用于服务运行 |
| Node / npm | v24.19.0 / 11.17.0 | Windows | verified；前端开发运行在 Windows 侧 |
| Git | 2.54.0.windows.1 | Windows | verified；仓库尚未初始化 |
| GPU | NVIDIA RTX 4050 Laptop，6141 MiB 显存，驱动 592.00 | Windows + WSL 直通均可见 | verified（驱动层）；CUDA 运行时待 T01 随 PyTorch 实测 |
| WSL 磁盘 | /dev/sdd 1007G，剩余 954G（虚拟盘） | WSL | verified；实际占用取决于宿主盘 |
| Windows 磁盘 | D 盘剩余约 61.8 GB | Windows | verified |
| 后端依赖（API） | fastapi 0.143 / uvicorn 0.54 / sqlalchemy 2.1.4 / pydantic 2.14 / pillow 12.3 / python-multipart 0.0.32 | WSL venv | **verified**；editable 安装 `astradesk 0.1.0`，依赖锁 `locks/python.lock.txt`（77 项） |
| 后端测试依赖 | pytest 9.1.1 / httpx 0.28.1 / jsonschema 4.26 | WSL venv | **verified**；16 用例全通过（mock 模式） |
| 前端构建 | Vite 5.4.21 / React 18.3 / TypeScript 5.5（apps/web，68 包） | Windows | **verified**；`npm run build` 通过（tsc 无类型错误），产出 `dist/` |
| API 服务启动（G0） | uvicorn `services.api.app:app`，`/api/v1/health`→200，8 条路由注册 | WSL | **verified**（证据 `artifacts/run_t02_api.sh` 输出） |

## 2 缺口表（gap）

| 缺口 | 影响 | 补全动作 | 状态 |
| --- | --- | --- | --- |
| WSL 缺 pip 且 ensurepip 不可用 | 阻塞 venv 策略与所有 Python 依赖安装 | 已执行 `sudo apt install -y python3.12-venv python3-pip`（已授权）；venv 现可正常创建（pip 26.2.1） | **resolved**（2026-10-11） |
| WSL 内未装 Node | 无（已决定前端跑 Windows Node v24） | 无需补全；注意跨系统路径与换行符 | resolved-by-decision |
| WSL 缺 CUDA toolkit（nvcc） | 不阻塞推理：torch cu124 轮子自带 CUDA 12.4 运行时，`torch.cuda` 实测通过；仅本地编译自定义算子时才需 nvcc | 已用 `torch.cuda.is_available()` + GPU 矩乘实测验证；编译需求出现再装 toolkit | **resolved**（2026-10-11，torch 2.6.0+cu124） |
| 无密钥/外部服务未配置 | 远端 VL/生成后端无法真实调用 → B 阶段相关任务阻塞 | 待用户提供凭据与预算授权后配置到服务端环境变量（`.env`，不入库） | **blocked**（需用户提供） |
| 无授权桌面照片 | T01 真实检测验证、T13 20 场景验收集 | 已获取 YOLO-DeskDataset（CC BY 4.0，1646 图+标签，见 `docs/DATASET.md`），可用于检测验证/微调；PRD 11.1 固定 20 场景验收集仍需单独构建 | **partially-resolved**（检测照片已得；专用验收集待建） |
| Git 仓库未初始化 | 无法做局部提交与版本追溯 | `git init` 与首次提交需用户明确授权后进行（提交不含密钥/照片，已有 .gitignore） | pending（待用户授权 git init/commit） |

## 3 模型能力表（T01 填写，当前为计划状态）

| 后端 | 计划路线 | 权重/服务 | 6GB 显存可行性 | 状态 |
| --- | --- | --- | --- | --- |
| 检测 Detector | 本地 YOLOv10 | yolov10n.pt（v8.3.0，sha256 11287ed0…c16b6f，AGPL-3.0） | 可行；实测显存峰值 56.6 MiB | **verified**（T01 独立脚本 7 框；T02 经完整 API 栈真实运行 6 框，含 laptop0.94/mouse0.89，`run_mode=real`，证据 `artifacts/t02_detect/`） |
| 检测 Detector（微调 desk9） | 本地 YOLOv10 迁移学习 | weights/yolov10_desk9.pt（起始 yolov10n.pt，data/desk9 9 产品类，AGPL-3.0） | **训练可行**；batch=8/imgsz=640/AMP 实测峰值 GPU_mem 1.91G（十进制）≈1.78GiB（6GB 内宽裕） | **verified（训练）**；100 epoch（1.061h），val(93) mAP50≈0.85 / mAP50-95≈0.64；产物接入 detector real 默认权重（证据 `artifacts/t_finetune/train_report.json`、`eval_track1.json`、`train_gpu_mem_evidence.txt`） |
| 检测 Detector（细化 desk_fine） | 本地 YOLOv10 迁移学习 | weights/yolov10_desk_fine.pt（起始 yolov10n.pt，data/desk_fine version 2，23 训练类+other，检测头重构，AGPL-3.0） | **训练可行**；23 类头 batch=8/imgsz=640/AMP 实测峰值 GPU_mem 2.01G（十进制）≈1.87GiB（6GB 内宽裕；试跑 1.84G，全卡含基线峰值 ~3.6G） | **verified（训练+评测+真实端到端）**；100 epoch（3407s≈0.95h），val(97,23类) mAP50≈0.747 / mAP50-95≈0.555；父类聚合 cup 召回 −0.022、bottle 召回 +0.018（细化未显著掉总召回）；产物接入 detector real 默认权重（证据 `artifacts/t_finetune/train_report_desk_fine.json`、`eval_track1b.json`、`smoke_real_desk_fine.json`、`train_desk_fine_gpu_mem_evidence.txt`） |
| 开放词表 OpenVocab | 本地 YOLO-World | weights/yolov8s-world.pt（27.2MB，AGPL-3.0）；首运行自动装 clip(git)+ftfy/regex/tqdm/wcwidth 并下载 338MB CLIP 文本编码器权重 | **6GB 可行（已实测）**；GPU 峰值 reserved 0.732 GiB / allocated 0.682 GiB | **verified（GPU+CPU）**；GPU 冷启 8.2s、热启 **0.025s/图**（CPU 热启 ~6.0s/图，`smoke_cpu.json`；526s 冷启为一次性装依赖+下 CLIP、不可复现）；22 raw 检出，映射正确（证据 `artifacts/t_openvocab/gpu_feasibility.json`、`smoke.json`、`smoke_cpu.json`） |
| 多模态 SceneInterpreter | 远端 Qwen-VL 服务 | 待用户提供凭据 | 不适用（远端） | blocked（缺凭据） |
| 生成 ImageGenerator | 远端布局条件生成（GLIGEN/SD 类） | 待用户提供凭据 | 不适用（远端） | blocked（缺凭据） |
| 评估 ResultEvaluator | 复用检测 + 远端视觉 | 同上 | — | blocked（缺凭据） |

说明：本表在 T01 完成一次真实或受控验证后，把每行改为 verified / blocked 并附实际输出与版本；未验证前不得声称模型可用（章程红线1、7）。

**检测权重来源与许可**：`weights/yolov10n.pt` 取自 ultralytics assets release v8.3.0（Windows 侧经代理下载）；YOLOv10/ultralytics 为 **AGPL-3.0**，闭源/商用分发需许可评估或企业授权。权重为 **COCO 预训练**（80 个 COCO 类），与 YOLO-DeskDataset 的 80 个桌面类别不同；当前验证只证明真实推理可用，桌面类别精度待 T14 微调后评测。

**微调与开放词表权重（识别提升方案，2026-10-12）**：
- `weights/yolov10_desk9.pt`：由 `tools/train_desk9.py` 在 `data/desk9`（重映射 YOLO-DeskDataset，9 产品类）上迁移学习产出（起始 yolov10n.pt）。**6GB 训练可行性已实测**：batch=8、imgsz=640、AMP 下 GPU_mem 峰值 1.91G（十进制，ultralytics 取 torch.cuda.memory_reserved()/1e9）≈1.78GiB，100 epoch（1.061h）全程无 OOM（证据 `artifacts/t_finetune/train_gpu_mem_evidence.txt`；原始日志被 .gitignore(*.log) 排除、仅本地）；训练脱离会话后台运行（`setsid nohup`，日志 `/tmp/train_desk9.log`）。real 模式检测默认权重已指向它（`ASTRADESK_YOLO_WEIGHTS`）；缺权重仍抛 `DetectorUnavailable`（不静默回退）。
- `weights/yolov10_desk_fine.pt`（识别细化方案 Phase 4 阶段 A，2026-10-13）：由 `tools/train_desk_fine.py` 在 `data/desk_fine`（重映射 YOLO-DeskDataset，`category_map.yaml` version 2，23 训练类+other）上迁移学习产出（起始 yolov10n.pt；类数变更→检测头重构 `Remapped 6/23 cls head rows`，仅 6 类与 COCO 同名）。**6GB 训练可行性已实测**：batch=8、imgsz=640、AMP 下 GPU_mem 峰值 2.01G（十进制）≈1.87GiB，100 epoch（3407s≈0.95h）全程无 OOM（试跑 2 epoch 峰值 1.84G，证据 `artifacts/t_finetune/train_desk_fine_gpu_mem_evidence.txt`；完整 val(97) mAP50≈0.747 / mAP50-95≈0.555，见 `eval_track1b.json`）。**后台训练方式变更（如实记录）**：`setsid nohup` 脱离启动后 WSL2 VM 会在 launcher wsl.exe 退出且无常驻进程时拆除、杀死脱离进程（Phase 1 靠常驻后端保活 VM，本轮无常驻后端），故改用**后台终端直接持有 wsl.exe 运行** `python tools/train_desk_fine.py 2>&1 | tee /tmp/train_desk_fine.log` 保活 VM（`artifacts/run_train_desk_fine.sh` 的 setsid 方式因此未用于本次全量训练）。real 模式检测默认权重已指向它（config.py:54 默认 / `ASTRADESK_YOLO_WEIGHTS`）；缺权重仍抛 `DetectorUnavailable`（不静默回退）。
- `weights/yolov8s-world.pt`（27.2MB）：YOLO-World s 变体，Windows 侧经代理下载（WSL 内 github 被墙）。**首运行副作用（如实记录）**：ultralytics 自动 `pip install clip @ git+https://github.com/ultralytics/CLIP.git@7ffa84b3…` + ftfy/regex/tqdm/wcwidth，并下载 338MB CLIP 文本编码器权重（缓存于 `weights/clip/`）；**冷启 526s 为一次性历史观测**（含安装+下载，依赖缓存后不可复现），缓存后重跑 CPU 开放词表推理热启 ~6.0s/图（`smoke_cpu.json` elapsed_seconds=6.013）。已记入 `locks/python.lock.txt`。**6GB GPU 可行性已实测（`artifacts/smoke_openvocab_gpu.py`）**：device=0 峰值 reserved 0.732 GiB / allocated 0.682 GiB，远小于 6GB（系统/桌面另占 ~2.6GiB 仍可容纳）；GPU 热启 **0.025s/图**（比 CPU 热启 6.0s 快 ~240×）、冷启 8.2s（CLIP 已装）。当前开放词表默认 `ASTRADESK_OPENVOCAB_ENABLED=false`，启用时建议走 GPU。
- **权重 sha256 manifest（G2）**：`tools/weights_manifest.py` 对 `weights/` 下全部 `.pt`（含 CLIP 缓存）计算 sha256+字节数，写 `artifacts/weights_sha256.json`（权重本身 gitignore不入库，以哈希留档供复现校验）。已录：yolov10_desk_fine.pt `93ed28bf…d6208521`、yolov10_desk9.pt `f3f99ff0…8ee67c`、yolov8s-world.pt `095f5266…e251cf`、yolov10n.pt `11287ed0…c16b6f`（与 T01 所记一致）、clip/ViT-B-32.pt `40d36571…ba950af`、yolo26n.pt `9b09cc8b…a8ad4fef`（ultralytics AMP 校验自动下载的小权重，非检测权重）。
- **物体属性模块（识别细化方案 Phase 4 阶段 B，2026-10-13）——免训练、免权重、免凭据**：`packages/understanding/object_attributes.py` 为纯函数、离线、确定性，**不依赖 GPU/模型权重/远端凭据**，仅用栈内已有的 numpy（量化直方图取代表色）+ pillow（bbox 反归一化裁剪）+ stdlib colorsys（RGB→HSV）；**未引入新依赖**（`locks/python.lock.txt` 不变）。颜色需关联原图像素：`service.process_interpret_job` 经 `_load_interpret_image` 从 detect job 的 image_asset 读原图（仅 detect_job 路径；显式 objects 无图 → color=unknown，不编造）；几何（aspect_ratio/orientation/size_class）仅需 bbox_desk，恒可派生。**语义属性（材质/开合/空满/精确朝向）全程 blocked**，`vl_interpreter.apply_semantic_attributes` 仅预留纯函数接口，待 VL 凭据到位再填充（当前不由 interpret 调用）。真实端到端证据：`artifacts/t_finetune/smoke_attributes_desk_fine.json`（real desk_fine 检测 4 张 val 图 → 取色非 unknown、几何齐全、semantic 全 blocked、同图同框两次结果一致 deterministic=true、facts 过 schema）。

## 4 A / B 范围明确（T00 验收项）

- **A 布局基线**：真实检测（本地 YOLOv10）+ 人工校正 + 规则规划 + 布局示意 + 整理步骤 + 保存导出。**当前无外部阻塞即可推进**（检测走本地，规划为确定性规则）。
- **B 完整 MVP**：A 之上接入真实多模态理解 + 真实图像生成 + 一致性检查 + 有界反馈 + 失败降级。**当前被"远端凭据缺失"阻塞**；凭据到位前 B 不可真实验收，降级输出 A 的结果不得记作 B 完成。
- 首版完成定义为 **B**；A 是中间里程碑。
