from autodownloader.main import Stream_repackager, m3u8_url_finder,get_m3u8_link
m3u8_link = get_m3u8_link("https://tvsportslive.fr/69377-2/")
packager = Stream_repackager("12345",m3u8_link)
packager.start()
print(packager.playlist)