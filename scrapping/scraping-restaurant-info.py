# Author: Álvaro Parafita (parafita.alvaro@gmail.com)

import time
import json

from random import random
from datetime import datetime

from pyvirtualdisplay import Display
from selenium.webdriver import Firefox
from selenium.common.exceptions import NoSuchElementException


def download_data(href):
    ff.get(href) # load the webpage
    
    data = { 'href': href }
    
    data['name'] = ff.find_element_by_xpath(
        '//h1[@property="name"]'
    ).text
    
    # Restaurant rating
    data['rating'] = float(
        ff.find_element_by_xpath(
            '//div[contains(@class, "rating")]/span/img'
        ).get_attribute('content')
    )
    
    # Street address
    address = {}
    for attr, name in (
        ('class', 'street-address'), 
        ('property', 'postalCode'),
        ('property', 'addressLocality'),
        ('property', 'addressCountry')
    ):
        try:
            address[name] = ff.find_element_by_xpath(
                '//span[@{attr}="{name}"]'.format(
                    attr=attr, name=name
                )
            ).text
        except NoSuchElementException:
            address[name] = None
        
    data['street_address'] = address
    
    # Location
    data['gmaps_uri'] = ff.find_element_by_xpath(
        '//img[contains(@src, "maps.google.com")]'
    ).get_attribute('src')
    
    # Reviews data
    
    # In order to extract data from ALL reviews,
    # we need to click on the "All languages" radio button first.
    ff.find_element_by_xpath(
        '//div[contains(@class, "language")]//input[@value="ALL"]'
    ).click()
    
    time.sleep(3) # it's necessary to let it load again
    
    # Then, extract reviews data
    data['reviews'] = {
        'reviews': {
            rating.find_element_by_xpath(
                r'.//div[@class="row_label"]'
            ).text: int(
                rating.find_element_by_xpath(r'.//span[2]').text
            )

            for rating in ff.find_elements_by_xpath(
                r'//div[@id="ratingFilter"]/ul//li'
            )
        }
    }
    
    data['reviews'].update(
        {
            category.find_element_by_xpath(
                r'./div[@class="colTitle"]'
            ).text: [
                item.text.strip()
                for item in category\
                    .find_elements_by_xpath(r'./ul/li/label')
            ]

            for cat, category in (
                (
                    cat, 
                    ff.find_element_by_xpath(
                        r'//div[contains(@class, "%s")]' % cat
                    )
                )

                for cat in ('segment', 'season', 'language')
            )
        }
    )
    
    # Phone number
    try:
        data['phone'] = ff.find_element_by_xpath(
            '//div[contains(@class, "phoneNumber")]'
        ).text
    except NoSuchElementException:
        data['phone'] = None
        
    # Detailed ratings (with subcategories)
    data['detailed_ratings'] = {
        row.find_element_by_xpath(
            './div[contains(@class, "label")]/span'
        ).text: (
            list(
                map(
                    lambda x: x.get_attribute('alt'), 
                    row.find_elements_by_xpath(
                        './/span[contains(@class, "rate")]/img'
                    )
                )
            ) or [None]
        )


        for row in ff.find_elements_by_xpath(
            '//div[contains(@class, "ratingRow")]'
        )
    }
    
    # Extra details
    data['extra'] = {}
    
    for row in ff.find_elements_by_xpath(
        '//div[@class="table_section"]//div[@class="row"]'
    ):
        try:
            data['extra'][
                row.find_element_by_xpath(
                    './div[contains(@class, "title")]'
                ).text
            ] = row.find_element_by_xpath(
                './div[contains(@class, "content")]'
            ).text
        except NoSuchElementException:
            continue

    data['additional_info'] = list(
        map(
            lambda x: x.text, 
            ff.find_elements_by_xpath(
                '//div[contains(@class, "additional_info")]'
                '//ul[contains(@class, "detailsContent")]'
                '/li/div'
            )
        )
    )
    
    return data


if __name__ == '__main__':
    display = Display(visible=0, size=(1024, 768))
    display.start()

    with open('restaurants.json') as f:
        restaurants = json.loads(f.read())

    try:
        with open('restaurants_data.json') as f:
            restaurants_data = json.loads(f.read())
    except FileNotFoundError:
        restaurants_data = {}

    ff = Firefox()
    ff.set_page_load_timeout(15)

    try:
        for k, d in restaurants.items():
            if k in restaurants_data: continue

            print(datetime.now(), d['name'], sep=' - ')

            restaurants_data[k] = download_data(d['href'])
            time.sleep(random() * 2 + 1) # delay between 1 and 3 seconds

    except KeyboardInterrupt:
        print(datetime.now(), 'KeyboardInterrupt', sep=' - ')
        raise

    except Exception as e:
        print(datetime.now(), repr(e), sep=' - ')
        raise

    finally:
        with open('restaurants_data.json', 'w') as f:
            f.write(json.dumps(restaurants_data, indent=2))

        ff.quit()
        display.stop()