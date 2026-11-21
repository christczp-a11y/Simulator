#!/bin/bash
# starts the frame server on port 8123 if it is not running (it does not survive between shell sessions)
F=${FRAMES_DIR:-work/frames}
curl -s -o /dev/null http://127.0.0.1:8123/s_00000.png || { (setsid nohup python3 -m http.server 8123 --bind 127.0.0.1 --directory $F > /dev/null 2>&1 &); sleep 1; }
curl -s -o /dev/null -w "frames server %{http_code}\n" http://127.0.0.1:8123/s_00000.png
