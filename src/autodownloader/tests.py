from autodownloader import *

manager = Stream_manager(r"https://streameast.ga/nfl/los-angeles-chargers-vs-buffalo-bills/")

while manager.cached_streams is None:
    pass
print(manager.cached_streams)