# -*- coding: utf-8 -*-
#
# Author: Michael Bernico <michael.bernico.qepz@statefarm.com>
#         Taylor Smith <taylor.smith.fp7y@statefarm.com>
# 
# Scrapes Bloomington-Normal data from realtor.com

import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re

PROTOCOL = 'http'
ROOT_URI = 'www.realtor.com'
SEARCH_PAGE = 'realestateandhomes-search'
CITIES = ['Bloomington_IL', 'Normal_IL']


def create_session(comp_specs='Macintosh; Intel Mac OS X 10_9_2', mozilla_v='5.0', 
                   web_kit_v='537.36', chrome_v='34.0.1847.131'):
    """Build a requests ``Session`` object with headers.
    
    Parameters
    ----------
    comp_specs : str, optional (default="Macintosh; Intel Mac OS X 10_9_2")
        The computer specifics of the calling machine. Optional.

    mozilla_v : str, optional (default="5.0")
        The version of Mozilla. Optional.
    
    web_kit_v : str, optional (default="537.36")
        The version of the Apple web-kit (doubles as the Safari version). Optional.
    
    chrome_v : str, optional (default="34.0.1847.131")
        The version of Chrome. Optional.
    """
    s = requests.Session()
    s.headers['User-Agent'] = 'Mozilla/%s (%s) AppleWebKit/%s (KHTML, like Gecko) Chrome/%s Safari/%s' \
                              % (mozilla_v, comp_specs, web_kit_v, chrome_v, web_kit_v)
    return s


def get_last_page_number(s, city, n_per_page=50):
    """Get the last page number for a city (or the number of pages
    that are available for this city).
    
    Parameters
    ----------
    s : ``requests.Session``
        The session object.
    
    city : str
        The name of the city.
    
    n_per_page : int, optional (default=50)
        The number per page to display. Optional.
    """
    r = s.get('%s://%s/%s/%s?pgsz=%i' % (PROTOCOL, ROOT_URI, SEARCH_PAGE, city, n_per_page))
    soup = BeautifulSoup(r.text, 'lxml')
    return int(soup.find_all("span", class_="page")[-1].text.strip())


def get_homes_on_page(s, page_number, city, n_per_page=50):
    """Get all of the homes on a given page number.

    Parameters
    ----------
    s : ``requests.Session``
        The session object.
    
    page_number : int
        The page number to search.
    
    city : str
        The name of the city.

    n_per_page : int, optional (default=50)
        The number per page to display. Optional.
    """
    url = '%s://%s/%s/%s/pg-%i?pgsz=%i' % (PROTOCOL, ROOT_URI, SEARCH_PAGE, city, page_number, n_per_page)
    soup = BeautifulSoup(s.get(url).text, 'lxml')
    houses = soup.find_all("div", class_="srp-item")

    house_list = []
    details = lambda attr: '' if attr is None else attr.text
    for i, house in enumerate(houses):
        house_listing = {
            'price':         house.attrs.get('data-price', ''),
            'agent':         house.attrs.get('data-advertiserid-agent', ''),
            'broker':        house.attrs.get('data-advertiserid-broker', ''),
            'baths_full':    house.attrs.get('data-baths_full', ''),
            'baths_half':    house.attrs.get('data-baths_half', ''),
            'address':       details(house.find("span", attrs={'itemprop': 'streetAddress'})),
            'city':          details(house.find("span", attrs={'itemprop': 'addressLocality'})),
            'zip_code':      details(house.find("span", attrs={'itemprop': 'postalCode'})),
            'photos':        details(house.find("span", attrs={'data-label': 'property-photo-count'})),
            'property_type': details(house.find("span", attrs={'class': 'srp-property-type'})),
            'bedrooms':      details(house.find("span", attrs={'class': 'data-value meta-beds'})),
            'sqft':          details(house.find("li", attrs={'data-label': 'property-meta-sqft'})),
            'garage':        details(house.find("li", attrs={'data-label': 'property-meta-garage'})),
            'lot_size':      details(house.find("li", attrs={'data-label': 'property-meta-lotsize'}))
        }

        house_list.append(house_listing)
        
        if any(not v for v in house_listing.values()):
            print("[W]: some fields could not be retrieved (%i)" % (i + 1))
        else:
            print("[I]: successfully scraped house (%i)" % (i + 1))

    return house_list


def standardize_lot_size(x):
    try:
        return float(x)
    except:
        if x:
            if 'acre' in x:
                x = re.sub('[A-Za-z,]', '', x)
                x = x.strip()
                return float(x) * 43560
            else:
                x = re.sub('[A-Za-z,]', '', x)
                x = x.strip()
                return x
        else:
            return -1  # lot size isn't defined


def standardize_sqft(x):
    try:
        return float(x)
    except:
        if x:
            x = re.sub('[A-Za-z,]', '', x)
            x = x.strip()
            return x
        else:
            return -1


def main():
    # create the session first (use default args)
    s = create_session()
    
    houses = []
    for city in CITIES:
        # find the last page for this city
        last_page_number = get_last_page_number(s, city)
        
        # for each page, scrape all the homes on the page
        for page in range(1, last_page_number + 1):
            houses.extend(get_homes_on_page(s, page_number=page, city=city))
    
    # standardize and save the house data
    df = pd.DataFrame.from_records(houses)
    df = pd.read_csv("../data/house_data.csv", na_values='NA')
    df.garage = df.garage.str.replace('[A-Za-z]', "").fillna(-1).astype(int)
    df.lot_size = df.lot_size.fillna(-1).map(standardize_lot_size)
    df.baths_half = df.baths_half.fillna(0).astype(int)
    df.baths_full = df.baths_full.fillna(0).astype(int)
    df.bedrooms = df.bedrooms.fillna(0).astype(int)
    df = df.fillna(-1)
    df.agent = df.agent.astype(int)
    df.broker = df.broker.astype(int)
    df.sqft = df.sqft.map(standardize_sqft)

    df.to_csv(os.path.join("..", "data", "house_data.csv"), index=False)

if __name__ == "__main__":
    main()

