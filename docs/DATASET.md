# 数据集来源与授权记录（DATASET）

本文件记录已获取数据集的来源、许可、实际内容与到产品词表的映射。任何数量以**实测**为准，不采用宣传值（章程红线1、7）。最后更新：2026-10-11。

## 1 来源与许可

| 项 | 值 |
| --- | --- |
| 名称 | YOLO-DeskDataset |
| 仓库 | https://huggingface.co/datasets/hhh134/YOLO-DeskDataset |
| 版本 sha | e53dc4af4f537c5134c9d9045a76854ee1b9fda4 |
| 可见性 | public，非 gated |
| 许可 | **CC BY 4.0**（允许使用/修改/商用，须署名） |
| 署名要求 | 使用时标注作者 `hhh134` 与仓库链接、许可证；派生数据集/权重需继承署名 |
| 来源与偏差（README 自述） | 图片主要来自社交平台；桌面场景偏干净整齐；部分类别样本少；光照/角度/风格多样性有限；对复杂凌乱桌面泛化可能不足 |
| 获取方式 | Windows 侧经本地代理 `git clone`（git-lfs 3.7.1）拉取，落盘 `data/YOLO-DeskDataset/`（已 gitignore，不入库） |
| 获取时间 | 2026-10-11 |

授权结论：CC BY 4.0 满足 PRD 11.1「照片必须有使用授权」的前提，可用于检测验证与后续微调；对外发布成果时须附署名。该数据集不等同于 PRD 计划的固定 20 场景验收集，验收集仍需按 PRD 11.1 单独构建（见 §5）。

## 2 实测内容（与宣传值的差异）

| 项 | README 宣称 | 实测（本仓库） |
| --- | --- | --- |
| 图片数量 | 3000+（含增强） | **1646**（train 1549 + val 97） |
| LFS 对象 | — | 1647（1.34 GiB 过滤完成） |
| 类别数 | 80 | 80（标签 class_id 实测范围 0–79） |
| 标注格式 | YOLO txt | 确认：每行 `class_id cx cy w h`（归一化 0–1，5 字段） |
| 划分 | train/val 80/20 | 实测 train 1549 / val 97（约 94/6，非 80/20） |
| 落盘大小 | — | 约 1375 MB（含 .git） |
| 图/签配对 | — | train 1549:1549、val 97:97，一一配对 |

**差异如实记录**：宣传 3000+ 与实际 1646 不符、划分比例与宣称的 80/20 不符。以实测为准；引用数量时不得沿用宣传值。

## 3 目录结构

```
data/YOLO-DeskDataset/
├── README.md
├── .gitattributes
└── dataset/
    ├── data.yaml            # names: 0..79；path 字段是作者本机绝对路径，使用前需改为本项目路径
    ├── train/images/*.jpg|png   (1549)
    ├── train/labels/*.txt       (1549)
    ├── val/images/*             (97)
    └── val/labels/*             (97)
```

注意：`data.yaml` 中 `path: D:/Code/Projects/dataset-ultimate5` 是作者本机路径，本项目使用前必须改为实际路径或改用相对定位，不能直接照搬。

## 4 到 PRD 产品词表的类别映射（PRD 5.1：10 类）

PRD 产品词表为 10 类，数据集为 80 类。检测适配器须显式建立映射（PRD 5.1：不覆盖类别列入能力表；显示器/电视等需说明映射后才可用）。建议映射（dataset class → product class）：

| 产品类（PRD 5.1） | 数据集 class_id（data.yaml 名称） | 说明 |
| --- | --- | --- |
| 笔记本电脑 laptop | 8 laptop | 直接对应 |
| 显示器 monitor | 11 monitor, 7 computer | computer(7) 含义模糊，映射前需抽查确认是否指台式机/显示器 |
| 键盘 keyboard | 10 keyboard | 直接对应 |
| 鼠标 mouse | 9 mouse | 直接对应；27 mouse pad 属"其他"，不并入鼠标 |
| 书本 book | 18 book, 19 document | document 是否并入 book 需在映射配置中显式声明 |
| 笔 pen | 0 pen | 直接对应；61 pencil case 属"其他" |
| 杯子 cup | 20 cup, 21 thermos cup, 22 plastic cup, 34 disposable cup | 多杯型合并为 cup，须在配置声明 |
| 瓶子 bottle | 72 bottle, 32 plastic bottle, 55 waterpot, 79 squeeze bottle | 多瓶型合并为 bottle；33 can 是否并入需声明 |
| 手机 mobile phone | 14 mobile phone | 直接对应；67 phone holder 属"其他" |
| 其他 other | 其余全部 class_id | 归入 other，保留原始 id 以便追溯 |

映射规则须写入版本化配置 `configs/category_map.yaml`（T04 落实），不硬编码；映射变更记入 DECISIONS。原始 80 类 id 在检测结果的 `source`/元数据中保留，保证可追溯（PRD 5.1、FR03）。

## 5 与验收集的关系

- 本数据集用于：T01 真实检测跑通、T04 检测适配与类别映射验证、T14 检测微调的候选训练数据。
- **不直接充当** PRD 11.1 的固定 20 场景验收集（学习桌8/办公桌8/边界4，且不用于调参）；验收集需单独构建并冻结划分（WORKFLOW 11.2：按拍摄会话分组，防连拍泄漏）。
- 用于评测时须报告实际使用的样本量、划分与失败案例，不以数据集宣传值代替。

## 6 复现获取命令（记录，供重建环境用）

```powershell
# Windows 侧，经本地代理（WSL NAT 模式无法使用 localhost 代理，故在 Windows 下载）
$env:HTTP_PROXY="http://127.0.0.1:10808"; $env:HTTPS_PROXY="http://127.0.0.1:10808"
cd d:\AstraDesk\data
git clone https://huggingface.co/datasets/hhh134/YOLO-DeskDataset
```

代理端口以本机实际代理软件为准；此处仅为本次实测值，不含任何凭据。

## 7 重映射实测结论（识别提升方案 Phase 1，2026-10-12）

`tools/build_desk9.py` 按 `configs/category_map.yaml`(version:1) 把 80 类重映射为 9 产品类，产物写 `data/desk9/`（不改原始数据集；images 用符号链接指向原图，原始 80 类标签旁挂 `labels_raw/<stem>.txt` 供 FR03 追溯）。实测结论：

- **产物规模**：train 1490 / val 93——**沿用 HF 数据集自带 train/val 划分（原 1549/97）**，仅丢弃重映射后无有效框的图（train −59、val −4）。`tools/build_desk9.py` 按 `("train","val")` 原样遍历两个 split，**不含随机留出代码**。
- **对方案的偏离（诚实标注）**：方案 Phase 1 原要求「从 1549 train 随机留 10-15% 作训练期 val」，实际**未执行内部随机留出**，直接复用数据集自带 val(97→93)。故 train/val 的同源泄漏风险由数据集原划分决定，非本仓库可控；Track1 数字仅供相对比较（见下「无会话元数据」）。
- **标签格式混写**：class_id 存在整数与浮点混写（如 `8` 与 `8.0`），读取统一 `int(float(x))`（`normalize_class_id`），否则同物异 id 会漏映射。
- **computer(7) 抽查结论**：目视抽查（证据 `artifacts/_tmp_class7/`）为**台式机机箱/主机**（白色机箱+木纹侧板+前置 USB），非显示器 → **归 other，不并入 monitor**（修正 §4 表中「7 computer」的存疑映射）。
- **document(19)/paper(39)**：语义为散页纸张，非书本 → 归 other，不并入 book（§4 表中「19 document」不采纳）。
- **合并项（已在 category_map.yaml 声明）**：cup = 20/21/22/34（thermos/plastic/disposable cup）；bottle = 72/32/55/79/33（含 can 饮料容器）；mouse pad(27)/pencil case(61)/phone holder(67) 归 other 不并入对应产品类。
- **死类/稀有类**：0 样本死类（5,29,35-38,45-48,54,60,62 等）与极稀有类(<50 样本)不单独训练，一律归 other。
- **无会话元数据（重要局限）**：数据集不含拍摄会话/时间戳，**无法按会话分组防连拍泄漏**（WORKFLOW 11.2 在此数据不可满足）；沿用数据集自带 train/val 划分（非本仓库随机划分），两 split 可能同源连拍 → Track1 定量数字仅供**相对比较**，凌乱桌面结论以用户冻结集人工复核(Track2)为准。
- **冻结评测集原则**：用户真实照片 = 冻结评测集（`data/eval_raw/`，gitignore、哈希留档），**绝不参与训练/调参**。

## 8 类别细化重映射实测（识别细化方案 Phase 4 阶段 A，2026-10-13）

`tools/build_desk.py`（泛化自 `build_desk9.py`，类数由 `configs/category_map.yaml`(version:2) 驱动）把 80 类重映射为 **23 训练类(0–22) + other(23)**，产物写 `data/desk_fine/`（不改原始数据集；images 符号链接；原始标签旁挂 `labels_raw/`）。每类框数实测证据：`artifacts/t_finetune/desk_fine_class_counts.json`。

- **产物规模**：train **1549** 图 / val **97** 图，**0 丢弃**（23 类词表覆盖面广，几乎每图都有在表内框；对比 desk9 因词表窄丢弃了 train −59/val −4）。train 12893 框 / val 905 框。
- **每类合计框数（train+val，实测）**：laptop 1081｜monitor 517｜keyboard 943｜mouse 1163｜mobile_phone 211｜book 1281｜pen 375｜cup 806｜thermos_cup 562｜plastic_cup 210｜disposable_cup 140｜bottle 735｜plastic_bottle 479｜squeeze_bottle 265｜can 154｜waterpot 140｜cable 1272｜charger 744｜tissue 898｜paper 674｜lamp 427｜headphones 412｜mouse_pad 309。
- **转正阈值规则**（延续 §7，写入 category_map.yaml 注释）：样本≥300 且桌面整理高频相关→独立训练类；150–300→候选池（暂归 other，视评测再纳入）；<50→死类归 other。
- **候选池**（已有独立标注、本轮暂归 other）：tablet 214｜earphones 305｜speaker 155｜phone_holder 214｜pencil_case 228｜fan 226｜eraser 174｜gamepad 167｜document 93｜box 236｜carton 336｜waste_paperball 293。
- **长尾与 val support 局限（重要）**：val 集细类样本极小——**can 3、waterpot 5、disposable_cup 6、plastic_cup 10、squeeze_bottle 11**，这些类的 Track1b 每类 P/R 统计噪声极大，数字仅供**相对比较**，不作绝对精度声称。类别高度不平衡（cable 1272 vs disposable_cup 140，约 9×），训练可能偏向高频类；如实报每类 P/R 与家族内混淆，不面向 val 调参。
- **细类互混风险**：cup vs thermos_cup、bottle vs plastic_bottle 视觉相近，细化后家族内可能互混；Track1b 用原生混淆矩阵量化家族内分化质量，并做**父类聚合对比**（细类预测聚合回 cup/bottle 与 desk9 的 cup/bottle 比 P/R）确认细化未显著掉总召回。
- **沿用数据集自带 train/val 划分**：延续 §7 已记偏离，未做内部随机留出；无会话元数据、无法防连拍泄漏，泄漏风险由数据集原划分决定。凌乱桌面结论仍以用户冻结集(Track2, blocked)为准。
