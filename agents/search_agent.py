from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent, Tool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_openai import ChatOpenAI
search = GoogleSerperAPIWrapper()
tools = [ 
    Tool(
        name="search",
        func=search.run,
        description="useful for when you need to ask with search"
    )]

# Get the prompt to use - you can modify this!
prompt = hub.pull("hwchase17/react")


class SearchAgent:
    def __init__(self):
        # Choose the LLM to use
        llm = ChatOpenAI(model="gpt-4o")

        # Construct the ReAct agent
        agent = create_react_agent(llm, tools, prompt)

        # Create an agent executor by passing in the agent and tools
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

        self.agent_executor = agent_executor

    def search(self, query, output_constraints):
        return self.agent_executor.invoke({"input": query + '\n' + output_constraints}, handle_parsing_errors=True)
    
query = """
椿记烧鹅的平均价格。

"""
output_constraints = """要求最终答案以json格式返回，schema为：
{
    "price_range": "人均价格范围, 如100-200元",
    "suggested_price": "一个数字+货币单位，表示综合考虑后估计的最终价格，如150元"
}
"""
search_agent = SearchAgent()
print(search_agent.search(query, output_constraints))