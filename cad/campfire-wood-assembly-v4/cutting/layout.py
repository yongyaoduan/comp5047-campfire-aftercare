from pathlib import Path
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import csv,json
R=Path(__file__).resolve().parent
# 7mm panels, preserve outer330x230x386. Saw kerf3mm, outer trim5mm.
pieces=[('FRONT',5,5,330,371.6),('BACK',338,5,330,371.6),('LEFT',671,5,215.6,371.6),('RIGHT',889.6,5,215.6,371.6),('BASE',5,379.6,330,230),('TOP',338,379.6,330,230)]
for a in pieces:
 assert a[1]>=5 and a[2]>=5 and a[1]+a[3]<=1195 and a[2]+a[4]<=892
for i,a in enumerate(pieces):
 for b in pieces[i+1:]:
  assert a[1]+a[3]+3<=b[1]+.001 or b[1]+b[3]+3<=a[1]+.001 or a[2]+a[4]+3<=b[2]+.001 or b[2]+b[4]+3<=a[2]+.001
fig,ax=plt.subplots(figsize=(13,9));ax.add_patch(Rectangle((0,0),1200,897,facecolor='#e9e2d3',edgecolor='black'))
for i,(name,x,y,w,h) in enumerate(pieces):
 ax.add_patch(Rectangle((x,y),w,h,facecolor=['#aed3d1','#aed3d1','#c4cbe5','#c4cbe5','#efd08f','#efd08f'][i],edgecolor='#304650'))
 ax.text(x+w/2,y+h/2,f'{name}\n{w:g} x {h:g} mm',ha='center',va='center',fontsize=12)
ax.text(600,740,'REUSABLE OFFCUT\nDo not discard until trial assembly is complete',ha='center',fontsize=13,color='#716a5d')
ax.set_xlim(-10,1210);ax.set_ylim(907,-10);ax.set_aspect('equal');ax.set_xlabel('Board width (mm)');ax.set_ylabel('Board length (mm)')
ax.set_title('BUY ONE: 1200 x 897 x 7 mm plywood | Photo shelf price A$36\n7 mm version: six panels; 3 mm saw kerf and 5 mm edge trim allowed',fontsize=15,pad=15)
fig.text(.1,.025,'Preserves outer box 330 x 230 x 386 mm. Four separate corner posts: 10 x 10 x 372 mm.\nUse these 7 mm panel sizes instead of the earlier 6 mm cut list. Verify actual board thickness and saw kerf before cutting.',fontsize=10)
fig.tight_layout(rect=(0,.06,1,1));fig.savefig(R/'7mm_board_cutting_layout.png',dpi=160)
with open(R/'7mm_cut_list.csv','w') as f:
 w=csv.writer(f);w.writerow(['part','width_mm','height_mm','thickness_mm','board_origin_x','board_origin_y'])
 for n,x,y,a,b in pieces:w.writerow([n,a,b,7,x,y])
 w.writerow(['CORNER_POST x4',10,372,10,'separate square timber',''])
(R/'checks.json').write_text(json.dumps({'stock':[1200,897,7],'kerf_mm':3,'edge_trim_mm':5,'all_parts_fit':True,'cutouts_in_roof':'same nominal X220 Y115 DIA190; bore still provisional','used_area_mm2':sum(a*b for _,_,_,a,b in pieces)},indent=2))
