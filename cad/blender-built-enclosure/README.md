# Blender models of the built enclosure (Charan)

- `build_woodwork_model.py` → builds the woodwork only: five glued 7 mm plywood panels and the removable L-shaped roof (115 × 95 mm corner notch for the funnel). `Campfire_Aftercare_Woodwork.glb` is the exported model.
- `build_leaf_model.py` + `Campfire_Aftercare_Leaf_Camouflage.glb` → imports the finished-station model (trellis, artificial leaves, roof funnel, webcam, LEDs, MLX90614, open tube, indicative tank and electronics) and organises it into a native `.blend`.

Run either script in Blender 4.x (Scripting → Open → Run Script) with the GLB in the same folder; it saves a `.blend` beside the script. Panel dimensions follow the 7 mm cut list; leaf layout and interior are approximate.

`renders_woodwork_and_leaf.png` is Figure 9 of the final report.
