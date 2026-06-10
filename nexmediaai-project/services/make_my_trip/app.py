from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import math
import warnings
import requests
import json
import os
from datetime import datetime
from functools import wraps

warnings.filterwarnings('ignore')

# Configuration from environment or default
API_KEY = os.environ.get('GOOGLE_API_KEY', "AIzaSyBsu2xsHBKMJBJUrBvXQLBlIxf92DG9ZSc")
FLASK_API_KEY = os.environ.get('API_KEY', 'your-secure-api-key-here')  # Should match Django's FLASK_API_KEY

app = Flask(__name__)
CORS(app)
 
columns_to_keep_df = ['name', 'rating', 'user_ratings_total', 'geometry', 'weighted_score', 'type', 'types', 'lat',
                      'lng', 'price_level', 'vicinity', 'photos', 'reference']

# API Key middleware
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        provided_key = request.headers.get('X-API-Key')
        if not provided_key or provided_key != FLASK_API_KEY:
            return jsonify({'error': 'Unauthorized: Invalid or missing API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

def extract_lat_lng(geometry):
    location = geometry['location']
    return location['lat'], location['lng']

def haversine(lat1, lon1, lat2, lon2): #distance between two point on earth
    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2]) #mn degree l redian
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) #haversine eqn
    r = 6371 #earth radius
    return r * c


def sort_locations_by_distance(df, my_lat, my_lon): #ترتيب الdata علي حسب مسافه haversine من المكان اللي انا فيه
    df['distance'] = df.apply(lambda row: haversine(my_lat, my_lon, row['lat'], row['lng']), axis=1)
    return df.sort_values(by='distance')


def weighted_score(df):
    if len(df) == 0:
        return df
    else:
        df['weighted_score'] = df['rating'] * np.log1p(df['user_ratings_total'])# le rating fe log(3dd el 3mlo el rate)
        df['lat'] = df['geometry'].apply(lambda x: str(x['location']['lat']))
        df['lng'] = df['geometry'].apply(lambda x: str(x['location']['lng']))
        return df.sort_values(by='weighted_score', ascending=False)


def get_largest_cluster(data):
    max_size = 0
    max_index = 0
    for i in range(4):
        cluster_size = data[data['cluster'] == i].shape[0] #bgeb 3dd el rows el fe el data 3la 7sb rqm el cluster
        if cluster_size > max_size:
            max_size = cluster_size
            max_index = i
    return max_index

def fetch_map_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching map data: {e}")
        return None

def process_photos(data):
    thumbnail = None
    for day, activities in data.items():
        for activity in activities:
            if "photos" in activity:
                for photo in activity["photos"]:
                    photo_reference = photo["photo_reference"]
                    api_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key={API_KEY}"

                    try:
                        response = requests.get(api_url, allow_redirects=False)
                        if response.status_code == 302:
                            redirect_url = response.headers.get("Location")
                            if redirect_url:
                                photo["photo_reference"] = redirect_url
                                if not thumbnail:
                                    thumbnail = redirect_url
                    except Exception as e:
                        print(f"Error processing photo_reference {photo_reference}: {e}")
    return thumbnail

def replace_nulls_with_unspecified(dataframe):
    return dataframe.fillna("unspecified").replace("", "unspecified")

# Original route
@app.route('/your_endpoint', methods=['GET'])
def your_endpoint():
    c = 0
    j = 0
    nameofcat = []
    itinerary = {}
    df_tourist = pd.DataFrame()
    temp = []

    days = int(request.args.get('day'))
    lng = request.args.get('lng')
    lat = request.args.get('lat')
    priceLevel = int(request.args.get('price'))
    your_array = request.args.getlist('your_array')
    activities = int(request.args.get('act'))
    radius = 10000

    indexat = [
        ["historical", "tourist_attraction"],
        ["mall", "shopping_mall"],
        ["museum", "museum"],
        ["", "art_gallery"],
        ["", "amusement_park"],
        ["park", "tourist_attraction"],
        ["", "natural_feature"]
    ]

    temp.append(["restaurant", "restaurant"])
    your_array = [int(item) for item in your_array] #mn string l int
    for index, i in enumerate(your_array):#7t asmaa el cat el a5trtha fe temp lw el i el fe yourarry b wa7d
        if i == 1:
            temp.append(indexat[int(index)])

    numOfChoosenCategouries = len(temp) #hat len el temp

####################################################################

    def build_url(first_string, second_string, page_token=None):
        url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius={radius}&key={API_KEY}"
        if first_string != "":
            url += f"&keyword={first_string}"
        url += f"&type={second_string}"
        if page_token:
            url += f"&pagetoken={page_token}"
        return url

    for item in temp: #3dy 3la kol cat
        first_string, second_string = item[0], item[1]
        response = requests.get(build_url(first_string, second_string))
        data = response.json()

        # Checking for errors
        if data["status"] != "OK":
            print(f"Error: {data['status']}")

        # Extracting results from the initial response
        places = data["results"]

        # Checking if there are more results available
        while "next_page_token" in data:
            import time
            time.sleep(2)
            response = requests.get(build_url(first_string, second_string, data["next_page_token"]))
            data = response.json()
            places.extend(data["results"])

        df = pd.DataFrame(places)#make the places dataframe

######################################

        if first_string == "restaurant":
            print(f"restaurant with length {len(df)}")
            df = weighted_score(df)
            df['type'] = first_string #colum gded
            if 'price_level' not in df.columns:
                df['price_level'] = '2'
            nameofcat.append(first_string) #name of the choosen cat (col el type) ,temp el 3dad
            df = df[df['price_level'] == priceLevel]# filter 3la 7sb el budget
            if 'photos' not in df.columns:
                df['photos'] = 'sample_photo_value' 
            df = df.loc[:, columns_to_keep_df]
            df_tourist = pd.concat([df_tourist, df], ignore_index=True)
            df_tourist = df_tourist.drop_duplicates(subset=['name']) #34an el mkan mmken ykon fe 2 cat
            df_tourist.reset_index(drop=True, inplace=True) #trqm bs
        else:
            print(f"tourist with length {len(df)}")
            if first_string == "":
                df['type'] = second_string
                nameofcat.append(second_string)
            else:
                df['type'] = first_string
                nameofcat.append(first_string)

            df = weighted_score(df)

            if len(df) != 0:
                # Ensure the 'photos' column exists with a default sample value
                if 'photos' not in df.columns:
                    df['photos'] = 'sample_photo_value'  # Replace with your desired sample value

                df['price_level'] = ''
                df = df.loc[:, columns_to_keep_df]  # Filter columns to keep
                df_tourist = pd.concat([df_tourist, df], ignore_index=True)


            print(f"tourist shape{df_tourist.shape[0]}")#zero 3dd el rows ,1 3dd el col

########################## clustering

    X = df_tourist[['lat', 'lng']]
    kmeans = KMeans(n_clusters=4)
    kmeans.fit(X)
    cluster_labels = kmeans.labels_
    df_tourist['cluster'] = cluster_labels
    df_tourist = df_tourist.sort_values(by=['cluster', 'type'])
    cluster_counts = df_tourist['cluster'].value_counts()

##############################  random bl trtib

    for i in range(4):
        print(f"count_cluster_{i} ")
        print(cluster_counts.get(i, 0))

    data = pd.DataFrame(columns=df_tourist.columns)#nfs el col bta3t el df_tourist
    food_df = df_tourist[df_tourist['type'] == 'restaurant']#mta3m el df_tourist

    for i in range(4): # 3mlyt el randma
        clust = df_tourist[df_tourist['cluster'] == i]
        clust['cluster'] = i
        for i in range(100): #
            df2 = clust[clust['type'] == nameofcat[c]]
            if nameofcat[c] == "restaurant":
                if c < numOfChoosenCategouries - 1:
                    c = c + 1
                elif c == numOfChoosenCategouries - 1:
                    c = 0
            df2 = clust[clust['type'] == nameofcat[c]]
            if len(df2) == 0:
                if c < numOfChoosenCategouries - 1:
                    c = c + 1
                elif c == numOfChoosenCategouries - 1:
                    c = 0
                continue
            else:
                subset = df2.iloc[0:1]
                data = pd.concat([data, subset], axis=0)
                clust = clust.drop(subset.index)
                if c < numOfChoosenCategouries - 1:
                    c = c + 1
                elif c == numOfChoosenCategouries - 1:
                    c = 0
###################### main places

    tempDay = pd.DataFrame(columns=data.columns)
    ToDelete = pd.DataFrame(columns=data.columns)
    mainFinal = pd.DataFrame(columns=data.columns)

    for i in range(days):
        print(f"Day {i}")
        max = get_largest_cluster(data)
        tempDay = data[data['cluster'] == j]
        if len(tempDay) < activities:
            tempDay = data[data['cluster'] == max]#ro7 5od mn el kber
            tempDay = tempDay.iloc[0:activities]
        else:
            tempDay = tempDay.iloc[0:activities]
        ToDelete = tempDay

        if len(tempDay) > 0: #bngeb el mmt3m
            restLat = tempDay.iloc[0]['lat']
            restLng = tempDay.iloc[0]['lng']
            food_only = food_df[food_df['type'] == 'restaurant']
            sortedDistance = sort_locations_by_distance(food_only, restLat, restLng)
            # filterPrice = sortedDistance[sortedDistance['price_level'] == priceLevel]
            sortedDistance = sortedDistance.sort_values(by='distance')
            nearstRestaurant = sortedDistance.iloc[0:1]
            nearstRestaurant.drop(columns='distance', inplace=True)
            tempDay = pd.concat([tempDay, nearstRestaurant], ignore_index=True)
            food_df = food_df.drop(nearstRestaurant.index)
        else:
            print("no restaurant wiht these specifics here")

        if j < 3:
            j += 1
        elif j == 3:
            j = 0

        tempDay['Day'] = i + 1
        data = data.drop(ToDelete.index)
        mainFinal = pd.concat([mainFinal, tempDay], axis=0)
        print(f"shape cluster{j} = {tempDay.shape[0]}")#ytb3 3dd el activites el fe el day w da fe anhy cluster
    ## adding remaining food to remaining data
    data = pd.concat([data, food_df], axis=0) # remaining data 3lha remaining resturants

################################################### suggested places

    randomdata = pd.DataFrame()
    suggestedFinal = pd.DataFrame()
    no_of_remaining_places_in_clusters = []
    needed_suggested_per_cluster = []
    no_of_days_per_cluster = [] #4 index

    # Knowing the number of rows in each Cluster in remaining data
    for i in range(4):
        x = data[data['cluster'] == i]
        count = x.shape[0]
        no_of_remaining_places_in_clusters.append(count)
    # ba3rf ana wa5d mn kol cluster kam day
    for i in range(4):
        test = mainFinal[mainFinal['cluster'] == i]
        test.drop(test[test['type'] == 'restaurant'].index, inplace=True)
        count = test.shape[0]
        used = count / 3
        no_of_days_per_cluster.append(used)

    for i in range(4):
        if no_of_days_per_cluster[i] != 0:
            xd = no_of_remaining_places_in_clusters[i] // no_of_days_per_cluster[i]
            needed_suggested_per_cluster.append(xd)
        else:
            needed_suggested_per_cluster.append(0)

    cat = 0
    for i in range(4):#random 5od wa7da mn kol catigory
        suggestedC = data[data['cluster'] == i]
        for i in range(200):
            supersub = suggestedC[suggestedC['type'] == nameofcat[cat]]
            if cat < len(nameofcat) - 1:
                cat = cat + 1
            elif cat == len(nameofcat) - 1:
                cat = 0
            subset = supersub.iloc[0:1]
            suggestedC = suggestedC.drop(subset.index)
            randomdata = pd.concat([randomdata, subset], ignore_index=True)

    for i in range(days):
        x = mainFinal[mainFinal['Day'] == i + 1]
        clustnum = x.iloc[0]['cluster'] #raqm el cluster bta3 el day
        test = randomdata[randomdata['cluster'] == clustnum]
        print(test.shape[0])
        print(f"clustnum{clustnum}")
        if test.shape[0] != 0:
            print("continued")
            if needed_suggested_per_cluster[clustnum] > 0:
                if needed_suggested_per_cluster[clustnum] >= 6:
                    tempsug = test.iloc[0:6]
                    tempsug['Day'] = i + 1
                    suggestedFinal = pd.concat([suggestedFinal, tempsug], ignore_index=True)
                elif needed_suggested_per_cluster[clustnum] < 6:
                    tempsug = test.iloc[0:int(needed_suggested_per_cluster[clustnum])]
                    tempsug['Day'] = i + 1
                    suggestedFinal = pd.concat([suggestedFinal, tempsug], ignore_index=True)

##########################################

    mainFinal['priority'] = "main"
    suggestedFinal['priority'] = "suggested"
    all = pd.concat([mainFinal, suggestedFinal])
    all = all.sort_values(by=['Day', 'priority'])
    print(f"mainFinal shape{mainFinal.shape[0]}")
    print(f"suggestedFinal shape{suggestedFinal.shape[0]}")
    print(f"all shape{all.shape[0]}")
    print(f"no_of_remaining_places_in_clusters{no_of_remaining_places_in_clusters}")
    print(f"no_of_days_per_cluster{no_of_days_per_cluster}")
    print(f"needed_suggested_per_cluster{needed_suggested_per_cluster}")

    for day in all['Day'].unique():
        day_data = all[all['Day'] == day][
            ['name', 'priority', 'rating', 'user_ratings_total', 'geometry', 'weighted_score', 'type', 'types', 'lat',
             'lng', 'cluster', 'price_level', 'vicinity', 'photos', 'reference']]
       
        day_data = replace_nulls_with_unspecified(day_data)
        day_dict = day_data.to_dict(orient='records')
        itinerary[f'Day {int(day)}'] = day_dict

    return itinerary

# New API endpoint to integrate with Django
@app.route('/process_map_data', methods=['POST'])
@require_api_key
def process_map_data():
    try:
        # Get data from the request
        data = request.json
        place = data.get('place')
        url_params = data.get('url_params', {})
        user_id = data.get('user_id')
        
        if not place:
            return jsonify({
                'status': 'error',
                'message': 'Location is required'
            }), 400
            
        # Extract lat/lng from place if not provided directly
        # This is just a placeholder - in a real app you might need to geocode the place
        lat = url_params.get('lat', '0')  
        lng = url_params.get('lng', '0')
        
        # Add parameters needed for the original endpoint
        if 'day' not in url_params:
            url_params['day'] = '1'  # Default
        if 'price' not in url_params:
            url_params['price'] = '2'  # Default
        if 'act' not in url_params:
            url_params['act'] = '3'  # Default
        if 'your_array' not in url_params:
            url_params['your_array'] = ['1', '0', '0', '0', '0', '0', '0']  # Default
            
        # Construct the URL for the original endpoint
        base_url = request.url_root + 'your_endpoint'
        query_items = []
        
        # Add lat/lng
        query_items.append(f"lat={lat}")
        query_items.append(f"lng={lng}")
        
        # Add other parameters
        for key, value in url_params.items():
            if key not in ['lat', 'lng']:  # Skip lat/lng as we've already added them
                if isinstance(value, list):
                    for v in value:
                        query_items.append(f"{key}={v}")
                else:
                    query_items.append(f"{key}={value}")
        
        query_string = "&".join(query_items)
        internal_url = f"{base_url}?{query_string}"
        
        # Make internal request to your_endpoint
        with app.test_client() as client:
            response = client.get(internal_url)
            map_data = json.loads(response.data)
        
        if not map_data:
            return jsonify({
                'status': 'error',
                'message': 'No places found. Try another location or add more categories.'
            }), 404
            
        # Process photos and generate thumbnail
        thumbnail = process_photos(map_data)
        
        # Return processed data
        return jsonify({
            'status': 'success',
            'data': map_data,
            'thumbnail': thumbnail,
            'processed_date': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f"An error occurred during processing: {str(e)}"
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    # Fixed the syntax error here
    port = 5010
    debug_mode = True
    app.run(host='0.0.0.0', port=port, debug=debug_mode)