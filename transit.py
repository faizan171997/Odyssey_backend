from flask import Flask, request, jsonify
import requests
import logging
from functools import lru_cache
import time

app = Flask(__name__)

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
    # formatted_stops = [
    #     {
    #         'route_short_name': route_departure['route_short_name'],
    #         #'headsign' : route_departure['iteneraries']['headsign'],
    #         'global_route_id' : route_departure['global_route_id']
    #     }
    #     for route_departure in route_departures
    # ]

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


@app.route('/places')
def get_places_for_a_bus():
    global_route_id=request.args.get('global_route_id')
    headsign=request.args.get('headsign')
    global_stop_id=request.args.get('global_stop_id')
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
                nearest_stop_name=stop['stop_name']
                places=fetch_places(lat,lon)
                for place in places.get('results', []):
                    place_lat = place.get('geometry', {}).get('location', {}).get('lat')
                    place_lng = place.get('geometry', {}).get('location', {}).get('lng')
                    formatted_place = {
                        'name': place.get('name'),
                        'nearest_stop': nearest_stop_name,
                        'type': place.get('types', []),  # Assuming you want the first two types
                        'rating': place.get('rating', None),
                        'latitude': place_lat,
                        'longitude': place_lng
                    }
                    formatted_places.append(formatted_place)
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




# @app.route('/reverse_search')
# def reverse_search():
#     dest_lat = request.args.get('dest_lat')
#     dest_lon = request.args.get('dest_lon')
#     source_lat = request.args.get('source_lat')
#     source_lon = request.args.get('source_lon')

#     # Fetch nearby stops for both the source and destination
#     source_stops = get_nearby_stops_direct(source_lat, source_lon)
#     dest_stops = get_nearby_stops_direct(dest_lat, dest_lon)

#     possible_routes = []

#     # Iterate over each source and destination stop pair
#     for source_stop in source_stops:
#         source_route_ids = get_global_route_ids(source_stop['global_stop_id'])
#         logging.debug(f"source_route_ids: {source_route_ids} source_stop {source_stop['global_stop_id']}")
#         for dest_stop in dest_stops:
#             dest_route_ids = get_global_route_ids(dest_stop['global_stop_id'])
#             logging.debug(f"dest_route_ids: {dest_route_ids}")
#             # Find intersection of route IDs from source and destination
#             common_route_ids = list(set(source_route_ids).intersection(dest_route_ids))
#             # Fetch details for each common route ID
#             for route_id in common_route_ids:
#                 route_stops = fetch_route_stops(route_id)

#                 # Determine if source comes before destination and filter the stops accordingly
#                 source_index = next((i for i, stop in enumerate(route_stops) if stop['global_stop_id'] == source_stop['global_stop_id']), -1)
#                 dest_index = next((i for i, stop in enumerate(route_stops) if stop['global_stop_id'] == dest_stop['global_stop_id']), -1)

#                 if source_index != -1 and dest_index != -1 and source_index < dest_index:
#                     filtered_stops = route_stops[source_index:dest_index + 1]
#                     possible_routes.append({
#                         'route_id': route_id,
#                         'source_stop_id': source_stop['global_stop_id'],
#                         'destination_stop_id': dest_stop['global_stop_id'],
#                         'stops': filtered_stops
#                     })

#     return jsonify(possible_routes)

#@lru_cache(maxsize=128) 
def throttled_request(url, headers, params, max_retries=5):
    delay = 1  # Initial delay in seconds between retries
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:  # Too Many Requests
            time.sleep(delay)
            delay *= 2  # Exponential backoff
        else:
            break  # Break the loop if other HTTP errors occur
    return None  # Return None if all retries fail

@app.route('/reverse_search')
def reverse_search():
    dest_lat = request.args.get('dest_lat')
    dest_lon = request.args.get('dest_lon')
    source_lat = request.args.get('source_lat')
    source_lon = request.args.get('source_lon')

    # Fetch nearby stops for both the source and destination
    source_stops = get_nearby_stops_direct(source_lat, source_lon)
    dest_stops = get_nearby_stops_direct(dest_lat, dest_lon)

    # Cache for destination route IDs
    dest_route_ids_cache = {}

    # Collect all route IDs for destination stops only once
    for dest_stop in dest_stops:
        dest_route_ids_cache[dest_stop['global_stop_id']] = get_global_route_ids(dest_stop['global_stop_id'])

    logging.debug(f"dest_route_ids_cache: {dest_route_ids_cache}")
    possible_routes = []

    # Iterate over each source and use cached destination route IDs
    for source_stop in source_stops:
        source_route_ids = get_global_route_ids(source_stop['global_stop_id'])
        logging.debug(f"source_route_ids: {source_route_ids}")
        for dest_stop in dest_stops:
            dest_route_ids = dest_route_ids_cache[dest_stop['global_stop_id']]

            # Find intersection of route IDs    from source and destination
            common_route_ids = list(set(source_route_ids).intersection(dest_route_ids))
            logging.debug(f"common_route_ids: {common_route_ids}")
            # Fetch details for each common route ID
            for route_id in common_route_ids:
                route_stops = fetch_route_stops(route_id)

                # Determine if source comes before destination and filter the stops accordingly
                source_index = next((i for i, stop in enumerate(route_stops) if stop['global_stop_id'] == source_stop['global_stop_id']), -1)
                dest_index = next((i for i, stop in enumerate(route_stops) if stop['global_stop_id'] == dest_stop['global_stop_id']), -1)

                if source_index != -1 and dest_index != -1 and source_index < dest_index:
                    filtered_stops = route_stops[source_index:dest_index + 1]
                    possible_routes.append({
                        'route_id': route_id,
                        'source_stop_id': source_stop['global_stop_id'],
                        'destination_stop_id': dest_stop['global_stop_id'],
                        'stops': filtered_stops
                    })

    return jsonify(possible_routes)



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

#@lru_cache(maxsize=128)
def get_global_route_ids(global_stop_id):
    URL = 'https://external.transitapp.com/v3/public/stop_departures'
    params = {'global_stop_id': global_stop_id}
    headers = {'apiKey': API_KEY}
    response = throttled_request(URL, headers, params)
    #response = requests.get(URL, headers=headers, params=params)
    
    if response:  # Check if the response is not None
        route_departures = response.get('route_departures', [])
        global_route_ids = [departure['global_route_id'] for departure in route_departures]
        return global_route_ids
    return []  # Return an empty list if the request failed

def fetch_route_stops(global_route_id):
    URL = 'https://external.transitapp.com/v3/public/route_details'
    params = {'global_route_id': global_route_id}
    headers = {'apiKey': API_KEY}
    #response = requests.get(URL, headers=headers, params=params)
    response = throttled_request(URL, headers, params)
    if response:  # Check if the response is not None
        route_details = response.get('itineraries', [])
        stops = []
        if route_details and 'stops' in route_details[0]:
            stops = [
                {
                    'global_stop_id': stop['global_stop_id'],
                    'stop_name': stop['stop_name'],
                    'stop_lat': stop['stop_lat'],
                    'stop_lon': stop['stop_lon']
                }
                for stop in route_details[0]['stops']
            ]
        return stops
    return []  # Return an empty list if the request failed


if __name__ == '__main__':
    app.run(debug=True)


