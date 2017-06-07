# Author: Álvaro Parafita (parafita.alvaro@gmail.com)

from collections import defaultdict 
import json
import re
import pandas as pd

gmaps_regex = re.compile(
    r'^.*?center=([0-9.]+),([0-9.]+).*?$'
)

avg_price_regex = re.compile(
    r'^.*?(?P<coin1>.)(?P<s>[0-9.]+)(?: - (?P<coin2>.)(?P<e>[0-9.]+))?.*?$'
)

detailed_ratings_regex = re.compile(
    r'^([0-9.]+) of ([0-9.]+).*$'
)

open_hours_weekday_regex = re.compile(
    r'^.*(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday).*$'
)

open_hours_regex = re.compile(
    '^.*?([0-9]{,2}:[0-9]{,2} (?:am|pm))'
    ' - '
    '([0-9]{,2}:[0-9]{,2} (?:am|pm)).*$'
)

review_filter_regex = re.compile(
    r'(?P<k>.+?)(?: \((?P<v>[0-9,]+)\))?'
)

with open('restaurants_data.json') as f:
    j = json.loads(f.read())

rows = []
for k, d in j.items():
    row = { 'id': k }

    # Make sure that from now on we don't get KeyErrors
    d = defaultdict(lambda: None, d) 
    
    # Copy columns that ought to go to d directly
    for k in ('href', 'name', 'phone', 'rating'):
        row[k] = d[k]

    # Process special columns
    if 'gmaps_uri' in d:
        row['gmaps_uri'] = d['gmaps_uri']

        match = gmaps_regex.fullmatch(d['gmaps_uri'])
        if match:
            lat, lon = list(map(float, match.groups()))

            row['latitude'] = lat
            row['longitude'] = lon

    for s in d.get('additional_info', []):
        i = s.index(':')
        k, v  = s[:i], s[i + 1:].strip()
        k = k.replace(' ', '_').lower()

        row[k] = v

    # Split location in several variables
    if 'location' in row:
        row['location'] = list(
            map(lambda x: x.strip(), row['location'].split('>'))
        )

    for k, v in d.get('detailed_ratings', {}).items():
        v = v[0] # always a list of 1 element

        if v is not None:
            x1, x2 = map(float, detailed_ratings_regex.fullmatch(v).groups())

            row['rating_%s' % k.lower()] = x1 / x2 * 5

    for k, v in d.get('extra', {}).items():
        row[k.replace(' ', '_').lower()] = v

    if 'average_prices' in row:
        match = avg_price_regex.fullmatch(row['average_prices'])

        if match:
            s = match.group('s')
            e = match.group('e')

            if s is not None: s = float(s)
            if e is not None: e = float(e)

            row['average_prices_from'] = s
            row['average_prices_to'] = e

    for k in (
        'meals', 'good_for', 
        'cuisine', 'restaurant_features'
    ):
        if k in row:
            row[k] = row[k].split(', ')

    if 'open_hours' in row:

        h = {}
        for line in row['open_hours'].split('\n'):
            weekday_match = open_hours_weekday_regex.fullmatch(line)
            
            if weekday_match:
                w = weekday_match.groups()[0]
                h[w] = []
            else:
                match = open_hours_regex.fullmatch(line)

                if match:
                    h[w].append('-'.join(match.groups()))

        row['open_hours'] = h

    for k, l in filter(
        lambda pair: pair[0] != 'reviews', 
        d.get('reviews', {}).items()
    ):
        for s in l:
            match = review_filter_regex.fullmatch(s)
            k2 = (k + '_' +  match.group('k')).replace(' ', '_').lower()

            v = match.group('v')
            if v is not None:
                v = int(v.replace(',', ''))

            row['review_filter_' + k2] = v

    for k, v in d.get('reviews', {}).get('reviews', {}).items():
        d['review_%s' % k.replace(' ', '_').lower()] = v

    for k, v in d.get('street_address', {}).items():
        d['address_' + k] = v

    for col in ['phone_number'] + [
        k for k in row if k.startswith('review_filter_')
    ]:
        if col in row:
            del row[col]

    rows.append(row)

with open('processed_restaurants_data.json', 'w') as f:
    f.write(json.dumps(rows, indent=2))