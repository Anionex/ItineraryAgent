# 项目Prompt解析
本文档用于解析项目中出现的prompt。


## zeroshot_react_agent_prompt
- 输入："query", "scratchpad"
- 模板：ZEROSHOT_REACT_INSTRUCTION

ZEROSHOT_REACT_INSTRUCTION：
- 简介：介绍了基本react规则和八个工具的使用方法。零样本（无提前设置的对话模板）
- 大意：使用交替进行'Thought', 'Action', and 'Observation' steps来搜集有关被查询计划的信息。
确保使用了正确的专有名词。所有获取的信息应该用notebook工具写入notebook。
