# El-Ayyat collision FE deck (OpenRadioss / OpenCourant, LS-DYNA keyword input)

    python gen_deck.py 60        # writes el_ayyat.k (impact speed km/h, illustrative)
    starter -i el_ayyat.k -np 1  # then run the engine on el_ayyat_0001.rad

Units kg-mm-ms. Coach = deformable steel shells (rear end at Y=0), loco = rigid 200 t moving -Y.
Animation output every 5 ms to 450 ms. Convert A### files to VTK for Blender.

## Run on this PC (2026-11-23)

    C:\YouTubeNeuropolis\tools\run_radioss.bat el_ayyat.k 6
    python export_frames.py 2    # every 2nd anim file = 10 ms -> out/frames.npz

Solver: OpenCourant latest-20261011 win64 (community continuation of OpenRadioss).
60 km/h run: 97,736 cycles, 55 min 45 s on i5-11400F with 6 threads, ~650 MB RAM, energy error -5.5% at 450 ms.
out/frames.npz: t (46,), xyz (46,133124,3) mm, deleted (46,133002) bool, quads (133002,4) indices into node_id,
node_id, elem_id, part_id (20 = rigid loco). 2432 coach shells eroded by 450 ms.
