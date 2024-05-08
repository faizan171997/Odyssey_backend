from flask import Flask, request, jsonify
import requests
import logging
from pymongo import MongoClient
from functools import lru_cache
from bson.json_util import dumps
import hashlib
import time

app = Flask(__name__)


# MongoDB setup
client = MongoClient('localhost', 27017)  # Connect to your MongoDB server
db = client.places_cache  # Use or create a database called 'places_cache'
collection = db.places  # Use or create a collection within the database

# Enable logging
logging.basicConfig(level=logging.DEBUG)
# Set your API key here
API_KEY = '0fc35ce9a6772ecc034b451152483c589e226ed3012eb8fbd39509fc84f73b24'
#TRANSIT_API_URL = 'https://external.transitapp.com/v3/public/nearby_stops'

@app.route('/get_nearby_stops')
def get_nearby_stops():
    # Extract query parameters from the incoming request
    URL = 'https://external.transitapp.com/v3/public/nearby_stops'
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    max_distance = request.args.get('max_distance', '1500')
    stop_filter = request.args.get('stop_filter', 'Routable')

    headers = {'apiKey': API_KEY}

    # Parameters for the request
    params = {
        'lat': lat,
        'lon': lon,
        'max_distance': max_distance,
        'stop_filter': stop_filter
    }

    # Call the transit API and capture the response
    response = requests.get(URL, headers=headers, params=params)
    
    # Log the status code and response for debugging
    #logging.debug(f"Status Code: {response.status_code}")
    #logging.debug(f"Response: {response.json()}")

    # Filter and format the response
    stops = response.json().get('stops', [])
    formatted_stops = [
        {
            'distance': stop['distance'],   
            'global_stop_id': stop['global_stop_id'],
            'stop_name': stop['stop_name']
        }
        for stop in stops
    ]

    # Return the filtered and formatted response
    return jsonify(formatted_stops)



@app.route('/get_stop_departures')
def get_stop_departure():
    # Extract query parameters from the incoming request
    URL = 'https://external.transitapp.com/v3/public/stop_departures'
    global_stop_id = request.args.get('global_stop_id')

    headers = {'apiKey': API_KEY}

    # Parameters for the request
    params = {
        'global_stop_id': global_stop_id,
    }

    # Call the transit API and capture the response
    response = requests.get(URL, headers=headers, params=params)
    
    # Log the status code and response for debugging
    #logging.debug(f"Status Code: {response.status_code}")
    #logging.debug(f"Response: {response.json()}")

    # Filter and format the response
    route_departures = response.json().get('route_departures', [])
    formatted_stops = []
    
    for route_departure in route_departures:
        # Loop through each itinerary in the route_departure
        for itinerary in route_departure.get('itineraries', []):
            # Extract all departure times from the schedule_items
            departures = [item['scheduled_departure_time'] for item in itinerary.get('schedule_items', [])]

            # Append each formatted stop information to the list
            formatted_stops.append({
                'route_short_name': route_departure['route_short_name'],
                'headsign': itinerary['headsign'],  # Now correctly accessing 'headsign' from 'itineraries'
                'global_route_id': route_departure['global_route_id'],
                'departures': departures  # List of all departure times
            })

    # Return the filtered and formatted response
    return jsonify(formatted_stops)

places_collection = db.places_cache

@app.route('/places')
def get_places_for_a_bus():
    global_route_id=request.args.get('global_route_id')
    headsign=request.args.get('headsign')
    global_stop_id=request.args.get('global_stop_id')

    unique_key = f"{global_route_id}_{headsign}_{global_stop_id}"
    hashed_key = hashlib.sha256(unique_key.encode()).hexdigest()

    cached_data = places_collection.find_one({'_id': hashed_key})
    if cached_data:
        logging.debug("Returning cached data")
        return jsonify(cached_data['data'])

    logging.debug("Data not found in cache, fetching new data")

    flag = False
    base_url = "https://external.transitapp.com/v3/public/route_details"
    headers = {'apiKey': API_KEY}
    params = {
        'global_route_id': global_route_id
    }
    response = requests.get(base_url, headers=headers, params=params)
    itineraries = response.json().get('itineraries', [])
    for itinerarie in itineraries:
        #logging.debug(f"itinerarie['direction_headsign']: {itinerarie['direction_headsign']}")
        #logging.debug(f"headsign: {headsign}")
        if itinerarie['direction_headsign'] == headsign:
            formatted_places=[]
            #logging.debug("Entered here")
            for stop in itinerarie['stops']:
                if stop['global_stop_id'] == global_stop_id :
                    flag=True
                    #logging.debug("Here")
                if flag is False:
                    continue
                lat=stop['stop_lat']
                lon=stop['stop_lon']
                stop_info = {
                        'name': stop['stop_name'],
                        'id': stop['global_stop_id']
                }
                places=fetch_places(lat,lon)
                for place in places.get('results', []):
                    place_lat = place.get('geometry', {}).get('location', {}).get('lat')
                    place_lng = place.get('geometry', {}).get('location', {}).get('lng')
                    formatted_place = {
                        'name': place.get('name'),
                        'stop': stop_info,
                        'type': place.get('types', []),  # Assuming you want the first two types
                        'rating': place.get('rating', None),
                        'latitude': place_lat,
                        'longitude': place_lng
                    }
                    formatted_places.append(formatted_place)
            places_collection.insert_one({'_id': hashed_key, 'data': formatted_places})
            logging.debug("Data cached for future use")
            return jsonify(formatted_places)
    return jsonify({'message': 'No places found for the specified route and headsign'})


def fetch_places(lat,lon):
    #lat = request.args.get('lat')
    #lon = request.args.get('lon')
    # Extract query parameters from the incoming request
    base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        'location': f'{lat},{lon}',
        'radius': '1000',  # Define the radius in meters
        'type': 'restaurant',  # Change to whatever place type you're interested in
        'key': 'AIzaSyD-u2cMuvQo2_yBphtFc5dbxJ4MBVPO2BI'
    }

    response = requests.get(base_url, params=params)
    return response.json()

@lru_cache(maxsize=128)
def throttled_request(url, headers_tuple, params_tuple, max_retries=10):
    headers = dict(headers_tuple)  # Convert tuple back to dict
    params = dict(params_tuple)  # Convert tuple back to dict
    delay = 1
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:  # Too Many Requests
            time.sleep(delay)
            delay *= 2  # Exponential backoff
        else:
            break
    return None

def round_coordinates(lat, lon, precision=4):
    """ Round the coordinates to a specified precision to create geospatial bins. """
    # The precision defines the number of decimal places, e.g., 4 decimal places ~ 11 meters
    return round(lat, precision), round(lon, precision)

reverse_search_collection = db.reverse_search_cache 
@app.route('/reverse_search')
def reverse_search():
    dest_lat = float(request.args.get('dest_lat'))
    dest_lon = float(request.args.get('dest_lon'))
    source_lat = float(request.args.get('source_lat'))
    source_lon = float(request.args.get('source_lon'))

    dest_lat, dest_lon = round_coordinates(dest_lat, dest_lon)
    source_lat, source_lon = round_coordinates(source_lat, source_lon)

    unique_key = f"{dest_lat}_{dest_lon}_{source_lat}_{source_lon}"
    hashed_key = hashlib.sha256(unique_key.encode()).hexdigest()

    cached_data = reverse_search_collection.find_one({'_id': hashed_key})
    if cached_data:
        logging.debug("Returning cached data")
        return jsonify(cached_data['data'])

    logging.debug("Data not found in cache, fetching new data")
    
    # Fetch nearby stops for both the source and destination
    source_stops = get_nearby_stops_direct(source_lat, source_lon)
    dest_stops = get_nearby_stops_direct(dest_lat, dest_lon)


    # Cache for destination route IDs with additional information
    dest_route_ids_cache = {}

    # Collect all route IDs and additional information for destination stops only once
    for dest_stop in dest_stops:
        dest_route_ids_cache[dest_stop['global_stop_id']] = get_global_route_ids(dest_stop['global_stop_id'])

    longest_routes = {}

    # Iterate over each source and use cached destination route IDs
    for source_stop in source_stops:
        source_route_info = get_global_route_ids(source_stop['global_stop_id'])
        for dest_stop in dest_stops:
            dest_route_info = dest_route_ids_cache[dest_stop['global_stop_id']]
            source_route_ids = {info['global_route_id']: info for info in source_route_info}
            dest_route_ids = {info['global_route_id']: info for info in dest_route_info}

            # Find intersection of route IDs from source and destination
            common_route_ids = set(source_route_ids.keys()).intersection(dest_route_ids.keys())

            # Fetch details for each common route ID
            for route_id in common_route_ids:
                logging.debug(f"common route id {route_id}")
                route_stops = fetch_route_stops(route_id)
                # Determine if source comes before destination and filter the stops accordingly
                source_index = next((i for i, stop in enumerate(route_stops) if stop['global_stop_id'] == source_stop['global_stop_id']), -1)
                dest_index = next((i for i, stop in enumerate(route_stops) if stop['global_stop_id'] == dest_stop['global_stop_id']), -1)
                if source_index != -1 and dest_index != -1 and source_index < dest_index:
                    filtered_stops = route_stops[source_index:dest_index + 1]
                    route_length = len(filtered_stops)
                    if route_id not in longest_routes or route_length > len(longest_routes[route_id]['stops']):
                        longest_routes[route_id] = {
                            'route_id': route_id,
                            'source_stop_id': source_stop['global_stop_id'],
                            'destination_stop_id': dest_stop['global_stop_id'],
                            'route_short_name': source_route_ids[route_id]['route_short_name'],
                            'headsign': source_route_ids[route_id]['headsign'],
                            'stops': filtered_stops  # Keeping this line for now to gather places later
                        }

    if longest_routes:
        logging.debug(f"longest_routes {longest_routes}")
        # Fetch places for each stop in the longest routes
        for route_id, route_info in longest_routes.items():
            places_results = []
            for stop in route_info['stops']:  # Using stops to find places
                places = fetch_places(stop['stop_lat'], stop['stop_lon'])
                for place in places.get('results', []):
                    place_details = {
                        'name': place['name'],
                        'nearest_stop': stop['stop_name'],
                        'type': place.get('types', []),
                        'rating': place.get('rating', None),
                        'latitude': place['geometry']['location']['lat'],
                        'longitude': place['geometry']['location']['lng']
                    }
                    places_results.append(place_details)
            route_info['places'] = places_results
            del route_info['stops']  # Remove stops from final output as requested

        reverse_search_collection.insert_one({'_id': hashed_key, 'data': list(longest_routes.values())})
        logging.debug("Data cached for future use")
        return jsonify(list(longest_routes.values()))
    else:
        logging.debug("No data to cache; response is empty.")
        return jsonify({'message': 'No routes found meeting the criteria'})



def get_nearby_stops_direct(lat, lon):
    URL = 'https://external.transitapp.com/v3/public/nearby_stops'
    params = {
        'lat': lat,
        'lon': lon,
        'max_distance': '400',  # You can adjust this value based on the required search radius
        'stop_filter': 'Routable'
    }
    headers = {'apiKey': API_KEY}
    response = requests.get(URL, headers=headers, params=params)
    stops = response.json().get('stops', [])
    return [
        {
            'global_stop_id': stop['global_stop_id'],
            'stop_name': stop['stop_name']
        }
        for stop in stops
    ]

@lru_cache(maxsize=128)
def get_global_route_ids(global_stop_id):
    URL = 'https://external.transitapp.com/v3/public/stop_departures'
    headers = {'apiKey': API_KEY}
    params = {'global_stop_id': global_stop_id}
    headers_tuple = tuple(sorted(headers.items()))
    params_tuple = tuple(sorted(params.items()))
    response = throttled_request(URL, headers_tuple, params_tuple)
    if response:
        route_departures = response.get('route_departures', [])
        return [
            {
                'global_route_id': departure['global_route_id'],
                'route_short_name': departure['route_short_name'],
                'headsign': departure.get('itineraries', [])[0]['headsign'] if departure.get('itineraries') else ""
            }
            for departure in route_departures
        ]
    return []


@lru_cache(maxsize=128)
def fetch_route_stops(global_route_id):
    URL = 'https://external.transitapp.com/v3/public/route_details'
    headers = {'apiKey': API_KEY}
    params = {'global_route_id': global_route_id}
    headers_tuple = tuple(sorted(headers.items()))
    params_tuple = tuple(sorted(params.items()))
    response = throttled_request(URL, headers_tuple, params_tuple)
    if response:
        route_details = response.get('itineraries', [])
        if route_details and 'stops' in route_details[0]:
            return [
                {
                    'global_stop_id': stop['global_stop_id'],
                    'stop_name': stop['stop_name'],
                    'stop_lat': stop['stop_lat'],
                    'stop_lon': stop['stop_lon']
                }
                for stop in route_details[0]['stops']
            ]
    return []

search_places_collection = db.search_places_cache 
@app.route('/search_places')
def search_places():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    keyword = request.args.get('keyword')

    hash_key = hashlib.sha256(f"{lat}{lon}{keyword}".encode()).hexdigest()

    cached_result = search_places_collection.find_one({'_id': hash_key})

    if cached_result:
        # Return the cached result if it exists
        return jsonify(cached_result['data'])

    # Construct the Google Places API URL
    base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        'location': f'{lat},{lon}',
        'radius': '5000',  # Search within 5km radius
        'keyword': keyword,
        'key': 'AIzaSyD-u2cMuvQo2_yBphtFc5dbxJ4MBVPO2BI'
    }

    # Make the API request to Google Places
    response = requests.get(base_url, params=params)
    places = response.json()

    # Extract the relevant information to return
    results = []
    if 'results' in places:
        for place in places['results']:
            result = {
                'name': place['name'],
                'address': place.get('vicinity'),
                'latitude': place['geometry']['location']['lat'],
                'longitude': place['geometry']['location']['lng']
            }
            results.append(result)
    
    # Cache the result in MongoDB
    if results:
        search_places_collection.insert_one({
            '_id': hash_key,
            'data': results
        })
        logging.debug("Data cached in search_places_cache for future use")
    

    return jsonify(results)


if __name__ == '__main__':
    app.run(host='0.0.0.0',port=50001, debug=True)


