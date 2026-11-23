# Wait for hook frame 129, stop Blender, build s01 = flash (s01h 109-129) + s01h 1-129, render v2, normalise, 720p.
$w = 'C:\YouTubeNeuropolis\Out\ep03-egypt-train\work'; $o = 'C:\YouTubeNeuropolis\Out\ep03-egypt-train'
$src = "$w\render_s01h\s01h"
while (-not (Test-Path "$src\s01h_0129.png")) { Start-Sleep 5 }
Start-Sleep 3
Get-Process blender -ErrorAction SilentlyContinue | Stop-Process -Force
"blender stopped $(Get-Date -Format HH:mm:ss)"
Remove-Item "$w\frames\s01" -Recurse -Force
New-Item -ItemType Directory "$w\frames\s01" | Out-Null
for ($i = 1; $i -le 150; $i++) {
    $from = if ($i -le 21) { 108 + $i } else { $i - 21 }
    Copy-Item ("$src\s01h_{0:D4}.png" -f $from) ("$w\frames\s01\s01_{0:D4}.png" -f $i)
}
"frames s01: $((Get-ChildItem "$w\frames\s01").Count)"
$pub = "$w\remotion\public"
if (-not (Test-Path "$pub\sfx_mix_horn55.wav")) { Copy-Item "$pub\sfx_mix.wav" "$pub\sfx_mix_horn55.wav" }
Copy-Item "$pub\sfx_mix_cand.wav" "$pub\sfx_mix.wav" -Force
Set-Location "$w\remotion"
$t = Get-Date
node render_pc.mjs ..\frames ..\ep03_v2.mp4 8 *> ..\render_v2_log.txt
"render exit $LASTEXITCODE $([int]((Get-Date)-$t).TotalSeconds)s"
Set-Location $w
$m = ffmpeg -hide_banner -i ep03_v2.mp4 -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | Out-String
$js = ($m -split "`n" | Select-String -Pattern '"input_i"|"input_tp"|"input_lra"|"input_thresh"|"target_offset"' | % { $_.Line.Trim().TrimEnd(',') }) -join ','
$p = "{$js}" | ConvertFrom-Json
$af = "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$($p.input_i):measured_TP=$($p.input_tp):measured_LRA=$($p.input_lra):measured_thresh=$($p.input_thresh):offset=$($p.target_offset):linear=true,aresample=192000,alimiter=limit=0.79:level=false:attack=1:release=50,aresample=48000"
ffmpeg -v error -y -i ep03_v2.mp4 -c:v copy -af $af -c:a aac -b:a 320k "$o\ep03_v2_norm.mp4"
ffmpeg -hide_banner -i "$o\ep03_v2_norm.mp4" -af ebur128=peak=true -f null - 2>&1 | Select-String -Pattern '^\s+(I:|Peak:)' | % Line
ffmpeg -v error -i "$o\ep03_v2_norm.mp4" -f null -; "decode exit $LASTEXITCODE"
ffmpeg -v error -y -i "$o\ep03_v2_norm.mp4" -vf scale=720:1280:flags=lanczos -c:v libx264 -preset medium -b:v 1200k -maxrate 1500k -bufsize 3000k -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart "$o\ep03_v2_720p_phone.mp4"
Get-ChildItem "$o\ep03_v2*.mp4" | % { "{0} {1:N1} MB" -f $_.Name, ($_.Length/1MB) }
"ALL DONE $(Get-Date -Format HH:mm:ss)"
