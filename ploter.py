from warzone_scraper import WarzoneTracker
import pandas as pd
import seaborn as sns
import datetime
from matplotlib import pyplot as plt


def prepare_total_kd_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans up the games data into 0.3-1.6 KD interval
    for uniform look and counts number of such lobbies"""
    df['match_team_kd'] = df['match_team_kd'].round(1)
    group = df.value_counts(subset=['match_team_kd'], sort=False).reset_index()
    print(group)
    group = group.set_index('match_team_kd').reindex([0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
                                           1.1, 1.2, 1.3, 1.4, 1.5, 1.6]).reset_index()
    print(group)
    return group


def prepare_daily_kd_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans up the data, groups the games by day,
    where day has to have atleast 3 games to count,
    calculates 3 and 7 day moving average"""

    df['day'] = df.timestamp.apply(
        lambda x: datetime.datetime.fromtimestamp(x)).astype('datetime64[D]')
    new_df = df[['match_team_kd', 'day', 'id']]
    group = new_df.groupby(by=[new_df.day], as_index=False).agg(
        {'match_team_kd': 'mean', 'id': 'size'}).rename(columns={'id': 'count'})

    # atleast 3 games in a day to use day in the calculations
    group.drop(group[group['count'] < 3].index, inplace=True)
    group.drop('count', inplace=True, axis=1)

    # Moving averages
    group['MA3'] = group['match_team_kd'].rolling(window=3, min_periods=1).mean()
    group['MA7'] = group['match_team_kd'].rolling(window=7, min_periods=1).mean()
    print(group)

    return group


# def plot_total_lobby_kd4(
#         usernames: list[str],
#         start_game: int, end_game: int, start_hour=0, end_hour=0):
#     """Plots 2x2 histograms with avg. match KD of latest games

#     Plots are saved with descriptive name into the plots/ folder

#     Arguments:
#         usernames (list[str]) - 4 battlenet or activision IDs
#         start_game (int) - Nth last game where the plotting starts
#         end_game (int) - Nth last game where the plotting ends
#         start_hour=0 (int) - Sets the start hour to use in the plot (example: filtering only morning games)
#         end_hour=0 (int) - Sets the end hour to use in the plot (example: filtering only morning games)

#         if start_hour == end_hour then games at any time are used
#     """
#     assert len(usernames) == 4

#     fig, ax = plt.subplots(2, 2, figsize=(13, 7), sharex=True, sharey=True)
#     ax = ax.flatten()

#     scraper = WarzoneScraper()

#     for idx, user in enumerate(usernames):
#         df = scraper.get_data_for_user(user, end_game, start_hour, end_hour)
#         # filter out the desired game interval
#         df = df[start_game:end_game]
#         avg_kd = round(df['kd'].mean(), 3)
#         df = prepare_total_kd_frame(df)

#         sns.barplot(ax=ax[idx], x=df.kd, y=df[0], palette='rocket_r')

#         title = f'{user} - Lobbies from {start_game} to {end_game} latest games'

#         if start_hour != end_hour:
#             title += f' between {start_hour}:00 and {end_hour}:59'
#         title += f' - Avg. KDR : {avg_kd}'

#         ax[idx].set(title=title, ylabel='Quantity', xlabel='Average lobby KD')

#     fig.tight_layout()
#     fig.savefig(
#         f'plots/total_{usernames[0]}_{usernames[1]}_{usernames[2]}\
# _{usernames[3]}_{start_game}-{end_game}_hour_{start_hour}-{end_hour}.png')
#     plt.show()


def plot_total_lobby_kd(df: pd.DataFrame):
    """Plots avg. match KD histogram of latest games

    Plots are saved with descriptive name into the plots/ folder

    Arguments:
        username (str) - battlenet or activision name
        start_game (int) - Nth last game where the plotting starts
        end_game (int) - Nth last game where the plotting ends
        start_hour=0 (int) - Sets the start hour to use in the plot (example: filtering only morning games)
        end_hour=0 (int) - Sets the end hour to use in the plot (example: filtering only morning games)

        if start_hour == end_hour then games at any time are used
    # """

    # scraper = WarzoneScraper()

    # df = scraper.get_data_for_user(username, end_game, start_hour, end_hour)

    # # filter out the desired game interval
    # df = df[start_game:end_game]
    # avg_kd = round(df['kd'].mean(), 3)
    df.drop(df[df['match_team_kd'] > 1.7].index, inplace=True)
    avg_kd = round(df['match_team_kd'].mean(), 3)
    print(df)
    df = prepare_total_kd_frame(df)

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    sns.barplot(ax=ax, x=df.match_team_kd, y=df[0], palette='rocket_r')

    # title = f'{username} - KDR of lobbies from {start_game} to {end_game} latest games'
    # if start_hour != end_hour:
    #     title += f' between {start_hour}:00 and {end_hour}:59'
    title = f' - Avg. KDR : {avg_kd}'

    ax.set(title=title, ylabel='Quantity', xlabel='Average lobby KD')

    fig.tight_layout()
    # fig.savefig(
    #     f'plots/total_{username}_{start_game}-{end_game}_hours_{start_hour}-{end_hour}.png')
    plt.show()


def plot_daily_lobby_kd(df: pd.DataFrame):
    """Plots average KD each day for last `count` matches, missing days are omitted

    3 lines are plotted, KD of the day, moving 3-day average, moving 7-day average

    Plots are saved with descriptive name into the plots/ folder

    Day has to have atleast 3 games in the hour interval to be used in the calculation

    Arguments:
        username (str) - battlenet or activision name
        count (int) - Number of latest games to plot
        start_hour=0 (int) - Sets the start hour to use in the plot (example: filtering only morning games)
        end_hour=0 (int) - Sets the end hour to use in the plot (example: filtering only morning games)

        if start_hour == end_hour then games at any time are used
    """
    df.drop(df[df['match_team_kd'] > 1.7].index, inplace=True)
    count = len(df.index)
    avg_kd = round(df['match_team_kd'].mean(), 3)
    df = prepare_daily_kd_frame(df)
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))

    df.set_index('day', inplace=True)
    sns.lineplot(ax=ax, data=df)
    ax.set(title=f'User - Daily average lobby KD from {count} games - Avg. KDR : {avg_kd}',
           ylabel='Average lobby KD', xlabel='Date')

    fig.tight_layout()
    # fig.savefig(f'plots/daily_{username}_{count}_hours_{start_hour}-{end_hour}.png')
    plt.show()


def plot_daily_lobby_kd2(df1, df2):
    """Plots average KD each day for last `count` matches for 2 players, missing days are omitted

    Each line represents 7-day moving average of a player

    Plots are saved with descriptive name into the plots/ folder

    Day has to have atleast 3 games in the hour interval to be used in the calculation

    Arguments:
        usernames (list[str]) - 2 battlenet or activision IDs
        count (int) - Number of latest games to plot
        start_hour=0 (int) - Sets the start hour to use in the plot (example: filtering only morning games)
        end_hour=0 (int) - Sets the end hour to use in the plot (example: filtering only morning games)

        if start_hour == end_hour then games at any time are used
    """
    df1.drop(df1[df1['match_team_kd'] > 1.7].index, inplace=True)
    df2.drop(df2[df2['match_team_kd'] > 1.7].index, inplace=True)

    df1 = prepare_daily_kd_frame(df1)
    df1.drop(['match_team_kd', 'MA3'], axis=1, inplace=True)
    df1['name'] = "achiles"

    df2 = prepare_daily_kd_frame(df2)
    df2.drop(['match_team_kd', 'MA3'], axis=1, inplace=True)
    df2['name'] = "tomor"

    df = pd.concat([df1, df2], ignore_index=True, sort=True)
    print(df)

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    sns.lineplot(ax=ax, x=df.day, y=df.MA7, hue=df.name)
    ax.set(title=f'tomor achil - Daily 7 day moving average of lobby KD from vela games',
           ylabel='Average lobby KD', xlabel='Date')

    fig.tight_layout()
    # fig.savefig(
    #     f'plots/daily_{usernames[0]}_{usernames[1]}_{count}_hour_{start_hour}-{end_hour}.png')
    plt.show()


if __name__ == "__main__":
    #     # set the seaborn visual
    sns.set_style("darkgrid", {"axes.facecolor": ".9"})

    tracker = WarzoneTracker(delay=1.5)
    ss, farb = tracker.get_user_data('RadekZachy', 'atvi', count=1500)
    # plot_total_lobby_kd(farb)
    # ss, farb = tracker.get_user_data('Farb#2499', 'battlenet', count=100)
    # plot_total_lobby_kd(farb)
    # ss, farb = tracker.get_user_data('Farb#2499', 'battlenet', count=2000)
    # print(hound_df)
    ss, tomor = tracker.get_user_data('Tomor36#2712', 'battlenet', count=2000)
    # ss, tomor = tracker.get_user_data('Tomor36#2712', 'battlenet', count=2000)
    # print(hound_df)
    plot_daily_lobby_kd2(farb, tomor)
    # hound_stats, hound_df = tracker.get_user_data('Farb#2499', 'battlenet', count=2000)
    # print(hound_df)
    # hound = tracker.get_user_data('TheHound#2293', 'battlenet', count=200)
#     # plot_total_lobby_kd('TheHound#2293', start_game=0, end_game=20)
#     # plot_total_lobby_kd('magorkapustaaaa#3886559', start_game=0, end_game=100)
#     # plot_daily_lobby_kd2(['Tomor36#2712', 'Farb#2499'], 1500, 0, 0)
#     # plot_total_lobby_kd('TheHound#2293', start_game=50, end_game=100)
#     # these are examples, results can be seen in the repository
#     # plot_total_lobby_kd('TheHound#2293', start_game=0, end_game=50, start_hour=14, end_hour=24)
#     # plot_daily_lobby_kd('Achiles#2615', 500, 0, 0)
#     plot_total_lobby_kd4(
#         usernames=['magorkapustaaaa#3886559', 'Tomor36#2712', 'TheHound#2293', 'Achiles#2615'],
#         start_game=0, end_game=100)

# 1619545876999
