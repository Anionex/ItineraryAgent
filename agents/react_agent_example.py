from langchain import hub
import json
from langchain.agents import load_tools
# 下载一个现有的 Prompt 模板
reflection_prompt = hub.pull("hwchase17/react")

react_prompt = hub.pull("hwchase17/react")

print(react_prompt.template)

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent


llm = ChatOpenAI(model_name='gpt-4o', temperature=0)

# 定义一个 agent: 需要大模型、工具集、和 Prompt 模板
tools = load_tools(["google-serper"], llm=llm)
agent = create_react_agent(llm, tools, react_prompt)
# 定义一个执行器：需要 agent 对象 和 工具集
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 执行
agent_executor.invoke({"input": "2024年周杰伦的演唱会星期几"})