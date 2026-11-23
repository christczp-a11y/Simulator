# El-Ayyat collision FE deck (OpenRadioss / OpenCourant, LS-DYNA keyword input)

    python gen_deck.py 60        # writes el_ayyat.k (impact speed km/h, illustrative)
    starter -i el_ayyat.k -np 1  # then run the engine on el_ayyat_0001.rad

Units kg-mm-ms. Coach = deformable steel shells (rear end at Y=0), loco = rigid 200 t moving -Y.
Animation output every 5 ms to 450 ms. Convert A### files to VTK for Blender.
