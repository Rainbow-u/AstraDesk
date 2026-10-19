# YOLO-DeskDataset

## 🧾 Dataset Summary
**YOLO-DeskDataset** 是一个用于检测桌面物品的图像数据集，旨在帮助训练目标检测模型（如 YOLOv8）识别桌面上常见的物品。  
数据集包括原图约 500 张，经过数据增强扩充至 3000+ 张。

---

## 📊 Dataset Structure
- **图片数量**：约 3000+ 张（含数据增强）  
- **类别**：共 80 类桌面物品，详见下表  
- **标注格式**：YOLO txt（每张图片对应一个 txt 文件，记录物体类别和边界框坐标）  
- **Split**：训练集 / 验证集，按 80% / 20% 划分  

---

### 🏷 Classes

| Class ID | Class Name |
|----------|------------|
| 0        | pen |
| 1        | eraser |
| 2        | ruler |
| 3        | scissors |
| 4        | sticky notes |
| 5        | paper clip |
| 6        | stapler |
| 7        | computer |
| 8        | laptop |
| 9        | mouse |
| 10       | keyboard |
| 11       | monitor |
| 12       | headphones |
| 13       | earphones |
| 14       | mobile phone |
| 15       | tablet |
| 16       | charger |
| 17       | cable |
| 18       | book |
| 19       | document |
| 20       | cup |
| 21       | thermos cup |
| 22       | plastic cup |
| 23       | keys |
| 24       | wallet |
| 25       | glasses |
| 26       | watch |
| 27       | mouse pad |
| 28       | package |
| 29       | snack box |
| 30       | carton |
| 31       | box |
| 32       | plastic bottle |
| 33       | can |
| 34       | disposable cup |
| 35       | bottle cap |
| 36       | straw |
| 37       | snack leftovers |
| 38       | food wrapper |
| 39       | paper |
| 40       | waste paperball |
| 41       | waste package |
| 42       | tissue |
| 43       | towel |
| 44       | plastic bag |
| 45       | broken items |
| 46       | debris |
| 47       | chopsticks |
| 48       | food container |
| 49       | instant noodles |
| 50       | toy |
| 51       | takeout |
| 52       | fan |
| 53       | bowl |
| 54       | mask |
| 55       | waterpot |
| 56       | lamp |
| 57       | card |
| 58       | backpack |
| 59       | handbag |
| 60       | cap |
| 61       | pencil case |
| 62       | umbrella |
| 63       | comb |
| 64       | power bank |
| 65       | mirror |
| 66       | socket |
| 67       | phone holder |
| 68       | calculator |
| 69       | clock |
| 70       | apple |
| 71       | printer |
| 72       | bottle |
| 73       | ointment |
| 74       | banana |
| 75       | orange |
| 76       | speaker |
| 77       | remote controller |
| 78       | gamepad |
| 79       | squeeze bottle |

---

## 📸 Data Collection
- **来源**：主要来自社交平台图片，小部分为自己拍摄  
- **采集地区**：多种环境的桌面场景  
- **隐私**：不包含人物正面照或敏感信息  
- **数据清洗**：对图片和标注进行了筛选与整理

---

## 🏷 Annotation
- **格式**：YOLO txt  
- **工具**：LabelImg 等标注工具  
- **标注方式**：人工标注 + 数据增强  
- **复核**：标注后进行了基础检查，保证边界框与标签对应

---

## 🧠 Use Cases
- 训练目标检测模型（YOLO 系列）  
- 桌面整理多模态 agent 的物品识别模块  
- 计算机视觉研究中小型桌面场景的目标检测任务

---

## ⚠ Limitations and Bias
- 数据集主要来源于社交平台，桌面场景可能偏向干净整齐  
- 部分类别样本量较少  
- 光照、角度和桌面风格多样性有限  
- 可能对复杂或非常混乱的桌面场景泛化能力不足

---

## 📜 License
- **CC BY 4.0**  

---

## 🛠 How to Use
```python
from datasets import load_dataset

# 加载数据集
dataset = load_dataset("hhh134/YOLO-DeskDataset")
train_data = dataset['train']
valid_data = dataset['validation']

# 查看每条数据
for item in train_data:
    print(item['image'], item['labels'])