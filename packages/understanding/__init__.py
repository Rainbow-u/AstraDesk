"""场景理解层（Phase 3 facts-first 自然语言）。

- ``scene_facts``：确定性几何事实计算（单一事实来源，H01 约束下游不得改写）。
- ``render_nl``：把事实模板化为中文场景描述与布局解释，绑定 PRD 6.2 软目标可测量维度。
- ``vl_interpreter``：B 阶段多模态增强接口（当前 blocked，缺凭据显式报错不静默回退）。
"""
