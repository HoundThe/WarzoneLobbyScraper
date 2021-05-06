import requests
import json
import time
import datetime
import os
import urllib.parse
import gzip
import pickle
import pandas as pd


class WarzoneScraper:
    def __init__(self, delay=1.0, cache_filename='matches.pkl.gz'):
        self.cache_filename = cache_filename
        self.headers = {
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="90", "Google Chrome";v="90"',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://cod.tracker.gg/',
            'Accept-Language': 'en',
            'sec-ch-ua-mobile': '?0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\
             (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
        }
        # delay between requests to dodge ratelimit
        self.delay = delay
        self.cache = {}

        # modes that are accounted for in the statistics
        self.accepted_modes = [
            "br_brquads",
            "br_brtrios",
            "br_brduos",
        ]
        # Load existing cache from drive
        if os.path.exists(self.cache_filename):
            with gzip.open(self.cache_filename, 'rb') as file:
                self.cache = pickle.load(file)

    def __get_cached_match(self, match_id: str) -> tuple:
        """Returns cached match KDR or None"""
        if match_id in self.cache:
            return self.cache[match_id]

        return None

    def __cache_match(self, match_id: str, match_data: tuple):
        """Caches match KDR to in-memory cache"""
        self.cache[match_id] = match_data

    def save_cache(self):
        """Saves cache to disk"""
        with gzip.open(self.cache_filename, 'wb') as file:
            pickle.dump(self.cache, file)

    def __is_inside_time_interval(self, timestamp, start_hour, end_hour):
        time = datetime.datetime.strptime(
            timestamp, "%Y-%m-%dT%H:%M:%S%z").timetuple()
        hour = time.tm_hour
        if start_hour == end_hour:
            return True
        if end_hour < start_hour:  # overlaps midnight
            if start_hour <= hour or hour <= end_hour:
                return True
        elif start_hour <= hour and hour <= end_hour:
            return True

        return False

    def __delay_request(self):
        time.sleep(self.delay)

    def get_last_n_matches(self, battlenet, count=20, start_hour=0, end_hour=0, next=None):
        """Fetch ids of `count` last matches of `username`"""
        self.__delay_request()

        params = (('type', 'wz'), ('next', str(next))
                  ) if next else (('type', 'wz'),)

        username_parsed = urllib.parse.quote(battlenet)
        p1, p2 = battlenet.split('#')
        # more numbers -> activision username
        url = 'https://api.tracker.gg/api/v2/warzone/standard/matches/atvi/'
        if len(p2) <= 5:
            url = 'https://api.tracker.gg/api/v2/warzone/standard/matches/battlenet/'

        resp = requests.get(url + username_parsed,
                            headers=self.headers, params=params)

        if resp.status_code == 429:
            print("RateLimited? Wwaiting 10 minutes.", resp.text)
            time.sleep(10 * 60)
            # Try again recursively
            return self.get_last_n_matches(battlenet, count, start_hour, end_hour, next)
        if resp.status_code == 500:
            print('Error with API, saving cache: ', resp.text)
            exit(1)
        if resp.status_code == 503 or resp.status_code == 504 or resp.status_code == 400:
            print('Service not available, retrying:')
            while resp.status_code == 503 or resp.status_code == 504 or resp.status_code == 400:
                time.sleep(30)
                resp = requests.get(url + username_parsed, headers=self.headers, params=params)

        match_json = json.loads(resp.text)
        match_ids = []

        for match in match_json['data']['matches']:
            timestamp = match['metadata']['timestamp']
            mode_id = match['attributes']['modeId']
            match_id = match['attributes']['id']
            is_accepted = mode_id in self.accepted_modes and self.__is_inside_time_interval(
                timestamp, start_hour, end_hour)
            if is_accepted:
                # remove
                time_t = datetime.datetime.strptime(
                    timestamp, "%Y-%m-%dT%H:%M:%S%z").timetuple()
                print(
                    f"Match {match_id} - time: {time_t.tm_hour}:{time_t.tm_min}")

                match_ids.append(match_id)

        amount = len(match_ids)

        if amount < count:
            # recursive
            next_timestamp = match_json['data']['metadata']['next']
            next_ids = self.get_last_n_matches(
                battlenet, count-amount, start_hour, end_hour, next_timestamp)

            amount += len(next_ids)
            match_ids += next_ids

        return match_ids

    def __calculate_match_kd(self, teams: list) -> float:
        matchKd = 0
        for team in teams:
            count_of_kds = 0
            teamKd = 0
            for player in teams[team]:
                # if KDR is not 0, players has stats
                if player[1] > 0:
                    count_of_kds += 1
                    teamKd += player[1]
            """ Copying COD Tracker Avg. team KD algo for identical results
            To use team in calculation, there must be atleast 2 members
            in the team and atleast 1 of them has to have KD statistics """
            if count_of_kds >= 1 and len(teams[team]) > 1:
                teamKd /= count_of_kds
                matchKd += teamKd

        return matchKd / len(teams)

    def get_match_data(self, match_id: str) -> tuple():
        """Fetches match data and calculates team KDR of the match"""
        self.__delay_request()

        url = 'https://api.tracker.gg/api/v2/warzone/standard/matches/'
        resp = requests.get(url + match_id, headers=self.headers)

        if resp.status_code == 429:
            self.save_cache()
            print("RateLimited? Saved cache, waiting 10 minutes.", resp.text)
            time.sleep(10 * 60)
            # Try again recursively
            return self.get_match_data(match_id)
        if resp.status_code == 500:
            print('Error with API, saving cache: ', resp.text)
            self.save_cache()
            exit(1)
        if resp.status_code == 503 or resp.status_code == 504 or resp.status_code == 400:
            print('Service not available, retrying:')
            self.save_cache()
            while resp.status_code == 503 or resp.status_code == 504 or resp.status_code == 400:
                time.sleep(30)
                resp = requests.get(url + match_id, headers=self.headers)

        teams = {}
        json = resp.json()
        # Sort all players into coresponding teams
        if 'data' not in json:
            print('Match not found? Saving cache, retrying --', resp.text)
            self.save_cache()
            while 'data' not in resp.json():
                time.sleep(30)
                resp = requests.get(url + match_id, headers=self.headers)

        for player in json['data']['segments']:
            team = player['attributes']['team']
            name = player['attributes']['platformUserIdentifier']
            kd = 0
            if 'lifeTimeStats' in player['attributes']:
                kd = player['attributes']['lifeTimeStats']['kdRatio']

            if team not in teams:
                teams[team] = [(name, kd, team)]
            else:
                teams[team].append((name, kd, team))

        match_kd = round(self.__calculate_match_kd(teams), 1)
        match_id = json['data']['attributes']['id']
        timestamp = int(json['data']['metadata']['timestamp']) / 1e3
        match_data = (match_id, match_kd, teams, timestamp)

        self.__cache_match(match_id, match_data)
        return match_data

    def get_data_for_user(self, username: str, count: int, start_hour=0, end_hour=0) -> pd.DataFrame:
        match_ids = self.get_last_n_matches(username, count, start_hour, end_hour)

        df = pd.DataFrame(columns=['id', 'kd', 'teams', 'timestamp'])
        for id in match_ids:
            # Try cache first
            match_data = self.__get_cached_match(id)
            if not match_data:
                match_data = self.get_match_data(id)

            print(match_data[0], match_data[1])
            df.loc[len(df)] = list(match_data)

        print('Caching matches')
        self.save_cache()
        return df
