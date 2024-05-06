from flask import Flask, request, jsonify
import requests
import logging

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
    logging.debug(f"Status Code: {response.status_code}")
    logging.debug(f"Response: {response.json()}")

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
    logging.debug(f"Status Code: {response.status_code}")
    logging.debug(f"Response: {response.json()}")

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
    base_url = "https://external.transitapp.com/v3/public/route_details"
    headers = {'apiKey': API_KEY}
    params = {
        'global_route_id': global_route_id
    }
    response = requests.get(base_url, headers=headers, params=params)
    itineraries = response.json().get('itineraries', [])
    for itinerarie in itineraries:
        logging.debug(f"itinerarie['direction_headsign']: {itinerarie['direction_headsign']}")
        logging.debug(f"headsign: {headsign}")
        if itinerarie['direction_headsign'] == headsign:
            formatted_places=[]
            logging.debug("Entered here")
            for stop in itinerarie['stops']:
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









# import requests

# def fetch_places(lat, lon, api_key):
#     base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         'location': f'{lat},{lon}',
#         'radius': '1000',  # Define the radius in meters
#         'type': 'restaurant',  # Change to whatever place type you're interested in
#         'key': api_key
#     }

#     response = requests.get(base_url, params=params)
#     results = response.json()
    
#     if results.get('status') == 'OK':
#         return results['results']
#     else:
#         return {'error': results.get('status', 'Unknown error')}




if __name__ == '__main__':
    app.run(debug=True)


#
