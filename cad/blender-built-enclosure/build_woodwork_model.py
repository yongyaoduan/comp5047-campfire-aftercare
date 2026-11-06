"""Run in Blender 4.x: Scripting > Open > Run Script. Saves a true .blend beside this script.
Units mm in the interface, actual geometry in metres. No external assets required.
"""
import bpy, os, math
from mathutils import Vector
W,D,T,wallH=330.0,230.0,7.0,371.6
H=wallH+2*T
NOTCH_WIDTH_MM=115.0  # editable, left edge to inside notch edge
NOTCH_DEPTH_MM=95.0   # editable, back edge to inside notch edge
# clear existing scene
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for col in list(bpy.data.collections):
 if col.name!='Collection' and col.users==0:bpy.data.collections.remove(col)
sc=bpy.context.scene
sc.unit_settings.system='METRIC';sc.unit_settings.length_unit='MILLIMETERS';sc.unit_settings.scale_length=1.0
# collections
def collection(name):
 c=bpy.data.collections.new(name);sc.collection.children.link(c);return c
panels=collection('WOODWORK - 7 mm PLYWOOD');details=collection('OPTIONAL HARDWARE - SCREW HEADS'); stage=collection('STUDIO - LIGHTING CAMERA')
def move_to(obj,col):
 for c in list(obj.users_collection): c.objects.unlink(obj)
 col.objects.link(obj)
def mat(name,color,metallic=0,roughness=.8):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metallic;p.inputs['Roughness'].default_value=roughness
 return m
ply=mat('Plain light plywood - no grain texture',(0.66,.51,.355))
metal=mat('Screw heads',(.15,.17,.20),.7,.4)
def cube(name,size_mm,location_mm,coll=panels,material=ply):
 bpy.ops.mesh.primitive_cube_add(size=1,location=[x/1000 for x in location_mm]);o=bpy.context.object;o.name=name
 o.dimensions=tuple(x/1000 for x in size_mm);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 o.data.materials.append(material);move_to(o,coll)
 return o
cube('01 | Base | 330 x 230 x 7', (W,D,T),(0,0,T/2))
cube('02 | Front | 330 x 371.6 x 7',(W,T,wallH),(0,-D/2+T/2,T+wallH/2))
cube('03 | Back | 330 x 371.6 x 7',(W,T,wallH),(0,D/2-T/2,T+wallH/2))
cube('04 | Left | 216 x 371.6 x 7',(T,D-2*T,wallH),(-W/2+T/2,0,T+wallH/2))
cube('05 | Right | 216 x 371.6 x 7',(T,D-2*T,wallH),(W/2-T/2,0,T+wallH/2))
# One true watertight concave L-shaped roof: outline + top/bottom triangulation via explicit triangles.
# Polygon outline ccw: cutout touches LEFT and BACK boundaries. No rim around the opening.
a=-W/2;b=W/2;c=-D/2;d=D/2;innerx=a+NOTCH_WIDTH_MM;innery=d-NOTCH_DEPTH_MM
outline=[(a,c),(b,c),(b,d),(innerx,d),(innerx,innery),(a,innery)]
# Decompose without seams into 4 polygon triangles in XY using two nonoverlapping rectangles.
# Plane triangulation:
tris=[(0,1,5),(1,4,5),(1,2,3),(1,3,4)]
verts=[(x/1000,y/1000,z/1000) for z in (H-T,H) for x,y in outline]
faces=[]
for i,j,k in tris:faces.append((k,j,i));faces.append((i+6,j+6,k+6))
for i in range(6):j=(i+1)%6;faces.extend([(i,j,j+6),(i,j+6,i+6)])
mesh=bpy.data.meshes.new('L roof with open corner notch');mesh.from_pydata(verts,[],faces);mesh.update()
obj=bpy.data.objects.new('06 | Removable roof | L notch 115 x 95 mm',mesh);panels.objects.link(obj);obj.data.materials.append(ply)
# select roof and set show edges for CAD inspection
obj['notch_width_mm']=NOTCH_WIDTH_MM;obj['notch_depth_mm']=NOTCH_DEPTH_MM;obj['wood_thickness_mm']=T
for x,y in [(-151,-102),(-65,-102),(0,-102),(76,-102),(150,-102),(-36,103),(32,103),(104,103),(150,45),(150,-45),(-151,-20)]:
 if x < innerx and y > innery:continue
 bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=.00175,depth=.0006,location=(x/1000,y/1000,(H+.35)/1000));o=bpy.context.object;o.name='Optional screw head';move_to(o,details);o.data.materials.append(metal)
# Optional detail toggle - screws visible to match reference, no timber texture or other accessories.
# Camera
bpy.ops.object.camera_add(location=(.78,-.97,.74));cam=bpy.context.object;cam.name='Camera | 3-4 view';move_to(cam,stage)
def point_at(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
point_at(cam,(0,0,.195));sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.88
def area(name,xyz,power,size):
 bpy.ops.object.light_add(type='AREA',location=xyz);o=bpy.context.object;o.name=name;move_to(o,stage);o.data.energy=power;o.data.shape='DISK';o.data.size=size;point_at(o,(0,0,.19))
area('Key light',(.1,-.6,.9),450,1.0);area('Fill light',(-.5,.4,.5),260,1.0);area('Rim light',(.5,.5,.8),350,.9)
world=bpy.data.worlds.new('Neutral backdrop');sc.world=world;world.use_nodes=True;world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.12,.13,.15,1)
try:
 sc.render.engine='BLENDER_EEVEE_NEXT'
except Exception:
 try: sc.render.engine='BLENDER_EEVEE'
 except Exception: sc.render.engine='CYCLES'
sc.render.resolution_x=1600;sc.render.resolution_y=1200;sc.render.resolution_percentage=100
sc.render.image_settings.file_format='PNG';sc.render.film_transparent=False
# user-friendly camera perspective in layout
for screen in bpy.data.screens:
 for area0 in screen.areas:
  if area0.type=='VIEW_3D':
   sp=area0.spaces.active;sp.clip_end=100;sp.shading.type='MATERIAL'
   sp.region_3d.view_distance=.83;sp.region_3d.view_location=(0,0,.19)
# save and render beside source script
folder=os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else bpy.path.abspath('//')
if not os.path.isdir(folder):folder=os.path.expanduser('~')
path=os.path.join(folder,'Campfire_Aftercare_Woodwork.blend')
bpy.ops.wm.save_as_mainfile(filepath=path)
sc.render.filepath=os.path.join(folder,'Blender_render_woodwork.png')
bpy.ops.render.render(write_still=True)
print('Saved native Blender file:',path)
