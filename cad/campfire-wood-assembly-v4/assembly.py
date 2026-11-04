from pathlib import Path
import csv,json
import cadquery as cq
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
R=Path(__file__).resolve().parent

def box(w,d,h,x=0,y=0,z=0):return cq.Workplane('XY').box(w,d,h,centered=(False,False,False)).translate((x,y,z))
# Keep the same outer envelope as the earlier 6 mm plywood version.
components=[('Base',box(330,230,6)),('Roof',box(330,230,6,0,0,380)),('Left',box(6,217.6,373.6,0,6.2,6)),('Right',box(6,217.6,373.6,324,6.2,6)),('Back',box(330,6,373.6,0,224,6)),('Front',box(330,6,373.6,0,0,6))]
for x in [6,314]:
 for y in [6,214]:components.append(('Corner post',box(10,10,374,x,y,6)))
# Real positions of all proposed screws; front/back X/Z, side Y/Z, deck X/Y.
rows=[]
def holes(part,coords,diam,fastener):
 for i,(u,v) in enumerate(coords,1):rows.append({'part':part,'hole':f'H{i:02d}','u_mm':u,'v_mm':v,'diameter_mm':diam,'fastener':fastener})
xy=[(11,11),(319,11),(11,219),(319,219)]
holes('Base',xy,3.5,'3 x 20 mm wood screw; into corner post')
holes('Roof',xy,3.5,'3 x 20 mm wood screw; removable')
holes('Front',[(x,z) for x in [11,319] for z in [34,324]],3.5,'3 x 12 mm wood screw; removable')
holes('Back',[(x,z) for x in [11,319] for z in [114,234]],3.5,'3 x 12 mm wood screw')
for part in ['Left','Right']:holes(part,[(u,z) for u in [4.8,212.8] for z in [74,274]],3.5,'3 x 12 mm wood screw')
# Intersections with each corner post are geometrically consistent; check dimensions.
assert 314-16==298 and 214-16==198
assert 298>294 and 198>194 # reference lid envelope only; measured lid still required
with open(R/'assembly_drilling.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
with open(R/'cut_list.csv','w') as f:
 w=csv.writer(f);w.writerow(['Part','Qty','Width','Height_or_length','Thickness','Units'])
 for row in [('Base',1,330,230,6),('Roof',1,330,230,6),('Front / Back',2,330,373.6,6),('Left / Right',2,217.6,373.6,6),('Corner post',4,10,374,10)]:w.writerow([*row,'mm'])
fig=plt.figure(figsize=(14,8))
for panel,exploded in [(121,False),(122,True)]:
 ax=fig.add_subplot(panel,projection='3d')
 for name,p in components:
  if not exploded and name in ['Front','Left','Roof']:continue
  if exploded:
   off={'Front':(0,-80,0),'Roof':(0,0,75),'Left':(-55,0,0)}.get(name,(0,0,0));p=p.translate(off)
  color='#ae7846' if name=='Corner post' else '#d4c1a4'
  v,t=p.val().tessellate(2);v=[(q.x,q.y,q.z) for q in v]
  ax.add_collection3d(Poly3DCollection([[v[j] for j in tri] for tri in t],facecolor=color,edgecolor='#756959',linewidth=.25,alpha=.85))
 if not exploded:
  p=box(290,190,150,20,20,6);v,t=p.val().tessellate(2);v=[(q.x,q.y,q.z) for q in v];ax.add_collection3d(Poly3DCollection([[v[j] for j in tri] for tri in t],facecolor='#6baac6',alpha=.35))
  ax.text(20,30,340,'4 x 10 x 10 mm\nCORNER POSTS',fontsize=9)
 ax.set_title('Frame + tank / covers removed' if not exploded else 'Exploded / front and roof removable',fontsize=12)
 ax.set_xlim(-60,350);ax.set_ylim(-90,250);ax.set_zlim(0,470);ax.set_box_aspect((410,340,470));ax.view_init(23,-57);ax.set_xlabel('X mm');ax.set_ylabel('Y mm');ax.set_zlabel('Z mm')
fig.suptitle('ASSEMBLY REVISION V4 | 6 mm plywood + four corner posts\n330 x 230 x 386 mm | Tank opening between posts: 298 x 198 mm',fontsize=14)
fig.text(.03,.02,'Connection concept and drilling coordinates verified analytically; physical fit/load/leak tests still required.\nRoof funnel opening/adapter follow the earlier layout and are omitted here to expose the corner-post connections.',fontsize=9)
fig.tight_layout(rect=(0,.06,1,.93));fig.savefig(R/'assembly_exploded.png',dpi=150)
(R/'checks.json').write_text(json.dumps({'outer_mm':[330,230,386],'post_mm':[10,10,374],'opening_between_posts_mm':[298,198],'tank_mm':[290,190,150],'reference_lid_only_mm':[294,194],'lid_not_measured':True,'hole_axes_to_post_centers_checked':True,'physical_tested':False},indent=2))
print('Assembly diagram and 24 panel mounting holes exported.')
