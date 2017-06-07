# -*- coding: utf-8 -*-
# Author: Álvaro Parafita (parafita.alvaro@gmail.com)

import time
import json
import sys
import gzip

from random import random
from datetime import datetime

from selenium.webdriver import Firefox
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.common.exceptions import \
    WebDriverException, NoSuchElementException, \
    TimeoutException, ElementNotVisibleException

from pyvirtualdisplay import Display


def read_json(filename, default=None):
    try:
        with open(filename) as f:
            return json.load(f)
    except IOError:
        if default is None:
            raise
        else:
            return default


def download_data(restaurant_id, href):
    for _ in range(3):
        try:
            ff.get(href)
            break
        except WebDriverException:
            pass
    else:
        return {
            'eatery_id': restaurant_id,
            'nreviews': None,
            'reviews': None
        }


    # Click on reviews (this avoids a "Element is not clickable at point" error)
    for _ in range(3): # 3 trials to avoid the Not Clickable error
        exc = None
        try:
            ff.find_element_by_xpath(
                '//li[@id="TABS_REVIEWS"]/span[@class="tabs_pers_titles"]'
            ).click()

            time.sleep(1) # let it load

            # Then select all possible reviews (in any language)
            ff.find_element_by_xpath(
                '//div[contains(@class, "language")]'
            ).click()

            time.sleep(1) # let it load
            break
        except WebDriverException as e:
            exc = e
            time.sleep(1) # the main method will capture this and re-run
            continue
    else:
        raise exc # reraise if we couldn't break the loop        

    try:
        nreviews = int(
            ff.find_element_by_xpath('//a[@property="reviewCount"]').get_attribute('content')
        )
    except (NoSuchElementException | TypeError):
        nreviews = None
        
    reviews_list = []
    
    review_pages = 1
    while True: # while there are more reviews to process
        for review in ff.find_elements_by_xpath(
            '//div[starts-with(@id, "review_")]'
        ):
            review_id = review.get_attribute('id')
            
            # Get the basic_review for starters
            # If we need the full review, we'll click it just next
            review = review.find_element_by_xpath(
                './div[contains(@class, "basic_review")]'
            )
            
            # User data
            member = review.find_element_by_xpath(
                './/div[@class="member_info"]'
            )

            try:
                uid = member.find_element_by_xpath(
                    './/div[contains(@class, "memberOverlayLink")]'
                ).get_attribute('id')
            except NoSuchElementException:
                # A "hidden" user
                uid = None

            if uid:
                try:
                    user_location = member.find_element_by_xpath(
                        './/div[@class="location"]'
                    ).text
                except NoSuchElementException:
                    user_location = None

                user_badges = {
                    badge.get_attribute('class'): badge.text
                    for badge in review.find_elements_by_xpath(
                        './/div[contains(@class, "memberBadging")]'
                        '//div[contains(@class, "badge")]'
                    )
                }
            else:
                user_location = None
                user_badges = None

            # Review data
            review = review.find_element_by_xpath(
                './/div[@class="col2of2"]'
            )

            review_title = review.find_element_by_xpath(
                './/span[@class="noQuotes"]'
            ).text

            review_rating = review.find_element_by_xpath(
                './/div[contains(@class, "rating")]/span[contains(@class, "rate")]/img'
            ).get_attribute('alt')

            # Look for incomplete review (More link appears)
            more = (
                review.find_elements_by_xpath(
                    './/div[@class="entry"]//span[contains(@class, "moreLink")]'
                ) or [None]
            )[0]

            if more:
                # Try to click more
                # If it is not visible in the screen, this click will just jump to it
                # We need to click again then
                # Continue clicking ad infinitum until it is not visible.
                # Then, it will indeed be clicked
                for _ in range(3): # 3 attempts
                    try: more.click(); time.sleep(.25) # this changes display:none for full_review
                    except ElementNotVisibleException: break # finally clicked
                    except WebDriverException: time.sleep(1) # wait for a second
                else:
                     more = None
                        
                if more:
                    # Now we can find the full_review
                    review = ff.find_element_by_xpath(
                        (
                            '//div[@id="%s"]/div[contains(@class, "full_review")]'
                            '//div[contains(@class, "col2of2")]'
                        ) % review_id
                    )
               
            # Now extract review text and subratings    
            review_text = review.find_element_by_xpath(
                './/div[@class="entry"]'
            ).text

            review_answers = {
                answer.find_element_by_xpath(
                    './div[@class="recommend-description"]'
                ).text: answer.find_element_by_xpath(
                    './span/img'
                ).get_attribute('alt')

                for answer in review.find_elements_by_xpath(
                    './/div[@class="entry"]//li[@class="recommend-answer"]'
                )
            }

            # Summarize everything in a dict
            review = {
                'review_id': review_id,
                'uid': uid,
                'user_location': user_location,
                'user_badges': user_badges,
                'review_title': review_title,
                'review_rating': review_rating,
                'review_text': review_text,
                'review_answers': review_answers
            }

            reviews_list.append(review)
          
        # Look for more reviews or end here
        try:
            next_button = ff.find_element_by_xpath(
                '//div[contains(@class, "pagination")]/a[contains(@class, "next")]'
            )
        except NoSuchElementException:
            break

        if next_button.is_enabled():
            next_button.click()
            
            review_pages += 1
            print ' '.join(map(str, ['\t', datetime.now(), review_pages]))

            time.sleep(3) # let the page reload
        else:
            break # we're done
    
    return {
        'eatery_id': restaurant_id,
        'nreviews': nreviews,
        'reviews': reviews_list
    }


def save(reviews, skip_restaurants, reviews_filename, skip_filename):
    now = datetime.now()
    
    skip_restaurants.update(set(reviews.keys()))

    while True:
        try:
            with gzip.open(reviews_filename % now, 'wb') as f:
                f.write(json.dumps(reviews, indent=2))

            with open(skip_filename, 'w') as f:
                f.write(json.dumps(list(skip_restaurants), indent=2))

            break
        except KeyboardInterrupt:
            continue

    for k in list(reviews.keys()):
        del reviews[k] # remove everything from reviews


if __name__ == '__main__':
    config = sys.argv[1] # compulsory

    with open(config) as f:
        config = json.load(f)

    output_filename = 'reviews_%s.json.gz'

    restaurants = read_json('restaurants.json')
    restaurants_data = read_json('restaurants_data.json', {})
    reviews = {} # initialize as a void dictionary

    skip_filename = 'skip_restaurants.json'
    skip_restaurants = set(read_json(skip_filename, []))
    # If there's at least a restaurant in skip_restaurants, 
    # only those restaurants will be downloaded

    total = len(restaurants_data)

    with Display(visible=0, size=(1024, 768)) as display:
        firefox_binary = FirefoxBinary(config['firefox_binary'])
        
        def firefox():
            browser = Firefox(
                executable_path=config['executable_path'],
                firefox_binary=firefox_binary
            )

            browser.set_page_load_timeout(30)
            return browser
       
        try:
            ff = firefox()
    
            for n, (k, d) in enumerate(restaurants_data.items()):
                if k in skip_restaurants: continue # already processed

                if d['rating'] is None: 
                    reviews[k] = None
                    continue # no ratings to download

                if len(reviews) >= 5:
                    print 'Saving...'
                    save(
                        reviews, skip_restaurants, 
                        output_filename, skip_filename
                    )

                    # Restart Firefox to reset memory
                    try:
                        ff.quit()
                    except WebDriverException:
                        pass # already closed
                    
                    ff = firefox()
                    
                for _ in range(3): # 3 trials
                    try:
                        n = len(reviews) + len(skip_restaurants) + 1
                        print ' '.join(
                            map(
                                str, 
                                [datetime.now(), k, '%.4d/%.4d' % (n, total)]
                            )
                        )
                        reviews[k] = download_data(k, d['href'])
                        
                        break # no need for more trials
                    except WebDriverException as e:
                        print ' '.join(map(str, [datetime.now(), e]))
                        
                        try:
                            ff.quit()
                        except WebDriverException:
                            pass # already closed
                        
                        ff = firefox()
                        continue # try again
                else:
                    # Ignore this page and go on
                    reviews[k] = {
                        'eatery_id': k,
                        'nreviews': None,
                        'reviews': None
                    }

        except:
            # Save final results
            print 'Saving...'
            save(reviews, skip_restaurants, output_filename, skip_filename)
            
            raise

    # Save final results
    print 'Saving...'
    save(reviews, skip_restaurants, output_filename, skip_filename)
    
    # Try quitting the browser
    try:
        ff.quit()
    except WebDriverException:
        pass # already closed
