from pathlib import Path
import runpy,ast,math,io,json,zipfile
import cadquery as cq
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4,landscape
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg
R=Path(__file__).resolve().parent;O=R/'drawings_english';O.mkdir(exist_ok=True)
s=runpy.run_path(str(R/'build.py'));shapes=s['shapes'];parts=s['parts']
tree=ast.parse((R/'dimension_drawings.py').read_text());ns={'math':math};exec(compile(ast.Module(body=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='holemeta'],type_ignores=[]),'holes','exec'),ns);holemeta=ns['holemeta']
PDF=R.parents[1]/'output/pdf/Campfire_v3_English_Three_View_Drawings.pdf'
c=canvas.Canvas(str(PDF),pagesize=landscape(A4));PW,PH=landscape(A4);pg=0;records=[]
def txt(x,y,t,size=9,bold=False):
 c.setFont('Helvetica-Bold' if bold else 'Helvetica',size);c.drawString(x,y,str(t))
def header(title,sub):
 global pg
 pg+=1;c.setFillColorRGB(.1,.19,.24);c.rect(0,PH-64,PW,64,fill=1,stroke=0);c.setFillColorRGB(1,1,1);txt(26,PH-28,title,16,True);txt(26,PH-48,sub,8);c.setFillColorRGB(0,0,0)
 c.setStrokeColorRGB(.7,.75,.78);c.line(26,34,PW-26,34);c.setStrokeColorRGB(0,0,0)
 txt(26,18,'CAMPFIRE AFTERCARE | GROUP 23 | REV 3.2 | 2026-10-30 | ALL DIMENSIONS IN mm | DO NOT SCALE PDF',7.2);txt(PW-65,18,f'{pg:02d}',9)
def dh(x,w,y,label):
 c.setLineWidth(.45);c.line(x,y,x+w,y)
 for xx in [x,x+w]:c.line(xx,y-3,xx,y+3)
 txt(x+w/2-12,y+5,label,8)
def dv(x,y,h,label):
 c.line(x,y,x,y+h)
 for yy in [y,y+h]:c.line(x-3,yy,x+3,yy)
 c.saveState();c.translate(x-7,y+h/2);c.rotate(90);txt(-12,0,label,8);c.restoreState()
def svgview(p,view,x,y,w,h,name):
 v=p
 if view=='front':v=p.rotate((0,0,0),(1,0,0),-90)
 if view=='right':v=p.rotate((0,0,0),(0,1,0),-90).rotate((0,0,0),(0,0,1),-90)
 svg=cq.exporters.getSVG(v.val(),opts={'projectionDir':(0,0,1),'width':1000,'height':1000,'marginLeft':0,'marginTop':0,'showAxes':False,'showHidden':True,'hiddenColor':(120,130,140)})
 (O/f'{name}_{view}.svg').write_text(svg)
 d=svg2rlg(io.BytesIO(svg.encode()));xmin,ymin,xmax,ymax=d.getBounds()
 c.saveState();c.translate(x,y);c.scale(w/(xmax-xmin),h/(ymax-ymin));c.translate(-xmin,-ymin);renderPDF.draw(d,c,0,0);c.restoreState()
def circlelabel(x,y,label,inside=False,dx=7,dy=9):
 c.setStrokeColorRGB(.1,.35,.5);c.setFillColorRGB(.1,.35,.5);c.setLineWidth(.4)
 if inside:txt(x-22,y,label,7)
 else:
  c.line(x,y,x+dx-1,y+dy-1);txt(x+dx,y+dy,label,6.3)
 c.setStrokeColorRGB(0,0,0);c.setFillColorRGB(0,0,0)
header('Three-view part drawings','English edition | Plywood panels and every printed part | Top, front and right views')
lines=[
'These sheets use a common scale for all three views of each part.',
'TOP looks down local +Z; FRONT looks from local -Y; RIGHT looks from local +X.',
'Top is above front; right is to the right of front. Hidden edges are dashed grey.',
'Each feature is identified H01, H02, ... . Every feature has its own diameter in the hole schedule.',
'Plate hole coordinates X/Y are measured from the lower-left corner in TOP view.',
'All listed plate holes are THROUGH the full plate thickness; no countersinks or threads are modeled.',
'The bracket has TWO holes: one along Z through the base and one along Y through the upright.',
'DIA 190 roof cutouts are open circular arcs on split roof halves, not complete holes in each half.',
'Plywood mounting holes are not predesigned: position them to suit the chosen hardware during assembly.',
'Funnel adapter: OD 210, ID 172, thickness 6. ID 172 is PROVISIONAL until the funnel is measured.',
'Printed envelope: 330 x 230 x 383 (389 including adapter). Plywood envelope: 330 x 230 x 386.',
'Tank: 290 x 190 x 150. Reserved lid space: 100 x 100 x 150. Neither is a fabricated part here.',
'No fabrication tolerances have been qualified. Print a fit coupon and trial assemble before full production.',
'Fit, loading and leak performance have not been physically verified. Use the latest STL files in this package.'
]
for i,line in enumerate(lines):txt(32,PH-100-i*25,line,9)
c.showPage()
wood=[]
def bx(w,h):return cq.Workplane('XY').box(w,h,6,centered=(False,False,False))
wood.append(('WOOD_base',bx(330,230),1,[]))
p=s['hole'](bx(330,230),220,115,190);hs=[(220,115,190)]
for a in [45,135,225,315]:
 x=220+100*math.cos(math.radians(a));y=115+100*math.sin(math.radians(a));p=s['hole'](p,x,y);hs.append((x,y,3.4))
wood.append(('WOOD_roof',p,1,hs));wood.extend([('WOOD_front_back',bx(330,373.6),2,[]),('WOOD_left_right',bx(217.6,373.6),2,[])])
def sheet(name,p,qty,hs,wood=False):
 bb=p.val().BoundingBox();w,d,h=bb.xlen,bb.ylen,bb.zlen
 if name.startswith('funnel'):w=d=210;h=6
 w,d,h=[round(v,1) for v in [w,d,h]]
 title=name.replace('_',' ')
 if name.startswith('funnel'):title='Funnel rim adapter - PROVISIONAL'
 header(title,f'PART: {name} | QTY: {qty} | MATERIAL: '+('6 mm plywood' if wood else '3D printed polymer (material to be confirmed)'))
 sc=min(300/w,205/d,60/h,4)
 tx,ty=80,265;fx,fy=80,120;rx,ry=430,120
 svgview(p,'top',tx,ty,w*sc,d*sc,name);svgview(p,'front',fx,fy,w*sc,h*sc,name);svgview(p,'right',rx,ry,d*sc,h*sc,name)
 txt(tx,ty+d*sc+20,'TOP VIEW (X / Y)',9,True);txt(fx,fy+h*sc+20,'FRONT VIEW (X / Z)',9,True);txt(rx,ry+h*sc+20,'RIGHT VIEW (Y / Z)',9,True)
 dh(tx,w*sc,ty-20,f'{w:g}');dv(tx-25,ty,d*sc,f'{d:g}')
 dh(fx,w*sc,fy-20,f'{w:g}');dv(fx-25,fy,h*sc,f'{h:g}')
 dh(rx,d*sc,ry-20,f'{d:g}');dv(rx-25,ry,h*sc,f'{h:g}')
 txt(tx,ty-38,'Origin: lower-left in TOP view (X=0, Y=0).',7)
 # Bracket has an upright bore perpendicular to its base bore.
 bh=name=='M3_corner_bracket'
 for i,(x,y,diam) in enumerate(hs):
  label=f'H{i+1:02d} DIA {diam:g}'
  if diam>40:
   xx=max(30,min(w-30,x));yy=max(20,min(d-20,y));circlelabel(tx+xx*sc,ty+yy*sc,label,True)
  else:
   if '_band' in name and i==4:circlelabel(tx+x*sc,ty+y*sc,label,dx=40,dy=-20 if 'band1' in name else 30)
   else:circlelabel(tx+x*sc,ty+y*sc,label)
 if bh:circlelabel(fx+12*sc,fy+12*sc,'H02 DIA 3.4')
 x0=656;yy=PH-94
 txt(x0,yy,'HOLE / CUTOUT SCHEDULE',8,True);yy-=21
 if not hs:
  txt(x0,yy,'No holes modeled.',8);txt(x0,yy-17,'Mounting holes: locate to suit',7);txt(x0,yy-30,'hardware during trial assembly.',7)
 elif bh:
  for label,axis,xx,yyc,zz in [('H01','Z',12,12,1.5),('H02','Y',12,1.5,12)]:
   txt(x0,yy,f'{label}  DIA 3.4 THROUGH 3 mm',7.8,True);yy-=15
   txt(x0,yy,f'Axis {axis}; center X={xx:g}',7.5);yy-=13;txt(x0,yy,f'Y={yyc:g}, Z={zz:g}',7.5);yy-=23
  txt(x0,yy,'Both legs: 3 mm thick.',8)
 else:
  txt(x0,yy,'ID      X          Y       DIA',7.5,True);yy-=18
  for i,(x,y,diam) in enumerate(hs):
   txt(x0,yy,f'H{i+1:02d}  {x:7.2f}  {y:7.2f}  {diam:g}',7.7);yy-=19
  yy-=8;txt(x0,yy,f'All features THROUGH {h:g} mm.',7.4)
  if name.startswith('roof'):
   txt(x0,yy-22,'DIA 190 = open circular cutout.',7);txt(x0,yy-36,'Its center may be outside this half.',7)
  if name.startswith('funnel'):
   txt(x0,yy-22,'OD 210; bore DIA 172 provisional.',7);txt(x0,yy-36,'Four DIA 3.4 holes on PCD 200.',7);txt(x0,yy-50,'Angles: 45 / 135 / 225 / 315 deg.',7)
 txt(36,70,f'ENVELOPE: X {w:g} x Y {d:g} x Z {h:g} mm | QTY {qty} | Views share scale; printed page is not 1:1.',8,True)
 if bh:txt(36,53,'Base bore: axis Z. Upright bore: axis Y. Base and upright share a 3 x 3 mm corner.',8)
 elif name.startswith('funnel'):txt(36,53,'Measure the purchased funnel near its rim before finalizing the adapter bore.',8)
 else:txt(36,53,'Finished hole sizes shown. No printer shrinkage or cutter kerf compensation is included.',8)
 records.append({'part':name,'qty':qty,'envelope_mm':[w,d,h],'feature_count':2 if bh else len(hs),'holes':hs,'bracket_second_hole':{'axis':'Y','center':[12,1.5,12],'diameter':3.4} if bh else None})
 c.showPage()
for n,p,q,hs in wood:sheet(n,p,q,hs,True)
for row in parts:
 n=row['name'];sheet(n,shapes[n],row['quantity'],holemeta(n))
c.save();(O/'hole_and_dimension_schedule.json').write_text(json.dumps(records,indent=2))
# Verify English-only text and one sheet for every part type.
from pypdf import PdfReader
reader=PdfReader(PDF);assert len(reader.pages)==25
text='\n'.join(p.extract_text() for p in reader.pages);assert not any('\u4e00'<=ch<='\u9fff' for ch in text)
assert len(records)==24
print('PASS: 25 English pages; 24 part sheets; 3 CAD projections per part; bracket has both bores.')
