from bs4 import BeautifulSoup
import requests
import json
import time
import os
import urllib.parse
import gzip
import pickle
import pandas as pd
from matplotlib import pyplot as plt
import seaborn as sns


class WarzoneScraper:
    def __init__(self, delay=2.0, cache_filename='matches.pkl.gz'):
        self.cache_filename = cache_filename
        self.headers = {
            # Fill in headers from your browser !!!
        }
        # delay between requests to dodge ratelimit
        self.delay = delay
        self.cache = {}

        # modes that are accounted for in the statistics
        self.accepted_modes = [
            "br_brquads",
            "br_brtrios",
            "br_brduos",
            "br_brsolos",
        ]
        # Load existing cache from drive
        if os.path.exists(self.cache_filename):
            with gzip.open(self.cache_filename, 'rb') as file:
                self.cache = pickle.load(file)

    def __get_cached_match(self, match_id: str) -> float:
        """Returns cached match KDR or None"""
        if match_id in self.cache:
            return self.cache[match_id]

        return None

    def __cache_match(self, match_id: str, kd: float):
        """Caches match KDR to in-memory cache"""
        self.cache[match_id] = kd

    def save_cache(self):
        """Saves cache to disk"""
        with gzip.open(self.cache_filename, 'wb') as file:
            pickle.dump(self.cache, file)

    def get_match_kd(self, match_id: str) -> float:
        """Fetches match data and calculates team KDR of the match"""
        cached_kd = self.__get_cached_match(match_id)
        if cached_kd:
            return cached_kd

        time.sleep(self.delay)

        resp = requests.get(
            'https://api.tracker.gg/api/v2/warzone/standard/matches/' + match_id, headers=self.headers)

        if resp.status_code == 500:
            print('Error with API: ', page.text)
            print("RateLimited? Waiting 10 minutes.")
            time.sleep(10 * 60)
            # Try again recursively
            return get_match_kd(self, match_id)

        players = []
        teams = {}
        # Sort all players into coresponding teams
        for player in resp.json()['data']['segments']:
            team = player['attributes']['team']
            name = player['attributes']['platformUserIdentifier']
            kd = 0
            if 'lifeTimeStats' in player['attributes']:
                kd = player['attributes']['lifeTimeStats']['kdRatio']

            if team not in teams:
                teams[team] = [(name, kd, team)]
            else:
                teams[team].append((name, kd, team))

        matchKd = 0
        for team in teams:
            count_of_kds = 0
            teamKd = 0
            for player in teams[team]:
                # if KDR is not 0, players has stats
                if player[1] > 0:
                    count_of_kds += 1
                    teamKd += player[1]
            # To use team in calculation, there must be atleast 2 members
            # in the team and atleast 1 of them has to have KD statistics
            if count_of_kds >= 1 and len(teams[team]) > 1:
                teamKd /= count_of_kds
                matchKd += teamKd

        matchKd = matchKd / len(teams)

        self.__cache_match(match_id, matchKd)

        return matchKd

    def get_last_n_matches(self, battlenet, count=20, next=None):
        """Fetch ids of `count` last matches of `username`"""

        if next:
            params = (
                ('type', 'wz'),
                ('next', str(next)),
            )
        else:
            params = (
                ('type', 'wz'),
            )

        # always returns packs of 20 games
        time.sleep(self.delay)

        username_parsed = urllib.parse.quote(battlenet)
        p1, p2 = battlenet.split('#')
        # more numbers -> activision username
        if len(p2) <= 5:
            page = requests.get(
                'https://api.tracker.gg/api/v2/warzone/standard/matches/battlenet/' + username_parsed, headers=self.headers, params=params)
        else:
            page = requests.get(
                'https://api.tracker.gg/api/v2/warzone/standard/matches/atvi/' + username_parsed, headers=self.headers, params=params)

        if page.status_code == 500:
            print('Error with API: ', page.text)
            exit(1)

        match_json = json.loads(page.text)
        match_ids = []

        for match in match_json['data']['matches']:
            if match['attributes']['modeId'] in self.accepted_modes:
                match_ids.append(match['attributes']['id'])

        amount = len(match_ids)

        if amount < count:
            # recursive
            next_ids = self.get_last_n_matches(
                battlenet, count=count-amount, next=match_json['data']['metadata']['next'])

            amount += len(next_ids)
            match_ids += next_ids

        return match_ids

    def get_data_for_user(self, username: str, count: int) -> pd.DataFrame:
        match_ids = self.get_last_n_matches(username, count)

        kds = []
        for id in match_ids:
            match_kd = self.get_match_kd(id)
            kds.append(round(match_kd, 1))
            # caching every response in case that
            # I get ratelimited or blocked so I don't lose progress
            # It take no time anyways
            self.save_cache()
            # print(id, round(match_kd, 1))

        return pd.DataFrame(kds, columns=['kd'])


def prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans up the data into 0.4-1.6 KD interval for easier comparison"""
    grp = df.value_counts(sort=False).reset_index()
    grp = grp.set_index('kd')
    return grp.reindex([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
                        1.1, 1.2, 1.3, 1.4, 1.5, 1.6]).reset_index()


def plot_lobbies_kd4(usernames: list[str], count: int):
    """Plots 2x2 subplots with team KD of 'count' lobbies of 4 users"""
    assert len(usernames) == 4

    sns.set_style("darkgrid", {"axes.facecolor": ".9"})
    fig, ax = plt.subplots(2, 2, figsize=(12, 7), sharex=True, sharey=True)
    ax = ax.flatten()

    scraper = WarzoneScraper()

    for idx, user in enumerate(usernames):
        df = scraper.get_data_for_user(user, count)
        size = len(df.index)
        df = prepare_frame(df)

        sns.barplot(ax=ax[idx], x=df.kd, y=df[0], palette='rocket_r')
        ax[idx].set(title=f'{user} - Match KDR graph from {size} games.',
                    ylabel='Game count', xlabel='KD Ratio')

    fig.tight_layout()
    fig.savefig(
        f'{usernames[0]}_{usernames[1]}_{usernames[2]}_{usernames[3]}_{count}_plot.png')
    plt.show()


def plot_lobbies_kd(username: str, count: int):
    """Plots team KD of `count` lobbies of 'username'"""
    sns.set_style("darkgrid", {"axes.facecolor": ".9"})

    scraper = WarzoneScraper()

    df = scraper.get_data_for_user(username, count)
    size = len(df.index)
    df = prepare_frame(df)

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    sns.barplot(ax=ax, x=df.kd, y=df[0], palette='rocket_r')
    ax.set(title=f'{username} - Match KDR graph from {size} games.',
           ylabel='Game count', xlabel='KD Ratio')

    fig.tight_layout()
    fig.savefig(f'{username}_{count}_plot.png')
    plt.show()


if __name__ == "__main__":
    plot_lobbies_kd('TheHound#2293', 200)
    plot_lobbies_kd4(["TheHound#2293", 'TheHound#2293',
                     'TheHound#2293', "TheHound#2293"], 200)
