from pathlib import Path
import runpy,math,csv,json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4,landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import cadquery as cq
R=Path(__file__).resolve().parent;out=R/'drawings';dx=out/'dxf';dx.mkdir(parents=True,exist_ok=True)
s=runpy.run_path(str(R/'build.py'));shapes=s['shapes'];parts=s['parts']
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
PDF=R.parents[1]/'output/pdf/Campfire_v3_2D_Dimensions.pdf';PDF.parent.mkdir(parents=True,exist_ok=True)
c=canvas.Canvas(str(PDF),pagesize=landscape(A4));PW,PH=landscape(A4);page=0

def text(x,y,t,size=10):
 c.setFont('STSong-Light',size);c.drawString(x,y,str(t).replace('Ø','Dia '))
def header(title,sub):
 global page
 page+=1;c.setFillColorRGB(.12,.2,.25);c.rect(0,PH-66,PW,66,fill=1,stroke=0);c.setFillColorRGB(1,1,1);text(28,PH-29,title,18);text(28,PH-49,sub,10);c.setFillColorRGB(0,0,0)
 text(28,18,'Campfire Aftercare | Group 23 | Rev v3.1 | 2026-10-30 | 单位 mm / Do not scale the PDF',9);text(PW-90,18,f'{page:02d}',10)
 c.setStrokeColorRGB(.75,.78,.8);c.line(28,35,PW-28,35);c.setStrokeColorRGB(0,0,0)
def dh(x1,x2,y,label):
 c.setLineWidth(.5);c.line(x1,y,x2,y)
 for x in [x1,x2]:c.line(x,y-4,x,y+4)
 c.setFillColorRGB(1,1,1);c.rect((x1+x2)/2-27,y-5,54,13,fill=1,stroke=0);c.setFillColorRGB(0,0,0);text((x1+x2)/2-22,y-2,label,10)
def dv(y1,y2,x,label):
 c.line(x,y1,x,y2)
 for y in [y1,y2]:c.line(x-4,y,x+4,y)
 c.saveState();c.translate(x-8,(y1+y2)/2);c.rotate(90);text(-20,0,label,10);c.restoreState()
def profile(shape,thick,x=90,y=115,maxw=460,maxh=350):
 section=shape.section(height=thick/2)
 bb=shape.val().BoundingBox();w,h=bb.xlen,bb.ylen
 if abs(w-210)<.2 and abs(h-210)<.2:w=h=210
 scale=min(maxw/w,maxh/h)
 c.setLineWidth(.8)
 for ed in section.val().Edges():
  N=2 if ed.geomType()=='LINE' else 120
  pp=[ed.positionAt(i/(N-1)) for i in range(N)]
  path=c.beginPath();path.moveTo(x+(pp[0].x-bb.xmin)*scale,y+(pp[0].y-bb.ymin)*scale)
  for q in pp[1:]:path.lineTo(x+(q.x-bb.xmin)*scale,y+(q.y-bb.ymin)*scale)
  c.drawPath(path)
 dh(x,x+w*scale,y-22,f'{w:.1f}');dv(y,y+h*scale,x-23,f'{h:.1f}')
 text(x,y-43,'(0,0) 左下角 / lower-left origin',9)
 return section

def holemeta(n):
 if n.startswith(('base','roof')):
  k=int(n[-1])-1;xs=[12,145] if k==0 else [153,20]
  hs=[(x,y,3.4) for x in xs for y in [12,218]]
  if n.startswith('roof'):
   hs.append((220-k*165,115,190))
   for a in [45,135,225,315]:
    x=220+100*math.cos(math.radians(a))-k*165;y=115+100*math.sin(math.radians(a))
    if 0<x<165:hs.append((x,y,3.4))
  return hs
 if '_band' in n:
  b=0 if 'band1' in n else 1;h=189.6 if b==0 else 186.6;w=164.8 if n.startswith(('front','back')) else 223.6
  xs=[12,145] if w==164.8 else [12,w-12]
  return [(x,y,3.4) for x in xs for y in [12,h-12]]+[(30,167 if b==0 else 17,3.4)]
 if n.startswith('funnel'):return [(105,105,172)]+[(105+100*math.cos(math.radians(a)),105+100*math.sin(math.radians(a)),3.4) for a in [45,135,225,315]]
 if n=='seam_strap':return [(12,10,3.4),(52,10,3.4)]
 if n=='M3_fit_coupon':return [(15,15,3.4)]
 return [(12,12,3.4)]
header('二维零件尺寸图 / 2D part drawings','木板方案 + 全打印方案 | Based on revised v3 CAD; funnel adapter remains provisional')
text(35,PH-100,'A. 推荐木板版：六块大板，厚 6 mm；顶板安装打印漏斗环。',13)
text(35,PH-125,'B. 全打印版：所有零件单独成页；数量按各页标注。',13)
text(35,PH-155,'水箱：290 × 190 × 150。打印盒体：330 × 230 × 383；含固定环最高389。',12)
text(35,PH-180,'木板盒体：330 × 230 × 386；含6 mm固定环最高392。',12)
text(35,PH-210,'水箱盖上预留：100 × 100 × 150 净空。粉色区域不是实体零件，不需要加工。',12)
text(35,PH-240,'孔位表：X、Y均从图中左下角量起；孔径为成品尺寸。STL未做打印机孔径补偿。',11)
text(35,PH-265,'漏斗环：外径210、内径172、厚6；内径待购买漏斗后实测修改。',11)
text(35,PH-290,'DXF为1:1毫米轮廓，含真实圆弧；PDF按页面适配，不能直接当1:1纸样。',11)
text(35,PH-315,'孔和板缝已经建模；实物配合、承重、防水尚未测试。木板边缘封边，插排放盒外。',11)
text(35,PH-345,'页码顺序：木板部件 → 20类打印部件。角码页附三视图；DXF只表示其水平截面。',11)
text(35,PH-385,'3D打印墙板上下缝现为0.4 mm；用最新版STL，勿混用旧版墙板。',12)
c.showPage()
# wood drawing profiles, one-piece panels, correct 6mm thickness
wood=[]
def bx(w,h):return cq.Workplane('XY').box(w,h,6,centered=(False,False,False))
wood.append(('WOOD_base',bx(330,230),1,[]))
p=bx(330,230);p=s['hole'](p,220,115,190)
hs=[(220,115,190)]
for a in [45,135,225,315]:
 x=220+100*math.cos(math.radians(a));y=115+100*math.sin(math.radians(a));p=s['hole'](p,x,y);hs.append((x,y,3.4))
wood.append(('WOOD_roof',p,1,hs));wood.extend([('WOOD_front_back',bx(330,373.6),2,[]),('WOOD_left_right',bx(217.6,373.6),2,[])])
allrows=[]
def drawpart(name,p,qty,th,hs,wood=False):
 header(name,('木板部件 / plywood' if wood else '打印部件 / printed part')+f' | 数量 Qty {qty} | 厚度 Thickness {th:g} mm')
 sec=profile(p,th)
 cq.exporters.export(sec,str(dx/(name+'.dxf')))
 # allow nominal circle dimension rather than tessellated bounding box
 if name.startswith('funnel'):text(80,50,'圆环标称外径 Ø210 / 内径 Ø172（待实测）',11)
 text(595,PH-103,'孔位表 / Hole coordinates',12)
 text(595,PH-128,'No.      X         Y        Diameter',10)
 for i,(x,y,d) in enumerate(hs):text(595,PH-151-i*20,f'{i+1:02d}    {x:7.2f}    {y:7.2f}    Ø{d:g}',10)
 noteY=PH-175-len(hs)*20
 if name.startswith('roof'):
  text(595,noteY,'Ø190为跨接缝圆形切口。',10);text(595,noteY-20,'左半片圆心可在片外。',10)
 if name.startswith('WOOD') and not hs:
  text(595,noteY,'无预制孔；按角码实物定位。',10)
 if '_band' in name:
  text(595,noteY,'孔5用于上下墙板接缝条。',10)
 if name=='M3_corner_bracket':
  text(595,noteY,'24 × 24 × 24；两腿厚3。',10)
  text(595,noteY-20,'两面各Ø3.4，孔中心12/12。',10)
  # side view shows actual L section; front view shows second hole
  xx,yy=620,110;sc=3
  c.setLineWidth(1);path=c.beginPath();pts=[(0,0),(24,0),(24,3),(3,3),(3,24),(0,24),(0,0)]
  path.moveTo(xx,yy)
  for a,b in pts[1:]:path.lineTo(xx+a*sc,yy+b*sc)
  c.drawPath(path);text(xx,yy-18,'侧视 / side',9)
  xx=735;c.rect(xx,yy,24*sc,24*sc);c.circle(xx+12*sc,yy+12*sc,1.7*sc);text(xx,yy-18,'前视 / front',9)
 if name.startswith('funnel'):
  text(595,noteY,'4孔均布：PCD Ø200。',10);text(595,noteY-20,'角度45/135/225/315度。',10)
 allrows.append(dict(name=name,qty=qty,width_mm=round(p.val().BoundingBox().xlen,2),height_mm=round(p.val().BoundingBox().ylen,2),thickness_mm=th,holes=hs))
 c.showPage()
for name,p,qty,hs in wood:drawpart(name,p,qty,6,hs,True)
for row in parts:
 n=row['name'];drawpart(n,shapes[n],row['quantity'],6 if n.startswith('funnel') else 3,holemeta(n))
c.save();(out/'dimension_coordinates.json').write_text(json.dumps(allrows,indent=2))
with open(out/'dimension_summary.csv','w') as f:
 w=csv.writer(f);w.writerow(['part','quantity','width_mm','height_mm','thickness_mm'])
 for r in allrows:w.writerow([r['name'],r['qty'],r['width_mm'],r['height_mm'],r['thickness_mm']])
print('Wrote',PDF,'pages',page)
