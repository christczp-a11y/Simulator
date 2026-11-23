# V1 picture (original s01) + v2 library sound with a calm s01 bed -> ep03_v1b_norm.mp4 + 720p
$w = 'C:\YouTubeNeuropolis\Out\ep03-egypt-train\work'; $o = 'C:\YouTubeNeuropolis\Out\ep03-egypt-train'
if (-not (Test-Path "$w\frames\s01_v2")) { Rename-Item "$w\frames\s01" 's01_v2' } else { Remove-Item "$w\frames\s01" -Recurse -Force }
Copy-Item "$w\frames\s01_v1" "$w\frames\s01" -Recurse
"s01 frames: $((Get-ChildItem "$w\frames\s01").Count)"
$pub = "$w\remotion\public"
if (-not (Test-Path "$pub\sfx_mix_v2.wav")) { Copy-Item "$pub\sfx_mix.wav" "$pub\sfx_mix_v2.wav" }
Copy-Item "$pub\sfx_mix_v1b.wav" "$pub\sfx_mix.wav" -Force
Set-Location "$w\remotion"; $t = Get-Date
node render_pc.mjs ..\frames ..\ep03_v1b.mp4 8 *> ..\render_v1b_log.txt
"render exit $LASTEXITCODE $([int]((Get-Date)-$t).TotalSeconds)s"
Set-Location $w
$m = ffmpeg -hide_banner -i ep03_v1b.mp4 -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | Out-String
$js = ($m -split "`n" | Select-String -Pattern '"input_i"|"input_tp"|"input_lra"|"input_thresh"|"target_offset"' | % { $_.Line.Trim().TrimEnd(',') }) -join ','
$p = "{$js}" | ConvertFrom-Json
$af = "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$($p.input_i):measured_TP=$($p.input_tp):measured_LRA=$($p.input_lra):measured_thresh=$($p.input_thresh):offset=$($p.target_offset):linear=true,aresample=192000,alimiter=limit=0.79:level=false:attack=1:release=50,aresample=48000"
ffmpeg -v error -y -i ep03_v1b.mp4 -c:v copy -af $af -c:a aac -b:a 320k "$o\ep03_v1b_norm.mp4"
ffmpeg -hide_banner -i "$o\ep03_v1b_norm.mp4" -af ebur128=peak=true -f null - 2>&1 | Select-String -Pattern '^\s+(I:|Peak:)' | % Line
ffmpeg -v error -i "$o\ep03_v1b_norm.mp4" -f null -; "decode exit $LASTEXITCODE"
ffmpeg -v error -y -i "$o\ep03_v1b_norm.mp4" -vf scale=720:1280:flags=lanczos -c:v libx264 -preset medium -b:v 1200k -maxrate 1500k -bufsize 3000k -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart "$o\ep03_v1b_720p_phone.mp4"
Get-ChildItem "$o\ep03_v1b*.mp4" | % { "{0} {1:N1} MB" -f $_.Name, ($_.Length/1MB) }
ffprobe -v error -show_entries format=duration:stream=nb_frames -of compact "$o\ep03_v1b_norm.mp4"
"ALL DONE"
