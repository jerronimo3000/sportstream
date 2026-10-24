   #!/bin/sh
   exec /usr/bin/ffmpeg -hide_banner -nostdin -loglevel warning \
     -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 \
     -rw_timeout 8000000 -fflags +genpts \
     -i "$1" \
     -codec copy -avoid_negative_ts make_zero \
     -mpegts_flags +resend_headers -f mpegts pipe:1