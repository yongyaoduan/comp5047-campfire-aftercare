# Simple enclosure v3 (3D-print design; historical — the final build is the v4 plywood box)

> This folder is the v3 design for a 3D-printed shell. It was replaced by the v4 7 mm plywood box (see the report, §11) because printing needed about 50 h and the brackets did not align as an assembly. It is kept as a record of the design process. The dimensions below were provisional and were never physically tested.

## v3 update: space for components and the power strip

Above the tank lid a 100 × 100 mm footprint with 150 mm clear height is reserved (default x 25–125, y 25–125, z 156–306). The pink transparent block in the preview is that reserved space, not a new divider or box. The existing circuit is still fixed to the lid. The shell grows to 330 × 230 × 383 mm (without the fixing ring); the lowest reference point of the funnel is at 324 mm, about 18 mm above the top of the reserved space. Treat this height as a first version; it can shrink once the plugs and cable bends have been measured.

100 × 100 mm does not guarantee room for an ordinary long power strip, nor for every component in the photos. It is only an extra reserved area; the components still use the whole tank lid. Measure the power strip housing (length, width, height and the total height with plugs inserted), and allow for power-cord bends and USB connections. If any side of the strip exceeds 100 mm, move it on the remaining lid area or place it outside the shell.

If "power strip" means a 220–240 V mains strip, keep it outside the box and bring only the existing 5 V / 12 V low-voltage leads inside; this model does not make the reserved space near the water inlet a waterproof mains enclosure. Do a leak check with the power off first.

## Simple enclosure v3

Based on photo IMG_0922 and the team's corrections: all internal dividers, electronics trays and the separate wet channel are removed. The shell only encloses the tank and the parts on its lid, and the top supports the purchased funnel. v1 is kept for reference; use this folder for this version.

## Dimensions and structure

Tank 290 × 190 × 150 mm (measured); printed shell 330 × 230 × 383 mm, 389 mm high including the 6 mm top fixing ring. Base 3 mm; inside 324 × 224 mm. About 17 mm clearance around the tank for the lid flange and tubing; re-measure how far the clip latches stick out.

The tank lid itself is the electronics mounting surface. Boards sit on insulating standoffs, the Raspberry Pi stays in its own case, and the standoffs are glued to the lid; there is no separate tray. The electronics blocks in the drawings only show positions, not real hole patterns. Hole positions and USB plug space follow the real layout.

The large top hole is 190 mm in diameter, centred at x 220, y 115 mm (origin at the front-left corner). A flat adapter ring (outer 210, inner 172, 6 mm thick) sits on it, fixed to the top panel with four M3 bolts on a 100 mm radius at 45/135/225/315°. The funnel cone sits in the ring near its rim, with about 5 mm of the rim showing; with a thin rubber strip it is held by removable silicone dots or by the funnel's own rim. The round hole alone does not stop it being pulled out.

**The funnel had not been bought or measured: the 180 mm mouth, 70 mm cone height and 172 mm seat diameter are provisional.** After measuring the real funnel, change the hole and reference body in `build.py`. The key measurement is the outer diameter 5 mm below the rim, not the outlet diameter. Ring bore = that diameter + measured fit clearance (start with a 0.6 mm diameter test piece). If the funnel has no rim or the taper does not match, change the ring; do not force it in.

The tube runs from the funnel outlet straight into the tank lid. Keep a separate inlet area on the lid (default x 220, y 115, at least 40 mm diameter, no electronics), and use a matching fitting and washer between tube and lid hole; buy the fitting to the real tube size. The drawing shows a vertical tube; if it clashes with existing parts, move the inlet sideways and connect it with a short hose. Do not fill this area with components.

Design references: tank top z 153 mm, highest component (schematic) z 186 mm, reserved 100 × 100 × 150 mm space (z 156–306 mm), funnel cone bottom z 324 mm. If the tallest real component exceeds 306 mm, re-check the clearance to the funnel and raise the shell if needed. Before lifting the tank out, remove the front panel and disconnect the inlet tube and cables; do not pull the lid out with the tube attached.

## Two ways to build it

**Plywood (preferred):** `wood_cut_list.csv`, 6 mm plywood. Only six large panels: base, top, front, back, left and right. The front panel is removable; the others are glued or fixed with corner brackets. Outside height 386 mm, inside 318 × 218 mm. Cut the top panel with the round hole and four bolt holes as above. Only the funnel adapter ring needs printing (the wooden corners can use bought brackets). If the panel thickness changes, recalculate the side-panel depth.

**Fully printed:** `stl/` holds 20 part types; quantities in `parts.csv`. Base and top are each printed in two halves; the walls in an upper and a lower section to fit a 256 mm print bed, with no horizontal shelf inside. M3 corner brackets join base/top to the walls; 4 seam strips join the left and right seams of the top and base (2 each, end holes 40 mm apart); 6 seam strips rotated 90° join the upper and lower wall sections (extra holes at local x 30 on each wall, world z 170/210, 40 mm apart); 2 are spares. The front panel stays bolted so it can be removed. Front/back and side seams can be glued after a trial fit, or joined with backing strips. Bracket and panel holes must be located at the trial fit and drilled if needed; a perfect fit without adjustment is not guaranteed.

The STLs use 3.4 mm through-holes for M3 bolts and nuts, not self-tapping holes. Not all hardware is modelled. All STLs passed closed-mesh, positive-volume and 256 mm size checks; load, leak and fit were not tested physically. Print the M3_fit_coupon, one corner bracket and a ring test piece for the real funnel first.

Load on the base centre seam is unverified; do a load test before filling with water. A single wooden base is better for load. After drilling the tank lid, fill it with the power off to check the fittings seal and that no overflow reaches the electronics, then fit the components. The shell itself is not waterproof and does not replace the lidded tank.

## Files

- `preview.png`: section view from the real CAD (front and left walls removed); funnel, tank and electronics blocks are only spatial references.
- `simple_enclosure.step`: editable layout reference; do not print it as one piece.
- `stl/*.stl`: individual parts. `parts.csv`: quantities and sizes. `wood_cut_list.csv`: plywood cut list. `checks.json`: mesh-check results. `build.py`: parametric source; rebuild with Python 3.12, cadquery, trimesh and matplotlib.
- `three_view_english.py` and `drawings_english/`: English three-view drawings (`dimension_drawings.py` is the older version with Chinese labels).
