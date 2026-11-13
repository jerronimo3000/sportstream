from autodownloader.main import Stream_repackager, m3u8_url_finder,get_m3u8_link
m3u8_link = get_m3u8_link("https://v2.streameast.ga/nfl/washington-commanders-vs-new-york-giants-1/")
packager = Stream_repackager("12345",m3u8_link)
packager.start()
print(packager.playlist)