import sys
import os
print(os.getcwd())
print(os.path.join(os.getcwd(), "tools"))
sys.path.append(os.path.abspath(os.getcwd()))
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "tools")))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from react_agent.react_agent import ReactAgent
from prompts import REACT_PLANNER_HUNTER_PROMPT
from tool_funcs import (get_attractions, 
                        get_restaurants,
                        get_accommodations,
                        get_flights,
                        get_google_distance_matrix,
                        calculator, 
                        google_search,
                        notebook_write
                        )

if __name__ == '__main__':
    agent = ReactAgent(model="gpt-4o")

    
    agent.tools.add_tool(
        name_for_human="calculator",
        name_for_model="calculator",
        func=calculator,
        description="calculator是一个用于进行数学计算的工具。",
        parameters=[
            {
                'name': 'expression',
                'description': '可以被python eval 函数执行的数学表达式',
                'required': True,
                'schema': {'type': 'string'},
            }
        ]
    )  
    agent.tools.add_tool(
        name_for_human="google search",
        name_for_model="google_search",
        func=google_search,
        description="google search是一个通用搜索引擎，可用于访问互联网、查询百科知识、了解时事新闻等。",
        parameters=[
            {
                'name': 'search_query',
                'description': '搜索关键词或短语',
                'required': True,
                'schema': {'type': 'string'},
            }
        ]
    )   
    
    agent.tools.add_tool(
        name_for_human="获取景点信息",
        name_for_model="get_attractions",
        func=get_attractions,
        description="获取指定城市的主要景点信息。",
        parameters=[
            {
                'name': 'city',
                'description': '城市名称',
                'required': True,
                'schema': {'type': 'string'},
            }
        ]
    )

    agent.tools.add_tool(
        name_for_human="获取餐厅信息",
        name_for_model="get_restaurants",
        func=get_restaurants,
        description="获取指定城市的餐厅推荐。",
        parameters=[
            {
                'name': 'city',
                'description': '城市名称',
                'required': True,
                'schema': {'type': 'string'},
            }
        ]
    )

    agent.tools.add_tool(
        name_for_human="获取住宿信息",
        name_for_model="get_accommodations",
        func=get_accommodations,
        description="获取指定城市的住宿选项。",
        parameters=[
            {
                'name': 'city',
                'description': '城市名称',
                'required': True,
                'schema': {'type': 'string'},
            }
        ]
    )

    agent.tools.add_tool(
        name_for_human="获取航班信息",
        name_for_model="get_flights",
        func=get_flights,
        description="获取指定出发地、目的地和日期的航班信息。",
        parameters=[
            {
                'name': 'origin',
                'description': '出发城市',
                'required': True,
                'schema': {'type': 'string'},
            },
            {
                'name': 'destination',
                'description': '目的地城市',
                'required': True,
                'schema': {'type': 'string'},
            },
            {
                'name': 'departure_date',
                'description': '出发日期，格式为YYYY-MM-DD',
                'required': True,
                'schema': {'type': 'string'},
            }
        ]
    )

    agent.tools.add_tool(
        name_for_human="获取距离和时间信息",
        name_for_model="get_google_distance_matrix",
        func=get_google_distance_matrix,
        description="获取两个地点之间的距离和行程时间信息。",
        parameters=[
            {
                'name': 'origin',
                'description': '起点',
                'required': True,
                'schema': {'type': 'string'},
            },
            {
                'name': 'destination',
                'description': '终点',
                'required': True,
                'schema': {'type': 'string'},
            },
            {
                'name': 'mode',
                'description': '交通方式，如driving、walking、bicycling或transit',
                'required': True,
                'schema': {'type': 'string'},
            }
        ]
    )
    
    agent.tools.add_tool(
    name_for_human="记录信息到笔记本",
    name_for_model="NotebookWrite",
    func=notebook_write,
    description="将新的数据条目写入笔记本工具,并附带简短描述。此工具应在使用FlightSearch、AccommodationSearch、AttractionSearch、RestaurantSearch或GoogleDistanceMatrix之后立即使用。只有存储在笔记本中的数据才能被规划器看到。因此,你应该将所有需要的信息写入笔记本。",
    parameters=[
        {
            'name': 'input_data',
            'description': '要存储的数据内容。这通常是之前搜索工具返回的结果。',
            'required': True,
            'schema': {'type': 'object'},
        },
        {
            'name': 'short_description',
            'description': '所存数据的标签。用于标识数据存储内容。',
            'required': True,
            'schema': {'type': 'string'},
        }
    ]
    )
    
    # result = agent.run("马斯克发射了多少颗卫星？")
    #result = agent.run(input("请输入问题："), extra_requirements=input("请输入额外要求："))
    result = agent.run(
        "Please help me plan a trip from St. Petersburg to Rockford spanning 3 days from March 16th to March 18th, 2022. The travel should be planned for a single person with a budget of $1,700.", 
        # extra_requirements="请使用中文输出",
        system_prompt=REACT_PLANNER_HUNTER_PROMPT)
    # print(result)