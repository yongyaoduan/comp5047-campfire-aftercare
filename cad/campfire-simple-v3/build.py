from pathlib import Path
import math,json,csv,zipfile
import cadquery as cq
import trimesh
R=Path(__file__).resolve().parent;O=R/'stl';O.mkdir(exist_ok=True)
W,D,H,T=330,230,380,3
FX,FY=220,115 # reserve lid entry at this position; adjust to actual electronics layout
parts=[];assembly=[];shapes={}
def box(x,y,z):return cq.Workplane('XY').box(x,y,z,centered=(False,False,False))
def hole(p,x,y,d=3.4):return p.cut(cq.Workplane('XY').center(x,y).circle(d/2).extrude(20,both=True))
def reg(n,p,q=1):
 assert p.val().isValid(),n
 shapes[n]=p
 cq.exporters.export(p,str(O/(n+'.stl')),tolerance=.08)
 m=trimesh.load_mesh(O/(n+'.stl'));assert m.is_watertight and m.is_winding_consistent and m.volume>0 and max(m.extents)<256,n
 parts.append(dict(name=n,quantity=q,x=round(m.extents[0],2),y=round(m.extents[1],2),z=round(m.extents[2],2),volume_cm3=round(m.volume/1000,2)))
 return p
for name,z in [('base',0),('roof',H)]:
 for k in [0,1]:
  p=box(W/2,D,T)
  for x in [12,W/2-20]:
   for y in [12,D-12]:p=hole(p,x if k==0 else W/2-x,y)
  if name=='roof':
   p=hole(p,FX-k*W/2,FY,190)
   for a in [45,135,225,315]:
    x=FX+100*math.cos(math.radians(a))-k*W/2;y=FY+100*math.sin(math.radians(a))
    if 0<x<W/2:p=hole(p,x,y)
  p=reg(f'{name}_{k+1}',p);assembly.append((name,p.translate((k*W/2,0,z))))
for band in range(2):
 height=(H/2-.4 if band==0 else H/2-T-.4);z=T+band*H/2
 for face in ['front','back']:
  for k in range(2):
   p=box(W/2-.2,height,T)
   for x in [12,W/2-20]:
    for y in [12,height-12]:p=hole(p,x,y)
   # no fixed webcam/LED holes until actual hardware layout is known
   p=hole(p,30,H/2-23 if band==0 else 17) # vertical seam strap, world seam minus/plus20
   p=reg(f'{face}_band{band+1}_{k+1}',p)
   assembly.append((face,p.rotate((0,0,0),(1,0,0),90).translate((k*W/2,T if face=='front' else D,z))))
 for face in ['left','right']:
  p=box(D-2*T-.4,height,T)
  for x in [12,D-2*T-.4-12]:
   for y in [12,height-12]:p=hole(p,x,y)
  p=hole(p,30,H/2-23 if band==0 else 17)
  p=reg(f'{face}_band{band+1}',p)
  assembly.append((face,p.rotate((0,0,0),(1,0,0),90).rotate((0,0,0),(0,0,1),90).translate((0 if face=='left' else W-T,T+.2,z))))
# Single flat ring: catches purchased funnel near the upper lip, no low shelf.
p=cq.Workplane('XY').center(105,105).circle(105).circle(86).extrude(6)
for a in [45,135,225,315]:p=hole(p,105+100*math.cos(math.radians(a)),105+100*math.sin(math.radians(a)))
p=reg('funnel_rim_adapter_ID172_OD210_PROVISIONAL',p)
assembly.append(('ring',p.translate((FX-105,FY-105,H+T))))
p=box(24,24,3).union(box(24,3,24));p=hole(p,12,12)
p=p.cut(cq.Workplane('XZ').center(12,12).circle(1.7).extrude(10,both=True));reg('M3_corner_bracket',p,24)
p=box(64,20,3)
for x in [12,52]:p=hole(p,x,10)
reg('seam_strap',p,12)
p=hole(box(30,30,3),15,15);reg('M3_fit_coupon',p)
cq.exporters.export(cq.Compound.makeCompound([p.val() for _,p in assembly]),str(R/'simple_enclosure.step'))
with open(R/'parts.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=parts[0].keys());w.writeheader();w.writerows(parts)
with open(R/'wood_cut_list.csv','w') as f:
 w=csv.writer(f);w.writerow(['part','qty','width_mm','height_mm','thickness_mm','notes'])
 w.writerow(['base / roof',2,330,230,6,'roof only: diameter190 at x220 y115; 4 holes radius100 at45/135/225/315deg'])
 w.writerow(['front / back',2,330,373.6,6,'front removable; no horizontal seam in wood'])
 w.writerow(['left / right',2,217.6,373.6,6,'between front and back'])
(R/'checks.json').write_text(json.dumps({'dimensions_mm':[W,D,H+T],'tank_mm':[290,190,150],'reserved_electrical_space_mm':[100,100,150],'all_stls_watertight':True,'all_stls_positive_volume':True,'all_parts_fit_256':True,'printed_volume_cm3':round(sum(p['volume_cm3']*p['quantity'] for p in parts),1),'fit_tested':False,'funnel_interface':'provisional 180mm mouth assumed; ring172mm bore; measure actual cone'},indent=2))
# Actual CAD cutaway preview with purchased objects and symbolic electronics.
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
fig=plt.figure(figsize=(12,9));ax=fig.add_subplot(111,projection='3d')
def draw(p,c,alpha=1):
 v,t=p.val().tessellate(1);v=[(q.x,q.y,q.z) for q in v]
 ax.add_collection3d(Poly3DCollection([[v[i] for i in tri] for tri in t],facecolor=c,edgecolor='none',alpha=alpha))
for name,p in assembly:
 if name in ['front','left']:continue
 draw(p,'#d4c1a4',.3 if name in ['back','right'] else 1)
draw(box(290,190,150).translate((20,20,3)),'#7ebbd1',.35)
draw(box(294,194,3).translate((18,18,153)),'#7ebbd1',.6)
for x,y,w,d in [(35,35,95,65),(35,115,90,60),(140,140,45,55)]:draw(box(w,d,30).translate((x,y,156)),'#537c6c')
f=cq.Workplane('XY').workplane(offset=324).circle(15).workplane(offset=70).circle(90).loft().cut(cq.Workplane('XY').workplane(offset=324).circle(12).workplane(offset=71).circle(89).loft())
# Reserved clear volume: visual reference, NOT a printed box or shelf
reserved=box(100,100,150).translate((25,25,156))
draw(reserved,'#ce6985',.18)
ax.text(25,25,311,'100 x 100 x 150 mm\nRESERVED ELECTRICAL SPACE',fontsize=9)
draw(f.translate((FX,FY,0)),'#e1a045',.65)
draw(cq.Workplane('XY').center(FX,FY).circle(12).circle(9).extrude(175).translate((0,0,149)),'#739bae')
ax.set_xlim(0,360);ax.set_ylim(-10,245);ax.set_zlim(0,430);ax.set_box_aspect((360,255,430));ax.view_init(25,-57)
ax.set_xlabel('Width mm');ax.set_ylabel('Depth mm');ax.set_zlabel('Height mm')
ax.set_title('Simple enclosure v3 | 330 x 230 x 383 mm\nFront/left removed for view | NO internal shelves\nBought funnel recessed into roof; electronics mounted on tank lid',fontsize=13,pad=20)
fig.text(.02,.03,'Reference tank: 290 x 190 x 150 mm. Funnel geometry and electronics blocks are illustrative.\nAdapter bore 172 mm is provisional; fit to the purchased funnel before printing.',fontsize=10)
fig.savefig(R/'preview.png',dpi=160,bbox_inches='tight')
print('PASS',len(parts),'STL types; watertight, positive volume and bed size checked')
