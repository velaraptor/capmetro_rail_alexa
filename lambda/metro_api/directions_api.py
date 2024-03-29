import googlemaps
from datetime import datetime
import pytz
import os
import logging
import time


def get_timezone(epoch):
    # get time in UTC
    tz = pytz.timezone('America/Chicago')
    dt = datetime.fromtimestamp(epoch).astimezone(tz)
    return dt.strftime('%I:%M %p')


def get_today(epoch):
    tz = pytz.timezone('America/Chicago')
    day = datetime.now(tz).day
    schedule = datetime.fromtimestamp(epoch).astimezone(tz).day
    if schedule > day:
        return 'tomorrow'
    elif schedule == day:
        return 'today'
    else:
        return None


def get_relevant_metro_times(response):
    arrival_time = None
    departure_time = None
    name = None
    for d in response:
        if 'legs' in d and type(d['legs']) == list:
            for leg in d['legs']:
                if 'steps' in leg and type(leg['steps']) == list:
                    for steps in leg['steps']:
                        if steps.get('travel_mode', '') == 'TRANSIT':
                            transit_details = steps.get('transit_details')
                            if transit_details:
                                name = transit_details['line']['name']
                                if name == 'Metro Rail Red Line':
                                    arrival_time = transit_details['arrival_time']['value']
                                    departure_time = transit_details['departure_time']['value']
                                    break
    arrival_timestamp = get_timezone(arrival_time) if arrival_time is not None else None
    departure_timestamp = get_timezone(departure_time) if departure_time is not None else None
    day_time = get_today(arrival_time) if arrival_time is not None else None
    return {'arrival_time_epoch': arrival_time,
            'departure_time_epoch': departure_time,
            'line': name,
            'arrival_time_local': arrival_timestamp,
            'departure_time_local': departure_timestamp,
            'day_indicator': day_time}


def get_walking(response):
    time_seconds = None
    for d in response:
        if 'legs' in d and type(d['legs']) == list:
            for leg in d['legs']:
                time_seconds = leg['duration']['value']
    return time_seconds


def log():
    logging.basicConfig()
    logger = logging.getLogger('metro-rail-info')
    logging.getLogger().setLevel(logging.INFO)
    return logger


def get_train(location="Austin Convention Center", departing_station='Crestview Station', home_address='801 Sugaree Ave'):
    start = time.time()
    log().info('Running metro rail info')
    key = os.getenv('API_KEY')
    gmap_client = googlemaps.Client(key=key)
    # Request directions via public transit
    now = datetime.now()
    log().info('Current Time: {}'.format(now))
    log().info('End Location: {}'.format(location))

    try:
        response = gmap_client.directions(departing_station, location, mode="transit", transit_mode='rail',
                                          departure_time=now)
        final_response = get_relevant_metro_times(response)
        final_response['departing_station'] = departing_station
        final_response['arrival_station'] = location

    except Exception as e:
        log().error('Could not run: {}'.format(e))
        final_response = None

    second_train = None
    if final_response and final_response.get('departure_time_epoch'):
        response = gmap_client.directions(departing_station, location, mode="transit", transit_mode='rail',
                                          departure_time=final_response['departure_time_epoch'] + 60)
        second_train = get_relevant_metro_times(response)
        second_train['departing_station'] = departing_station
        second_train['arrival_station'] = location

    # walking directions
    walking = gmap_client.directions(home_address, departing_station, mode="walking", departure_time=now)
    walking_seconds = get_walking(walking)

    rel = final_response.get('departure_time_epoch', datetime.now().timestamp())
    rel = rel if rel is not None else datetime.now().timestamp()
    log().info('rel: {}, walking_seconds {}'.format(rel, walking_seconds))
    time_to_get_there = {'relative': get_timezone(rel - walking_seconds - (60 * 5)),
                         'epoch': rel - walking_seconds - (60 * 5)}

    log().info('Alexa Response: {}'.format(final_response))
    end = time.time() - start
    log().info('Time to run {} seconds'.format(end))
    return final_response, second_train, time_to_get_there


if __name__ == "__main__":
    get_train()
