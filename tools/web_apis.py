import json
import os
import sys
import time
import concurrent.futures
import googlemaps
from datetime import datetime, timedelta
import dotenv
from openai import OpenAI
from diskcache import Cache
from functools import wraps, lru_cache
current_dir = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(current_dir, '..')))

from config import *
from tools.utils import translate_city, get_restaurant_average_cost, get_entity_attribute

dotenv.load_dotenv()


from functools import lru_cache
current_dir = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(current_dir, '..')))

from config import *
from tools.utils import translate_city, get_restaurant_average_cost, get_entity_attribute

# 设置缓存
cache = Cache('./cache_directory')

# 定义磁盘缓存装饰器
def disk_cache(expire=timedelta(days=7)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            result = cache.get(key)
            if result is None:
                result = func(*args, **kwargs)
                # 修改这里
                expire_time = None if expire is None else time.time() + expire.total_seconds()
                cache.set(key, result, expire=expire_time)
            return result
        return wrapper
    return decorator
gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))

from amadeus import Client, ResponseError, Location

amadeus = Client(
    client_id=os.getenv("AMADEUS_API_KEY"),
    client_secret=os.getenv("AMADEUS_API_SECRET"),
    hostname='production'
)

@disk_cache(expire=timedelta(days=30))
def get_accommodations(city, check_in_date, check_out_date, adults, rooms=1, currency=GLOBAL_CURRENCY, language=GLOBAL_LANGUAGE, max_results=15):
    try:
        # Translate first
        # city = translate_city(city)
        # get city code
        city_code = amadeus.reference_data.locations.get(
            keyword=city,
            subType=Location.ANY
        ).data[0]['iataCode']
        
        # Search for hotels in the city
        hotel_list = amadeus.reference_data.locations.hotels.by_city.get(
            cityCode=city_code  # City's IATA code
        )

        # Get the IDs of the first max_results hotels
        hotel_ids = [hotel['hotelId'] for hotel in hotel_list.data[:max_results]]
        # print("hotel_ids:", hotel_ids)
        
        # Search for offers for these hotels
        str_answer = ""
        index = 0
        for hotel_id in hotel_ids:
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
                
                if hotel_offer.data:
                    offer = hotel_offer.data[0]
                    hotel_name = offer['hotel']['name']
                    price = offer['offers'][0]['price']['total']
                    
                    # Get rating for each hotel separately
                    try:
                        hotel_rating = amadeus.e_reputation.hotel_sentiments.get(
                            hotelIds=hotel_id
                        )
                        # print(f"hotel_rating for {hotel_id}:", str(hotel_rating.data))
                        rating = (float(hotel_rating.data[0]['overallRating']) / 20) if hotel_rating.data else "N/A"
                    except ResponseError:
                        rating = "N/A"
                    if rating != "N/A":
                        index += 1
                        str_answer += f"{index}. {hotel_name}, price for {adults} adults: {price} {currency}, rating: {rating}\n"
            except ResponseError as error:
                # print(f"获取酒店 {hotel_id} 的信息时发生错误: {error}")
                pass

        if str_answer == "":
            return f"There are no accommodations found in {city} from {check_in_date} to {check_out_date}."
        return str_answer

    except ResponseError as error:
        return f"An error occurred: {error}"

@disk_cache(expire=timedelta(days=30))
def get_attractions(city, query: str = "must-visit attractions", language=GLOBAL_LANGUAGE, num=10):
    # Get the latitude and longitude of the city
    geocode_result = gmaps.geocode(city)
    lat = geocode_result[0]['geometry']['location']['lat']
    lng = geocode_result[0]['geometry']['location']['lng']
    # Execute search
    results = gmaps.places(query=f"{query} in {city}", 
                           location=(lat, lng),
                           language=language,
                           type="tourist_attraction",
                           )
    
    # Extract results
    attractions = []
    for place in results.get('results', [])[:num]:
        attraction = {
            "Name": place.get('name'),
            # "Address": place.get('formatted_address').split(' 邮政编码')[0],
            "Rating": place.get('rating'),
        }
        # Add to the list if rating is not 0
        if attraction["Rating"] > 0:
            attractions.append(attraction)      
              
    # Concurrently get ticket prices for attractions
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(num, 10)) as executor:
        future_to_price = {
            executor.submit(get_entity_attribute, attraction['Name'], 'ticket price', 'free', "return cost for a single person.if there is no such information, return 'free' rather than a uncertain range.Your output should be a single number+currency code, e.g. $25"): attraction
            for attraction in attractions[:num]
        }
        
        for future in concurrent.futures.as_completed(future_to_price):
            attraction = future_to_price[future]
            try:
                price, extra_info = future.result()
                attraction['Ticket Price'] = price
            except Exception as exc:
                print(f'Error getting ticket price for {attraction["Name"]}: {exc}')
                raise
    
    str_answer = ""
    for index, attraction in enumerate(attractions):
        str_answer += f"{index+1}. {attraction['Name']}, rating: {attraction['Rating']}, cost/person: {attraction.get('Ticket Price', 'free')}\n"
    
    if str_answer == "":
        return f"There are no attractions found in {city}."
    return str_answer

@disk_cache(expire=timedelta(days=7))
def get_restaurants(city, query: str = "must-visit restaurants", language=GLOBAL_LANGUAGE, num=10):
    # Get the latitude and longitude of the city
    geocode_result = gmaps.geocode(city)
    lat = geocode_result[0]['geometry']['location']['lat']
    lng = geocode_result[0]['geometry']['location']['lng']
    # Execute search
    results = gmaps.places(query=f"{query} in {city}", 
                           location=(lat, lng),
                           language=language,
                           type="restaurant",
                           )

    # Extract results
    restaurants = []
    for place in results.get('results', []):
        # Add to the list if rating is not 0
        if place.get('rating') > 0:
            restaurants.append({
                "Name": place.get('name'),
                # "Address": place.get('formatted_address').split(' 邮政编码')[0].strip(),
                "Rating": place.get('rating'),
                # "Editorial Summary": overview
            })
            if len(restaurants) == num:
                break
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(restaurants), 10)) as executor:
        # 1. Concurrently get average cost for restaurants
        future_to_restaurant = {
            executor.submit(get_restaurant_average_cost, f"{city} {restaurant['Name']}"): restaurant
            for restaurant in restaurants
        }
        
        # 2. Concurrently get restaurant descriptions
        future_to_description = {
            executor.submit(get_entity_attribute, f"{city} {restaurant['Name']}", 'types of cuisine', ''): restaurant
            for restaurant in restaurants
        }

        str_answer = ""

        # 3. Collect all Future objects
        all_futures = list(future_to_restaurant.keys()) + list(future_to_description.keys())

        # 4. Process all completed tasks
        for index, future in enumerate(concurrent.futures.as_completed(all_futures)):
            if future in future_to_restaurant:
                # Process average cost for restaurant
                restaurant = future_to_restaurant[future]
                try:
                    average_cost, extra_info = future.result()
                except Exception as exc:
                    print(f'Error generating average price for {restaurant["Name"]}: {exc}')
                    average_cost = "$25"
                
                # Store restaurant information for later use
                restaurant['average_cost'] = average_cost

            elif future in future_to_description:
                # Process restaurant description
                restaurant = future_to_description[future]
                try:
                    description_value, description_info = future.result()
                except Exception as exc:
                    print(f'Error getting description for {restaurant["Name"]}: {exc}')
                    description_value = ""
                
                # Store description information for later use
                restaurant['description'] = description_value

        # 5. Build final result string
        for index, restaurant in enumerate(restaurants[:num]):
            str_answer += (f"{index + 1}. {restaurant['Name']}, "
                        f"rating: {restaurant['Rating']}, Average Cost/person: {restaurant.get('average_cost', '$25')}. "
                        f"{restaurant.get('description', '')}\n"
                        )

    if str_answer == "":
        return f"There are no restaurants found in {city}."
    return str_answer # todo use amadeus api to get real POI information

@disk_cache(expire=timedelta(hours=24))
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

AMADEUS_MAX_LENGTH = 28
@disk_cache(expire=timedelta(hours=12))
def get_flights(origin, destination, date):
    try:
        print("origin, destination:", origin, destination)
        # origin_code = amadeus.reference_data.locations.get(
        #     keyword=origin[:AMADEUS_MAX_LENGTH],
        #     subType=Location.ANY
        # ).data[0]['iataCode']

        # destination_code = amadeus.reference_data.locations.get(
        #     keyword=destination[:AMADEUS_MAX_LENGTH],
        #     subType=Location.ANY
        # ).data[0]['iataCode']
        # print("origin_code, destination_code:", origin_code, destination_code)
        # print("date:", date)
        origin_code = origin
        destination_code = destination
        # Get flight information
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode=origin_code,
            destinationLocationCode=destination_code,
            departureDate=date, # format: '2024-11-01'
            adults=1,
            currencyCode=GLOBAL_CURRENCY,
            max=5  # Increase the number of returned flights
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
        
        if flights_str == "":
            return f"There are no flights found from {origin} to {destination} on {date}."
        return flights_str

    except ResponseError as error:
        print(error)
        return f"Something wrong. Please check the input(especially the departure date)."

if __name__ == "__main__":
    import time
    
    start_time = time.time()
    # result = get_attractions("Hongkong", num=10)
    # {"origin":"ZGN","destination":"LAX","departure_date":"2024-10-19"}
    # result = get_flights("ZGN", "LAX", "2024-10-19")
    result = get_attractions("San Francisco")
    end_time = time.time()
    
    print(result)
    print(f"Runtime: {end_time - start_time:.2f} seconds")
