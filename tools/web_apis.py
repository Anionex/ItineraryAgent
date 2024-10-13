import asyncio
import json
import googlemaps
from datetime import datetime
import dotenv
from openai import OpenAI


dotenv.load_dotenv()
import os
import sys
import concurrent.futures

current_dir = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(current_dir, '..')))

from config import *
from utils import translate_city, get_restaurant_average_cost_async, get_entity_attribute_async

gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
from amadeus import Client, ResponseError

def get_accommodations(city, check_in_date, check_out_date, adults, rooms=1, currency=GLOBAL_CURRENCY, language=GLOBAL_LANGUAGE, max_results=30):

    try:
        # 先翻译
        city = translate_city(city)
        # get city code
        city_code = amadeus.reference_data.locations.get(
            keyword=city,
            subType=Location.ANY
        ).data[0]['iataCode']
        
        # 搜索城市的酒店
        hotel_list = amadeus.reference_data.locations.hotels.by_city.get(
            cityCode=city_code  # 城市的IATA代码
        )

        # 获取前max_results个酒店的ID
        hotel_ids = [hotel['hotelId'] for hotel in hotel_list.data[:max_results]]
        # print("hotel_ids:", hotel_ids)
        
        # 搜索这些酒店的报价
        str_answer = ""
        for index, hotel_id in enumerate(hotel_ids):
            try:
                hotel_offer = amadeus.shopping.hotel_offers_search.get(
                    hotelIds=hotel_id,
                    adults=str(adults),
                    roomQuantity=str(rooms),
                    checkInDate=check_in_date,
                    checkOutDate=check_out_date,
                    currency=currency,
                    lang=language
                )
                # print(f"hotel_offer for {hotel_id}:", str(hotel_offer.data))
                
                if hotel_offer.data:
                    offer = hotel_offer.data[0]
                    hotel_name = offer['hotel']['name']
                    price = offer['offers'][0]['price']['total']
                    
                    # 单独获取每个酒店的评分
                    try:
                        hotel_rating = amadeus.e_reputation.hotel_sentiments.get(
                            hotelIds=hotel_id
                        )
                        # print(f"hotel_rating for {hotel_id}:", str(hotel_rating.data))
                        rating = hotel_rating.data[0]['overallRating'] if hotel_rating.data else "N/A"
                    except ResponseError:
                        rating = "N/A"
                    if rating != "N/A":
                        str_answer += f"{index+1}. {hotel_name}, 价格: {price} {currency}, 评分: {rating}\n"
            except ResponseError as error:
                # print(f"获取酒店 {hotel_id} 的信息时发生错误: {error}")
                pass

        return str_answer

    except ResponseError as error:
        return f"发生错误: {error}"

def get_attractions(city, language=GLOBAL_LANGUAGE, num=10):
    # Get the latitude and longitude of the city
    geocode_result = gmaps.geocode(city)
    lat = geocode_result[0]['geometry']['location']['lat']
    lng = geocode_result[0]['geometry']['location']['lng']
    # Execute search
    results = gmaps.places(query=f"attractions in {city}", 
                           location=(lat, lng),
                           language=language,
                           type="tourist_attraction",
                           )
    
    # Extract results
    attractions = []
    for place in results.get('results', []):
        attraction = {
            "Name": place.get('name'),
            "Address": place.get('formatted_address').split(' 邮政编码')[0],
            "Rating": place.get('rating'),
        }
        # Add to the list if rating is not 0
        if attraction["Rating"] > 0:
            attractions.append(attraction)        
    
    # Sort
    attractions.sort(key=lambda x: x["Rating"], reverse=True)
    attractions = attractions[0:num] if len(attractions) > num else attractions
    str_answer = ""
    for index, attraction in enumerate(attractions):
        str_answer += f"{index+1}. {attraction['Name']}({attraction['Address']}), rating: {attraction['Rating']}\n"
    return str_answer


async def get_restaurants_async(city, language=GLOBAL_LANGUAGE, num=10):
    # Get the latitude and longitude of the city
    geocode_result = gmaps.geocode(city)
    lat = geocode_result[0]['geometry']['location']['lat']
    lng = geocode_result[0]['geometry']['location']['lng']
    # Execute search
    results = gmaps.places(query=f"specialty restaurants in {city}", 
                           location=(lat, lng),
                           language=language,
                           type="restaurant",
                           )

    # Extract results
    
    restaurants = []
    for place in results.get('results', []):
        # use place_id to get more information
        # overview = ""
        # try:
        #     place_id = place.get('place_id')
        #     details = gmaps.place(place_id=place_id)
        #     overview = details.get('result').get('editorial_summary').get('overview')
        # except:
        #     pass
        restaurant = {
            "Name": place.get('name'),
            "Address": place.get('formatted_address').split(' 邮政编码')[0],
            "Rating": place.get('rating'),
            # "Editorial Summary": overview
        }
        # Add to the list if rating is not 0
        # return place, details
        if restaurant["Rating"] > 0:
            restaurants.append(restaurant)
    
    # Sort
    results = results['results'][:13]  # 只取前13个结果
    # restaurants.sort(key=lambda x: x["Rating"], reverse=True)
    # restaurants是字典数组
    restaurants = restaurants[0:num] if len(restaurants) > num else restaurants    

    async def process_restaurant(restaurant, city):
        average_cost, extra_info = await get_restaurant_average_cost_async(city + " " + restaurant['Name'])
        description_value, description_info = await get_entity_attribute_async(city + " " + restaurant['Name'], 'types of cuisine', '')
        restaurant['average_cost'] = average_cost
        restaurant['description'] = description_value
        return restaurant

    async def process_all_restaurants(restaurants, city, num):
        tasks = [process_restaurant(restaurant, city) for restaurant in restaurants[:num]]
        processed_restaurants = await asyncio.gather(*tasks)
        
        str_answer = ""
        for index, restaurant in enumerate(processed_restaurants):
            str_answer += (f"{index + 1}. {restaurant['Name']}({restaurant['Address']}), "
                        f"rating: {restaurant['Rating']}, Average Cost: {restaurant.get('average_cost', '25$')}. "
                        f"{restaurant.get('description', '')}\n")
        
        return str_answer

    str_answer = await process_all_restaurants(restaurants, city, num)

    return str_answer # todo 用amadeus api 获取真正的POI 信息

def get_restaurants(city, language=GLOBAL_LANGUAGE, num=10):
    return asyncio.run(get_restaurants_async(city, language, num))

def google_get_accommodations(city, language=GLOBAL_LANGUAGE, num=10):
    # Get the latitude and longitude of the city
    geocode_result = gmaps.geocode(city)
    lat = geocode_result[0]['geometry']['location']['lat']
    lng = geocode_result[0]['geometry']['location']['lng']
    # Execute search
    results = gmaps.places(query=f"accommodations in {city}", 
                           location=(lat, lng),
                           language=language,
                           type="lodging")
    
    # Extract results
    accommodations = []
    for place in results.get('results', []):
        accommodation = {
            "Name": place.get('name'),
            "Address": place.get('formatted_address').split(' 邮政编码')[0],
            # "Price": get_accommodation_price(place.get('name')),
            "Rating": place.get('rating'),
        }
        # Add to the list if rating is not 0
        if accommodation["Rating"] > 0:
            accommodations.append(accommodation)
    
    # Sort
    accommodations.sort(key=lambda x: x["Rating"], reverse=True)
    accommodations = accommodations[0:num] if len(accommodations) > num else accommodations   
    str_answer = ""
    for index, accommodation in enumerate(accommodations):
        str_answer += f"{index+1}. {accommodation['Name']}({accommodation['Address']}), rating: {accommodation['Rating']}\n"
    return str_answer

def get_distance_matrix(origin, destination, mode, language=GLOBAL_LANGUAGE):
    # Origin lat, lng
    geocode_result = gmaps.geocode(origin)
    origin_lat = geocode_result[0]['geometry']['location']['lat']
    origin_lng = geocode_result[0]['geometry']['location']['lng']
    # Destination lat, lng
    geocode_result = gmaps.geocode(destination)
    destination_lat = geocode_result[0]['geometry']['location']['lat']
    destination_lng = geocode_result[0]['geometry']['location']['lng']
    # Execute
    distance_matrix = gmaps.distance_matrix(origins=(origin_lat, origin_lng),
                                           destinations=(destination_lat, destination_lng),
                                           mode=mode,
                                           language=language)
    duration = distance_matrix['rows'][0]['elements'][0]['duration']['text']
    distance = distance_matrix['rows'][0]['elements'][0]['distance']['text']
    return f"{mode.capitalize()}, from {origin} to {destination}, duration: {duration}, distance: {distance}"


from amadeus import Client, ResponseError, Location

amadeus = Client(
    client_id=os.getenv("AMADEUS_API_KEY"),
    client_secret=os.getenv("AMADEUS_API_SECRET"),
    hostname='production'
)

def get_flights(origin, destination, date):
    try:
        # 先翻译
        origin = translate_city(origin)
        destination = translate_city(destination)
        # 获取 IATA 代码
        print("origin, destination:", origin, destination)
        origin_code = amadeus.reference_data.locations.get(
            keyword=origin,
            subType=Location.ANY
        ).data[0]['iataCode']

        destination_code = amadeus.reference_data.locations.get(
            keyword=destination,
            subType=Location.ANY
        ).data[0]['iataCode']
        print("origin_code, destination_code:", origin_code, destination_code)
        print("date:", date)
        # 获取航班信息
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode=origin_code,
            destinationLocationCode=destination_code,
            departureDate=date, # format: '2024-11-01'
            adults=1,
            currencyCode=GLOBAL_CURRENCY,
            max=5  # 增加返回的航班数量
        )

        flights_info = []
        for offer in response.data:
            for itinerary in offer['itineraries']:
                for segment in itinerary['segments']:
                    flight = {
                        'Flight Number': f"{segment['carrierCode']}{segment['number']}",
                        'Departure Time': ':'.join(segment['departure']['at'].split('T')[1].split(':')[0:2]),
                        'Arrival Time': ':'.join(segment['arrival']['at'].split('T')[1].split(':')[0:2]),
                        # 'Duration': itinerary['duration'].split('PT')[1].split('H')[0] 
                        #             + ' hours ' + 
                        #             itinerary['duration'].split('PT')[1].split('H')[1].split('M')[0] + ' minutes',
                        'Price': f"{offer['price']['total']} {offer['price']['currency']}"
                    }
                    flights_info.append(flight)

        # Convert flights_info to string
        flights_str = ""
        for flight in flights_info:
            flights_str += f"Flight number {flight['Flight Number']}, {flight['Departure Time']}-{flight['Arrival Time']}, price: {flight['Price']}/person\n"
        return flights_str

    except ResponseError as error:
        print(error)

if __name__ == "__main__":
    # print(get_distance_matrix("New York", "Los Angeles", "driving"))
    # print(get_flights("nanjing", "beijing", "2024-10-10"))
    # tool_invocation: get_flights
    # tool_input: {'origin': 'St. Petersburg', 'destination': 'Rockford', 'departure_date': '2022-03-16'}
    # print(get_flights("St. Petersburg", "Rockford", "2024-10-11"))
    # Atlanta to Orlando, Fri, Nov 8 <-> Thu, Nov 14
    # print(get_flights("Atlanta", "MCO", "2024-11-08"))
    # print(get_restaurants("中山"))
    # print(get_distance_matrix("中山", "广州", "driving"))
    # accomodations = get_accommodations("桂林")
#     result = get_accommodations(
#         city='KWL',  # 桂林的IATA城市代码
#         check_in_date='2024-10-11',
#         check_out_date='2024-10-12',
#         adults=2,
#         rooms=1,
#         currency=GLOBAL_CURRENCY,
#         language=GLOBAL_LANGUAGE,
#         max_results=20
# )

#     print(result)
    # [1]<Tool Invocation:get_flights/>
    # tool_invocation: get_flights
    # tool_input: {'origin': '广州', 'destination': '桂林', 'departure_date': '2024-10-12'}
    # print(get_flights("中山", "桂林", "2024-10-13"))
    # origin_code = amadeus.reference_data.locations.get(
    #     keyword="zhongshan",
    #     subType=Location.ANY
    # ).data[0]['iataCode']
    # print("origin_code:", origin_code)
    # print(get_attractions("中山"))
    import time
    
    start_time = time.time()
    result = get_restaurants("中山")
    end_time = time.time()
    
    print(result)
    print(f"运行时间: {end_time - start_time:.2f} 秒")
    # print(get_restaurant_average_cost("椿记烧鹅"))
    
    # results = gmaps.places(query=f"specialty restaurants in 中山", 
    #                     location=(22.5152, 113.3924),
    #                     language="zh-CN",
    #                     type="restaurant",
    #                     )
    # print(results)