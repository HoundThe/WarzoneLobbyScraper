### Warzone KDR lobby scraper

Python script that can plot lobby KDRs of someones last N lobbies.

If you wonder why some people seem to have very easy lobbies, you can easily compare them with yours! You might find that some people abuse the game to match with weaker players to feel good.

If you find the script useful, hit the ★ Star button!

File `warzone.scraper.py` contains all the data fetching from COD Tracker.
File `ploter.py` has the plotting functions and the main program.

To use you need Python3. All the necessary libraries can be downloaded using `pip install -r requirements.txt`

When first used, the program caches downloaded matches so you don't have to download them everytime, but the first plotting takes a while.
I set delay to 1 second per request, so 100 matches to plot would take atleast 100 seconds - realisticaly about twice of that.

There is TODO to cache also the list of last player games, but it is not implemented yet, so every plot will have to fetch all the games the user played and then fetch data about each match (but data about each match is cached). Fetching the list of games is fast, because it fetches 20 games each request.

There are 4 kinds of graphs to plot:

Average game KDR bar graph of a single player:
![Average game KDR bar graph of a single player:](plots/total_TheHound%232293_0-300_hours_0-0.png)

Average game KDR bar graph of 4 players:
![Average game KDR bar graph of 4 players:](plots/total_Farb%232499_Tomor36%232712_TheHound%232293_Achiles%232615_0-200_hour_0-0.png)

Daily average KDR line graph (Daily avg. KDR, 3-day moving average, 7-day moving average) of a single player:
![Daily average KDR line graph (Daily avg. KDR, 3-day moving average, 7-day moving average) of a single player:](plots/daily_Achiles%232615_508_hours_0-0.png)

Daily average KDR line graph (7-day moving average) of 2 players:
![Daily average KDR line graph (7-day moving average) of 2 players:](plots/daily_bachio99%232426_Achiles%232615_600_hour_0-0.png)

Every graph has option to filter out certain day hours (afternoon games, morning games).

![Example:](plots/total_TheHound%232293_0-50_hours_14-24.png)

In the bar graph you can also use game interval, for example 0 to 150 last games, and then 150 to 350 last games. Useful to see difference in the lobbies if the user started abusing easy lobbies just recently.

![Example:](plots/total_TheHound%232293_50-100_hours_0-0.png)

All of these graphs are plotted by function calls in `ploter.py`, some are commented out. It should be pretty intuitive to use them as you wish (replace the username with your, number of games, etc.)

About program:
- There is hour interval filter, so you can filter morning hours like 00:00-12:00 and afternoon like 12:00 - 00:00.
- There is delay between requests 1 second by default, you can lower it, but be careful about ratelimits if you are trying to plot large amount of lobbies.
- Some people might not have enough games played or data on codtracker.
- Bar graphs have fixed ticks from 0.3 to 1.6 KDR, which works for pretty much everyone except some outliers (that are usually due to lack of match data).
- All calculated match KDRs are cached into the disk with Pickle, so you don't have to spam API for the same match twice if you want to replot.
- I've made the calculation the same as COD Trackers with average team KDR

Data source: https://cod.tracker.gg/warzone/
