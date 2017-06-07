import re
import json
import math

import pandas as pd
np = pd.np

from recommender import Recommender
from utils import path, Menu, run_query, namespaces


tripadvisor_url_regex = re.compile(
    r'.+\.tripadvisor\..+-d([0-9]+)-.+'
)


def create_blank_profile():
    # Just create a new blank dict
    Menu.variables['user'] = {}


def get_current_profile():
    query = """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX ont: <http://schema.org/ontology/>

        SELECT ?name WHERE { 
            <%s> foaf:name ?name
        }
    """

    user = MAIN_MENU.variables['user']

    if not user:
        print('User profile is empty!')

    rows = []

    for uri, rating in user.items():
        # In case the URIs do not belong to the database (come from TripAdvisor)
        uri = restaurant_uri(uri)

        df = run_query(query, uri)
        if not len(df):
            print(
                'Error: %s doesn\'t appear in our dataset' % uri
            )
            continue

        name = df.iloc[0, 0]
        rows.append((name, rating))

    df = pd.DataFrame(rows, columns=['restaurant', 'rating'])

    if len(df):
        print(df)
    else:
        print('No ratings yet!')


def rate_restaurant():
    # Use it to check that the restaurant exists
    query = """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX ont: <http://schema.org/ontology/>

        SELECT ?name WHERE { 
            <%s> foaf:name ?name
        }
    """

    while True:
        print('Type the url of the restaurant (or q to quit):')
        uri = input('> ').lower().strip()

        if uri in ('q', 'quit'):
            break

        try:
            uri = restaurant_uri(uri)
        except ValueError as e:
            print(e)
            continue

        df = run_query(query, uri)
        if not len(df):
            print(
                'Error: the provided restaurant doesn\'t appear in our dataset'
            )
            continue

        print(df.iloc[0, 0])
        print()

        print('Type a rating for this restaurant (or q to quit):')
        rating = input('> ').lower().strip()

        if rating in ('q', 'quit'):
            break

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError('rating must be between 1 and 5')
        except ValueError as e:
            print('Error: %s' % e)
            continue

        MAIN_MENU.variables['user'][uri] = rating

        print('\nRating added to profile\n')


def load_user_profile(load=None):
    while True:
        if load is None:
            filename = input(
                'Type the filepath for your user profile (or q to quit): '
            )
            if filename.lower().strip() in ('q', 'quit'):
                return 
        else:
            filename = load

        try:
            with open(filename) as f:
                MAIN_MENU.variables['user'] = json.load(f)
                print('User profile loaded')
                
                # Reassign the urls, converting them to our database URI's
                for old_uri, rating in MAIN_MENU.variables['user'].items():
                    try:
                        uri = restaurant_uri(old_uri)
                    except ValueError as e:
                        print(e)
                        continue

                    del MAIN_MENU.variables['user'][old_uri]
                    MAIN_MENU.variables['user'][uri] = rating

                return

        except FileNotFoundError:
            if load is None:
                print('File not found: %s' % filename)
            else:
                # Just assign a void profile
                MAIN_MENU.variables['user'] = {}
                return

        except Exception as e:
            if load is None:
                print('Malformed user profile: %s' % e)
            else:
                raise


def save_user_profile():
    while True:
        filename = input(
            'Type the filepath for your user profile '
            '(press ENTER for the default filepath or q to quit): '
        )

        if filename.lower().strip() in ('q', 'quit'):
            return
        elif not filename:
            filename = 'user.json'
    
        with open(filename, 'w') as f:
            json.dump(MAIN_MENU.variables['user'], f, indent=2)
            print('User profile saved')
            return


def restaurant_uri(uri):
    base_uri = 'http://schema.org/resource/eatery_'

    if not uri.startswith('http://schema.org/resource/'):
        try:
            eatery = tripadvisor_url_regex.fullmatch(uri).groups()[0]

        except Exception as e:
            raise ValueError('Error: not a TripAdvisor Restaurant URL')

        uri = base_uri + eatery

    return uri


def restaurant_information():
    query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX ont: <http://schema.org/ontology/>

        SELECT ?predicate ?object WHERE { 
            <%s> ?predicate ?object
        }
    """

    while True:
        print('Type the url of the restaurant (or q to quit):')
        uri = input('> ').lower().strip()

        if uri in ('q', 'quit'):
            break

        try:
            uri = restaurant_uri(uri)
        except ValueError as e:
            print(e)
            continue

        df = run_query(query, uri)
        if not len(df):
            print(
                'Error: the provided restaurant doesn\'t appear in our dataset'
            )
            continue

        d = dict(zip(df.predicate, df.object))
        rest_cuisine = list(
            restaurant_cuisine[
                restaurant_cuisine.restaurant == uri
            ].cuisine.unique()
        )

        print('=' * 50)
        print(d['foaf:name'])
        print('-' * 50)

        print('Mean rating:', d['ont:rating'])

        print('Cuisine types: %s' % ', '.join(rest_cuisine))
        if 'ont:address' in d:
            print('Address:', d['ont:address'])
        if 'phone' in d:
            print('Phone:', d['ont:phone'])

        print('=' * 50)
        print()

cuisine_query = """
PREFIX ont: <http://schema.org/ontology/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
select ?cuisine (COUNT(*) AS ?count)
where { 
    ?r ont:restaurantCuisine ?cuisine
} GROUP BY ?cuisine ORDER BY DESC(?count) LIMIT 25
"""

cuisine_result = run_query(cuisine_query)

def menu_cuisine(cuisine):
    return lambda: cuisine


metro_query = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://schema.org/ontology/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT ?station_idx ?line ?station ?latitude ?longitude WHERE { 
    ?station_idx rdf:type ont:Transport .
    ?station_idx ont:transportType 'Metro' .
    ?station_idx ont:transportLine ?line .
    ?station_idx foaf:name ?station .
    ?station_idx ont:latitude ?latitude .
    ?station_idx ont:longitude ?longitude .    
}
"""

metro_result = run_query(metro_query)
metro_result.line = metro_result.line.str.strip()
metro_result.station = metro_result.station.apply(
    lambda x: x.strip().title()
)

metro_line_regex = re.compile(r'L([0-9]+).*')
metro_lines = sorted(
    metro_result.line.unique(),
    key=lambda x: int(metro_line_regex.fullmatch(x).groups()[0])
)

metro_stations = {
    line: sorted(
        station

        for station in metro_result[
            metro_result.line == line
        ].station.unique()
    )

    for line in metro_result.line.unique()
}

metro_coordinates = {
    (line, station): dict(
        metro_result[
            (metro_result.line == line) & (metro_result.station == station)
        ][['latitude', 'longitude']].astype(float).mean()
    )

    for line, stations in metro_stations.items()
    for station in stations
}

def menu_station(line, station):
    return lambda: (line, station)

restaurant_coordinates_query = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://schema.org/ontology/>

SELECT ?restaurant ?latitude ?longitude WHERE { 
    ?restaurant rdf:type ont:Restaurant .
    ?restaurant ont:latitude ?latitude .
    ?restaurant ont:longitude ?longitude 
}
"""

restaurant_coordinates = run_query(
    restaurant_coordinates_query, 
    use_prefixes=False
)

restaurant_cuisine_query = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://schema.org/ontology/>

select ?restaurant ?cuisine where { 
    ?restaurant rdf:type ont:Restaurant .
    ?restaurant ont:restaurantCuisine ?cuisine
}
"""

restaurant_cuisine = run_query(
    restaurant_cuisine_query,
    use_prefixes=False
)


def recommender_menu():
    restaurant_info_query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX ont: <http://schema.org/ontology/>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>

        select * where { 
            BIND(<%s> AS ?r) .
            ?r rdf:type ont:Restaurant .
            ?r foaf:name ?name .
            ?r ont:address ?address .
            ?r ont:rating ?rating .
            OPTIONAL { ?r ont:phone ?phone }
        }
    """

    cuisine = CUISINE_MENU.run()

    if cuisine is None:
        return 

    metro_result = METRO_LINES_MENU.run()
    if metro_result is None:
        return
    else:
        line, station = metro_result

    print(
        'I am in %s (line %s) '
        'and I look for %s restaurants.' % (station, line, cuisine)
    )

    d = metro_coordinates[(line, station)]
    lat, lon = d['latitude'], d['longitude']
    del d

    while True:
        print(
            'From %s, how far away (in km) do you want to go? '
            '(just press ENTER for no filter)' % station
        )

        dist = input('> ').lower().strip()
        if dist in ('q', 'quit'):
            return

        else:
            try:
                if dist:
                    dist = float(dist)
                else:
                    dist = None

                break

            except ValueError as e:
                print('Error: you must input a number')
                continue

    user = MAIN_MENU.variables['user']
    predictions = recommender.predict(user)
    restaurants = recommender.restaurants

    df = predictions.reset_index(drop=False)
    df.columns = ['restaurant', 'rating']

    # Those ratings that could not be predicted will have NA. Let's drop them
    df = df.dropna(how='any')

    # Filter by cuisine
    df = df[
        df.restaurant.isin(
            set(
                restaurant_cuisine[
                    restaurant_cuisine.cuisine == cuisine
                ].restaurant.unique()
            )
        )
    ]

    # Filter by distance
    # First compute distances...
    df = df.merge(restaurant_coordinates, 'left')
    df['km'] = df.apply(
        lambda row: math.sqrt(
            (row['latitude'] - lat) ** 2 + (row['longitude'] - lon) ** 2
        ),
        axis=1
    ) * .13 / .001632 

    df = df.drop(['latitude', 'longitude'], axis=1)

    # ... sort by rating and distance ...
    df = df.sort_values(['rating', 'km'], ascending=[False, True])

    # ... then filter
    if dist is None:
        filtered = pd.DataFrame(columns=df.columns)
    else:
        filtered = df[df.km <= dist]

    if not len(df):
        print(
            'No restaurants matched your criteria '
            'or could be recommended to you. '
            'Try another query.'
        )

        return

    elif dist is not None and not len(filtered):
        print(
            'No restaurants appear near the station you specified, '
            'so we\'ll recommend other restaurants that are further away.'
        )

    elif len(filtered) < 3:
        print(
            'There weren\'t many options close enough, '
            'so we\'ll display other restaurants as well.'
        )

    results = pd.concat(
        [
            filtered,
            df[~df.restaurant.isin(set(filtered.restaurant.unique()))]
        ]
    )

    # Ratings were floats to properly order them. Now convert them to ints
    results.rating = results.rating.round().astype(int)

    # Display results
    for i in range(0, len(results), 3):
        if dist is not None and i == len(filtered):
            print('-' * 50)
            print(
                'Starting from here, these restaurants '
                'are outside your radius.'
            )
            print('-' * 50)

        rest = results.iloc[i]
        idx = rest['restaurant']

        rest_cuisine = list(
            restaurant_cuisine[
                restaurant_cuisine.restaurant == idx
            ].cuisine.unique()
        )

        rest_info = run_query(
            restaurant_info_query % idx, 
            use_prefixes=False
        )

        rest_info = {
            k: v

            for _, row in rest_info.iterrows()
            for k, v in row.items()
            if v is not None and not (type(v) == float and np.isnan(v))
        }

        print('=' * 50)
        print(rest_info['name'])
        print('-' * 50)

        print('At %.2fkm' % rest['km'])
        print(
            'Expected rating: %d / Mean rating: %d' % (
                rest['rating'], rest_info['rating']
            )
        )

        print('Cuisine types: %s' % ', '.join(rest_cuisine))
        if 'address' in rest_info:
            print('Address:', rest_info['address'])
        if 'phone' in rest_info:
            print('Phone:', rest_info['phone'])

        print('=' * 50)
        print()

        if i + 1 < len(results):
            print('More results? [y]/n')
            if input('> ').lower().strip() in ('n', 'no', 'q', 'quit'):
                break


USER_PROFILE = Menu(
    'User profile Menu',
    [
        [
            'Create blank profile', None,
            create_blank_profile
        ],
        [
            'Show current profile', None,
            get_current_profile
        ],
        [
            'Rate a restaurant', None,
            rate_restaurant
        ],
        [
            'Load user profile', None,
            load_user_profile
        ],
        [
            'Save current user profile', None,
            save_user_profile
        ]
    ]
)


CUISINE_MENU = Menu(
    'Cuisine type selector',
    [
        [cuisine, None, menu_cuisine(cuisine)]
        for cuisine in cuisine_result.cuisine
    ]
)


METRO_STATION_MENUS = {
    line: Menu(
        'Metro station selector (line %s)' % line,
        [
            [station, None, menu_station(line, station)]
            for station in metro_stations[line]
        ]
    )
    for line in metro_lines
}

METRO_LINES_MENU = Menu(
    'Metro line selector',
    [
        [line, None, METRO_STATION_MENUS[line]]
        for line in metro_lines
    ]
)


MAIN_MENU = Menu(
    'Main Menu',
    [
        [
            'User profile', 
            'Define the current user profile',
            USER_PROFILE
        ],
        [
            'Restaurant information',
            'Retrieve information about a specific restaurant',
            restaurant_information
        ],
        [
            'Recommender',
            'Obtain restaurant recommendations',
            recommender_menu
        ]
    ]
)

# Load default user profile, if it exists
load_user_profile(load='user.json')

# This line makes the recommender use the already downloaded information
# recommender = Recommender(path('data/ratings-matrix.csv.gz'))
# This line makes the recommender download all the needed information
print('Loading Recommender data...')
recommender = Recommender()

if __name__ == '__main__':
    MAIN_MENU.run()