"""CAMPFIRE AFTERCARE | Build an editable native .blend from the supplied GLB.

USAGE:
1. Open Blender 4.x, go to Scripting.
2. Open this .py file, then click Run Script.
3. It automatically imports the scene, organises objects, configures rendering,
   and saves Campfire_Aftercare_Leaf_Camouflage.blend in this directory.

Alternatively:
  blender --background --python CREATE_NATIVE_BLEND_IN_BLENDER.py

All geometry is in real-world metre units; displayed dimensions are millimetres.
This script does NOT require any third-party Blender addons.
"""
import os, sys, math
from pathlib import Path
import bpy
from mathutils import Vector

# Detect this script's folder in both Blender Scripting and --background modes.
folders=[]
if '__file__' in globals():
    folders.append(Path(__file__).resolve().parent)
try:
    for tx in bpy.data.texts:
        if tx.name.startswith('CREATE_NATIVE_BLEND_IN_BLENDER') and tx.filepath:
            folders.append(Path(bpy.path.abspath(tx.filepath)).resolve().parent)
except Exception: pass
if bpy.data.filepath: folders.append(Path(bpy.data.filepath).resolve().parent)
folders.append(Path.cwd())
BASE=next((p for p in folders if (p/'Campfire_Aftercare_Leaf_Camouflage.glb').exists()),folders[0])
SRC=BASE / 'Campfire_Aftercare_Leaf_Camouflage.glb'
DEST=BASE / 'Campfire_Aftercare_Leaf_Camouflage.blend'
if not SRC.exists():
    raise FileNotFoundError('Missing GLB in the same folder as this script: '+str(SRC))

# Start with a clean scene, without losing any file on disk.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name == 'Collection':
        if len(c.objects)==0: bpy.data.collections.remove(c)

# Import the actual geometry that was programmatically built to match the reference.
bpy.ops.import_scene.gltf(filepath=str(SRC))
scene=bpy.context.scene
scene.name='Campfire Aftercare | foliage enclosure'
scene.unit_settings.system='METRIC'
scene.unit_settings.length_unit='MILLIMETERS'
scene.unit_settings.scale_length=1.0

main=scene.collection

def newcol(name):
    c=bpy.data.collections.new(name);main.children.link(c);return c
cats={
    'shell':newcol('01 | 7 mm plywood enclosure + removable lid'),
    'collector':newcol('02 | Roof rainwater collector'),
    'foliage':newcol('03 | Artificial leaves and trellis'),
    'camera':newcol('04 | Webcam, LEDs and thermal sensor'),
    'outlet':newcol('05 | Short transparent dry outlet tube'),
    'interior':newcol('06 | Tank and wall-mounted electronics (approx)'),
    'stage':newcol('07 | Cameras, lights and background')
}

# Move all model objects into one editable, searchable Outliner hierarchy.
for o in list(scene.objects):
    n=o.name.lower()
    if n.startswith('internal'):dst=cats['interior']
    elif 'outlet' in n:dst=cats['outlet']
    elif ('webcam' in n or 'led ' in n or 'mlx90614' in n or 'thermal sensor' in n):dst=cats['camera']
    elif ('leaf' in n or 'trellis' in n or 'vein' in n):dst=cats['foliage']
    elif ('rainwater collector' in n):dst=cats['collector']
    else:dst=cats['shell']
    if dst not in o.users_collection:
        for old in list(o.users_collection):old.objects.unlink(o)
        dst.objects.link(o)

# Parent the top plywood and collector assembly to a single transform control.
roof_controller=bpy.data.objects.new('MOVE THIS EMPTY | removable roof assembly',None)
roof_controller.empty_display_type='CUBE';roof_controller.empty_display_size=.13
cats['shell'].objects.link(roof_controller)
roof_controller.location=(0,0,.382)
for o in list(scene.objects):
    if o==roof_controller:continue
    if o.name.startswith(('Removable roof','Rainwater collector','Roof screw')):
        mat=o.matrix_world.copy()
        o.parent=roof_controller
        o.matrix_world=mat
roof_controller['Usage']='Select and move upward along Z to take the lid and rainwater collector off.'

# Material upgrades from the transport GLB: procedural wood grain, transparent silicone,
# emissive status LEDs. These edits are native to the Blender project.
def material_match(substr):
    return [m for m in bpy.data.materials if substr.lower() in m.name.lower()]

def pbsdf(m):
    m.use_nodes=True
    return next((n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)

for m in material_match('wood'):
    if 'woodgrain' in m.name.lower(): continue
    bs=pbsdf(m)
    if not bs:continue
    nodes=m.node_tree.nodes; links=m.node_tree.links
    wave=nodes.new('ShaderNodeTexWave'); wave.label='Natural timber grain bands'
    wave.wave_type='BANDS';wave.bands_direction='Y'
    wave.inputs['Scale'].default_value=10
    wave.inputs['Distortion'].default_value=7
    wave.inputs['Detail'].default_value=2
    noise=nodes.new('ShaderNodeTexNoise');noise.label='Subtle plywood grain detail'
    noise.inputs['Scale'].default_value=125
    noise.inputs['Detail'].default_value=3
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.07
    bump.inputs['Distance'].default_value=.005
    ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.20
    ramp.color_ramp.elements[0].color=(.35,.19,.095,1)
    ramp.color_ramp.elements[1].position=.78
    ramp.color_ramp.elements[1].color=(.69,.48,.27,1)
    links.new(wave.outputs['Fac'],ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'],bs.inputs['Base Color'])
    links.new(noise.outputs['Fac'],bump.inputs['Height'])
    links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    bs.inputs['Roughness'].default_value=.76

for m in material_match('Transparent outlet'):
    bs=pbsdf(m)
    if bs:
        bs.inputs['Base Color'].default_value=(.78,.85,.87,1)
        bs.inputs['Roughness'].default_value=.09
        if 'Transmission Weight' in bs.inputs:bs.inputs['Transmission Weight'].default_value=.82
        elif 'Transmission' in bs.inputs:bs.inputs['Transmission'].default_value=.82
        bs.inputs['IOR'].default_value=1.46
        bs.inputs['Alpha'].default_value=.5
        try:
            if hasattr(m,'surface_render_method'): m.surface_render_method='DITHERED'
            elif hasattr(m,'blend_method'): m.blend_method='BLEND'
        except Exception: pass

for state,col,strength in [('green',(0.04,1.0,.07,1),1.8),('red',(1.0,.045,.025,1),1.7)]:
    for m in material_match('Status LED | '+state):
        bs=pbsdf(m)
        if bs:
            bs.inputs['Base Color'].default_value=col
            if 'Emission Color' in bs.inputs:bs.inputs['Emission Color'].default_value=col
            if 'Emission Strength' in bs.inputs:bs.inputs['Emission Strength'].default_value=strength

# Gently rounded camera and housing components, without modifying dimensions.
for o in scene.objects:
    if o.type=='MESH' and ('black housing' in o.name.lower() or 'lid' in o.name.lower()):
        try:
            bev=o.modifiers.new('Softened manufactured edges','BEVEL')
            bev.width=.002
            bev.segments=2
            o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
        except Exception:pass

# A neutral studio ground below the foliage (its overhang extends below the plywood base).
ground=bpy.data.materials.new('Studio ground | charcoal')
ground.diffuse_color=(.095,.105,.13,1)
ground.use_nodes=True
n=pbsdf(ground)
if n:
    n.inputs['Base Color'].default_value=(.095,.105,.13,1)
    n.inputs['Roughness'].default_value=.85
bpy.ops.mesh.primitive_plane_add(size=3.0,location=(0,0,-.040))
floor=bpy.context.object;floor.name='STUDIO | graphite floor';floor.data.materials.append(ground)
for c in list(floor.users_collection):c.objects.unlink(floor)
cats['stage'].objects.link(floor)

# Useful camera views for Blender's Render menu. No images are baked or faked.
def point_at(obj,p):
    vec=Vector(p)-obj.location
    obj.rotation_euler=vec.to_track_quat('-Z','Y').to_euler()

def camera(name,loc,focus,ortho=False,scale=.52):
    data=bpy.data.cameras.new(name)
    o=bpy.data.objects.new(name,data);cats['stage'].objects.link(o)
    o.location=loc;point_at(o,focus)
    if ortho:data.type='ORTHO';data.ortho_scale=scale
    else:data.type='PERSP';data.lens=46
    return o
cams={}
cams['main']=camera('CAM 01 | three-quarter hero',(-.61,-.75,.63),(0,0,.195))
cams['front']=camera('CAM 02 | front orthographic',(0,-1.4,.205),(0,0,.205),True,.52)
cams['right']=camera('CAM 03 | right orthographic',(.9,0,.205),(0,0,.205),True,.50)
cams['back']=camera('CAM 04 | rear orthographic',(0,1.4,.205),(0,0,.205),True,.52)
cams['top']=camera('CAM 05 | top orthographic',(0,0,1.0),(0,0,.195),True,.50)
scene.camera=cams['main']

def area_light(name, loc, power, size,colour=(1,1,1)):
    dat=bpy.data.lights.new(name,'AREA');dat.energy=power;dat.shape='DISK';dat.size=size;dat.color=colour
    ob=bpy.data.objects.new(name,dat);cats['stage'].objects.link(ob)
    ob.location=loc;point_at(ob,(0,0,.2));return ob
area_light('LIGHT | front softbox',(-.48,-.55,.84),300,.65)
area_light('LIGHT | front fill',(.62,-.30,.49),215,.55)
area_light('LIGHT | back rim',(.20,.48,.77),400,.60)
area_light('LIGHT | roof fill',(-.10,.10,.94),150,.44)

scene.render.resolution_x=1600;scene.render.resolution_y=1250
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
try:scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
except:pass
try:scene.view_settings.view_transform='AgX'
except:pass
scene.render.filepath=str(BASE/'01_render_in_Blender.png')
world=bpy.data.worlds.new('Studio world')
world.use_nodes=True
bg=next((n for n in world.node_tree.nodes if n.type=='BACKGROUND'),None)
if bg:
    bg.inputs['Color'].default_value=(.18,.19,.22,1)
    bg.inputs['Strength'].default_value=.7
scene.world=world

# Studio collections can be hidden before exporting just the object.
scene['Reference'] = 'User 6-Nov-2026 foliage enclosure Blender-style concept screenshot'
scene['Wooden box width (mm)']=330.0
scene['Wooden box depth (mm)']=230.0
scene['Wooden box height (mm)']=385.6
scene['Plywood panel thickness (mm)']=7.0
scene['Model accuracy note']='Leaf arrangement & internal electronics are visual approximations, dimensions apply to plywood core only.'
scene['Tube']='Clear empty silicone tube emerging directly from leaves at upper right, no connector, water or cable outside.'

# Preview as a normal material-viewport model on opening the .blend file.
bpy.ops.object.select_all(action='DESELECT')
roof_controller.select_set(True)
bpy.context.view_layer.objects.active=roof_controller
for s in bpy.data.screens:
    for a in s.areas:
        if a.type=='VIEW_3D':
            try:
                a.spaces.active.shading.type='MATERIAL'
                a.spaces.active.region_3d.view_location=(0,0,.19)
                a.spaces.active.region_3d.view_distance=.90
                q=(Vector((0,0,.20))-Vector((-.65,-.8,.64))).to_track_quat('-Z','Y')
                a.spaces.active.region_3d.view_rotation=q
            except Exception:pass

bpy.ops.wm.save_as_mainfile(filepath=str(DEST))
print('Native Blender file created:',DEST)
print('Model meshes:',len([o for o in scene.objects if o.type=='MESH']))

# Optional standalone camera rendering from Blender:
# Set environment CAMPFIRE_RENDER=1 when running blender --background --python script.
if os.environ.get('CAMPFIRE_RENDER')=='1':
    for key,c in cams.items():
        scene.camera=c
        scene.render.filepath=str(BASE/('BLENDER_RENDER_'+key+'.png'))
        bpy.ops.render.render(write_still=True)
    scene.camera=cams['main']
    bpy.ops.wm.save_as_mainfile(filepath=str(DEST))
