from pandas.core.accessor import CachedAccessor
import requests
import calendar
import time
import datetime
import os
import urllib.parse
import gzip
import pickle
import pandas as pd


class WarzoneTracker:
    """
    Class that offers functions to fetch data from COD Tracker API

    It uses pickle cache to cache all match data, so you don't need to wait or spam API 
    every time you want to plot.
    """

    def __init__(self, delay=1.0, cache_filename='matches.pkl'):
        self.cache_filename = cache_filename
        self.headers = {
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="90", "Google Chrome";v="90"',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://cod.tracker.gg/',
            'Accept-Language': 'en',
            'sec-ch-ua-mobile': '?0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
        }
        # delay between requests to dodge ratelimit
        self.delay = delay
        self.cache = {'users': {
            # 'match_history': [],
            # 'stats': {}
        },
            'matches': {}
        }

        # modes that are accounted for in the statistics
        self.accepted_modes = [
            "br_brquads",
            "br_brtrios",
            "br_brduos",
        ]

        self.accepted_platforms = [
            "battlenet",
            "atvi",
            "psn",
        ]

        # Load existing cache from drive
        if os.path.exists(self.cache_filename):
            with open(self.cache_filename, 'rb') as file:
                self.cache = pickle.load(file)

    def __get_cached_user_stats(self, nickname):
        if nickname in self.cache['users']:
            return self.cache['users'][nickname]
        return None

    def __cache_user_stats(self, nickname, user_data):
        if nickname not in self.cache['users']:
            self.cache['users'][nickname] = {
                'match_history': []
            }

        self.cache['users'][nickname]['stats'] = user_data

    def __get_cached_user_history(self, nickname) -> list:
        if nickname in self.cache['users']:
            return self.cache['users'][nickname]['match_history']
        return None

    def __cache_user_history(self, nickname, history):
        if nickname not in self.cache['users']:
            self.cache['users'][nickname] = {
                'match_history': []
            }
        self.cache['users'][nickname]['match_history'] = history

    def __get_cached_match(self, id):
        if id in self.cache['matches']:
            return self.cache['matches'][id]

        return None

    def __cache_match(self, id, match_data):
        self.cache['matches'][id] = match_data

    def __is_inside_time_interval(self, timestamp, start_hour, end_hour):
        """Check if timestamp is inside day hour interval"""
        if start_hour == end_hour:
            return True

        time = datetime.datetime.strptime(
            timestamp, "%Y-%m-%dT%H:%M:%S%z").timetuple()
        hour = time.tm_hour

        if end_hour < start_hour:  # overlaps midnight
            if start_hour <= hour or hour <= end_hour:
                return True
        elif start_hour <= hour and hour <= end_hour:
            return True

        return False

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

    def __delay_request(self):
        time.sleep(self.delay)

    def save_cache(self):
        """Saves cache to disk"""
        with open(self.cache_filename, 'wb') as file:
            fastPickler = pickle.Pickler(file, pickle.HIGHEST_PROTOCOL)
            fastPickler.fast = 1
            fastPickler.dump(self.cache)

    def get_user_lifetime_data(self, nickname: str, platform: str) -> tuple:
        # Try cache first
        cached_user = self.__get_cached_user_stats(nickname)
        if cached_user:
            sec_in_day = 60 * 60 * 24
            timestamp = time.time()
            # use cache if it's not more than day old
            if cached_user['stats'][0] + sec_in_day >= timestamp:
                return cached_user['stats']

        endpoint = f'https://api.tracker.gg/api/v2/warzone/standard/profile'
        encoded_name = urllib.parse.quote(nickname)
        url = f'{endpoint}/{platform}/{encoded_name}'

        resp = requests.get(url, headers=self.headers)

        # Check if BR is always second
        warzone_lifetime_data = resp.json()['data']['segments'][1]
        assert warzone_lifetime_data['attributes']['mode'] == 'br'

        lifetime_stats = warzone_lifetime_data['stats']
        kdr = lifetime_stats['kdRatio']['value']
        winrate = lifetime_stats['wlRatio']['value']
        wins = lifetime_stats['wins']['value']
        kills = lifetime_stats['kills']['value']
        avg_life = lifetime_stats['averageLife']['value']
        game_played = lifetime_stats['gamesPlayed']['value']

        timestamp = time.time()

        user_data = (timestamp, nickname, kdr, winrate, wins, kills, avg_life, game_played)
        self.__cache_user_stats(nickname, user_data)
        return user_data

    def _get_match_player_data(self, stats_json):
        kills = -1
        deaths = -1
        damage = -1
        team_alive_time = -1
        headshots = -1

        if 'kills' in stats_json:
            kills = stats_json['kills']['value']
        if 'deaths' in stats_json:
            deaths = stats_json['deaths']['value']
        if 'damageDone' in stats_json:
            damage = stats_json['damageDone']['value']
        if 'teamSurvivalTime' in stats_json:
            team_alive_time = stats_json['teamSurvivalTime']['value']
        if 'headshots' in stats_json:
            headshots = stats_json['headshots']['value']

        return kills, deaths, damage, team_alive_time, headshots

    def get_match_data(self, match_id: str) -> tuple():
        """Fetches match data and calculates avg. team KDR of the match

        Arguments:
            match_id (str) - id of the match

        Returns:
            match_data - Tuple of (match_id, avg. KD, collection of teams, timestamp)
        """
        self.__delay_request()

        url = f'https://api.tracker.gg/api/v2/warzone/standard/matches/{match_id}'
        resp = requests.get(url, headers=self.headers)

        if resp.status_code == 429:
            print("RateLimited? Saved cache, waiting 10 minutes.", resp.text)
            self.save_cache()
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
                resp = requests.get(url, headers=self.headers)

        if 'data' not in resp.json():
            print('Match not found? Saving cache, retrying --', resp.text)
            self.save_cache()
            while 'data' not in resp.json():
                time.sleep(30)
                resp = requests.get(url, headers=self.headers)

        teams = {}
        json = resp.json()
        # Sort all players into coresponding teams
        for player in json['data']['segments']:
            team = player['attributes']['team']
            name = player['attributes']['platformUserIdentifier']

            kills, deaths, damage, team_alive_time, headshots = self._get_match_player_data(
                player['stats'])

            lifetime_kd = 0
            if 'lifeTimeStats' in player['attributes']:
                lifetime_kd = player['attributes']['lifeTimeStats']['kdRatio']

            player_data = (name, lifetime_kd, kills, deaths,
                           damage, team_alive_time, headshots)

            if team not in teams:
                teams[team] = [player_data]
            else:
                teams[team].append(player_data)

        match_kd = round(self.__calculate_match_kd(teams), 3)
        match_id = json['data']['attributes']['id']
        match_mode = json['data']['attributes']['modeId']
        match_time = int(json['data']['metadata']['duration']['value']) / 1e3
        timestamp = int(json['data']['metadata']['timestamp']) / 1e3
        match_data = (match_id, match_mode, timestamp, match_time, match_kd, teams)

        self.__cache_match(match_id, match_data)
        return match_data

    def get_matches(self, nickname, platform, next=0):
        self.__delay_request()

        params = (('type', 'wz'), ('next', str(next)))

        endpoint = f'https://api.tracker.gg/api/v2/warzone/standard/matches'
        encoded_name = urllib.parse.quote(nickname)
        url = f'{endpoint}/{platform}/{encoded_name}'

        resp = requests.get(url, headers=self.headers, params=params)

        # Handle various errors that COD Tracker might return
        if resp.status_code == 429:
            print("RateLimited? Waiting 10 minutes.", resp.text)
            self.save_cache()
            time.sleep(10 * 60)
            print("Retrying:")
            # Try again recursively
            return self.get_matches(nickname, platform, next)
        if resp.status_code == 500:
            print('Error with API, saving cache: ', resp.text)
            self.save_cache()
            print('Waiting 5 minutes')
            time.sleep(5 * 60)
            print('Retrying:')
            return self.get_matches(nickname, platform, next)
        if resp.status_code == 503 or resp.status_code == 504 or resp.status_code == 400:
            print('Service not available, waiting 30 seconds:')
            self.save_cache()
            time.sleep(30)
            print('Retrying:')
            return self.get_matches(nickname, platform, next)

        match_json = resp.json()
        matches = []

        # iterate and filter matches
        for match in match_json['data']['matches']:
            timestamp = match['metadata']['timestamp']
            mode_id = match['attributes']['modeId']
            match_id = match['attributes']['id']
            match_duration = match['metadata']['duration']['value']
            # is_accepted = mode_id in self.accepted_modes and self.__is_inside_time_interval(
            #     timestamp, start_hour, end_hour)
            is_accepted = mode_id in self.accepted_modes
            if is_accepted:
                time_t = datetime.datetime.strptime(
                    timestamp, "%Y-%m-%dT%H:%M:%S%z").timetuple()
                print(
                    f"Fetched match history {match_id: <20} - time: {time_t.tm_hour:02}:{time_t.tm_min:02}")
                # From seconds to miliseconds so it's compatible with 'Next' argument
                timestamp = int(calendar.timegm(time_t) * 1e3)
                matches.append((match_id, timestamp))

        next_timestamp = match_json['data']['metadata']['next']

        raw_count = len(match_json['data']['matches'])
        if raw_count < 20:
            next_timestamp = -1
        return matches, next_timestamp

    def get_matches_from_history(self, nickname: str, matches: list, count: int) -> list:
        """ returns as much matches from history it can up to `count` or None"""
        cached_history = self.__get_cached_user_history(nickname)

        if not cached_history:
            return None

        last_tst_new = matches[-1][1]
        last_tst_cache = cached_history[-1][1]

        if last_tst_new <= last_tst_cache:
            return None

        # we try to find match between newest dowloaded matches and first cached one
        for idx, match in enumerate(matches):
            if match[1] == cached_history[0][1]:
                print('Found cache match, reading further from cache')
                return matches[0:idx] + cached_history
        return None

    def get_user_matches(self,
                         nickname: str,
                         platform: str,
                         count=0):
        """
        # situations:
        We request past 20 matches
            - N-th one is in the history
            - None of them are in history

        We continue reading cached history:
            - until we're happz
            - until we run out of cache - requesting further
        """
        matches = []
        next_timestamp = 0

        while len(matches) < count:
            next_matches, next_timestamp = self.get_matches(nickname, platform, next_timestamp)

            if next_timestamp == -1:
                print("I guess we found end of players match history")
                matches += next_matches
                break

            history = self.get_matches_from_history(nickname, next_matches, count - len(matches))
            if history:
                matches += history
                # timestmap of 19th match from the end because COD Tracker after is broken
                next_timestamp = matches[-19][1] - 1
                print(f'Loaded {len(history)} matches from history cache')
                print(f"Next match timestamp: {next_timestamp}")
            else:
                matches += next_matches

        # remove duplicates in case of history going around COD Tracker broken 'next' argument
        matches = list(dict.fromkeys(matches))

        self.__cache_user_history(nickname, matches)

        # clip the extra matches
        if len(matches) > count:
            matches = matches[:count]

        # use only ids
        match_ids = list(map(lambda x: x[0], matches))

        # debug
        if any(match_ids.count(x) > 1 for x in match_ids):
            print('Error, duplicates in match ids')

        return match_ids

    def get_user_data(self,
                      nickname: str,
                      platform: str,
                      **kwargs) -> pd.DataFrame:

        lifetime_stats = self.get_user_lifetime_data(nickname, platform)
        match_ids = self.get_user_matches(nickname, platform, **kwargs)
        self.save_cache()

        df = pd.DataFrame(columns=['id', 'mode', 'timestamp',
                          'duration', 'match_team_kd', 'players'])
        for idx, id in enumerate(match_ids):
            # Try cache first
            match_data = self.__get_cached_match(id)
            if not match_data:
                match_data = self.get_match_data(id)
            print(f'Fetched match details - {id: <20} KD: {match_data[4]:1.3}, Left: {len(match_ids) - idx - 1}')
            df.loc[len(df)] = list(match_data)

        print('Caching matches')
        self.save_cache()
        return (lifetime_stats, df)
