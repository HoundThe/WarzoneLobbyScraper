### Warzone KDR lobby scraper

Python script that can plot average lobby KDR of someones last N lobbies.

If you wonder why some people seem to have very easy lobbies, you can easily compare them with yours! You might find that some people abuse the game to match with weaker players to feel good.

About program:
- To use you need to fill in your browser headers on line 21 and the rest if pretty straightforward.
- There is delay between requests 2 seconds by default, you can lower it, but be careful about ratelimits if you are trying to plot large amount of lobbies.
- Some people might not have enough games played or data on codtracker.
- Plots have fixed ticks from 0.4 to 1.6 KDR, which works for pretty much everyone except some outliers.
- All calculated match KDRs are cached into the disk with Pickle, so you don't have to spam API for the same match twice if you want to replot.

[Example graph:](example.png)

Data source: https://cod.tracker.gg/warzone/