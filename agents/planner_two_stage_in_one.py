import sys
import os
print(os.getcwd())
print(os.path.join(os.getcwd(), "tools"))
sys.path.append(os.path.abspath(os.getcwd()))
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "tools")))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from agents.react_agent import ReactAgent
from prompts import REACT_PLANNER_PROMPT_TWO_STAGE_IN_ONE
from tool_funcs import get_attractions, get_restaurants, get_accommodations, get_flights, get_google_distance_matrix, calculator, google_search

planner_two_stage_in_one = ReactAgent(model="gpt-4o", stop=['/>']) # import this


planner_two_stage_in_one.tools.add_tool(
    name_for_human="calculator",
    name_for_model="calculator",
    func=calculator,
    description="A tool for performing mathematical calculations.",
    parameters=[
        {
            'name': 'expression',
            'description': 'A mathematical expression that can be executed by the Python eval function',
            'required': True,
            'schema': {'type': 'string'},
        }
    ]
)  
planner_two_stage_in_one.tools.add_tool(
    name_for_human="google search",
    name_for_model="google_search",
    func=google_search,
    description="A general search engine for accessing the internet, querying encyclopedic knowledge, and staying updated on current events.",
    parameters=[
        {
            'name': 'search_query',
            'description': 'Search keywords or phrases',
            'required': True,
            'schema': {'type': 'string'},
        }
    ]
)   
planner_two_stage_in_one.tools.add_tool(
    name_for_human="Get Attraction Information",
    name_for_model="get_attractions",
    func=get_attractions,
    description="Retrieve information about major attractions in a specified city.",
    parameters=[
        {
            'name': 'city',
            'description': 'City name',
            'required': True,
            'schema': {'type': 'string'},
        }
    ]
)
planner_two_stage_in_one.tools.add_tool(
    name_for_human="Get Restaurant Information",
    name_for_model="get_restaurants",
    func=get_restaurants,
    description="Get restaurant recommendations for a specified city.",
    parameters=[
        {
            'name': 'city',
            'description': 'City name',
            'required': True,
            'schema': {'type': 'string'},
        }
    ]
)
planner_two_stage_in_one.tools.add_tool(
    name_for_human="Get Accommodation Information",
    name_for_model="get_accommodations",
    func=get_accommodations,
    description="Retrieve accommodation options for a specified city.",
    parameters=[
        {
            'name': 'city',
            'description': 'City name',
            'required': True,
            'schema': {'type': 'string'},
        }
    ]
)
planner_two_stage_in_one.tools.add_tool(
    name_for_human="Get Flight Information",
    name_for_model="get_flights",
    func=get_flights,
    description="Retrieve flight information for specified origin, destination, and date.",
    parameters=[
        {
            'name': 'origin',
            'description': 'Departure city',
            'required': True,
            'schema': {'type': 'string'},
        },
        {
            'name': 'destination',
            'description': 'Destination city',
            'required': True,
            'schema': {'type': 'string'},
        },
        {
            'name': 'departure_date',
            'description': 'Departure date in YYYY-MM-DD format',
            'required': True,
            'schema': {'type': 'string'},
        }
    ]
)
planner_two_stage_in_one.tools.add_tool(
    name_for_human="Get Distance and Time Information",
    name_for_model="get_google_distance_matrix",
    func=get_google_distance_matrix,
    description="Get distance and travel time information between two locations.",
    parameters=[
        {
            'name': 'origin',
            'description': 'Starting point',
            'required': True,
            'schema': {'type': 'string'},
        },
        {
            'name': 'destination',
            'description': 'End point',
            'required': True,
            'schema': {'type': 'string'},
        },
        {
            'name': 'mode',
            'description': 'Mode of transportation, such as driving, walking, bicycling, or transit',
            'required': True,
            'schema': {'type': 'string'},
        }
    ]
) 
# planner_two_stage_in_one.tools.add_tool(
#     name_for_human="Check Plan",
#     name_for_model="check_plan",
#     func=check_plan,
#     description="Check if the travel plan meets the requirements.",
#     parameters=[
#         {
#             'name': 'query',
#             'description': 'Query',
#             'required': True,
#             'schema': {'type': 'string'},
#         },
#         {
#             'name': 'plan',
#             'description': 'Plan',
#             'required': True,
#             'schema': {'type': 'string'},
#         } 
#     ]
# )
if __name__ == '__main__':

    # result = agent.run("马斯克发射了多少颗卫星？")
    #result = agent.run(input("请输入问题："), extra_requirements=input("请输入额外要求："))
    result = planner_two_stage_in_one.run(
        "Please help me plan a trip from St. Petersburg to Rockford spanning 3 days from March 16th to March 18th, 2022. The travel should be planned for a single person with a budget of $1,700.", 
        # extra_requirements="请使用中文输出",
        system_prompt=REACT_PLANNER_PROMPT_TWO_STAGE_IN_ONE)
    # print(result)