# Author: Álvaro Parafita (parafita.alvaro@gmail.com)

import gzip
import json
import re

with gzip.open('reviews.json.gz', 'rt') as f:
    reviews = json.load(f)

uid_regex = re.compile(r'(UID_[0-9A-Z]+)-SRC_.*')
rating_regex = re.compile(r'([1-5]) of 5 bubbles')

def extract(s, regex):
    if not s: return

    match = regex.fullmatch(s)

    if match:
        return match.groups()[0]
    else:
        return

processed_reviews = [
    {
        'review_id': review['review_id'],
        'uid': extract(review['uid'], uid_regex),
        'eatery_id': eatery_id,
        
        'review_title': review['review_title'],
        'review_text': review['review_text'],
        'review_rating': int(extract(review['review_rating'], rating_regex))
    }

    for eatery_id, d in reviews.items() if d
    for review in d.get('reviews') or []
]

with gzip.open('processed_reviews.json.gz', 'wt') as f:
    json.dump(processed_reviews, f, indent=2)