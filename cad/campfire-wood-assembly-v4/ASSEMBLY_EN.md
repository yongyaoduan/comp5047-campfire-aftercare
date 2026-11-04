# Assembly revision V4 - plywood + corner posts

## Correction to the earlier drawings

The earlier V3 printed corner bracket and panel holes were not fully positioned and checked as an assembly. In particular, a bracket placed against the inside of a 3 mm front wall shifts its base-hole center from Y=12 to Y=15 mm. Some other wall corner positions also fail to align with deck holes. Do not fabricate the V3 full-print shell as a verified screw-together kit. This V4 assembly resolves the recommended PLYWOOD route only; it does not validate the full-print route.

## Structure

Use six 6 mm plywood panels and FOUR 10 x 10 x 374 mm wood corner posts. Outer size: 330 W x 230 D x 386 H mm. No internal shelves. Existing tank lid carries the electronics. Bought funnel sits in the roof adapter ring.

Coordinates: X left to right, Y front to rear, Z up. Base occupies Z=0..6. Post locations are X=6..16 or314..324 and Y=6..16 or214..224, extending Z=6..380. Roof underside Z=380. Posts provide roof support. Side/front/back panels extend Z=6..379.6, leaving a 0.4 mm cover clearance.

Between posts: 298 x 198 mm. This fits the 290 x 190 tank, but the lid/handles must also pass through. The illustrated lid envelope of294 x194 is only a reference, NOT a measured lid. If actual lid/handles exceed298 x198, increase box width/depth before fabrication. A 10 mm square post may need straight-grain wood and carefully drilled pilots to avoid splitting.

## Hardware

- Four wood posts, 10 x10 x374 mm.
- Six plywood panels; see cut_list.csv.
- 16 pan-head wood screws, 3 x12 mm (4 front,4 rear,4 each side).
- Eight pan-head wood screws, 3 x20 mm (4 base,4 roof).
- 24 washers sized for 3 mm screws.
- Wood glue for permanent side/rear/post joints. Do NOT glue front or roof.
- Funnel adapter ring: four M3 x18 pan-head machine bolts, washers and nuts (two 6 mm layers). Confirm actual head/nut access after choosing funnel.
- Hose and a matching tank-lid fitting, plus suitable gasket. Actual sizes depend on the purchased funnel/hose.

Panel mounting holes are DIA3.5 THROUGH. Transfer actual post pilots from the assembled panels; start with approximately DIA2 mm pilot and test on spare wood. Do not use 3.5 mm through-holes as wood screw pilot holes. V4 panel holes supersede the earlier plywood sheets that did not specify mounting holes.

## Assembly order

1. Check the actual lid/handles against the298 x198 mm opening. Cut panels/posts. Dry-fit and square the frame before drilling.
2. Place four posts on the base using the coordinates above. Drill DIA3.5 clearance holes through base. Transfer the pilot centers into post ends. Fasten from underside using3 x20 screws, with glue under the fixed posts. Keep the base supported on a flat surface.
3. Fit left, right and rear panels to the posts. Apply wood glue at these permanent joints. Drill panel holes and transfer pilots; use3 x12 screws with washers. Side and rear screws are staggered vertically, so they do not meet inside a10 mm post. Clamp square and let the glue cure.
4. Fit front panel to the FRONT faces of posts. Fasten its four3 x12 screws without glue. The front stays removable for tank access.
5. Fit roof on TOP of the posts. Fasten four3 x20 screws downward into post ends, without glue. Both top and front can be removed independently.
6. Install funnel adapter with four M3 bolts on the roof; see previous roof pattern: DIA190 opening at X220,Y115 and four DIA3.4 holes on PCD200. Adapter bore DIA172 remains provisional. Match and restrain the actual funnel, using a suitable rim adapter/retainer before use. Roof screws at11/319,11/219 do not conflict with these holes.
7. Fit a matching inlet fitting through a clear area of the tank lid. Run the funnel hose to it; leave a disconnectable joint and enough service slack. Mount electronics on their insulating bases on the lid, clear of the inlet and hose.
8. Disconnect power and perform a small-water leak test before installing electronics. Test base/frame with intended water load. The bottom panel should rest on the supporting table; do not carry the filled assembly by its roof/front.

## Service / disassembly

For tank removal: power off -> disconnect inlet hose and external cables -> remove4 front screws -> pull tank forward. If the lid/electronics do not clear the front opening, remove4 roof screws and lift the lid/top-access components first. Never pull against attached wires or hose.

## Drill coordinate table

assembly_drilling.csv uses local panel coordinates in mm, measured from lower-left when looking at that panel's outer face. For front/back, U=X and V=worldZ-6. For side panels, U=worldY-6.2 and V=worldZ-6 (mirror the physical face if viewing from the opposite direction). For base/roof, U=X and V=Y. Read the global convention above when transferring side holes.

The screw axes align with the modeled post centerlines analytically. This is still an untested prototype: no real fit, pullout-strength, loading or leak verification has been completed.
