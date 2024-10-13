import os
import sys
import asyncio
import aiohttp
import json

current_dir = os.path.dirname(__file__)
external_dir = os.path.abspath(os.path.join(current_dir, '..'))  
sys.path.append(external_dir)

from openai import AsyncOpenAI
from langchain_community.utilities import GoogleSerperAPIWrapper
from agents.chat_model import OpenAIChat
from translate import Translator

search = GoogleSerperAPIWrapper()
llm = OpenAIChat(model="gpt-4o-mini")

def translate_city(city_name):
    if not any('\u4e00' <= char <= '\u9fff' for char in city_name):
        return city_name
    
    translator = Translator(to_lang="en", from_lang="zh")
    try:
        translated = translator.translate(city_name)
        return translated.split(' ')[0]
    except Exception as e:
        print(f"翻译过程中发生错误: {str(e)}")
        return city_name

async def relavant_with_query_async(title, content, query):
    relavant_with_query_system_prompt = "You focus on determining whether information about the query is relavant to a given website. If possible, return 'yes', otherwise return 'no'. Do not output anything else!"
    completion = await llm.achat(f"query: {query}, website title: {title}", [], relavant_with_query_system_prompt)
    return "yes" in completion[0].lower(), f"query:{query}\ntitle:{title}\ncontent:{content}\ncompletion:{completion[0]}\n"

async def filter_search_results_async(search_results, query):
    extra_info = ""
    search_results = json.loads(search_results)['organic']
    short_search_results = []

    async def process_result(result):
        result["snippet"] = result["snippet"].split("...")[0] + '...'
        judge, extra = await relavant_with_query_async(result['title'], result['snippet'], query)
        if judge:
            return {
                "title": result['title'],
                "content": result['snippet']
            }, extra
        return None, None

    tasks = [process_result(result) for result in search_results]
    results = await asyncio.gather(*tasks)

    for result, extra in results:
        if result:
            short_search_results.append(result)
            extra_info += extra

    return short_search_results, extra_info

async def get_restaurant_average_cost_async(restaurant_name):
    extra_info = ""
    query = f"{restaurant_name} average cost 人均 价格"
    payload = json.dumps({"q": query})
    
    async with aiohttp.ClientSession() as session:
        async with session.post("https://google.serper.dev/search", 
                                headers={'X-API-KEY': os.getenv("SERPER_API_KEY"),'Content-Type': 'application/json'}, 
                                data=payload) as response:
            response_text = await response.text()
    
    filtered_search_results, extra_info = await filter_search_results_async(response_text, query)
    extra_info += "\nfiltered search results: " + str(filtered_search_results)
    
    get_restaurant_average_cost_system_prompt = """You focus on extracting average cost information for a restaurant from web search results and returning the average cost data.
The final answer should be returned in JSON format, with the following schema:{"inference": "The inference process for determining the average cost in 20 words", "average_cost": "A number + currency unit expressing the average cost *per person*.set it to $25 if no relevant information is found"}
If the currency type is not provided, please infer it from the search results context. Do not output anything other than the JSON format answer!
    """
    completion = await llm.achat('average cost search results:\n' + str(filtered_search_results), [], get_restaurant_average_cost_system_prompt)
    extra_info += "\ncompletion 2: " + completion[0] + '\n'
    
    if not 'average_cost":' in completion[0]:
        return "25$", extra_info
    return completion[0].split('average_cost":')[1].split('}')[0].strip().strip('"'), extra_info

async def get_entity_attribute_async(entity_name, attribute, default_value):
    extra_info = ""
    query = f"{entity_name} {attribute} "
    payload = json.dumps({"q": query})
    
    async with aiohttp.ClientSession() as session:
        async with session.post("https://google.serper.dev/search", 
                                headers={'X-API-KEY': os.getenv("SERPER_API_KEY"),'Content-Type': 'application/json'}, 
                                data=payload) as response:
            response_text = await response.text()
    
    filtered_search_results, extra_info = await filter_search_results_async(response_text, query)
    extra_info += f"\nFiltered search results: {str(filtered_search_results)}"
    
    get_attribute_system_prompt = f"""Your task is to extract information about the {attribute} of {entity_name} from web search results.
Please return the final answer in JSON format as follows: {{"inference": "Brief description of the inference process for determining the {attribute}", "{attribute}": "Extracted {attribute} information.Should be within 20 words"}}
If no relevant information is found, set it to "{default_value}". Do not output anything other than the JSON format answer!
    """
    completion = await llm.achat(f'{attribute} search results:\n{str(filtered_search_results)}', [], get_attribute_system_prompt)
    extra_info += f"\nCompletion result: {completion[0]}\n"
    
    if not attribute in completion[0]:
        return default_value, extra_info
    return completion[0].split(attribute+'":')[1].split('}')[0].strip().strip('"'), extra_info

# Usage examples
if __name__ == "__main__":
    async def main():
        response, extra_info = await get_entity_attribute_async("飞牌", "起源", "no information")
        print(response)
        print(extra_info)

    asyncio.run(main())
