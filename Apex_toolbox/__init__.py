# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Apex Toolbox",
    "author": "Random Blender Dude, maintained by ALR",
    "version": (3, 9, 0),
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar > Apex Tools",
    "description": "Blender tools for Apex Legends models, materials, shaders and RSX/CAST workflows",
    "category": "3D View"
}
#"version": (3, 6)

import bpy
import os
import re
from bpy.types import Scene
from bpy.props import (BoolProperty,FloatProperty)
from urllib.request import Request, urlopen
import webbrowser
import sys
import platform
import textwrap

##########################################
#   Reload-safe submodule handling
##########################################
#
# Blender re-executes THIS file when the add-on is re-enabled, but any
# submodule already in ``sys.modules`` is reused untouched.  Installing a new
# version over a running old one therefore left a new caller in this file
# talking to an old ``apex_tex.autotex`` -- which is exactly the
# "run() got an unexpected keyword argument 'remembered_roots'" crash reported
# against v3.7 beta 4.  Reload the package explicitly, dependencies first, so
# the whole add-on always comes from one revision.
#
# The marker is ``sys.modules``, not a name in this file's globals: v3.7 beta 3
# bound only ``apex_autotex``/``apex_roles``/``apex_shaders``, never
# ``apex_tex``, so a globals check would miss the very upgrade path that broke.
# If the package is already imported, this execution is a re-enable and every
# submodule must be refreshed from disk.
_APEX_TEX_PACKAGE = __name__ + ".apex_tex"
if _APEX_TEX_PACKAGE in sys.modules:
    import importlib as _importlib

    _apex_tex_pkg = _importlib.reload(sys.modules[_APEX_TEX_PACKAGE])
    for _name in getattr(_apex_tex_pkg, "RELOAD_ORDER", ()):
        _submodule = sys.modules.get(_APEX_TEX_PACKAGE + "." + _name)
        if _submodule is not None:
            _importlib.reload(_submodule)
    print("Apex Toolbox: reloaded apex_tex after an in-session update")
    del _importlib, _apex_tex_pkg, _name, _submodule
del _APEX_TEX_PACKAGE

from . import apex_tex
from .apex_tex import autotex as apex_autotex
from .apex_tex import roles as apex_roles
from .apex_tex import shaders as apex_shaders
from .apex_tex import resolver as apex_resolver
from .apex_tex import diagnostics as apex_diagnostics
from .apex_tex import health as apex_health
from .apex_tex import naming as apex_naming
from .apex_tex.versions import newer_version

#: The apex_tex API revision this file is written against.  If the two ever
#: disagree at register() time, a stale module survived the reload above and
#: the add-on says so instead of failing later with a TypeError.
APEX_TEX_API_VERSION = 7


def modules_are_stale():
    """True when apex_tex is not the revision this file expects."""
    return getattr(apex_tex, "API_VERSION", 0) != APEX_TEX_API_VERSION


def require_fresh_modules(operator=None):
    """Guard for operators that call into apex_tex."""
    if not modules_are_stale():
        return True
    message = ("Apex Toolbox was updated while Blender was running. "
               "Restart Blender to finish the update.")
    print("Apex Toolbox: " + message)
    if operator is not None:
        operator.report({'ERROR'}, message)
    return False


## Toolbox vars ##
ver = "v3.9.0"
#ver = "v.3.6"
lts_ver = ver
loadImages = True
texSets = [['albedoTexture'],['specTexture'],['emissiveTexture'],['scatterThicknessTexture'],['opacityMultiplyTexture'],['normalTexture'],['glossTexture'],['aoTexture'],['cavityTexture'],['anisoSpecDirTexture'],['iridescenceRampTexture']]
## Garlicus List vars ##
lgnd_list = []
ver_list = []
## Legion update vars ##
legion_cur_ver = '0'
legion_lts_ver = '0'
legion_folder_exist = 0
## Addons update vars ##
addon_name = []
addon_ver = []
io_anim_lts_ver = '0'
cast_lts_ver = '0'
semodel_lts_ver = '0'
mprt_lts_ver = '0'


#: Historical developer switch.  The hardcoded personal drive paths the
#: ``mode == 0`` branch used to carry were removed in v3.7 beta 4; folder
#: access now goes through addon_asset_folder() / addon_legion_folder().
mode = 1

my_path = os.path.dirname(os.path.realpath(__file__))


### For Blender HDRI ###    
bldr_path = (os.path.dirname(bpy.app.binary_path))
bldr_ver = bpy.app.version_string.split('.')
bldr_fdr = bldr_ver[0] + '.' + bldr_ver[1] 
    
if platform.system() == 'Windows':
    fbs = '\\'
    blend_file = ("\\ApexShader.blend")
    ap_node = ("\\NodeTree")
    ap_object = ("\\Object")
    ap_collection = ("\\Collection")
    ap_material = ("\\Material")
    ap_image = ("\\Image")
    ap_world = ("\\World")
    ap_action = ("\\Action")
    bldr_hdri_path = (bldr_path + "\\" + bldr_fdr + "\\datafiles\\studiolights\\world\\")
else:
    fbs = '/'   #forward/back slashes (MacOs)
    blend_file = ("/ApexShader.blend")
    ap_node = ("/NodeTree")
    ap_object = ("/Object")
    ap_collection = ("/Collection")
    ap_material = ("/Material")
    ap_image = ("/Image")
    ap_world = ("/World")
    ap_action = ("/Action")
    bldr_hdri_path = (bldr_path + "/" + bldr_fdr + "/datafiles/studiolights/world/")  

### Absolute image paths are required by Recolor and Auto Texture; this is
### applied by the operators that need it, not silently at import time.

print("**********************************************")
print("OS Platform: " + platform.system())
print("**********************************************")



##########################################
#   Shared helpers
##########################################

#: The key this add-on is registered under.  Never hardcode "Apex_toolbox":
#: installing the GitHub "Download ZIP" produces a folder called
#: "Apex-Toolbox-main", and every bpy.context.preferences.addons["Apex_toolbox"]
#: lookup then raised KeyError and killed the operator.
ADDON_KEY = __package__ or __name__


def addon_prefs():
    """This add-on's preferences, or ``None`` when it is not registered."""
    addon = bpy.context.preferences.addons.get(ADDON_KEY)
    if addon is None:
        addon = bpy.context.preferences.addons.get(__name__)
    return addon.preferences if addon is not None else None


def addon_asset_folder():
    """Path of the optional Apex_Toolbox_Assets download (may be empty)."""
    prefs = addon_prefs()
    return getattr(prefs, "asset_folder", "") if prefs else ""


def addon_legion_folder():
    """Folder that contains the user's Legion+ install (may be empty)."""
    prefs = addon_prefs()
    return getattr(prefs, "legion_folder", "") if prefs else ""


def assets_installed():
    """True when the Extended asset pack is present and correctly named."""
    folder = addon_asset_folder()
    if not folder:
        return False
    folder = bpy.path.abspath(folder)
    if not os.path.isdir(folder):
        return False
    return os.path.isfile(os.path.join(folder, "Assets.blend"))


def assets_blend():
    """Full path of the Extended pack's Assets.blend, or ``""``."""
    folder = addon_asset_folder()
    if not folder:
        return ""
    return os.path.join(bpy.path.abspath(folder), "Assets.blend")


def require_assets(operator):
    """Report a clear message when an Extended-pack-only action is used."""
    if assets_installed():
        return True
    if operator is not None:
        operator.report(
            {"ERROR"},
            "This needs the Apex Toolbox Assets pack. Set its folder in "
            "Preferences > Add-ons > Apex Toolbox (choose the folder "
            "containing Assets.blend).")
    return False


def remembered_texture_roots():
    """Export folders Auto Texture has previously resolved textures from."""
    prefs = addon_prefs()
    raw_value = getattr(prefs, "texture_root_memory", "") if prefs else ""
    return [p for p in raw_value.split("|") if p]


def store_texture_roots(paths_list):
    """Persist the remembered export folders (add-on preferences)."""
    prefs = addon_prefs()
    if prefs is None:
        return
    try:
        prefs.texture_root_memory = "|".join(paths_list)
    except (AttributeError, TypeError):
        pass


def selected_meshes(context):
    return [o for o in context.selected_objects if o.type == "MESH"]


def texture_targets(context):
    return apex_health.model_meshes(context.selected_objects, context.view_layer,
                                    context.scene.my_prefs.include_model_meshes)


def health_targets(context):
    if context.scene.my_prefs.health_scope == 'VIEW_LAYER':
        return [obj for obj in context.view_layer.objects if obj.type == 'MESH']
    return texture_targets(context)


def save_tool_report(prefs, kind, summary, body):
    field = kind + '_report'
    report = getattr(prefs, field)
    if report is None:
        report = bpy.data.texts.new('Apex ' + kind.title() + ' Report')
        setattr(prefs, field, report)
    report.clear()
    report.write(body)
    report.cursor_set(0, character=0, select=False)
    setattr(prefs, kind + '_summary', summary)


def capture_texture_report(context, batch, definition, outcomes):
    summary, body = apex_diagnostics.texture_report(batch, definition, outcomes)
    save_tool_report(context.scene.my_prefs, 'texture', summary, body)


def draw_wrapped(layout, text, context):
    width = max(24, int(getattr(context.region, 'width', 300) / 7))
    layout = layout.column(align=True)
    for line in textwrap.wrap(text, width=width):
        layout.label(text=line)


def draw_report_actions(layout, kind):
    row = layout.row(align=True)
    op = row.operator('object.apex_report', text='Open Report', icon='TEXT')
    op.kind = kind
    op.copy = False
    op = row.operator('object.apex_report', text='Copy', icon='COPYDOWN')
    op.kind = kind
    op.copy = True


def selected_armature(context):
    for obj in context.selected_objects:
        if obj.type == "ARMATURE":
            return obj
    active = context.active_object
    if active is not None and active.type == "ARMATURE":
        return active
    return None


def eevee_engine():
    """The EEVEE identifier for the running Blender (renamed in 4.2)."""
    try:
        identifiers = [
            item.identifier for item in
            bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    except (KeyError, AttributeError):
        identifiers = []
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if candidate in identifiers:
            return candidate
    return identifiers[0] if identifiers else "BLENDER_EEVEE"


def set_if_present(owner, attribute, value):
    """Assign an optional property that some Blender versions removed."""
    if owner is not None and hasattr(owner, attribute):
        try:
            setattr(owner, attribute, value)
            return True
        except (TypeError, AttributeError):
            pass
    return False


def toon_shader_node(context):
    """The Apex ToonShader group node on the active material, if any."""
    obj = getattr(context, "object", None)
    material = getattr(obj, "active_material", None) if obj else None
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return None
    for node in tree.nodes:
        if node.bl_idname != "ShaderNodeGroup":
            continue
        if getattr(node.node_tree, "name", "") == "Apex ToonShader":
            return node
    return None


def world_background_inputs(world):
    """``(strength, rotation)`` sockets of a world, or ``None``.

    Returns ``None`` rather than raising when the world has no node tree or
    was built differently, which the previous bare ``except`` hid.
    """
    tree = getattr(world, "node_tree", None)
    if tree is None:
        return None
    background = tree.nodes.get("Background")
    if background is None or "Strength" not in background.inputs:
        return None
    mapping = tree.nodes.get("Mapping")
    rotation = None
    if mapping is not None and "Rotation" in mapping.inputs:
        rotation = mapping.inputs["Rotation"]
    return background.inputs["Strength"], rotation


def show_text_datablock(context, name, body, operator=None):
    """Open a text datablock in a Text Editor without hijacking the panel.

    The previous implementation turned whatever area the button was clicked in
    into a Text Editor, and raised AttributeError whenever ``context.area``
    was ``None``.
    """
    text = bpy.data.texts.get(name)
    if text is None:
        text = bpy.data.texts.new(name)
        text.write(body)
    text.cursor_set(0, character=0, select=False)

    def display(area):
        area.spaces.active.text = text
        area.spaces.active.top = 0
        area.spaces.active.show_word_wrap = True

    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "TEXT_EDITOR":
                display(area)
                return True
    area = getattr(context, "area", None)
    if area is not None and area.type == "VIEW_3D":
        area.ui_type = "TEXT_EDITOR"
        display(area)
        return True
    if operator is not None:
        operator.report(
            {"INFO"},
            "Opened as text block '%s' - switch an editor to the Text Editor "
            "to read it." % name)
    return False



all_loot_items = {
    '0': 'White Armor',
    '1': 'Blue Armor',
    '2': 'Purple Armor',
    '3': 'Gold Armor',
    '4': 'Red Armor',
    '5': 'White Helmet',
    '6': 'Blue Helmet',
    '7': 'Purple Helmet',
    '8': 'Gold Helmet',
    '9': 'Red Helmet',
    '10': 'Phoenix Kit',
    '11': 'Shield Battery',
    '12': 'Shield Cell',
    '13': 'Med Kit',
    '14': 'Syringe',
    '15': 'Health Injector',
    '16': 'Grenade',
    '17': 'Arc Star',
    '18': 'Thermite',
    '19': 'Backpack Lv.4',
    '20': 'Backpack Lv.3',
    '21': 'Backpack Lv.2',
    '22': 'Backpack Lv.1',
    '23': 'Light Ammo',
    '24': 'Heavy Ammo',
    '25': 'Energy Ammo',
    '26': 'Shotgun Ammo',
    '27': 'Respawn Beacon',
    '28': 'Knockdown Shield',
    '29': 'Heat Shield',
    '30': 'Death Box',
    }

### add +1 to item end range ###
armor_range = (0,5)
helmet_range = (5,10)    
meds_range = (10,16)
nades_range = (16,19)
bag_range = (20,23)
ammo_range = (23,27)
other_range = (27,31)

    
all_lobby_other_items = {
    '0': 'Heirloom Shards',
    '1': 'Epic Shards',
    '2': 'Rare Shards',
    '3': 'Loot Drone',
    '4': 'RESERVED',
    '5': 'RESERVED',
    '6': 'RESERVED',
    '7': 'RESERVED',
    '8': 'RESERVED',
    '9': 'RESERVED',
    '10': 'RESERVED',
    '11': 'RESERVED',
    '12': 'RESERVED',
    '13': 'RESERVED',
    '14': 'RESERVED',
    '15': 'RESERVED',
    '16': 'RESERVED',
    '17': 'RESERVED',
    '18': 'RESERVED',
    '19': 'RESERVED',
    '20': 'Respawn Beacon Hologram',
    '21': 'Loot Ball'
    }    
            
### add +1 to item end range ###
lobby_lobby_range = (0,4)
lobby_other_range = (20,22)


all_heirloom_items = {
    '0': 'Gibraltar Set',
    '1': 'Bangalore Set',
    '2': 'Lifeline Set (Animated)',
    '3': 'Bloodhound Set',
    '4': 'Caustic Set',
    '5': 'Crypto Set',
    '6': 'Wraith Set',
    '7': 'Mirage Set',
    '8': 'Octane Set',
    '9': 'Pathfinder Set (Animated)',
    '10': 'Rampart Set',
    '11': 'Revenant Set',
    '12': 'Valkyrie Set',
    '13': 'Wattson Set (Animated)'
    }  

### add +1 to item end range ###
heirloom_range = (0,14)
    
    
all_seer_items = {
    '0': 'Seer Ultimate',
    }
    
all_skydive_items = {
    '0': 'Skydive Ranked S9 Diamond',
    '1': 'Skydive Ranked S9 Master',
    '2': 'Skydive Ranked S9 Predator',
    }         

addon = [
    'io_anim_seanim',
    'io_scene_cast',
    'io_model_semodel',
    'ApexMapImporter'
    ]    
    
    #OPERATOR         
########################################   
class apexToolsPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_KEY

    asset_folder: bpy.props.StringProperty(
        name="Toolbox Assets Folder",
        description="Optional. Folder of the downloaded Apex Toolbox Assets "
                    "pack, which unlocks the HDRI themes, loot, heirlooms, "
                    "badges and lobby items. Choose the folder containing Assets.blend",
        default="",
        maxlen=1024,
        subtype="DIR_PATH")

    legion_folder: bpy.props.StringProperty(
        name="Legion+ Parent Folder",
        description="Optional. Folder that CONTAINS your Legion+ folder (not "
                    "the folder holding LegionPlus.exe). Used by the update "
                    "tracker to read your installed Legion+ version",
        default="",
        maxlen=1024,
        subtype="DIR_PATH")

    update_repo: bpy.props.StringProperty(
        name="Releases Repository",
        description="Optional. GitHub repository this build publishes its releases from, as owner/name. This add-on is a fork, so the original's releases do not describe this build; leave empty to disable the update notice",
        default="",
        maxlen=200)

    texture_root_memory: bpy.props.StringProperty(
        name="Remembered Texture Folders",
        description="Export folders Auto Texture has successfully found "
                    "textures in. Auto Texture reuses these so later models "
                    "from the same export need no folder picking",
        default="",
        maxlen=4096)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Folders", icon='FILE_FOLDER')
        box.prop(self, "asset_folder")
        if self.asset_folder and not assets_installed():
            box.label(text="Assets.blend is missing from this folder",
                      icon='ERROR')
        box.prop(self, "legion_folder")

        box = layout.box()
        box.label(text="Updates", icon='FILE_REFRESH')
        box.prop(self, "update_repo")
        box.label(text="This build is a fork of the original Apex Toolbox.")
        box.label(text="Leave empty to disable the update notice.")

        box = layout.box()
        box.label(text="Auto Texture", icon='TEXTURE')
        remembered = remembered_texture_roots()
        if remembered:
            box.label(text="Remembered export folders (%d):" % len(remembered))
            for path in remembered:
                row = box.row()
                row.label(text=path, icon='DOT')
            box.operator("object.apex_forget_texture_roots",
                         text="Forget Remembered Folders", icon='TRASH')
        else:
            box.label(text="No export folder remembered yet.", icon='INFO')


class APEX_PG_health_issue(bpy.types.PropertyGroup):
    code: bpy.props.StringProperty()
    severity: bpy.props.StringProperty()
    object: bpy.props.PointerProperty(type=bpy.types.Object)
    title: bpy.props.StringProperty()
    detail: bpy.props.StringProperty()


class PROPERTIES_CUSTOM(bpy.types.PropertyGroup):
    include_model_meshes: BoolProperty(
        name='Include Model Meshes', default=True,
        description='Include meshes parented to a selected armature or empty, and meshes bound to its rig')
    texture_report: bpy.props.PointerProperty(type=bpy.types.Text)
    texture_summary: bpy.props.StringProperty()
    health_report: bpy.props.PointerProperty(type=bpy.types.Text)
    health_summary: bpy.props.StringProperty()
    repair_report: bpy.props.PointerProperty(type=bpy.types.Text)
    repair_summary: bpy.props.StringProperty()
    health_scope: bpy.props.EnumProperty(
        name='Check', default='SELECTION',
        items=[('SELECTION', 'Selected Models', 'Selected meshes and included model meshes'),
               ('VIEW_LAYER', 'View Layer', 'All meshes in the current view layer, plus camera and world checks')])
    health_issues: bpy.props.CollectionProperty(type=APEX_PG_health_issue)
    health_index: bpy.props.IntProperty(default=0, min=0)
    repair_folder: bpy.props.StringProperty(
        name='New Texture Folder', subtype='DIR_PATH',
        description='Search for moved images by exact filename; duplicate matches are left unchanged')
    repair_subfolders: BoolProperty(name='Search Subfolders', default=True)
    
    name : bpy.props.StringProperty(name= "ver", default="", maxlen=40) #not in use            
                    
    ### For Autotex ####
    cust_enum : bpy.props.EnumProperty(
        name = "Shader",
        description = "Shader for recolor",
        default='OP1',
        items = [('OP1', "Apex Shader", ""),
                 ('OP2', "Apex Shader+_v3.4", ""),
                 ('OP3', "S/G-Blender", "")    
                ]
        )
        
    autotex_folder: bpy.props.StringProperty(name="Textures Folder",
                                        description="Optional. Extra folder Auto_tex may search for textures. Leave empty when the imported material already references its images",
                                        default="",
                                        maxlen=1024,
                                        subtype="DIR_PATH")
                                        
    aut_subf : BoolProperty(
    name="Search Sub-folders",
    description="Search the folder above recursively (RSX nests textures under <export>/<model>/)",
    default = False
    )                                                
    
    ### For Recolor ####    
    cust_enum2 : bpy.props.EnumProperty(
        name = "Shader",
        description = "Shader for Autotex",
        default='OP1',
        items = [('OP1', "Apex Shader", ""),
                 ('OP2', "Apex Shader+_v3.4", ""),
                 ('OP3', "S/G-Blender", "")    
                ]
        )
        
    recolor_folder: bpy.props.StringProperty(name="Folder",
                                        description="Select Recolor textures folder",
                                        default="",
                                        maxlen=1024,
                                        subtype="DIR_PATH")
                                        
    
    rec_alpha : BoolProperty(
    name="Plug Alpha?",
    description="Recolor Alpha property",
    default = True
    ) 
    

    cust_enum_shader : bpy.props.EnumProperty(
        name = "Shader",
        description = "Append Shader",
        default='OP1',
        items = [('OP1', "Apex Shader", ""),
                 ('OP2', "Apex Shader+_v3.4", ""),
                 ('OP3', "S/G-Blender", ""),
                 ('OP4', "Apex Cycles (Blue)", ""),
                 ('OP5', "Apex Mobile (Biast12)", "")     
                ]
        )
    
    
    cust_enum_hdri : bpy.props.EnumProperty(
        name = "Theme",
        description = "Append HDRI",
        default='OP1',
        items = [('OP1', "Blender Default", ""),
                 ('OP2', "Apex Lobby", ""),
                 ('OP3', "Party Crasher", ""),
                 ('OP4', "Encore", ""),
                 ('OP5', "Habitat", ""),
                 ('OP6', "Kings Canyon (Old)", ""),
                 ('OP7', "Kings Canyon (New)", ""),
                 ('OP8', "Kings Canyon (Night)", ""),
                 ('OP9', "Olympus", ""),
                 ('OP10', "Phase Runner", ""),
                 ('OP11', "Storm Point", ""),
                 ('OP12', "Worlds Edge", ""),
                 ('OP13', "Sky", ""),
                 ('OP14', "-- HDRI from Poly Haven --", ""),
                 ('OP15', "Indoor", ""),
                 ('OP16', "Outdoor", ""),
                 ('OP17', "Outdoor under shade", ""),
                 ('OP18', "Morning Forest", ""), 
                 ('OP19', "-- Blender Built-in HDRI --", ""),
                 ('OP20', "City", ""),
                 ('OP21', "Courtyard", ""),
                 ('OP22', "Forest", ""),
                 ('OP23', "Interior", ""),
                 ('OP24', "Night", ""),
                 ('OP25', "Studio", ""),
                 ('OP26', "Sunrise", ""),
                 ('OP27', "Sunset", "")      
                ]
        )

        
    cust_enum_hdri_noast : bpy.props.EnumProperty(
        name = "HDRI",
        description = "Append default HDRI",
        default='OP1',
        items = [('OP1', "Blender Default", ""),
                 ('OP2', "City", ""),
                 ('OP3', "Courtyard", ""),
                 ('OP4', "Forest", ""),
                 ('OP5', "Interior", ""),
                 ('OP6', "Night", ""),
                 ('OP7', "Studio", ""),
                 ('OP8', "Sunrise", ""),
                 ('OP9', "Sunset", "")      
                ]
        )      

        
    my_bool : BoolProperty(
    name="Parent to Bone? (Not done yet)",
    description="Mirage Bone parent property",
    default = False
    )
    
    '''
    mytool_color : bpy.props.FloatVectorProperty(
                     name = "Color",
                     subtype = "COLOR",
                     size = 4,
                     min = 0.0,
                     max = 1.0,
                     default = (1.0,1.0,1.0,1.0))
    OPERATOR: 
    clr = scene.my_prefs.mytool_color
                    
    mat = bpy.data.objects['Laser_pt1'].active_material
    nodes = mat.node_tree.nodes['Mix']
    node_color = nodes.inputs['Color1'].default_value
    nodes.inputs['Color1'].default_value = (clr[0], clr[1], clr[2], clr[3]) 
    '''                    
    
    
    
    ####   Add-on update check ####
    # The online version check used to run here, in the class body, which made
    # every Blender launch wait on a GitHub request with no timeout.  It now
    # runs only when the user presses "Check for Updates".
    global addon_name
    global addon_ver 
    temp_ver = []   
    for mod_name in bpy.context.preferences.addons.keys():
        mod_name_split = mod_name.split("-")[0]
        for x in range(len(addon)):
            if mod_name_split == addon[x]:
                addon_name.append(mod_name_split)
                mod = sys.modules[mod_name]
                mod_ver = mod.bl_info.get('version', (-1, -1, -1))
                for i in range(len(mod_ver)):
                    temp_ver.append(str(mod_ver[i]))
                addon_ver.append('.'.join(temp_ver))
                del temp_ver[:]
                
    
##########################################
#   Online version tracking
##########################################

#: The original add-on this build is forked from.  Kept as a link only: a
#: fork publishes its own releases, so checking the upstream feed would
#: report version numbers that have nothing to do with what is installed
#: here.  Point the "Releases Repository" preference at this build's own
#: repository to have Auto-update notices track it instead.
UPSTREAM_URL = "https://github.com/Gl2imm/Apex-Toolbox"

#: ``key -> (atom feed, marker, split index)``.  Each GitHub releases feed is
#: parsed for the newest tag.  Every parse is guarded: a feed whose layout has
#: changed must not abort the whole update check, which is exactly what used
#: to happen with the cast feed.
_RELEASE_FEEDS = {
    "legion": ("https://github.com/r-ex/LegionPlus/releases.atom",
               "437133675/", 2),
    "io_anim_seanim": ("https://github.com/SE2Dev/io_anim_seanim/releases.atom",
                       "72251837/", 1),
    "ApexMapImporter": (
        "https://github.com/llennoco22/Apex-mprt-importer-for-Blender/releases.atom",
        "433190309/", 1),
}

#: The cast plugin publishes its Blender version inside the release title.
#: The title format changed from "[Plugins] Blender <v>, Maya <v>" to
#: "[Plugins] Blender, Maya v1.99"; both are accepted now.
_CAST_FEED = "https://github.com/dtzxporter/cast/releases.atom"
_CAST_TITLE_RE = re.compile(
    r"<title>\[Plugins\][^<]*?v?(\d+\.\d+(?:\.\d+)?)[^<]*</title>")

#: Seconds before an online check gives up.  The old code had no timeout at
#: all and ran at import time, so an unreachable GitHub stalled Blender.
NETWORK_TIMEOUT = 8


def _fetch(url):
    """GET ``url`` and return the body, or ``None`` on any failure."""
    try:
        request = Request(url, headers={'User-Agent': 'Apex-Toolbox/' + ver})
        with urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            return response.read().decode('utf-8', errors='replace')
    except (OSError, ValueError) as error:
        print("Apex Toolbox: could not reach %s (%s)" % (url, error))
        return None


_ENTRY_TITLE_RE = re.compile(r"<entry>.*?<title>(.*?)</title>", re.DOTALL)


def newest_release_tag(repo):
    """Newest release title of ``owner/name`` on GitHub, or ``None``.

    Repository agnostic, because this build is a fork: the numeric feed ids
    the original hardcoded are specific to the original's repository.
    """
    repo = (repo or "").strip().strip("/")
    if not repo or repo.count("/") != 1:
        return None
    text = _fetch("https://github.com/%s/releases.atom" % repo)
    if not text:
        return None
    match = _ENTRY_TITLE_RE.search(text)
    return match.group(1).strip() if match else None


def _tag_from_feed(text, marker, index):
    """Newest release tag from an atom feed, or ``None`` if unrecognised."""
    if not text or marker not in text:
        return None
    parts = text.split(marker)
    if len(parts) <= index:
        return None
    tag = parts[index].split("</id>")[0].strip()
    return tag or None


def fetch_online_versions(operator=None):
    """Refresh every tracked version. Never raises; reports what it found."""
    global lts_ver, legion_lts_ver, io_anim_lts_ver
    global cast_lts_ver, semodel_lts_ver, mprt_lts_ver

    checked = 0
    failed = []

    prefs = addon_prefs()
    repo = getattr(prefs, "update_repo", "") if prefs else ""
    if repo:
        tag = newest_release_tag(repo)
        if tag:
            lts_ver = tag
            checked += 1
        else:
            failed.append(repo)

    tag = _tag_from_feed(_fetch(_RELEASE_FEEDS["legion"][0]),
                         _RELEASE_FEEDS["legion"][1],
                         _RELEASE_FEEDS["legion"][2])
    if tag and tag != "nightly":
        legion_lts_ver = tag
        checked += 1
    elif not tag:
        failed.append("Legion+")

    for name in addon_name:
        if name in _RELEASE_FEEDS:
            url, marker, index = _RELEASE_FEEDS[name]
            tag = _tag_from_feed(_fetch(url), marker, index)
            if not tag:
                failed.append(name)
                continue
            checked += 1
            if name == "io_anim_seanim":
                io_anim_lts_ver = tag
            elif name == "ApexMapImporter":
                mprt_lts_ver = tag
        elif name == "io_scene_cast":
            text = _fetch(_CAST_FEED)
            match = _CAST_TITLE_RE.search(text) if text else None
            if match:
                cast_lts_ver = match.group(1)
                checked += 1
            else:
                failed.append("io_scene_cast")
        elif name == "io_model_semodel":
            # No releases feed; the repo publishes from its default branch.
            semodel_lts_ver = "0.0.3"

    if operator is not None:
        if failed:
            operator.report(
                {"WARNING"},
                "Checked %d source(s); could not read: %s"
                % (checked, ", ".join(failed)))
        else:
            operator.report({"INFO"},
                            "Checked %d version source(s)." % checked)
    return checked


TOON_INSTRUCTIONS = """Apex Toon Shader (Beta)

Inspired by the Lightning Boy Studio Toon Shader. Some nodes and the key light
setup come from https://youtu.be/VmyMbgMh-eQ

Notes
  1. Do not expect the model to look finished straight away. You will need to
     aim the Key Light and Fill Light, which set the shadow outline directions.
  2. This setup works in EEVEE only.
  3. It needs no lights or HDRI, and will not look right if you add any.
  4. It shades the model only. Other objects in the scene need the
     "Apex ToonShader" group applied by hand.
  5. If the head outline shows through the eyes, lower the Solidify modifier
     thickness towards 0 (for example -0.015 m).

Guide
  1. Import a model and texture it.
  2. Select the parts you want to toon shade and press "Toon It".
  3. Use the Key Light and Fill Light objects to aim the shadow outlines.
  4. If shadows glitch, set the material Shadow Mode to None.
  5. Set the Key/Fill Light colours to taste.
  6. The Toolbox panel exposes the key settings; the rest are in the Shader tab.

Good luck with your renders.
"""


############   URL HANDLER OPERATOR   ##############    
class LGNDTRANSLATE_URL(bpy.types.Operator):
    bl_label = "BUTTON CUSTOM"
    bl_idname = "object.lgndtranslate_url"
    bl_options = {'REGISTER', 'UNDO'}
    link : bpy.props.StringProperty(name= "Added")


    def execute(self, context):
        link = (self.link)
        

        if link == "check_update":
            fetch_online_versions(self)

        if link == "io_anim_seanim":
            webbrowser.open_new("https://github.com/SE2Dev/io_anim_seanim/releases")
            
        if link == "cast":
            webbrowser.open_new("https://github.com/dtzxporter/cast/releases")
            
        if link == "io_model_semodel":
            # Used to open the io_anim_seanim page by mistake, and the old
            # blender-28 branch URL is a 404.
            webbrowser.open_new("https://github.com/dtzxporter/io_model_semodel")
            
        if link == "mprt":
            webbrowser.open_new("https://github.com/llennoco22/Apex-mprt-importer-for-Blender/releases")                                                

        if link == "legion_update":
            webbrowser.open_new("https://github.com/r-ex/LegionPlus/releases")
                    
        if link == "upstream":
            # The project this build is forked from.
            webbrowser.open_new(UPSTREAM_URL)

        if link == "update":
            prefs = addon_prefs()
            repo = getattr(prefs, "update_repo", "") if prefs else ""
            webbrowser.open_new(
                "https://github.com/%s/releases" % repo if repo
                else UPSTREAM_URL)
            
        if link == "instructions":
            path = os.path.join(my_path, "Credits and Instructions.txt")
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    body = handle.read()
            except OSError as error:
                self.report({"ERROR"}, "Could not read Credits and Instructions.txt: %s" % error)
                return {"CANCELLED"}
            show_text_datablock(context, "Instructions", body, self)

        if link == 'workflow_guide':
            path = os.path.join(my_path, 'WORKFLOW_GUIDE.md')
            try:
                with open(path, encoding='utf-8') as handle:
                    body = handle.read()
            except OSError as error:
                self.report({'ERROR'}, 'Could not open the workflow guide: %s' % error)
                return {'CANCELLED'}
            show_text_datablock(context, 'Apex Workflow Guide', body, self)

        if link == "version":
            path = os.path.join(my_path, "Version_log.txt")
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    body = handle.read()
            except OSError as error:
                self.report({"ERROR"}, "Could not read Version_log.txt: %s" % error)
                return {"CANCELLED"}
            show_text_datablock(context, "Version_log", body, self)

        if link == "toon_shader":
            show_text_datablock(context, "Toon Shader Instructions",
                                TOON_INSTRUCTIONS, self)

        if link == "asset_file":
            webbrowser.open_new("https://drive.google.com/file/d/14z98OfTWH9Uku2MFssg1bs2qjjVVkOWz/view?usp=sharing")            
                
            '''
            text = "https://github.com/Gl2imm/Apex-Toolbox/releases"
            t = bpy.data.texts.new("Your Favourite Addon Link")
            t.write(text)
            bpy.context.area.ui_type = 'TEXT_EDITOR'
            bpy.context.space_data.text = bpy.data.texts['Your Favourite Addon Link']
            '''
            
        return {'FINISHED'}
        
    
############   AUTO_TEX   ##############
def append_apex_node_group(group_name, restore_selection=()):
    """Append one of the Apex shader node groups from ApexShader.blend.

    Selection and the active object remain unchanged. ``restore_selection``
    is retained for compatibility with the existing operator callbacks.
    """
    # Loading datablocks directly leaves the user's selection and active
    # object intact, including in background Blender and non-3D editors.
    with bpy.data.libraries.load(os.path.join(my_path, 'ApexShader.blend'),
                                 link=False) as (available, requested):
        if group_name not in available.node_groups:
            raise RuntimeError("Shader '%s' is missing from ApexShader.blend" % group_name)
        requested.node_groups = [group_name]


class BUTTON_CUSTOM(bpy.types.Operator):
    """Auto_tex -- resolve and connect the textures of the selected meshes.

    The texture resolution itself lives in the ``apex_tex`` package so that the
    legacy Legion+ naming convention and current RSX/CAST exports share one
    implementation across all three shader options.
    """

    bl_label = "Texture Model"
    bl_idname = "object.button_custom"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(texture_targets(context))

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        prefs = context.scene.my_prefs
        return apex_autotex.run(
            context,
            shader_key=prefs.cust_enum2,
            append_node_group=append_apex_node_group,
            texture_folder=prefs.autotex_folder,
            search_subfolders=prefs.aut_subf,
            operator=self,
            remembered_roots=remembered_texture_roots(),
            remember_callback=store_texture_roots,
            objects=texture_targets(context),
            report_callback=lambda *args: capture_texture_report(context, *args),
        )


class APEX_OT_report(bpy.types.Operator):
    """Open the latest saved report in the Text Editor, or copy its full contents"""
    bl_idname = 'object.apex_report'
    bl_label = 'Apex Report'
    kind: bpy.props.EnumProperty(items=[('texture', 'Texture', ''),
                                        ('health', 'Scene Health', ''),
                                        ('repair', 'Repair', '')])
    copy: BoolProperty(default=False, options={'SKIP_SAVE'})

    def execute(self, context):
        report = getattr(context.scene.my_prefs, self.kind + '_report')
        if report is None:
            self.report({'WARNING'}, 'Run the tool to create a report first.')
            return {'CANCELLED'}
        if self.copy:
            context.window_manager.clipboard = report.as_string()
            self.report({'INFO'}, 'Report copied.')
        else:
            show_text_datablock(context, report.name, report.as_string(), self)
        return {'FINISHED'}


class APEX_OT_check_scene(bpy.types.Operator):
    """Check materials, missing images, UVs, rig targets and render setup without changing them"""
    bl_idname = 'object.apex_check_scene'
    bl_label = 'Check Scene Health'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = context.scene.my_prefs
        objects = health_targets(context)
        if not objects and prefs.health_scope == 'SELECTION':
            self.report({'WARNING'}, 'Select a model, or choose View Layer to check the scene.')
            return {'CANCELLED'}
        issues = apex_health.inspect_scene(objects, context.scene,
                                           prefs.health_scope == 'VIEW_LAYER')
        prefs.health_issues.clear()
        prefs.health_index = 0
        for issue in issues:
            entry = prefs.health_issues.add()
            for field in ('code', 'severity', 'object', 'title', 'detail'):
                setattr(entry, field, getattr(issue, field))
        summary, body = apex_health.format_health(issues, len(objects), prefs.health_scope)
        save_tool_report(prefs, 'health', summary, body)
        self.report({'INFO'}, summary)
        return {'FINISHED'}


class APEX_OT_select_issues(bpy.types.Operator):
    """Select visible, selectable meshes in the last health check, optionally by issue type"""
    bl_idname = 'object.apex_select_issues'
    bl_label = 'Select Affected Meshes'
    bl_options = {'REGISTER', 'UNDO'}
    code: bpy.props.StringProperty(default='', options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        targets = {issue.object for issue in context.scene.my_prefs.health_issues
                   if issue.object and (not self.code or issue.code == self.code)}
        targets = [obj for obj in targets if obj.name in context.view_layer.objects
                   and obj.visible_get(view_layer=context.view_layer) and not obj.hide_select]
        if not targets:
            self.report({'WARNING'}, 'No visible, selectable meshes for these issues. Run Check again if the scene changed.')
            return {'CANCELLED'}
        for obj in context.selected_objects:
            obj.select_set(False)
        targets.sort(key=lambda obj: obj.name.casefold())
        for obj in targets:
            obj.select_set(True)
        context.view_layer.objects.active = targets[0]
        return {'FINISHED'}


class APEX_OT_repair_textures(bpy.types.Operator):
    """Relink missing images by unique exact filename; shared images update for all users"""
    bl_idname = 'object.apex_repair_textures'
    bl_label = 'Repair Missing Textures'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        prefs = context.scene.my_prefs
        objects = health_targets(context)
        if not objects and prefs.health_scope == 'SELECTION':
            self.report({'WARNING'}, 'Select a model first.')
            return {'CANCELLED'}
        folder = bpy.path.abspath(prefs.repair_folder) if prefs.repair_folder else ''
        images = apex_health.referenced_images(
            objects, context.scene.world if prefs.health_scope == 'VIEW_LAYER' else None)
        try:
            summary, body = apex_health.repair_images(images, folder, prefs.repair_subfolders)
        except ValueError as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        save_tool_report(prefs, 'repair', summary, body)
        bpy.ops.object.apex_check_scene()
        self.report({'INFO'}, summary)
        return {'FINISHED'}


class APEX_UL_health_issues(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.title, icon='ERROR' if item.severity == 'ERROR' else 'INFO')
        row.label(text=item.object.name if item.object else 'Scene')


def model_xyz_euler(context):
    targets = apex_health.model_rotation_targets(context.selected_objects, context.view_layer)
    bones = [bone for obj in targets if obj.type == 'ARMATURE' for bone in obj.pose.bones]
    return apex_health.use_xyz_euler(targets, bones)


def report_xyz_euler(operator, result):
    objects, bones, skipped = result
    message = 'XYZ Euler: %d objects, %d bones changed.' % (objects, bones)
    if skipped:
        message += ' %d animated, driven, constrained or read-only targets left unchanged.' % skipped
    operator.report({'WARNING'} if skipped else {'INFO'}, message)


class APEX_OT_xyz_euler(bpy.types.Operator):
    """Switch quaternion rotations to XYZ Euler on selected models and their bones, or selected pose bones; preserve orientation and skip animated, driven, constrained or read-only targets"""
    bl_label = 'Quaternion to XYZ Euler'
    bl_idname = 'object.apex_xyz_euler'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'POSE':
            return bool(context.selected_pose_bones)
        return context.mode == 'OBJECT' and any(
            obj.type in {'MESH', 'ARMATURE', 'EMPTY'} for obj in context.selected_objects)

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        result = (apex_health.use_xyz_euler((), context.selected_pose_bones)
                  if context.mode == 'POSE' else model_xyz_euler(context))
        report_xyz_euler(self, result)
        return {'FINISHED'} if sum(result[:2]) or not result[2] else {'CANCELLED'}


class APEX_OT_forget_texture_roots(bpy.types.Operator):
    """Clear the export folders Auto Texture has remembered"""

    bl_label = "Forget Remembered Folders"
    bl_idname = "object.apex_forget_texture_roots"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        store_texture_roots([])
        self.report({'INFO'}, "Remembered texture folders cleared.")
        return {'FINISHED'}


############   TOON AUTOTEX   ##############
#: The Toon shader group exposes three texture inputs; the fourth role is used
#: as the transparency factor for hair, matching the historical node "3".
TOON_ROLES = [apex_roles.ALBEDO, apex_roles.SPECULAR, apex_roles.EMISSIVE,
              apex_roles.SCATTER]


class BUTTON_TOON(bpy.types.Operator):
    bl_label = "BUTTON_TOON"
    bl_idname = "object.button_toon"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        scene = context.scene
        prefs = scene.my_prefs
        skip = ['wraith_base_hair','wraith_base_eyecornea','wraith_base_eyeshadow','wraith_base_eye']

        if not selected_meshes(context):
            self.report({'WARNING'},
                        "Select the mesh objects you want to toon shade.")
            return {'CANCELLED'}
        selection = [obj.name for obj in bpy.context.selected_objects]
         
        if bpy.data.node_groups.get('Apex ToonShader') == None:
            bpy.ops.wm.append(directory =my_path + blend_file + ap_node, filename ='Apex ToonShader')
        
        if bpy.data.collections.get('Apex ToonShader') == None:
            bpy.ops.wm.append(directory =my_path + blend_file + ap_collection, filename ='Apex ToonShader')
        
        # The Toon shader needs EEVEE.  Blender 4.2 renamed the engine to
        # BLENDER_EEVEE_NEXT, and the old hardcoded identifier raised
        # "enum BLENDER_EEVEE not found", which made Toon It fail outright.
        scene.render.engine = eevee_engine()
        shading = getattr(getattr(context, "space_data", None), "shading", None)
        set_if_present(shading, "use_scene_lights", True)
        set_if_present(shading, "use_scene_world", True)
        set_if_present(scene.eevee, "taa_samples", 64)
        # Bloom / AO / shadow bit depth are legacy EEVEE options that EEVEE
        # Next dropped; set them only where they still exist.
        set_if_present(scene.eevee, "use_bloom", True)
        set_if_present(scene.eevee, "use_gtao", True)
        set_if_present(scene.eevee, "use_shadow_high_bitdepth", True)
        set_if_present(scene.view_settings, "view_transform", 'Standard')
        set_if_present(scene.view_settings, "look", 'Medium High Contrast')
        
           
        if bpy.context.scene.world != "World":
            if "World" not in bpy.data.worlds:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_world, filename ="World")
            set_default = bpy.data.worlds["World"]
            scene.world = set_default      
        
        mat = bpy.data.materials.get("Black Outline")
        if mat == None:
            bpy.ops.wm.append(directory =my_path + blend_file + ap_material, filename ='Black Outline')
            mat = bpy.data.materials.get("Black Outline")        
            
        for x in range(len(selection)):
            bpy.data.objects[selection[x]].select_set(True)
            x += 1            

        # One shared texture-discovery pass for every selected material.
        toon_targets = [obj for obj in bpy.context.selected_objects
                        if obj.type == 'MESH']
        toon_batch = apex_autotex.resolve_for_objects(
            toon_targets, TOON_ROLES,
            texture_folder=prefs.autotex_folder,
            search_subfolders=prefs.aut_subf,
            remembered_roots=remembered_texture_roots(),
        )
        resolved_toon = toon_batch.images
        apex_autotex.learn_roots(toon_batch, remembered_texture_roots(),
                                 store_texture_roots)
 
                    
        for o in bpy.context.selected_objects:
            if o.type == 'MESH':    
                isbase = False

                for i in range(len(skip)):
                    if skip[i] in o.material_slots:
                        isbase = True
                        break
                
                if isbase == False:
                    if "Black Outline" not in o.material_slots:
                        o.data.materials.append(mat)
                        #Modifier
                        exists = False
                        for mod in o.modifiers:
                            if mod.name == "OUTLINE_SOLIDIFY":
                                exists = True
                        if exists:
                            mod = o.modifiers["OUTLINE_SOLIDIFY"]
                            mod.thickness = -0.1
                        else: 
                            o.modifiers.new("OUTLINE_SOLIDIFY","SOLIDIFY")
                            mod = o.modifiers["OUTLINE_SOLIDIFY"]
                            mod.use_flip_normals = True
                            mod.use_rim = False
                            mod.thickness = -0.1
                            mod.material_offset = 999
                    else:
                        pass
                else:
                    pass

                
                for mSlot in o.material_slots:
                    if mSlot.material is None:
                        continue
                    MatNodeTree = mSlot.material
                    # Toon uses the same RSX/CAST aware resolver as Auto
                    # Texture (v3.7 beta 4); it used to carry its own copy of
                    # the pre-RSX "<material name>_albedoTexture.png" lookup,
                    # which never matched a current RSX export.
                    toon_images = resolved_toon.get(MatNodeTree.name) or {}
                    if not toon_images:
                        print("[Toon] %s - no textures resolved, skipped."
                              % MatNodeTree.name)
                        continue

                    MatNodeTree.node_tree.nodes.clear()

                    for i, role in enumerate(TOON_ROLES):
                        texImage = toon_images.get(role)
                        if texImage is None:
                            continue
                        apex_shaders.apply_colorspace(texImage, role)
                        texNode = MatNodeTree.node_tree.nodes.new('ShaderNodeTexImage')
                        texNode.image = texImage
                        texNode.name = str(i)
                        texNode.location = (-50,50-260*i)

                    if isbase == True:        
                        if mSlot.name == 'wraith_base_eyecornea' or mSlot.name == 'wraith_base_eyeshadow':
                            NodeOutput = MatNodeTree.node_tree.nodes.new('ShaderNodeOutputMaterial')
                            NodeOutput.location = (800,0)
                            node_transparency = MatNodeTree.node_tree.nodes.new(type="ShaderNodeBsdfTransparent")
                            node_transparency.location = 300,200 
                            MatNodeTree.node_tree.links.new(NodeOutput.inputs[0], node_transparency.outputs[0])                 
                        else:
                            NodeGroup = MatNodeTree.node_tree.nodes.new('ShaderNodeGroup')
                            NodeGroup.node_tree = bpy.data.node_groups.get('Apex ToonShader')
                            MatNodeTree.node_tree.nodes['Group'].name = 'Apex ToonShader'
                            MatNodeTree.node_tree.nodes['Apex ToonShader'].label = 'Apex ToonShader'
                            NodeGroup.location = (300,0)
                            NodeOutput = MatNodeTree.node_tree.nodes.new('ShaderNodeOutputMaterial')
                            NodeOutput.location = (800,0)
                            
                            node_transparency = MatNodeTree.node_tree.nodes.new(type="ShaderNodeBsdfTransparent")
                            node_transparency.location = 300,200
                            node_mix = MatNodeTree.node_tree.nodes.new(type="ShaderNodeMixShader")
                            node_mix.location = 500,150
                                
                            MatNodeTree.node_tree.links.new(node_mix.inputs[1], node_transparency.outputs[0])
                            MatNodeTree.node_tree.links.new(node_mix.inputs[2], NodeGroup.outputs[0])
                            MatNodeTree.node_tree.links.new(node_mix.outputs[0], NodeOutput.inputs[0])
                            if mSlot.name == 'wraith_base_eye':
                                node_mix.inputs[0].default_value = 1 
                            
                        try:
                            MatNodeTree.node_tree.links.new(NodeGroup.inputs["--- Base Color ---"], MatNodeTree.node_tree.nodes[0].outputs["Color"])
                        except:
                            pass
                        
                        if mSlot.name == 'wraith_base_hair':
                            try:
                                MatNodeTree.node_tree.links.new(node_mix.inputs[0], MatNodeTree.node_tree.nodes[3].outputs["Color"])
                            except:
                                pass                            

                    else:  
                          
                        NodeGroup = MatNodeTree.node_tree.nodes.new('ShaderNodeGroup')
                        NodeGroup.node_tree = bpy.data.node_groups.get('Apex ToonShader')
                        MatNodeTree.node_tree.nodes['Group'].name = 'Apex ToonShader'
                        MatNodeTree.node_tree.nodes['Apex ToonShader'].label = 'Apex ToonShader'
                        NodeGroup.location = (300,0)
                        NodeOutput = MatNodeTree.node_tree.nodes.new('ShaderNodeOutputMaterial')
                        NodeOutput.location = (500,0)
                        MatNodeTree.node_tree.links.new(NodeOutput.inputs[0], NodeGroup.outputs[0])
                            
                        ColorDict = {
                            "0": "--- Base Color ---",
                            "1": "--- Specular map ---",
                            "2": "--- Emission Map ---",
                        }
                                          

                        for slot in ColorDict:
                            try:
                                MatNodeTree.node_tree.links.new(NodeGroup.inputs[ColorDict[slot]], MatNodeTree.node_tree.nodes[slot].outputs["Color"])
                            except:
                                pass
                    mSlot.material.blend_method = 'HASHED'
                    print("Textured",mSlot.name)
                                 
                      
        return {'FINISHED'}
    


############   AUTO SHADOW   ##############    
class BUTTON_SHADOW(bpy.types.Operator):
    bl_label = "BUTTON_SHADOW"
    bl_idname = "object.button_shadow"
    bl_options = {'REGISTER', 'UNDO'}
    shadow : bpy.props.StringProperty(name= "Added")
    
    
    
    def execute(self, context):
        scene = context.scene
        prefs = scene.my_prefs  
        shadow = (self.shadow)
        shdw_mat = ['Shadow_big', 'Shadow_med', 'Shadow_med_face', 'shadow_black', 'shadow_eye']  
        body_parts = [
                "eye",       #0 - eye
                "eyecornea", #1 - eye
                "glass",     #2 - eye
                "lense",     #3 - eye
                "eyeshadow", #4 - black
                "teeth",     #5 - black
                "head",      #6 - face
                "helmet",    #7 - face
                "hair",      #8 - face
                "body",      #9 - big
                "suit",      #10 - big
                "v_arms",    #11 - med
                "boots",     #12 - med
                "gauntlet",  #13 - med
                "jumpkit",   #14 - med
                "gear"       #15 - med
                ]        

        shadow_items = {
            'Eyes': [
                {'name': 'Shadow eyes'},            
                {'name': 'Shadow fog'}, 
                {'name': 'Shadow left eye'},
                {'name': 'Shadow right eye'},
            ]                                                                                                                                                                    
            }  
            
        shdw_bones = ['def_c_noseBridge', 'def_c_top_rope_12']
            
        if shadow == "Shadow":    
            selection = [obj.name for obj in bpy.context.selected_objects]
            bpy.context.scene.render.fps = 30
            
            print("############# TEXTURING SHADOW START #############")
            
            if bpy.data.objects.get('Shadow eyes') == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files =shadow_items.get("Eyes"))        
            
            for x in range(len(shdw_mat)):
                mat = bpy.data.materials.get(shdw_mat[x])
                if mat == None:
                    bpy.ops.wm.append(directory =my_path + blend_file + ap_material, filename =shdw_mat[x])
                
            for x in range(len(selection)):
                bpy.data.objects[selection[x]].select_set(True)
                x += 1             
             
            for o in bpy.context.selected_objects:
                if o.type == 'MESH':
                    mat_exist = False
                    try:
                        mat_part = o.material_slots[0].name.rsplit('_', 1)[1] 
                        mat_name = o.material_slots[0].name
                        mat_exist = True
                    except:
                        print("Unable to find any Material. Shadow Material cannot assign") 
                    
                    if mat_exist == True:
                        if mat_part in body_parts:
                            if body_parts.index(mat_part) in range(0,2):
                                mat = bpy.data.materials.get(shdw_mat[4])
                                o.data.materials.clear()
                                o.data.materials.append(mat)
                                print(mat_name + " *Assigned Shadow eye material*")
                            if body_parts.index(mat_part) in range(2,4):
                                bpy.data.objects[o.name].hide_set(True)
                                bpy.data.objects[o.name].hide_render = True
                                print(mat_name + " *Set as Hidden*")                                
                            if body_parts.index(mat_part) in range(4,6):
                                mat = bpy.data.materials.get(shdw_mat[3])
                                o.data.materials.clear()
                                o.data.materials.append(mat)
                                print(mat_name + " *Assigned Shadow black material*") 
                            if body_parts.index(mat_part) in range(6,9):
                                mat = bpy.data.materials.get(shdw_mat[2])
                                o.data.materials.clear()
                                o.data.materials.append(mat)
                                print(mat_name + " *Assigned Shadow face material*")  
                            if body_parts.index(mat_part) in range(9,11):
                                mat = bpy.data.materials.get(shdw_mat[0])
                                o.data.materials.clear()
                                o.data.materials.append(mat)
                                print(mat_name + " *Assigned Shadow big material*")  
                            if body_parts.index(mat_part) in range(11,16):
                                mat = bpy.data.materials.get(shdw_mat[1])
                                o.data.materials.clear()
                                o.data.materials.append(mat)
                                print(mat_name + " *Assigned Shadow med material*")    
                        else:
                            print(mat_name + " *Skipped*")                                                                                           
            print("############# TEXTURING SHADOW END #############")
        
        
        #######  ADJUST AND PARENT SHADOW EYE  #######
        if shadow == "Eyes_parent":
            sel_objects = bpy.context.selected_objects
            sel_names = [obj.name for obj in bpy.context.selected_objects]
            
            if bpy.data.objects.get('Shadow eyes') == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files =shadow_items.get("Eyes"))  
                bpy.ops.object.select_all(action='DESELECT')   
                bpy.context.view_layer.objects.active = None  
                bpy.data.objects[sel_names[0]].select_set(True)  
                bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]]   
            
            if not bpy.context.selected_objects:
                print("Nothing selected. Please select Model Bones in Object Mode")
            else:
                if len(sel_objects) > 1:
                    print("More than 1 Object slected. Please select only 1 Bone Object")
                else: 
                    if sel_objects[0].type != 'ARMATURE':
                        self.report({'WARNING'},
                                    "Select the model's armature (its bones "
                                    "object), not a mesh.")
                        return {'CANCELLED'}
                    else:
                        nose_bone = None
                        for bone_name in shdw_bones:
                            if sel_objects[0].pose.bones.get(bone_name) is not None:
                                nose_bone = sel_objects[0].pose.bones[bone_name].bone
                                break

                        if nose_bone is None:
                            # Not every legend rig carries a nose bone; say so
                            # instead of raising UnboundLocalError.
                            self.report(
                                {'ERROR'},
                                "'%s' has none of the head anchor bones (%s), "
                                "so the shadow eyes cannot be placed "
                                "automatically. Position and parent them by "
                                "hand." % (sel_objects[0].name,
                                           ", ".join(shdw_bones)))
                            return {'CANCELLED'}

                        if nose_bone is not None:
                            bpy.ops.object.posemode_toggle()
                            bpy.context.object.data.bones.active = nose_bone
                            nose_bone.select = True
                            bpy.ops.view3d.snap_cursor_to_selected()               
                            bpy.ops.object.posemode_toggle()
                            bpy.data.objects['Shadow eyes'].location = bpy.context.scene.cursor.location
                            if nose_bone.name == 'def_c_top_rope_12':
                                bpy.data.objects['Shadow eyes'].location = 0.0005311064887791872, -0.15554966032505035, 1.686505675315857
                            bpy.ops.view3d.snap_cursor_to_center()
                                             
                            bpy.ops.object.select_all(action='DESELECT')
                            bpy.context.view_layer.objects.active = None 
                            bpy.data.objects['Shadow eyes'].select_set(True) 
                            bpy.context.view_layer.objects.active = bpy.data.objects['Shadow eyes']        
                            boneToSelect = bpy.data.objects['Shadow eyes'].pose.bones['Bone'].bone
                            bpy.context.object.data.bones.active = boneToSelect
                            
                            bpy.context.view_layer.objects.active = None 
                            bpy.data.objects[sel_names[0]].select_set(True) 
                            bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]]    
                            boneToSelect2 = bpy.data.objects[sel_names[0]].pose.bones[nose_bone.name].bone
                            bpy.context.object.data.bones.active = boneToSelect2
                            boneToSelect2.select = True  
                            bpy.ops.object.parent_set(type='BONE')
                            
                            bpy.ops.object.select_all(action='DESELECT')
                            bpy.context.view_layer.objects.active = None
                            bpy.data.objects[sel_names[0]].select_set(True)
                            bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]] 
                            print("Parenting Shadow Eyes to " + sel_names[0] + " Done")
                                                              
        return {'FINISHED'}                                
    
############   RECOLOR   ##############     
class BUTTON_CUSTOM2(bpy.types.Operator):
    bl_label = "BUTTON CUSTOM2"
    bl_idname = "object.button_custom2"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        scene = context.scene
        prefs = scene.my_prefs
        rec_alpha = prefs.rec_alpha
        recoloured = 0
        skipped = 0

        if not selected_meshes(context):
            self.report({'WARNING'},
                        "Select the mesh objects you want to recolour.")
            return {'CANCELLED'}
        if not prefs.recolor_folder:
            self.report({'WARNING'},
                        "Choose the skin's texture folder first.")
            return {'CANCELLED'}
        texSets = [['albedoTexture'],['specTexture'],['emissiveTexture'],['scatterThicknessTexture'],['opacityMultiplyTexture'],['normalTexture'],['glossTexture'],['aoTexture'],['cavityTexture'],['anisoSpecDirTexture'],['iridescenceRampTexture']]
        ttf_texSets = [['col'],['spc'],['ilm'],['nml'],['gls'],['ao']]
        
        recolor_folder = os.path.normpath(bpy.path.abspath(prefs.recolor_folder))
        if not os.path.isdir(recolor_folder):
            self.report({'WARNING'}, 'The skin folder does not exist.')
            return {'CANCELLED'}
        recolor_folder = os.path.join(recolor_folder, '')
        visited_materials = set()
        report_lines = ['APEX TOOLBOX | Recolour', '', 'Skin folder: ' + recolor_folder]
        
        
        #print("Realpath") 
        #print(os.path.realpath(recolor_folder)) 
        #print("ABS") 
        #print(os.path.abspath(recolor_folder)) 
        #print("Dirname") 
        #print(os.path.dirname(os.path.realpath(recolor_folder)))   
            
        ######## Check if the Extended asset pack is installed ########
        asset_folder_set = os.path.join(bpy.path.abspath(addon_asset_folder()), '')
        assets_set = 1 if assets_installed() else 0
        
        print("asset_folder_set: " + asset_folder_set)       
        
        body_parts = [
                "head",
                "helmet",
                "hair",
                "eye",
                "eyecornea",
                "eyeshadow",
                "teeth",
                "body",
                "v_arms",
                "boots",
                "gauntlet",
                "jumpkit",
                "gear"
                ]    
            
    ########## OPTION - 1 (Apex Shader) ############
        if prefs.cust_enum == 'OP1':
            print("\n######## RECOLORING MODEL: ########")
            if bpy.data.node_groups.get('Apex Shader') == None:
                selection = [obj.name for obj in bpy.context.selected_objects]
                bpy.ops.wm.append(directory =my_path + blend_file + ap_node, filename ='Apex Shader')
                for x in range(len(selection)):
                    bpy.data.objects[selection[x]].select_set(True)
                    x += 1
                print("Appended Apex Shader")

    ########## OPTION - 2 (Apex Shader+) ############
        if prefs.cust_enum == 'OP2':
            print("\n######## RECOLORING MODEL: ########")
            if bpy.data.node_groups.get('Apex Shader+_v3.4') == None:
                selection = [obj.name for obj in bpy.context.selected_objects]
                bpy.ops.wm.append(directory =my_path + blend_file + ap_node, filename ='Apex Shader+_v3.4')
                for x in range(len(selection)):
                    bpy.data.objects[selection[x]].select_set(True)
                    x += 1
                print("Apex Shader+ v3.4 Shader")
                
    ########## OPTION - 3 (S/G-Blender) ############
        if prefs.cust_enum == 'OP3':
            print("\n######## RECOLORING MODEL: ########")
            if bpy.data.node_groups.get('S/G-Blender') == None:
                selection = [obj.name for obj in bpy.context.selected_objects]
                bpy.ops.wm.append(directory =my_path + blend_file + ap_node, filename ='S/G-Blender')
                for x in range(len(selection)):
                    bpy.data.objects[selection[x]].select_set(True)
                    x += 1
                print("S/G Blender Shader")
                
                
        for o in bpy.context.selected_objects:
            if o.type == 'MESH':
                sel_objects = bpy.context.selected_objects
                for mSlot in o.material_slots:
                    if mSlot.material is None or mSlot.material in visited_materials:
                        continue
                    MatNodeTree = mSlot.material
                    visited_materials.add(MatNodeTree)
                    
                    mSlot_clean = apex_naming.strip_datablock_suffix(mSlot.name)

                    #rec_folder2 = ("D:\Personal\G-Drive\Blender\Apex\models\Wraith\Materials\wraith_lgnd_v19_liberator_rc01\\") #recolour folder
                    #rec_folder2 = ("D:\\Personal\\G-Drive\\Blender\\Apex\\models\Wraith\\pilot_light_wraith_legendary_01\\_images\\") #recolour folder
                    #rec_folder2 = ("C:\\Users\\User\\Downloads\\pilots\\materials\\") #TTF2 recolour folder
                    #rec_folder2 = ("D:\\Personal\\G-Drive\\Blender\\Apex\\models\\Wraith\\pov_pilot_light_wraith_legendary_01\\_images\\") #POV recolour folder
                    #rec_folder2 = ("D:\\Personal\\G-Drive\\Blender\\Apex\\models\\0. Guns\\flatline_v20_assim_w\\Materials\\flatline_react_v20_assim_rt01_main\\") #recolour folder
                    #rec_folder2 = ("D:\\Personal\\G-Drive\\Blender\\Apex\\models\\0. Guns\\flatline_v20_assim_w\\_images\\") #recolour folder
                    #recolor_folder = rec_folder2

                    try: 
                        foldername = recolor_folder.split(fbs)[-2] #folder name
                    except:
                        print("Materials Folder not selected")
                    else:    
                        foldernameSplit = foldername.split("_")[-1] #folder suffix _main _body to check forattachments
                        folderpath = recolor_folder 
                        imgBodyPart = mSlot_clean.split('_')[-1] #part name 
                        try:
                            ttf = mSlot_clean.split('_')[-2]  #ttf2 models
                        except:
                            continue
                        exist = 0                            
                        weapon = 1
                        
                        for b in range(len(body_parts)):
                            if body_parts[b] in mSlot_clean:
                                weapon = 0
                                break    
                                                                                    
                        ######## Weapon Codes ########
                        if weapon == 1:
                            if foldername == "_images": #normal autotex
                                foldername = mSlot_clean
                                
                            if foldernameSplit != imgBodyPart: #check if this is attachment
                                foldername = mSlot_clean
                        
                        ######## Legend Codes ########    
                        if weapon == 0:
                            
                            ######## Check folders in the recolor folder ######## 
                            body_part_found = 0
                            subf_name = None
                            rec_dir = os.listdir(recolor_folder)
                            #print(rec_dir)
                            for x in range(len(rec_dir)):
                                if body_part_found == 1:
                                    break
                                else:
                                    for i in range(len(body_parts)):
                                        if body_parts[i] in rec_dir[x]:
                                            print("Found: " + body_parts[i] + " in " + rec_dir[x])
                                            body_part_found = 1
                                            subf_name = rec_dir[x].rsplit('_' + body_parts[i])[0]
                                            break  
                            ######## Check folders in the recolor folder ########
                        
                            if foldername == "_images":              #normal autotex
                                foldername = mSlot_clean  
                            else:                                    #with sub folders
                                if body_parts[b] == "v_arms":        #with sub folders and check for v_arms in name
                                    folderpath = recolor_folder + foldername + "_" + body_parts[b]
                                    foldername = foldername + "_" + body_parts[b]  
                                else: 
                                    if subf_name != None:
                                        if foldername != subf_name:
                                            foldername = subf_name
                                    folderpath = recolor_folder + foldername + "_" + imgBodyPart
                                    foldername = foldername + "_" + imgBodyPart                                     
                                    if ttf == "skn":   #TTF Texturing
                                        folderpath = recolor_folder + mSlot_clean
                                        foldername = mSlot_clean
                                        texSets = ttf_texSets
           
                        
                        texFile = folderpath + fbs + foldername + '_' + texSets[0][0] + ".png" #check if albedo image exist, if not dont proceed clear nodes
                        
                        if os.path.isfile(texFile):
                            exist = 1
                        else:
                            if weapon == 0:
                                if assets_set == 1:
                                    texFile = asset_folder_set + "0. Legend_base" + fbs + mSlot_clean + '_' + texSets[0][0] + ".png" #Set path for Base files from assets folder
                                else:
                                    texFile = recolor_folder + "base" + fbs + mSlot_clean + '_' + texSets[0][0] + ".png" #check legend base files in the "Base" folder
                                if os.path.isfile(texFile):
                                    if assets_set == 1:
                                        folderpath = asset_folder_set + "0. Legend_base"
                                        foldername = mSlot_clean                                        
                                    else:
                                        folderpath = recolor_folder + "base"
                                        foldername = mSlot_clean
                                    exist = 1
                                if ttf == "skn":                                #TTF Try look different skin folders
                                    skn_name = mSlot_clean.rsplit('_', 2)[0]
                                    for s in ("_skn_02", "_skn_31"):
                                        texFile = recolor_folder + skn_name + s + fbs + skn_name + s + '_' + texSets[0][0] + ".png" #Set path for Base files from assets folder
                                        if os.path.isfile(texFile):
                                            print(texFile)
                                            folderpath = recolor_folder + skn_name + s
                                            foldername = skn_name + s
                                            exist = 1
                                            break
                                        
                        # Resolve before deciding whether a skin is usable.
                        # The old PNG-only gate rejected RSX _col / _nml and
                        # every non-PNG skin before reaching the shared resolver.
                        definition = apex_shaders.SHADER_DEFS[prefs.cust_enum]
                        candidates = [(folderpath, foldername),
                                      (recolor_folder, foldername),
                                      (os.path.join(recolor_folder, 'base'), mSlot_clean)]
                        if assets_set:
                            candidates.append((os.path.join(asset_folder_set, '0. Legend_base'),
                                               mSlot_clean))
                        if ttf == 'skn':
                            skn_name = mSlot_clean.rsplit('_', 2)[0]
                            for suffix in ('_skn_02', '_skn_31'):
                                candidates.append((os.path.join(recolor_folder, skn_name + suffix),
                                                   skn_name + suffix))
                        images = {}
                        for candidate_folder, candidate_name in dict.fromkeys(candidates):
                            results, candidate_images = apex_autotex.resolve_from_folder(
                                MatNodeTree, definition.wanted_roles,
                                candidate_folder, name_override=candidate_name)
                            if apex_roles.ALBEDO in candidate_images:
                                images = candidate_images
                                folderpath, foldername = candidate_folder, candidate_name
                                break

                        if images:
                            # Recolour now shares the Auto Texture resolver
                            # instead of carrying its own hardcoded
                            # "<name>_<role>Texture.png" probe, so an RSX
                            # named recolour folder works too.
                            definition = apex_shaders.SHADER_DEFS.get(
                                prefs.cust_enum)
                            if definition is None:
                                self.report({"ERROR"},
                                            "Unknown shader option.")
                                return {"CANCELLED"}
                            if bpy.data.node_groups.get(
                                    definition.group_name) is None:
                                append_apex_node_group(definition.group_name,
                                                       sel_objects)
                            for line in apex_resolver.format_report(
                                    mSlot_clean, "Recolour folder", results,
                                    order=definition.wanted_roles,
                                    prefix="[Recolour]"):
                                print(line)
                                report_lines.append(line)
                            try:
                                apex_shaders.build_material(
                                    MatNodeTree, definition, images,
                                    plug_alpha=rec_alpha)
                            except (RuntimeError, KeyError,
                                    AttributeError, TypeError, ValueError) as error:
                                print("[Recolour] %s could not be rebuilt: %s"
                                      % (mSlot_clean, error))
                                skipped += 1
                                report_lines.append('%s: left untouched (%s)' % (mSlot_clean, error))
                                continue
                            recoloured += 1
                            print("[Recolour] Textured " + mSlot_clean)
                        else:
                            skipped += 1
                            report_lines.append('%s: no matching albedo found; left untouched.' % mSlot_clean)
                            print("[Recolour] '%s' has no '%s_albedoTexture' "
                                  "style texture in %s"
                                  % (mSlot_clean, foldername, folderpath))

        save_tool_report(prefs, 'texture', 'Recolour: %d updated; %d left untouched' % (recoloured, skipped),
                         '\n'.join(report_lines) + '\n')
        if recoloured:
            self.report({"INFO"},
                        "Recolour: %d material(s) re-textured, %d skipped."
                        % (recoloured, skipped))
        else:
            self.report({"WARNING"},
                        "Recolour found nothing to apply. Check the skin "
                        "folder; see the console for details.")
        return {'FINISHED'}

class BUTTON_SHADERS(bpy.types.Operator):
    bl_label = "BUTTON_SHADERS"
    bl_idname = "object.button_shaders"
    bl_options = {'REGISTER', 'UNDO'}
    


    def execute(self, context):
        scene = context.scene
        prefs = scene.my_prefs
        
        if prefs.cust_enum_shader == 'OP1':
            if bpy.data.node_groups.get('Apex Shader') == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_node, filename ='Apex Shader')
                print("Apex Shader Appended")
            else:
                print("Apex Shader Already exist")
        if prefs.cust_enum_shader == 'OP2':
            if bpy.data.node_groups.get('Apex Shader+_v3.4') == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_node, filename ='Apex Shader+_v3.4')
                print("Apex Shader+_v3.4 Appended")
            else:
                print("Apex Shader+_v3.4 Already exist")                
        if prefs.cust_enum_shader == 'OP3':
            if bpy.data.node_groups.get('S/G-Blender') == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_node, filename ='S/G-Blender')
                print("S/G-Blender Appended")
            else:
                print("S/G-Blender Already exist")
        if prefs.cust_enum_shader == 'OP4':
            if bpy.data.node_groups.get('Apex Cycles (Blue)') == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_node, filename ='Apex Cycles (Blue)')
                print("Apex Cycles (Blue) Appended")
            else:
                print("Apex Cycles (Blue) Already exist")
        if prefs.cust_enum_shader == 'OP5':
            if bpy.data.node_groups.get('Apex Mobile Shader (Biast12)') == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_node, filename ='Apex Mobile Shader (Biast12)')
                print("Apex Mobile Shader (Biast12) Appended")
            else:
                print("Apex Mobile Shader (Biast12) Already exist")                
        return {'FINISHED'}  
    
    

class BUTTON_HDRIFULL(bpy.types.Operator):
    bl_label = "BUTTON_HDRIFULL"
    bl_idname = "object.button_hdrifull"
    bl_options = {'REGISTER', 'UNDO'}
    hdri : bpy.props.StringProperty(name= "Added")

    def execute(self, context):
        scene = context.scene
        prefs = scene.my_prefs
        hdri = (self.hdri)
        bldr_hdri = ['City','Courtyard','Forest','Interior','Night','Studio','Sunrise','Sunset']
        
        asset_folder = bpy.path.abspath(addon_asset_folder())

        if platform.system() == 'Windows':
            blend_file = ("\\Assets.blend")
        else:
            blend_file = ("/Assets.blend")
                               

        if hdri == 'hdri_noast': 
            if prefs.cust_enum_hdri_noast == 'OP1':
                hdri_name = "World"
            if prefs.cust_enum_hdri_noast == 'OP2':
                hdri_name = "City"
            if prefs.cust_enum_hdri_noast == 'OP3':
                hdri_name = "Courtyard"
            if prefs.cust_enum_hdri_noast == 'OP4':
                hdri_name = "Forest"
            if prefs.cust_enum_hdri_noast == 'OP5':
                hdri_name = "Interior"
            if prefs.cust_enum_hdri_noast == 'OP6':
                hdri_name = "Night"
            if prefs.cust_enum_hdri_noast == 'OP7':
                hdri_name = "Studio"
            if prefs.cust_enum_hdri_noast == 'OP8':
                hdri_name = "Sunrise"
            if prefs.cust_enum_hdri_noast == 'OP9':
                hdri_name = "Sunset" 

            if platform.system() == 'Windows':
                blend_file = ("\\ApexShader.blend")
            else:
                blend_file = ("/ApexShader.blend")               
            if hdri_name == "World":
                if bpy.context.scene.world != hdri_name:
                    if hdri_name not in bpy.data.worlds:
                        bpy.ops.wm.append(directory =my_path + blend_file + ap_world, filename =hdri_name)
                    hdri = bpy.data.worlds[hdri_name]
                    scene.world = hdri
            else:
                if bpy.context.scene.world != 'Blender HDRI':
                    if 'Blender HDRI' not in bpy.data.worlds:                       
                        bpy.ops.wm.append(directory =my_path + blend_file + ap_world, filename ='Blender HDRI')
                    hdri = bpy.data.worlds['Blender HDRI']
                    scene.world = hdri
                    # Blender ships these lowercase; matters on case-sensitive filesystems.
                    hdri_img_path = bldr_hdri_path + hdri_name.lower() + '.exr'
                    hdri_image = bpy.data.images.load(hdri_img_path)
                    bpy.data.worlds['Blender HDRI'].node_tree.nodes['Environment Texture'].image = hdri_image              


        if hdri == 'hdri': 
            if not require_assets(self):
                return {"CANCELLED"}
            if prefs.cust_enum_hdri == 'OP1':
                hdri_name = "World"                    
            if prefs.cust_enum_hdri == 'OP2':
                hdri_name = "Apex Lobby HDRI"          
            if prefs.cust_enum_hdri == 'OP3':
                hdri_name = "Party crasher HDRI"
            if prefs.cust_enum_hdri == 'OP4':
                hdri_name = "Encore HDRI"
            if prefs.cust_enum_hdri == 'OP5':
                hdri_name = "Habitat HDRI"
            if prefs.cust_enum_hdri == 'OP6':
                hdri_name = "Kings Canyon HDRI"
            if prefs.cust_enum_hdri == 'OP7':
                hdri_name = "Kings Canyon New HDRI"
            if prefs.cust_enum_hdri == 'OP8':
                hdri_name = "Kings Canyon Night HDRI"                        
            if prefs.cust_enum_hdri == 'OP9':
                hdri_name = "Olympus HDRI"
            if prefs.cust_enum_hdri == 'OP10':
                hdri_name = "Phase Runner HDRI"
            if prefs.cust_enum_hdri == 'OP11':
                hdri_name = "Storm Point HDRI"
            if prefs.cust_enum_hdri == 'OP12':
                hdri_name = "Worlds Edge HDRI" 
            if prefs.cust_enum_hdri == 'OP13':
                hdri_name = "Sky HDRI"
            if prefs.cust_enum_hdri == 'OP14':
                hdri_name = "blank"
            if prefs.cust_enum_hdri == 'OP15':
                hdri_name = "Indoor"
            if prefs.cust_enum_hdri == 'OP16':
                hdri_name = "Outdoor"
            if prefs.cust_enum_hdri == 'OP17':
                hdri_name = "Outdoor under shade"
            if prefs.cust_enum_hdri == 'OP18':
                hdri_name = "Morning Forest" 
            if prefs.cust_enum_hdri == 'OP19':
                hdri_name = "blank"
            if prefs.cust_enum_hdri == 'OP20':
                hdri_name = "City"
            if prefs.cust_enum_hdri == 'OP21':
                hdri_name = "Courtyard"
            if prefs.cust_enum_hdri == 'OP22':
                hdri_name = "Forest"
            if prefs.cust_enum_hdri == 'OP23':
                hdri_name = "Interior"
            if prefs.cust_enum_hdri == 'OP24':
                hdri_name = "Night"
            if prefs.cust_enum_hdri == 'OP25':
                hdri_name = "Studio"
            if prefs.cust_enum_hdri == 'OP26':
                hdri_name = "Sunrise"
            if prefs.cust_enum_hdri == 'OP27':
                hdri_name = "Sunset"                                                                                                 
            
            
            if hdri_name in bldr_hdri:
                if bpy.context.scene.world != 'Blender HDRI':
                    if 'Blender HDRI' not in bpy.data.worlds:
                        if platform.system() == 'Windows':
                            blend_file = ("\\ApexShader.blend")
                        else:
                            blend_file = ("/ApexShader.blend")                         
                        bpy.ops.wm.append(directory =my_path + blend_file + ap_world, filename ='Blender HDRI')
                    hdri = bpy.data.worlds['Blender HDRI']
                    scene.world = hdri
                    # Blender ships these lowercase; matters on case-sensitive filesystems.
                    hdri_img_path = bldr_hdri_path + hdri_name.lower() + '.exr'
                    hdri_image = bpy.data.images.load(hdri_img_path)
                    bpy.data.worlds['Blender HDRI'].node_tree.nodes['Environment Texture'].image = hdri_image 
            else:
                if hdri_name not in bpy.data.worlds:
                    if hdri_name == 'blank':
                        pass
                    else:
                        bpy.ops.wm.append(directory =asset_folder + blend_file + ap_world, filename =hdri_name)
                        hdri = bpy.data.worlds[hdri_name]
                        scene.world = hdri
                        print(hdri_name + " has been Appended and applied to the World")            
                else:
                    if bpy.context.scene.world != hdri_name:
                        hdri = bpy.data.worlds[hdri_name]
                        scene.world = hdri
                        print(hdri_name + " is already inside and it's been applied to the World") 


        if hdri == 'background': 
            if not require_assets(self):
                return {"CANCELLED"}
            hdri_name = 'blank'
            
            if prefs.cust_enum_hdri == 'OP1':
                hdri_name = "blank"                    

            if prefs.cust_enum_hdri == 'OP2':
                hdri_name = "blank" 
                        
            if prefs.cust_enum_hdri == 'OP3':
                hdri_name = "party crasher.png"
                
            if prefs.cust_enum_hdri == 'OP4':
                hdri_name = "encore.png"
                
            if prefs.cust_enum_hdri == 'OP5':
                hdri_name = "habit.png"
                
            if prefs.cust_enum_hdri == 'OP6':
                hdri_name = "Kings Canyon.png"
                
            if prefs.cust_enum_hdri == 'OP7':
                hdri_name = "Kings Canyon_new.png"
                
            if prefs.cust_enum_hdri == 'OP8':
                hdri_name = "Kings Canyon_night.png"                        
                
            if prefs.cust_enum_hdri == 'OP9':
                hdri_name = "olympus.png"
                
            if prefs.cust_enum_hdri == 'OP10':
                hdri_name = "phase runner.png"
                
            if prefs.cust_enum_hdri == 'OP11':
                hdri_name = "storm point.png"
                
            if prefs.cust_enum_hdri == 'OP12':
                hdri_name = "worlds edge.png" 
                
            if prefs.cust_enum_hdri == 'OP13':
                hdri_name = "Sky-1.png" 
                
            if prefs.cust_enum_hdri == 'OP14':
                hdri_name = "blank"
                
            if prefs.cust_enum_hdri == 'OP15':
                hdri_name = "blank"
                
            if prefs.cust_enum_hdri == 'OP16':
                hdri_name = "blank"
                
            if prefs.cust_enum_hdri == 'OP17':
                hdri_name = "blank"
                
            if prefs.cust_enum_hdri == 'OP18':
                hdri_name = "blank"                                   


            if hdri_name == 'blank':
                pass
            else:                
                if bpy.data.objects.get('Sky_background') == None:
                    bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, filename='Sky_background')
                    print("Sky Sphere Appended")

                for obj in bpy.context.selected_objects:
                    obj.select_set(False)             
                bpy.data.objects['Sky_background'].select_set(True)
                mat = bpy.data.objects['Sky_background'].active_material
                nodes = mat.node_tree.nodes['Image Texture.001']
                if bpy.data.images.get(hdri_name) == None:
                    bpy.ops.wm.append(directory =asset_folder + blend_file + ap_image, filename=hdri_name)
                img = bpy.data.images[hdri_name]
                nodes.image = img  
                print(hdri_name + " image has been set as Sky Texture")

        return {'FINISHED'}  



######### IK Bones set ########### 
class BUTTON_IKBONE(bpy.types.Operator):
    bl_label = "BUTTON_IKBONE"
    bl_idname = "object.button_ikbone"
    bl_options = {'REGISTER', 'UNDO'}
    ik_b : bpy.props.StringProperty(name= "Added")

    def execute(self, context):
        scene = context.scene
        prefs = scene.my_prefs
        ik_b = (self.ik_b)
        
        bones_to_select = ['def_l_wrist','def_r_wrist','def_l_elbow','def_r_elbow','def_l_ankle','def_r_ankle','def_l_knee','def_r_knee']
        constr_bones = ['def_l_wrist','def_r_wrist','def_l_ankle','def_r_ankle']
        adj_bones_f = ['def_l_knee','def_r_knee']
        ik_bone_names = ['HandIK.L','HandIK.R','LegIK.L','LegIK.R']
        ik_pole_names = ['ElbowIK.L','ElbowIK.R','KneeIK.L','KneeIK.R']
        ik_pole_move_f = ['KneeIK.L','KneeIK.R']
        ik_pole_move_b = ['ElbowIK.L','ElbowIK.R']

        arm = selected_armature(context)
        if arm is None:
            self.report({'WARNING'},
                        "Select the model's armature (its bones object) first.")
            return {'CANCELLED'}
        missing = [name for name in bones_to_select
                   if name not in arm.data.bones]
        if missing:
            self.report(
                {'ERROR'},
                "'%s' is missing the limb bones this needs (%s). It expects a "
                "standard Apex legend rig." % (arm.name, ", ".join(missing[:3])))
            return {'CANCELLED'}

        if arm is not None:
            # The edit-mode toggles below act on the active object.
            context.view_layer.objects.active = arm

            ##### GOTO Edit Mode #####
            if context.active_object.mode == 'EDIT':
                pass
            else:
                bpy.ops.object.editmode_toggle()
            
            
            ##### Create Poles and Targets #####    
            bpy.ops.armature.select_all(action='DESELECT')
            for bone in arm.data.edit_bones:
                if bone.name in bones_to_select:
                    bone.select_head = True
                    bone.select_tail = True   
            bpy.ops.armature.extrude_move(ARMATURE_OT_extrude={"forked":False}, TRANSFORM_OT_translate={"value":(0, 0.06, 0), "orient_type":'GLOBAL', "orient_matrix":((1, 0, 0), (0, 1, 0), (0, 0, 1)), "orient_matrix_type":'GLOBAL', "constraint_axis":(False, True, False),})
            bpy.ops.armature.select_more()
            bpy.ops.armature.parent_clear(type='CLEAR')
            
            
            ##### Rename all Selected Bones #####   
            for bone in bpy.context.selected_bones:
                if bone.name == 'def_l_elbow.001':
                    bone.name = 'ElbowIK.L'
                if bone.name == 'def_l_wrist.001':
                    bone.name = 'HandIK.L'
                if bone.name == 'def_r_elbow.001':
                    bone.name = 'ElbowIK.R'
                if bone.name == 'def_r_wrist.001':
                    bone.name = 'HandIK.R'
                if bone.name == 'def_l_ankle.001':
                    bone.name = 'LegIK.L'
                if bone.name == 'def_r_ankle.001':
                    bone.name = 'LegIK.R'
                if bone.name == 'def_l_knee.001':
                    bone.name = 'KneeIK.L'
                if bone.name == 'def_r_knee.001':
                    bone.name = 'KneeIK.R'    
            
                    
                               
            ##### MOVE Pole Bones #####
            bpy.ops.armature.select_all(action='DESELECT')
            for bone in arm.data.edit_bones:
                if bone.name in ik_pole_move_b:
                    bone.select_head = True
                    bone.select_tail = True                                                    
                bpy.ops.transform.translate(value=(0, 0.25, 0), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', constraint_axis=(False, True, False))
                bpy.ops.armature.select_all(action='DESELECT')
                if bone.name in ik_pole_move_f:
                    bone.select_head = True
                    bone.select_tail = True                                                    
                bpy.ops.transform.translate(value=(-0, -0.75, -0), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', constraint_axis=(False, True, False))
                bpy.ops.armature.select_all(action='DESELECT')
                
                ##### small bone adjustments #####
                if bone.name in adj_bones_f:
                    bone.select_head = True
                    bone.select_tail = True                                                    
                bpy.ops.transform.translate(value=(-0, -0.002, -0), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', constraint_axis=(False, True, False))
                bpy.ops.armature.select_all(action='DESELECT')                
                  
            
            
            ##### GOTO Pose Mode #####
            bpy.ops.object.editmode_toggle()
            if context.active_object.mode == 'POSE':
                pass
            else:
                bpy.ops.object.posemode_toggle()


            ##### Add Constrains #####
            for x in range(len(constr_bones)):
                ik_bone = arm.pose.bones[constr_bones[x]].bone
                bpy.context.selected_objects[0].pose.bones[ik_bone.name].bone.select = True
                bpy.context.selected_objects[0].data.bones.active = ik_bone
                bpy.ops.pose.constraint_add(type='IK')
                constr = bpy.context.object.pose.bones[constr_bones[x]].constraints["IK"]
                constr.target = arm
                constr.subtarget = ik_bone_names[x]
                constr.pole_target = arm
                constr.pole_subtarget = ik_pole_names[x]
                if x == 1:
                    constr.pole_angle = 1.5708
                if x == 3:
                    constr.pole_angle = 3.14159
                constr.iterations = 500
                if x <= 1:
                    constr.chain_count = 4
                else:
                    constr.chain_count = 3
                    
                    
            ##### Limit Distance IK Poles ##### 
            for x in range(len(ik_pole_names)): 
                lim_bone = arm.pose.bones[ik_pole_names[x]].bone 
                bpy.context.selected_objects[0].pose.bones[lim_bone.name].bone.select = True
                bpy.context.selected_objects[0].data.bones.active = lim_bone
                bpy.ops.pose.constraint_add(type='LIMIT_DISTANCE')
                limit = bpy.context.object.pose.bones[ik_pole_names[x]].constraints["Limit Distance"]
                limit.target = arm
                limit.subtarget = constr_bones[x]
                if x >= 2:
                    limit.distance = 1
                else:
                    limit.distance = 0.5


        return {'FINISHED'} 
    
    

######### Wraith Buttons ###########    
    
# Wraith Portal #
class WR_BUTTON_PORTAL(bpy.types.Operator):
    bl_label = "WR_BUTTON_PORTAL"
    bl_idname = "object.wr_button_portal"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        portal_items = [
                {'name': 'wraith_portal'}, 
                {'name': 'Inner_Ring_1'}, 
                {'name': 'Inner_Ring_1_br'},
                {'name': 'Inner_Ring_2'},
                {'name': 'Inner_Ring_2_br'}
                ]    
        if bpy.data.objects.get('wraith_portal') == None:
            bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files =portal_items)
            print("Wraith Portal Appended")
        else:
            print("Wraith Portal already exist")
        return {'FINISHED'}      
   


######### Gibby Buttons ###########    

class GB_BUTTON_ITEMS(bpy.types.Operator):
    bl_label = "GB_BUTTON_ITEMS"
    bl_idname = "object.gb_button_items"
    bl_options = {'REGISTER', 'UNDO'}
    gibby : bpy.props.StringProperty(name= "Added")


    def execute(self, context):
        scene = context.scene
        prefs = scene.my_prefs
        gibby = (self.gibby)
        bubble_items_friendly = [
                {'name': 'Gibby bubble friendly'}, 
                {'name': 'Gibby bubble core friendly'}, 
                {'name': 'Gibby bubble image friendly'},
                {'name': 'Gibby bubble rod friendly'}
                ]    
        bubble_items_enemy = [
                {'name': 'Gibby bubble enemy'}, 
                {'name': 'Gibby bubble core enemy'}, 
                {'name': 'Gibby bubble image enemy'},
                {'name': 'Gibby bubble rod enemy'}
                ]                   
    
           
        #Gibby Dome Shield friendly
        if gibby == "Gibby bubble friendly":
            if bpy.data.objects.get(gibby) == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files=bubble_items_friendly)
                print("Gibby Friendly Bubble Appended")
            else:
                print("Gibby Friendly Bubble already exist")
        
        #Gibby Dome Shield enemy        
        if gibby == "Gibby bubble enemy":
            if bpy.data.objects.get(gibby) == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files=bubble_items_enemy)
                print("Gibby Enemy Bubble Appended")
            else:
                print("Gibby Enemy Bubble already exist")
                
        return {'FINISHED'} 
    
       
   
######### Mirage Buttons ###########    
    
# Mirage Decoy #
class MR_BUTTON_DECOY(bpy.types.Operator):
    bl_label = "Decoy Outline Thickness"
    bl_idname = "object.mr_button_decoy"
    bl_options = {'REGISTER', 'UNDO'}
    mr_decoy : bpy.props.StringProperty(name= "Added")
    
    
    #Operator Properties
    outline_thickness : FloatProperty(
        name = "Outline Thickness",
        description = "Thickness of the applied outline",
        default = 0.23,
        min = 0,
        max = 1000000
    )

        
    def execute(self, context):
        scene = context.scene
        prefs = scene.my_prefs   
        sel = bpy.context.selected_objects
        mr_decoy = (self.mr_decoy)
        decoy_items = [
                {'name': 'Decoy'}, 
                {'name': 'Floor_bloom'}, 
                {'name': 'Flare Generator'},
                {'name': 'Decoy Effects'},
                {'name': 'Decoy flare'},
                {'name': 'Decoy Text'},
                {'name': 'Decoy text triangle'},
                {'name': 'Psyche_Out'}
                ]
        
        # Mirage Decoy Effect Add #               
        if mr_decoy == "Decoy":
            if bpy.data.objects.get('Decoy') == None:
                # Copy current selection #
                selection = [obj.name for obj in bpy.context.selected_objects]
                # Append Objects #
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files=decoy_items)
                 # Unselect all in selected #
                for obj in bpy.context.selected_objects:
                    obj.select_set(False)
                # Select initially selected #
                for x in range(len(selection)):
                    bpy.data.objects[selection[x]].select_set(True)
                    x += 1 
                # Append Material #               
                bpy.ops.wm.append(directory =my_path + blend_file + ap_material, filename ='Mirage_decoy_Material')
                # Unselect all in selected #
                for obj in bpy.context.selected_objects:
                    obj.select_set(False)
                # Select initially selected #
                for x in range(len(selection)):
                    bpy.data.objects[selection[x]].select_set(True)
                    x += 1

                print("Mirage Decoy Effect Appended, Material applied. Adding Modifier")
            else:
                print("Mirage Decoy Effect already exist. Adding Modifier only")
            

                   
            for obj in sel:
                if obj.type in ["MESH", "CURVE"]:
                    bpy.context.view_layer.objects.active = obj

                    #Material

                    mat_missing = True

                    for slot in obj.data.materials:
                        if slot is not None:
                            if slot.name == "Mirage_decoy_Material":
                                mat_missing = False

                    if mat_missing:
                        mat = bpy.data.materials.get("Mirage_decoy_Material")
                        bpy.context.object.data.materials.append(mat)


                    #Modifier

                    exists = False

                    for mod in bpy.context.object.modifiers:
                        if mod.name == "mirage_decoy":
                            exists = True

                    if exists:
                        mod = bpy.context.object.modifiers["mirage_decoy"]
                        mod.thickness = -(self.outline_thickness)
                    else: 
                        obj.modifiers.new("mirage_decoy","SOLIDIFY")
                        mod = obj.modifiers["mirage_decoy"]
                        mod.use_flip_normals = True
                        mod.use_rim = False
                        mod.thickness = -(self.outline_thickness)
                        mod.material_offset = 999
                        
            print("Mirage Decoy Effect Modifier Added") 

        # Mirage Decoy Effect Parenting #
        if mr_decoy == "Decoy_parent":
            sel_objects = bpy.context.selected_objects
            sel_names = [obj.name for obj in bpy.context.selected_objects]
            
                
            if not bpy.context.selected_objects:
                print("Nothing selected. Please select Model Bones in Object Mode")
            else:
                if len(sel_objects) > 1:
                    print("More than 1 Object slected. Please select only 1 Bone Object")
                else:
                    for bones in sel_objects:
                        if bones.type in ["ARMATURE"]:
                            if bpy.data.objects.get('Decoy') == None:
                                print("Decoy Effect not Found. Pls add Effect first")
                            else:
                                #print(sel_objects.type)
                                bpy.ops.object.mode_set(mode='OBJECT')
                                bpy.ops.object.select_all(action='DESELECT')
                                bpy.context.view_layer.objects.active = None
                                bpy.data.objects['Decoy'].select_set(True)
                                bpy.data.objects[sel_names[0]].select_set(True)
                                bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]]
                                

                                arm = bpy.data.objects['Decoy']
                                bpy.ops.object.mode_set(mode='EDIT')
                                bpy.ops.armature.select_all(action='DESELECT')
                                

                                bones_to_select = ['Bone']
                                for bone in arm.data.edit_bones:
                                    if bone.name in bones_to_select:
                                        bone.select = True
                                        
                                arm = bpy.data.objects[sel_names[0]]
                                bones_to_select = ['def_c_spineA']
                                for bone in arm.data.edit_bones:
                                    if bone.name in bones_to_select:
                                        bone.select = True 
                                        
                                bpy.ops.object.mode_set(mode='OBJECT')
                                bpy.ops.object.parent_set(type='OBJECT')
                                
                                print("Parenting Decoy Effect to Mirage Done")
                        else:
                            print("Selected Object is Not a Bone. Pls Select Bones")                                

        return {'FINISHED'} 
                

######### Valkyrie Buttons ###########    

class VK_BUTTON_ITEMS(bpy.types.Operator):
    bl_label = "VK_BUTTON_ITEMS"
    bl_idname = "object.vk_button_items"
    bl_options = {'REGISTER', 'UNDO'}
    valk : bpy.props.StringProperty(name= "Added")


    def execute(self, context):
        scene = context.scene
        prefs = scene.my_prefs
        valk = (self.valk)
        flames_items = [
                {'name': 'Flames left'}, 
                {'name': 'Flames right'} 
                ]    
    
           
        #Valk Flames
        if valk == "Flames":
            if bpy.data.objects.get('Flames left') == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files=flames_items)
                print("Valkyrie Flames Bubble Appended")
            else:
                print("Valkyrie Flames Bubble already exist")
        

        # Valk Flames Parenting #
        if valk == "Flames_parent":
            sel_objects = bpy.context.selected_objects
            sel_names = [obj.name for obj in bpy.context.selected_objects]
            
                
            if not bpy.context.selected_objects:
                print("Nothing selected. Please select Model Bones in Object Mode")
            else:
                if len(sel_objects) > 1:
                    print("More than 1 Object slected. Please select only 1 Bone Object")
                else:
                    for bones in sel_objects:
                        if bones.type in ["ARMATURE"]:
                            if bpy.data.objects.get('Flames left') == None:
                                print("Flames Effect not Found. Pls add Effect first")
                            else:
                                #Deselect All and select only bones that were chosen
                                bpy.ops.object.mode_set(mode='OBJECT')
                                bpy.ops.object.select_all(action='DESELECT')
                                bpy.context.view_layer.objects.active = None
                                bpy.data.objects[sel_names[0]].select_set(True)
                                bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]]
                                
                                #Select left turbine bone in Bone Edit Mode       
                                arm = bpy.data.objects[sel_names[0]]
                                bpy.ops.object.mode_set(mode='EDIT')
                                bones_to_select = ['def_l_turbine']
                                for bone in arm.data.edit_bones:
                                    if bone.name in bones_to_select:
                                        bone.select = True 
                                
                                #Exit out Edit Mode and Deselect All    
                                bpy.ops.object.mode_set(mode='OBJECT')
                                bpy.ops.object.select_all(action='DESELECT')
                                
                                #Select Flames, Select bones that were chosen, set bones active and parent to them
                                bpy.data.objects['Flames left'].select_set(True)
                                bpy.data.objects[sel_names[0]].select_set(True)
                                bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]]
                                bpy.ops.object.parent_set(type='BONE')
                                
                                #Deselect All and select only bones that were chosen    
                                bpy.ops.object.select_all(action='DESELECT')
                                bpy.data.objects[sel_names[0]].select_set(True)
                                bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]] 
                                
                                #Select right turbine bone in Bone Edit Mode       
                                arm = bpy.data.objects[sel_names[0]]
                                bpy.ops.object.mode_set(mode='EDIT')
                                bones_to_select = ['def_r_turbine']
                                for bone in arm.data.edit_bones:
                                    if bone.name in bones_to_select:
                                        bone.select = True 
                                
                                #Exit out Edit Mode and Deselect All    
                                bpy.ops.object.mode_set(mode='OBJECT')
                                bpy.ops.object.select_all(action='DESELECT')
                                
                                #Select Flames, Select bones that were chosen, set bones active and parent to them
                                bpy.data.objects['Flames right'].select_set(True)
                                bpy.data.objects[sel_names[0]].select_set(True)
                                bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]]
                                bpy.ops.object.parent_set(type='BONE') 
                                
                                bpy.ops.object.select_all(action='DESELECT')                                                              
                                                                
                                print("Parenting Flames to Valkyrie Done")
                        else:
                            print("Selected Object is Not a Bone. Pls Select Bones") 
                
        return {'FINISHED'} 
    
    

######### Badge Buttons ###########    
class BDG_BUTTON_SPAWN(bpy.types.Operator):
    bl_label = "BDG_BUTTON_SPAWN"
    bl_idname = "object.bdg_button_spawn"
    bl_options = {'REGISTER', 'UNDO'}
    badge : bpy.props.StringProperty(name= "Added")


    def execute(self, context):
        if platform.system() == 'Windows':
            blend_file = ("\\Assets.blend")
        else:
            blend_file = ("/Assets.blend")

        asset_folder = bpy.path.abspath(addon_asset_folder())
        if not require_assets(self):
            return {"CANCELLED"}

        badge_items = {
            'Badge - 20 Bombs (v2)': [
                {'name': 'Badge - 20 Bombs (v2)'}, 
                {'name': 'skull_gladcard_LOD0_SEModelMesh'}    
            ]
            } 
                
        if bpy.data.objects.get(self.badge) == None:
            if self.badge == 'Badge - 20 Bombs (v2)':
                bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=badge_items.get('Badge - 20 Bombs (v2)'))
            else:
                bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, filename =self.badge)
            print(self.badge + " Appended")
        else:
            print(self.badge + " already inside")
  
        return {'FINISHED'} 
    
    
######### Legends Effects Seer ###########    
class SEER_BUTTON_SPAWN(bpy.types.Operator):
    bl_label = "SEER_BUTTON_SPAWN"
    bl_idname = "object.seer_button_spawn"
    bl_options = {'REGISTER', 'UNDO'}
    lgnd_effect : bpy.props.StringProperty(name= "Added")


    def execute(self, context):
        lgnd_effect = self.lgnd_effect
        
        lgnd_effect_items = {
            'Seer Ultimate': [
                {'name': 'Seer Ultimate'},            
            ],
            }  

        #### Main loop for Seer items ####    
        for i in range(len(all_seer_items)):
            item = all_seer_items.get(str(i))
            split_item = item.split()
            if lgnd_effect == all_seer_items.get(str(i)):
                
                ### Ultimate ###
                if i == 0:
                    bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files=lgnd_effect_items.get(item))
                    
                print(item + " Appended") 
                break
            
        
        return {'FINISHED'}                       


######### Skydive Effects ###########    
class SKY_BUTTON_SPAWN(bpy.types.Operator):
    bl_label = "SKY_BUTTON_SPAWN"
    bl_idname = "object.sky_button_spawn"
    bl_options = {'REGISTER', 'UNDO'}
    sky_effect : bpy.props.StringProperty(name= "Added")


    def execute(self, context):
        sky_effect = self.sky_effect
        
        sky_effect_items = {
            'Skydive Ranked S9': [
                {'name': 'Skydive Ranked S9'}, 
                {'name': 'Skydive Ranked S9 trails'}, 
                {'name': 'Skydive Ranked S9 Smoke'},           
            ],
            } 

        def color():
            selection = [obj.name for obj in bpy.context.selected_objects]
            for obj in bpy.context.selected_objects:
                obj.select_set(False)
            bpy.data.objects[selection[2]].select_set(True)
            mat = bpy.data.objects[selection[2]].active_material
            nodes = mat.node_tree.nodes['Skydive Group Color S9'].node_tree.nodes
            links = mat.node_tree.nodes['Skydive Group Color S9'].node_tree.links
            node_output = nodes['Group Output']
            colours = {
                'Diamond': nodes['RGB.001'],
                'Master': nodes['RGB.002'],
                'Predator': nodes['RGB.003'],
                } 
            node_color = colours.get(split_item[1])
            link = links.new(node_color.outputs[0], node_output.inputs[0])
            
                            
        #### Main loop for Skydive items ####    
        for i in range(len(all_skydive_items)):
            item = all_skydive_items.get(str(i))
            split_item = item.rsplit(" ",1)

            if sky_effect == all_skydive_items.get(str(i)):
                 ### Ranked S9 ###
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files=sky_effect_items.get(split_item[0]))
                color()
                    
                print(item + " Appended")    
        
        # Skydive Parenting #
        if sky_effect == "Skydive_parent":
            sel_objects = bpy.context.selected_objects
            sel_names = [obj.name for obj in bpy.context.selected_objects]
            
                
            if not bpy.context.selected_objects:
                print("Nothing selected. Please select Model Bones in Object Mode")
            else:
                if len(sel_objects) > 1:
                    print("More than 1 Object slected. Please select only 1 Bone Object")
                else:
                    for bones in sel_objects:
                        if bones.type in ["ARMATURE"]:
                            if bpy.data.objects.get('Skydive Ranked S9') == None:
                                print("Skydive not Found. Pls add Effect first")
                            else:
                                #Deselect All and select only bones that were chosen
                                bpy.ops.object.mode_set(mode='OBJECT')
                                bpy.ops.object.select_all(action='DESELECT')
                                bpy.context.view_layer.objects.active = None
                                bpy.data.objects['Skydive Ranked S9'].select_set(True)
                                bpy.data.objects[sel_names[0]].select_set(True)
                                bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]]

                                

                                arm = bpy.data.objects['Skydive Ranked S9']
                                bpy.ops.object.mode_set(mode='EDIT')
                                bpy.ops.armature.select_all(action='DESELECT')
                                

                                bones_to_select = ['Bone']
                                for bone in arm.data.edit_bones:
                                    if bone.name in bones_to_select:
                                        bone.select = True
                                        
                                arm = bpy.data.objects[sel_names[0]]
                                bones_to_select = ['jx_c_pov']
                                for bone in arm.data.edit_bones:
                                    if bone.name in bones_to_select:
                                        bone.select = True 
                                        
                                bpy.ops.object.mode_set(mode='OBJECT')
                                bpy.ops.object.parent_set(type='BONE')
                                bpy.ops.object.select_all(action='DESELECT')                                                              
                                                                
                                print("Parenting Skydive Done")
                        else:
                            print("Selected Object is Not a Bone. Pls Select Bones") 
            
        return {'FINISHED'}  
    

######### Weapons Buttons ###########    
class WPN_BUTTON_SPAWN(bpy.types.Operator):
    bl_label = "WPN_BUTTON_SPAWN"
    bl_idname = "object.wpn_button_spawn"
    bl_options = {'REGISTER', 'UNDO'}
    weapon : bpy.props.StringProperty(name= "Added")


    def execute(self, context):
        scene = context.scene
        prefs = scene.my_prefs
        weapon = (self.weapon)

        
        weapon_items = {
            'Laser': [
                {'name': 'Laser'},            
                {'name': 'Laser_pt1'}, 
                {'name': 'Laser_pt2'}
            ]
            }        
           
        #Flatline flame button normal
        if weapon == "flatline_s4_glow_hex_LOD0_SEModelMesh.125":
            if bpy.data.objects.get(weapon) == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, filename =weapon)
                print("Flatline Flames Effect Appended")
            else:
                print("Flatline Flames Effect already exist")

        
        #Flatline flame parent button
        if weapon == "flatline_parent_flame":
            if bpy.data.objects.get("flatline_s4_glow_hex_LOD0_SEModelMesh.125") == None:
                print("Flatline Flames Effect not Found. Pls add Effect first")
            else:
                if bpy.data.objects.get("flatline_v20_assim_w_LOD0_skel") == None:
                    print("Flatline model <<flatline_v20_assim_w>> not detected. Add the model then click Parent it")
                else:
                    bpy.ops.object.select_all(action='DESELECT')
                    bpy.context.view_layer.objects.active = None 
                    bpy.data.objects['flatline_s4_glow_hex_LOD0_skel'].select_set(True) 
                    bpy.context.view_layer.objects.active = bpy.data.objects['flatline_s4_glow_hex_LOD0_skel']        
                    boneToSelect = bpy.data.objects['flatline_s4_glow_hex_LOD0_skel'].pose.bones['static_prop'].bone
                    bpy.context.object.data.bones.active = boneToSelect
                    
                    bpy.context.view_layer.objects.active = None 
                    bpy.data.objects['flatline_v20_assim_w_LOD0_skel'].select_set(True) 
                    bpy.context.view_layer.objects.active = bpy.data.objects['flatline_v20_assim_w_LOD0_skel']        
                    boneToSelect2 = bpy.data.objects['flatline_v20_assim_w_LOD0_skel'].pose.bones['def_c_base'].bone
                    bpy.context.object.data.bones.active = boneToSelect2
                    boneToSelect2.select = True  
                    bpy.ops.object.parent_set(type='BONE')
                    print("Parenting Flames to Flatline Done")                  
                    
                    
                    '''
                    bpy.ops.object.select_all(action='DESELECT')
                    bpy.context.view_layer.objects.active = None
                    bpy.data.objects['flatline_s4_glow_hex_LOD0_skel'].select_set(True)
                    bpy.data.objects['flatline_v20_assim_w_LOD0_skel'].select_set(True)
                    bpy.context.view_layer.objects.active = bpy.data.objects['flatline_v20_assim_w_LOD0_skel']
                    

                    arm = bpy.data.objects['flatline_s4_glow_hex_LOD0_skel']
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.armature.select_all(action='DESELECT')
                    

                    bones_to_select = ['static_prop']
                    for bone in arm.data.edit_bones:
                        if bone.name in bones_to_select:
                            bone.select = True
                            
                    arm = bpy.data.objects['flatline_v20_assim_w_LOD0_skel']
                    bones_to_select = ['def_c_base']
                    for bone in arm.data.edit_bones:
                        if bone.name in bones_to_select:
                            bone.select = True 
                            
                    bpy.ops.object.mode_set(mode='OBJECT')
                    bpy.ops.object.parent_set(type='BONE')
                    print("Parenting Flames to Flatline Done")
                    '''
            '''    
            if bpy.data.objects.get(self.weapon) == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, filename =self.badge)
                print(self.weapon + " Appended")
            else:
                print(self.weapon + " already inside")
            '''
        
        #Flatline flame button POV    
        if weapon == "flatline_s4_glow_hex_LOD0_SEModelMesh.001":
            if bpy.data.objects.get(weapon) == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, filename ="flatline_s4_glow_hex_LOD0_SEModelMesh.001")
                print("POV Flatline Flames Effect Appended")
            else:
                print("POV Flatline Flames Effect already exist")

        #Flatline flame parent button POV
        if weapon == "flatline_pov_parent_flame":
            if bpy.data.objects.get("flatline_s4_glow_hex_LOD0_SEModelMesh.001") == None:
                print("POV Flatline Flames Effect not Found. Pls add Effect first")
            else:
                if bpy.data.objects.get("flatline_v20_assim_v_LOD0_skel") == None:
                    print("POV Flatline model <<flatline_v20_assim_v>> not detected. Add the model then click Parent it")
                else:
                    bpy.ops.object.select_all(action='DESELECT')
                    bpy.context.view_layer.objects.active = None 
                    bpy.data.objects['flatline_s4_glow_hex_LOD0_skel.001'].select_set(True) 
                    bpy.context.view_layer.objects.active = bpy.data.objects['flatline_s4_glow_hex_LOD0_skel.001']        
                    boneToSelect = bpy.data.objects['flatline_s4_glow_hex_LOD0_skel.001'].pose.bones['static_prop'].bone
                    bpy.context.object.data.bones.active = boneToSelect
                    
                    bpy.context.view_layer.objects.active = None 
                    bpy.data.objects['flatline_v20_assim_v_LOD0_skel'].select_set(True) 
                    bpy.context.view_layer.objects.active = bpy.data.objects['flatline_v20_assim_v_LOD0_skel']        
                    boneToSelect2 = bpy.data.objects['flatline_v20_assim_v_LOD0_skel'].pose.bones['def_c_base'].bone
                    bpy.context.object.data.bones.active = boneToSelect2
                    boneToSelect2.select = True  
                    bpy.ops.object.parent_set(type='BONE')
                    print("Parenting Flames to POV Flatline Done") 
 
        #Flatline POV Animation   
        if weapon == "idle_reactive_layer_3_Fixed":
            if bpy.data.objects.get("flatline_v20_assim_v_LOD0_skel") == None:
                print("POV Flatline model 'flatline_v20_assim_v_LOD0_skel' not Found. Pls add model first")
            else:
                if bpy.data.objects.get(weapon) == None:
                    bpy.ops.wm.append(directory =my_path + blend_file + ap_action, filename ="idle_reactive_layer_3_Fixed")
                    print("POV Reactive Animation Appended")
                else:
                    print("POV Reactive Animation already exist")  
                
                object = bpy.data.objects.get('flatline_v20_assim_v_LOD0_skel')   
                object.animation_data_create()
                action = object.animation_data.action
                object.animation_data.action = bpy.data.actions.get("idle_reactive_layer_3_Fixed")   

               
        #######  LASER EFFECT  #######
        if weapon == "Laser":
            if bpy.data.objects.get(weapon) == None:
                bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files =weapon_items.get("Laser"))
                print("Laser Effect Appended")
            else:
                print("Laser Effect already exist")


        if weapon == "Laser_parent":
            if bpy.data.objects.get("Laser") == None:
                print("Laser Effect not Found. Pls add effect first")
            else:
                sel_objects = bpy.context.selected_objects
                sel_names = [obj.name for obj in bpy.context.selected_objects]
                if not bpy.context.selected_objects:
                    print("Nothing selected. Please select Model Bones in Object Mode")
                else:
                    if len(sel_objects) > 1:
                        print("More than 1 Object slected. Please select only 1 Bone Object")
                    else: 
                        try:
                            bpy.data.objects['Laser'].location = bpy.data.objects[sel_names[0]].pose.bones['ja_c_propGun'].location
                        except:
                            print("Bone 'ja_c_propGun' not found")
                        else:                                            
                            bpy.ops.object.select_all(action='DESELECT')
                            bpy.context.view_layer.objects.active = None 
                            bpy.data.objects['Laser'].select_set(True) 
                            bpy.context.view_layer.objects.active = bpy.data.objects['Laser']        
                            boneToSelect = bpy.data.objects['Laser'].pose.bones['Bone'].bone
                            bpy.context.object.data.bones.active = boneToSelect
                            
                            bpy.context.view_layer.objects.active = None 
                            bpy.data.objects[sel_names[0]].select_set(True) 
                            bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]]  
                            bpy.data.objects[sel_names[0]].rotation_euler.x = 1.5707963705062866
                            bpy.data.objects[sel_names[0]].rotation_euler.y = 0
                            bpy.data.objects[sel_names[0]].rotation_euler.z = 0                                  
                            boneToSelect2 = bpy.data.objects[sel_names[0]].pose.bones['ja_c_propGun'].bone
                            bpy.context.object.data.bones.active = boneToSelect2
                            boneToSelect2.select = True  
                            bpy.ops.object.parent_set(type='BONE')
                            
                            bpy.ops.object.select_all(action='DESELECT')
                            bpy.context.view_layer.objects.active = None
                            bpy.data.objects[sel_names[0]].select_set(True)
                            bpy.context.view_layer.objects.active = bpy.data.objects[sel_names[0]] 
                            print("Parenting laser to " + sel_names[0] + " Done")
                            
                                            
        if weapon == "Laser_move":
            if bpy.data.objects.get("Laser") == None:
                print("Laser Effect not Found. Pls add effect first")
            else:
                sel_objects = bpy.context.selected_objects
                sel_names = [obj.name for obj in bpy.context.selected_objects]
                if not bpy.context.selected_objects:
                    print("Nothing selected. Please select Model Bones in Object Mode")
                else:
                    if len(sel_objects) > 1:
                        print("More than 1 Object slected. Please select only 1 Bone Object")
                    else:
                        try:
                            bpy.data.objects['Laser'].location = bpy.data.objects[sel_names[0]].pose.bones['ja_c_propGun'].location
                        except:
                            print("Bone 'ja_c_propGun' not found")
                        else:
                            bpy.data.objects[sel_names[0]].rotation_euler.x = 1.5707963705062866
                            bpy.data.objects[sel_names[0]].rotation_euler.y = 0
                            bpy.data.objects[sel_names[0]].rotation_euler.z = 0
                            bpy.data.objects['Laser'].location.z = bpy.data.objects[sel_names[0]].pose.bones['ja_c_propGun'].bone.matrix_local[1][3] * 0.0254 - 0.018
                            bpy.data.objects['Laser'].location.y -= bpy.data.objects[sel_names[0]].pose.bones['ja_c_propGun'].bone.matrix_local[2][3] * 0.0254 + 0.04
                            print("Laser Effect moved") 

                                                                                               
        return {'FINISHED'}   
              


######### Loot Items Buttons ###########    
class LT_BUTTON_SPAWN(bpy.types.Operator):
    bl_label = "LT_BUTTON_SPAWN"
    bl_idname = "object.lt_button_spawn"
    bl_options = {'REGISTER', 'UNDO'}
    loot : bpy.props.StringProperty(name= "Added")
 

    def execute(self, context):
        loot = (self.loot)
        
        if platform.system() == 'Windows':
            blend_file = ("\\Assets.blend")
        else:
            blend_file = ("/Assets.blend")
        
        asset_folder = bpy.path.abspath(addon_asset_folder())
        if not require_assets(self):
            return {"CANCELLED"}


        loot_items = {
            'Armor': [
                {'name': 'w_loot_cha_shield_upgrade_body_LOD0_skel'},            
                {'name': 'w_loot_cha_shield_upgrade_body_LOD0_SEModelMesh.106'}, 
                {'name': 'w_loot_cha_shield_upgrade_body_LOD0_SEModelMesh.107'}
            ],
            'Helmet': [
                {'name': 'w_loot_cha_shield_upgrade_head_LOD0_skel'}, 
                {'name': 'w_loot_cha_shield_upgrade_head_LOD0_SEModelMesh.108'}, 
                {'name': 'w_loot_cha_shield_upgrade_head_LOD0_SEModelMesh.109'}
            ],
            'Phoenix Kit': [
                {'name': 'w_loot_wep_iso_phoenix_kit_v1_LOD0_skel'}, 
                {'name': 'w_loot_wep_iso_phoenix_kit_v1_LOD0_SEModelMesh.135'}, 
                {'name': 'w_loot_wep_iso_phoenix_kit_v1_LOD0_SEModelMesh.136'}
            ],
            'Shield Battery': [
                {'name': 'w_loot_wep_iso_shield_battery_large_LOD0_skel'}, 
                {'name': 'w_loot_wep_iso_shield_battery_large_LOD0_SEModelMesh.137'}, 
                {'name': 'w_loot_wep_iso_shield_battery_large_LOD0_SEModelMesh.138'}
            ],
            'Shield Cell': [
                {'name': 'w_loot_wep_iso_shield_battery_small_LOD0_skel'}, 
                {'name': 'w_loot_wep_iso_shield_battery_small_LOD0_SEModelMesh.139'}, 
                {'name': 'w_loot_wep_iso_shield_battery_small_LOD0_SEModelMesh.140'}
            ],
            'Med Kit': [
                {'name': 'w_loot_wep_iso_health_main_large_LOD0_skel'}, 
                {'name': 'w_loot_wep_iso_health_main_large_LOD0_SEModelMesh.133'}
            ],
            'Syringe': [
                {'name': 'w_loot_wep_iso_health_main_small_LOD0_skel'}, 
                {'name': 'w_loot_wep_iso_health_main_small_LOD0_SEModelMesh.134'}
            ],
            'Health Injector': [
                {'name': 'w_health_injector_LOD0_skel'}, 
                {'name': 'w_health_injector_LOD0_SEModelMesh.084'}
            ],            
            'Grenade': [
                {'name': 'm20_f_grenade_LOD0_skel'}, 
                {'name': 'm20_f_grenade_LOD0_SEModelMesh.147'}
            ],
            'Arc Star': [
                {'name': 'w_loot_wep_iso_shuriken_LOD0_skel'}, 
                {'name': 'w_loot_wep_iso_shuriken_LOD0_SEModelMesh.142'}
            ],
            'Thermite': [
                {'name': 'w_thermite_grenade_LOD0_skel'}, 
                {'name': 'w_thermite_grenade_LOD0_SEModelMesh.143'}
            ], 
            'Backpack Lv.3': [
                {'name': 'w_loot_char_backpack_heavy_LOD0_skel'}, 
                {'name': 'w_loot_char_backpack_heavy_LOD0_SEModelMesh.118'}
            ],    
            'Backpack Lv.2': [
                {'name': 'w_loot_char_backpack_medium_LOD0_skel'}, 
                {'name': 'w_loot_char_backpack_medium_LOD0_SEModelMesh.120'}
            ],    
            'Backpack Lv.1': [
                {'name': 'w_loot_char_backpack_light_LOD0_skel'}, 
                {'name': 'w_loot_char_backpack_light_LOD0_SEModelMesh.119'}
            ], 
            'Light Ammo': [
                {'name': 'w_loot_wep_ammo_sc_LOD0_skel'}, 
                {'name': 'w_loot_wep_ammo_sc_LOD0_SEModelMesh.123'}
            ], 
            'Heavy Ammo': [
                {'name': 'w_loot_wep_ammo_hc_LOD0_skel'}, 
                {'name': 'w_loot_wep_ammo_hc_LOD0_SEModelMesh.121'}
            ], 
            'Energy Ammo': [
                {'name': 'w_loot_wep_ammo_nrg_LOD0_skel'}, 
                {'name': 'w_loot_wep_ammo_nrg_LOD0_SEModelMesh.122'}
            ],
            'Shotgun Ammo': [
                {'name': 'w_loot_wep_ammo_shg_LOD0_skel'}, 
                {'name': 'w_loot_wep_ammo_shg_LOD0_SEModelMesh.124'}
            ], 
            'Respawn Beacon': [
                {'name': 'beacon_capsule_01_LOD0_skel'}, 
                {'name': 'beacon_capsule_01_LOD0_SEModelMesh.144'}
            ],  
            'Knockdown Shield': [
                {'name': 'w_loot_wep_iso_shield_down_v1_LOD0_skel'}, 
                {'name': 'w_loot_wep_iso_shield_down_v1_LOD0_SEModelMesh.141'}
            ],  
            'Heat Shield': [
                {'name': 'loot_void_ring_LOD0_skel'}, 
                {'name': 'loot_void_ring_LOD0_SEModelMesh.146'}
            ],  
            'Death Box': [
                {'name': 'death_box_01_gladcard_LOD0_skel.001'}, 
                {'name': 'death_box_01_gladcard_LOD0_SEModelMesh.145'},
                {'name': 'death_box_02_LOD0_skel'},
                {'name': 'death_box_02_LOD0_SEModelMesh.007'},
                {'name': 'deathbox_banner_line'},
                {'name': 'deathbox_banner_text'}
            ],                                                                                                                                                                       
            }  

            
        def armor_color():
            selection = [obj.name for obj in bpy.context.selected_objects]
            for obj in bpy.context.selected_objects:
                obj.select_set(False)
            bpy.data.objects[selection[1]].select_set(True)
            mat = bpy.data.objects[selection[1]].active_material
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            node_output = nodes['Armor shader']
            colours = {
                'Blue': nodes['RGB.001'],
                'Purple': nodes['RGB.002'],
                'Gold': nodes['RGB'],
                'Red': nodes['RGB.003'],
                } 
            if split_item[0] == "White":
                pass
            else:
                node_color = colours.get(split_item[0])
                link = links.new(node_color.outputs[0], node_output.inputs[0]) 
                
        
        #### Main loop for Loot items ####    
        for i in range(len(all_loot_items)):
            item = all_loot_items.get(str(i))
            split_item = item.split()

            if loot == all_loot_items.get(str(i)):
                
                ### Body Armor ###
                if i in range(*armor_range):
                    bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=loot_items.get(split_item[1]))
                    armor_color()
                    
                ### Helmet ###                    
                if i in range(*helmet_range):
                    bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=loot_items.get(split_item[1]))
                    armor_color()
                
                ### Meds ###                    
                if i in range(*meds_range):
                    bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=loot_items.get(item))

                ### Nades ###                    
                if i in range(*nades_range):
                    bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=loot_items.get(item))

                ### Ammo ###                    
                if i in range(*ammo_range):
                    bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=loot_items.get(item))

                ### Backpack ###                    
                if i in range(*bag_range):
                    bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=loot_items.get(item))
                  
                ### Backpack ###                    
                if i in range(*other_range):
                    bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=loot_items.get(item))
                                      
                print(item + " Appended") 
                break
            

        return {'FINISHED'} 



######### Lobby and Other Items Buttons ###########    
class LB_BUTTON_SPAWN(bpy.types.Operator):
    bl_label = "LB_BUTTON_SPAWN"
    bl_idname = "object.lb_button_spawn"
    bl_options = {'REGISTER', 'UNDO'}
    lobby_other : bpy.props.StringProperty(name= "Added")
 

    def execute(self, context):
        lobby_other = (self.lobby_other)
        
        if platform.system() == 'Windows':
            blend_file = ("\\Assets.blend")
        else:
            blend_file = ("/Assets.blend")
        
        asset_folder = bpy.path.abspath(addon_asset_folder())
        if lobby_other != 'Animated Staging' and not require_assets(self):
            return {"CANCELLED"}


        lobby_other_items = {
            'Heirloom Shards': [
                {'name': 'heirloom_LOD0_skel'},            
                {'name': 'heirloom_LOD0_SEModelMesh'}
            ],
            'Epic Shards': [
                {'name': 'currency_crafting_epic_LOD0_skel'}, 
                {'name': 'currency_crafting_epic_LOD0_SEModelMesh.003'}
            ], 
            'Rare Shards': [
                {'name': 'currency_crafting_rare_LOD0_skel'}, 
                {'name': 'currency_crafting_rare_LOD0_SEModelMesh.004'}
            ],   
            'Loot Drone': [
                {'name': 'drone_frag_loot_LOD0_skel'}, 
                {'name': 'drone_frag_loot_LOD0_SEModelMesh.005'}
            ],   
            'Respawn Beacon Hologram': [
                {'name': 'goblin_dropship_holo_LOD0_skel'}, 
                {'name': 'goblin_dropship_holo_LOD0_SEModelMesh.001'}, 
                {'name': 'goblin_dropship_holo_LOD0_SEModelMesh.002'}, 
                {'name': 'Respawn Hologram'}, 
                {'name': 'Respawn Spot Light'}
            ],   
            'Loot Ball': [
                {'name': 'loot_sphere_LOD0_skel'}, 
                {'name': 'loot_sphere_LOD0_SEModelMesh.006'}
            ],
            'Animated Staging': [
                {'name': 'Animated Staging With Light'}, 
                {'name': 'Area_left'},
                {'name': 'Area_overhead'},
                {'name': 'Area_right'},
                {'name': 'Floor Plane'},
                {'name': 'Staging Camera'},
            ]                                                                                                                                                                                                                     
            }   
        
        #### Main loop for Lobby and Other items #### 
        if lobby_other == 'Animated Staging':
            if platform.system() == 'Windows':
                blend_file = ("\\ApexShader.blend")
            else:
                blend_file = ("/ApexShader.blend")                         
            bpy.ops.wm.append(directory =my_path + blend_file + ap_object, files=lobby_other_items.get(lobby_other))
            print(lobby_other + " Appended")
        else:                       
            for i in range(len(all_lobby_other_items)):
                item = all_lobby_other_items.get(str(i))
                split_item = item.split()

                if lobby_other == all_lobby_other_items.get(str(i)):
                    
                    ### Lobby Items ###
                    if i in range(*lobby_lobby_range):
                        bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=lobby_other_items.get(item))
                        
                    ### Other Items ###                    
                    if i in range(*lobby_other_range):
                        bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=lobby_other_items.get(item))
                                                      
                    print(item + " Appended") 
                    break
            

        return {'FINISHED'} 
    
    

######### Heirloom Buttons ###########    
class HL_BUTTON_SPAWN(bpy.types.Operator):
    bl_label = "HL_BUTTON_SPAWN"
    bl_idname = "object.hl_button_spawn"
    bl_options = {'REGISTER', 'UNDO'}
    heirloom : bpy.props.StringProperty(name= "Added")
 

    def execute(self, context):
        heirloom = (self.heirloom)
        
        if platform.system() == 'Windows':
            blend_file = ("\\Assets.blend")
        else:
            blend_file = ("/Assets.blend")
        
        asset_folder = bpy.path.abspath(addon_asset_folder())
        if not require_assets(self):
            return {"CANCELLED"}


        heirloom_items = {
            'Gibraltar Set': [
                {'name': 'gibraltar_heirloom_v_LOD0_skel'},            
                {'name': 'gibraltar_heirloom_v_LOD0_SEModelMesh.008'}
            ],
            'Bangalore Set': [
                {'name': 'ptpov_bangalore_heirloom_LOD0_skel'}, 
                {'name': 'ptpov_bangalore_heirloom_LOD0_SEModelMesh.009'},
                {'name': 'ptpov_bangalore_heirloom_LOD0_SEModelMesh.010'}
            ], 
            'Lifeline Set (Animated)': [
                {'name': 'ptpov_baton_lifeline_LOD0_skel'}, 
                {'name': 'ptpov_baton_lifeline_LOD0_SEModelMesh.011'}
            ],   
            'Bloodhound Set': [
                {'name': 'ptpov_bloodhound_axe_LOD0_skel'}, 
                {'name': 'ptpov_bloodhound_axe_LOD0_SEModelMesh.013'}
            ],   
            'Caustic Set': [
                {'name': 'ptpov_caustic_heirloom_LOD0_skel'}, 
                {'name': 'ptpov_caustic_heirloom_LOD0_SEModelMesh.014'}
            ],   
            'Crypto Set': [
                {'name': 'ptpov_crypto_heirloom_LOD0_skel'}, 
                {'name': 'ptpov_crypto_heirloom_LOD0_SEModelMesh.015'},
                {'name': 'ptpov_crypto_heirloom_LOD0_SEModelMesh.016'},
                {'name': 'ptpov_crypto_heirloom_LOD0_SEModelMesh.017'}
            ],
            'Wraith Set': [
                {'name': 'ptpov_kunai_wraith_LOD0_skel'}, 
                {'name': 'ptpov_kunai_wraith_LOD0_SEModelMesh.018'}
            ],  
            'Mirage Set': [
                {'name': 'ptpov_mirage_heirloom_LOD0_skel'}, 
                {'name': 'ptpov_mirage_heirloom_LOD0_SEModelMesh.019'}, 
                {'name': 'ptpov_mirage_heirloom_LOD0_SEModelMesh.020'}, 
                {'name': 'ptpov_mirage_heirloom_LOD0_SEModelMesh.021'}
            ],  
            'Octane Set': [
                {'name': 'ptpov_octane_knife_LOD0_skel'}, 
                {'name': 'ptpov_octane_knife_LOD0_SEModelMesh.022'}, 
                {'name': 'ptpov_octane_knife_LOD0_SEModelMesh.023'}
            ],  
            'Pathfinder Set (Animated)': [
                {'name': 'ptpov_pathfinder_gloves_LOD0_skel'}, 
                {'name': 'ptpov_pathfinder_gloves_LOD0_SEModelMesh.024'},
                {'name': 'ptpov_pathfinder_gloves_LOD0_SEModelMesh.025'},
                {'name': 'ptpov_pathfinder_gloves_LOD0_SEModelMesh.026'},
                {'name': 'ptpov_pathfinder_gloves_LOD0_SEModelMesh.027'},
                {'name': 'ptpov_pathfinder_gloves_LOD0_SEModelMesh.028'},
                {'name': 'ptpov_pathfinder_gloves_LOD0_SEModelMesh.029'},
                {'name': 'ptpov_pathfinder_gloves_LOD0_SEModelMesh.030'},
                {'name': 'ptpov_pathfinder_gloves_LOD0_SEModelMesh.031'} 
            ],  
            'Rampart Set': [
                {'name': 'ptpov_rampart_heirloom_LOD0_skel'}, 
                {'name': 'ptpov_rampart_heirloom_LOD0_SEModelMesh.032'}, 
                {'name': 'ptpov_rampart_heirloom_LOD0_SEModelMesh.033'},
                {'name': 'ptpov_rampart_heirloom_LOD0_SEModelMesh.034'}
            ],  
            'Revenant Set': [
                {'name': 'revenant_heirloom_v21_base_v_LOD0_skel'}, 
                {'name': 'revenant_heirloom_v21_base_v_LOD0_SEModelMesh.035'}
            ],  
            'Valkyrie Set': [
                {'name': 'valkyrie_heirloom_v22_base_v_LOD0_skel'}, 
                {'name': 'valkyrie_heirloom_v22_base_v_LOD0_SEModelMesh.036'}
            ],  
            'Wattson Set (Animated)': [
                {'name': 'wattson_heirloom_v21_base_v_LOD0_skel'}, 
                {'name': 'wattson_heirloom_v21_base_v_LOD0_SEModelMesh.037'}
            ]                                                                                                                                                                                                                                                                                                                    
            }   
        
        #### Main loop for Heirloom items ####    
        for i in range(len(all_heirloom_items)):
            item = all_heirloom_items.get(str(i))
            split_item = item.split()

            if heirloom == all_heirloom_items.get(str(i)):
                
                ### Heirloom Items ###
                if i in range(len(all_heirloom_items)):
                    bpy.ops.wm.append(directory =asset_folder + blend_file + ap_object, files=heirloom_items.get(item))
                                                  
                print(item + " Appended") 
                break
            

        return {'FINISHED'} 
    

######### Other Effects Buttons ###########    
class EF_BUTTON_SPAWN(bpy.types.Operator):
    bl_label = "EF_BUTTON_SPAWN"
    bl_idname = "object.ef_button_spawn"
    bl_options = {'REGISTER', 'UNDO'}
    cool_effect : bpy.props.StringProperty(name= "Added")

    #Operator Properties
    wfrm_thickness : FloatProperty(
        name = "Wireframe Thickness",
        description = "Thickness of the applied wireframe",
        default = 0.07,
        min = 0,
        max = 0.15
    ) 

    def execute(self, context):
        cool_effect = (self.cool_effect)
        wfrm_thickness = (self.wfrm_thickness)
        sel = bpy.context.selected_objects 
        
        #### Wireframe Effect #### 
        if cool_effect == 'wireframe':
            if not bpy.context.selected_objects:
                print("Nothing selected. Please select Object to apply Effect")
            else:
                for obj in sel:
                    if obj.type in ["MESH"]:
                        bpy.context.view_layer.objects.active = obj

                        exists = False
                        for mod in bpy.context.object.modifiers:
                            if mod.name == "Wireframe":
                                exists = True

                        if exists:
                            mod = bpy.context.object.modifiers["Wireframe"]
                            mod.thickness = (wfrm_thickness)
                        else: 
                            obj.modifiers.new("Wireframe","WIREFRAME")
                            mod = obj.modifiers["Wireframe"]
                            mod.thickness = (wfrm_thickness)
                                
                    print("Cool Wireframe Effect Applied") 
        
        #### Wireframe Clear Effect #### 
        if cool_effect == 'wireframe_clear':
            if not bpy.context.selected_objects:
                print("Nothing selected. Please select Object to apply Effect")
            else:
                for obj in sel:
                    if obj.type in ["MESH"]:
                        bpy.context.view_layer.objects.active = obj

                        exists = False
                        for mod in bpy.context.object.modifiers:
                            if mod.name == "Wireframe":
                                exists = True

                        if exists:
                            mod = obj.modifiers["Wireframe"]
                            obj.modifiers.remove(mod)
                                
                    print("Cool Wireframe Effect Cleared")                   

        #### Set Active (Staging spawn in Lobby Other Items) ####
        if cool_effect == 'Staging Camera':
            cam = bpy.data.objects.get('Staging Camera')
            if cam is None:
                self.report({'WARNING'},
                            "No 'Staging Camera' in the scene. Add Animated "
                            "Staging + Camera first.")
                return {'CANCELLED'}
            # Used to hardcode bpy.data.scenes['Scene'].
            context.scene.camera = cam
            bpy.ops.object.select_all(action='DESELECT')
            bpy.context.view_layer.objects.active = None
            bpy.data.objects['Staging Camera'].select_set(True)
            bpy.context.view_layer.objects.active = bpy.data.objects['Staging Camera']
            print("'Staging Camera' Set as Active")
            del cam
            
            
        #### Add Basic Lights ####    
        if cool_effect == 'basic lights':
            bpy.ops.wm.append(directory =my_path + blend_file + ap_collection, filename='Basic Lights Setup')
            
            
        #### Adjust Model ####
        if cool_effect == 'adjust_model':
            if context.mode != 'OBJECT':
                self.report({'WARNING'}, 'Switch to Object Mode to prepare the model.')
                return {'CANCELLED'}
            if not bpy.context.selected_objects:
                self.report({'WARNING'},
                            "Select the imported model (its armature, or its "
                            "objects) in Object Mode first.")
                return {'CANCELLED'}
            if selected_armature(context) is None:
                self.report({'WARNING'},
                            "No armature among the selected objects. Select "
                            "the model's bones object.")
                return {'CANCELLED'}
            converted, skipped = apex_health.prepare_armatures(context.selected_objects)
            self.report({'INFO'}, '%d rigs prepared; %d already prepared.' % (converted, skipped))
            report_xyz_euler(self, model_xyz_euler(context))
            
        return {'FINISHED'}             
                              
    
    #PANEL UI
####################################
#   The sidebar is built from real Blender sub-panels instead of the nine
#   hand-rolled fold-outs the previous releases drew inside one 360-line
#   draw().  Each tool now owns a panel, so Blender handles the collapse
#   arrows, the open/closed state and the spacing consistently.
####################################

APEX_CATEGORY = "Apex Tools"


class ApexPanel:
    """Shared panel setup for everything in the Apex Tools tab."""

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = APEX_CATEGORY


class APEX_PT_main(ApexPanel, bpy.types.Panel):
    """Apex Toolbox"""

    bl_label = "Apex Toolbox " + ver
    bl_idname = "APEX_PT_main"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        if modules_are_stale():
            box = layout.box()
            box.alert = True
            box.label(text="Restart Blender", icon='ERROR')
            box.label(text="Update finishes on restart")
            return

        if newer_version(lts_ver, ver):
            layout.operator('object.lgndtranslate_url',
                            text="Update Available: " + lts_ver,
                            icon='IMPORT').link = "update"
        else:
            extended = assets_installed()
            layout.label(text=("Extended" if extended else "Lite") + " mode",
                         icon='CHECKMARK' if extended else 'INFO')


class APEX_PT_model(ApexPanel, bpy.types.Panel):
    """Preparing a freshly imported model"""

    bl_label = "Model"
    bl_idname = "APEX_PT_model"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        column.operator('object.ef_button_spawn',
                        text="Set Correct Model Size",
                        icon='FULLSCREEN_ENTER').cool_effect = 'adjust_model'
        layout.label(text="Select the armature", icon='INFO')
        layout.operator('object.apex_xyz_euler', icon='DRIVER_ROTATIONAL_DIFFERENCE')


class APEX_PT_materials(ApexPanel, bpy.types.Panel):
    """Texturing and shading the imported model"""

    bl_label = "Materials"
    bl_idname = "APEX_PT_materials"
    bl_order = 2

    def draw(self, context):
        pass


class APEX_PT_autotex(ApexPanel, bpy.types.Panel):
    """Find and connect the model's textures automatically"""

    bl_label = "Auto Texture"
    bl_idname = "APEX_PT_autotex"
    bl_parent_id = "APEX_PT_materials"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        prefs = context.scene.my_prefs

        targets = texture_targets(context)
        layout.label(text='%d meshes / %d materials' % (
            len(targets), len(apex_autotex.material_slots(targets))), icon='OUTLINER_OB_MESH')
        row = layout.row()
        row.use_property_split = False
        row.prop(prefs, 'include_model_meshes')
        layout.prop(prefs, "cust_enum2", text="Shader")

        column = layout.column()
        column.use_property_split = False
        column.scale_y = 1.3
        column.operator("object.button_custom", text="Texture Model",
                        icon='TEXTURE')
        if not targets:
            draw_wrapped(layout, 'Select meshes or the model armature to begin.', context)
        elif context.mode != 'OBJECT':
            layout.label(text='Switch to Object Mode', icon='INFO')
        if prefs.texture_report:
            box = layout.box()
            box.label(text='Last texture report', icon='INFO')
            draw_wrapped(box, prefs.texture_summary, context)
            draw_report_actions(box, 'texture')


class APEX_PT_autotex_search(ApexPanel, bpy.types.Panel):
    """Where Auto Texture looks for the texture files"""

    bl_label = "Search Options"
    bl_idname = "APEX_PT_autotex_search"
    bl_parent_id = "APEX_PT_autotex"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        prefs = context.scene.my_prefs

        layout.prop(prefs, "autotex_folder", text="Texture Folder")
        layout.prop(prefs, "aut_subf", text="Search Sub-folders")

        column = layout.column(align=True)
        column.use_property_split = False
        remembered = remembered_texture_roots()
        if remembered:
            column.label(text="%d folder(s) remembered" % len(remembered),
                         icon='CHECKMARK')
        else:
            column.label(text="Empty = automatic", icon='INFO')


class APEX_PT_recolour(ApexPanel, bpy.types.Panel):
    """Re-texture the model from a different skin's texture folder"""

    bl_label = "Recolour"
    bl_idname = "APEX_PT_recolour"
    bl_parent_id = "APEX_PT_materials"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        prefs = context.scene.my_prefs

        layout.prop(prefs, 'recolor_folder', text="Skin Folder")
        layout.prop(prefs, 'cust_enum', text="Shader")
        layout.prop(prefs, 'rec_alpha', text="Plug Alpha")

        column = layout.column()
        column.use_property_split = False
        column.scale_y = 1.3
        column.enabled = bool(prefs.recolor_folder)
        column.operator("object.button_custom2", text="Recolour Model",
                        icon='NODE_TEXTURE')
        if not prefs.recolor_folder:
            layout.label(text="Pick a skin folder", icon='INFO')


class APEX_PT_toon(ApexPanel, bpy.types.Panel):
    """Cel-shaded look (EEVEE only)"""

    bl_label = "Toon Shader"
    bl_idname = "APEX_PT_toon"
    bl_parent_id = "APEX_PT_materials"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator('object.lgndtranslate_url', text="Read Instructions",
                        icon='INFO').link = "toon_shader"

        column = layout.column()
        column.scale_y = 1.3
        column.operator("object.button_toon", text="Toon It", icon='UV')
        layout.label(text="Select meshes first", icon='INFO')


class APEX_PT_toon_settings(ApexPanel, bpy.types.Panel):
    """Live settings of the Apex ToonShader on the active material"""

    bl_label = "Toon Settings"
    bl_idname = "APEX_PT_toon_settings"
    bl_parent_id = "APEX_PT_toon"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return toon_shader_node(context) is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        node = toon_shader_node(context)
        if node is None:
            return

        # Key inputs of the Apex ToonShader group, by index.
        for index, label in ((4, None), (5, None), (6, None), (7, None),
                             (8, None), (11, "Reflection Color"),
                             (12, None), (13, None), (21, None)):
            try:
                socket = node.inputs[index]
            except IndexError:
                continue
            layout.prop(socket, "default_value", text=label or socket.name)

        material = context.object.active_material if context.object else None
        if material is not None and hasattr(material, "shadow_method"):
            layout.prop(material, "shadow_method", text="Shadow")
            layout.label(text="Set 'None' if shadows glitch", icon='INFO')


class APEX_PT_toon_render(ApexPanel, bpy.types.Panel):
    """Render settings the Toon shader depends on"""

    bl_label = "Toon Render Settings"
    bl_idname = "APEX_PT_toon_render"
    bl_parent_id = "APEX_PT_toon"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return bpy.data.collections.get('Apex ToonShader') is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        scene = context.scene

        column = layout.column(align=True)
        column.label(text="Optional")
        column.prop(scene.render, "film_transparent", text="Transparent BG")
        column.prop(scene.view_settings, "view_transform", text="Color")
        column.prop(scene.view_settings, "look")

        column = layout.column(align=True)
        column.label(text="Required by the shader")
        column.prop(scene.render, "engine")
        shading = getattr(context.space_data, "shading", None)
        if shading is not None:
            column.prop(shading, "use_scene_lights")
            column.prop(shading, "use_scene_world")
        for name, label in (("taa_samples", "Samples"),
                            ("use_bloom", "Bloom"),
                            ("use_gtao", "Ambient Occlusion"),
                            ("use_shadow_high_bitdepth", "High Bitdepth")):
            if hasattr(scene.eevee, name):
                column.prop(scene.eevee, name, text=label)


class APEX_PT_environment(ApexPanel, bpy.types.Panel):
    """Shader groups, world and HDRI"""

    bl_label = "Shaders & Environment"
    bl_idname = "APEX_PT_environment"
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        prefs = context.scene.my_prefs
        extended = assets_installed()

        column = layout.column(align=True)
        column.prop(prefs, 'cust_enum_shader', text="Shader")
        row = column.row()
        row.use_property_split = False
        row.operator("object.button_shaders", text="Add Selected Shader",
                     icon='NODE_MATERIAL')

        layout.separator()

        column = layout.column(align=True)
        if extended:
            column.prop(prefs, 'cust_enum_hdri', text="Environment")
            row = column.row(align=True)
            row.use_property_split = False
            row.operator("object.button_hdrifull",
                         text="Set as Sky").hdri = "background"
            row.operator("object.button_hdrifull",
                         text="Set as HDRI").hdri = "hdri"
        else:
            column.prop(prefs, 'cust_enum_hdri_noast', text="HDRI")
            row = column.row()
            row.use_property_split = False
            row.operator("object.button_hdrifull",
                         text="Set as HDRI").hdri = "hdri_noast"

        world = context.scene.world
        background = world_background_inputs(world)
        if background:
            layout.separator()
            column = layout.column(align=True)
            column.label(text="Current World")
            strength, rotation = background
            column.prop(strength, "default_value", text="Brightness")
            if rotation is not None:
                column.prop(rotation, "default_value", text="Rotation")


class APEX_PT_rigging(ApexPanel, bpy.types.Panel):
    """Bone display and IK helpers"""

    bl_label = "Rigging & Animation"
    bl_idname = "APEX_PT_rigging"
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        armature = selected_armature(context)
        column = layout.column(align=True)
        if armature is None:
            column.label(text="Select an armature", icon='INFO')
        else:
            column.prop(armature, 'show_in_front', text="Bones In Front")
            column.prop(armature.data, 'show_names', text="Bone Names")

        column = layout.column()
        column.use_property_split = False
        column.enabled = armature is not None
        column.operator("object.button_ikbone", text="Add IK Bones",
                        icon='CON_KINEMATIC')


class APEX_PT_effects(ApexPanel, bpy.types.Panel):
    """Shadow squad, legend effects and scene helpers"""

    bl_label = "Effects"
    bl_idname = "APEX_PT_effects"
    bl_order = 5
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        pass


class APEX_PT_shadow(ApexPanel, bpy.types.Panel):
    """Turn a legend into a Shadow Squad shadow"""

    bl_label = "Auto Shadow"
    bl_idname = "APEX_PT_shadow"
    bl_parent_id = "APEX_PT_effects"

    def draw(self, context):
        layout = self.layout

        column = layout.column()
        column.scale_y = 1.2
        column.operator("object.button_shadow", text="Shadow Selected Meshes",
                        icon='GHOST_ENABLED').shadow = "Shadow"

        layout.separator()
        column = layout.column()
        column.operator('object.button_shadow',
                        text="Add & Parent Shadow Eyes",
                        icon='HIDE_OFF').shadow = "Eyes_parent"
        layout.label(text="Select the armature only", icon='INFO')


######### Apex effects Tab ###########
class APEX_PT_apex_effects(ApexPanel, bpy.types.Panel):
    """Legend and weapon effects from the Apex Toolbox assets"""

    bl_label = "Apex Effects"
    bl_idname = "APEX_PT_apex_effects"
    bl_parent_id = "APEX_PT_effects"
    bl_options = {"DEFAULT_CLOSED"}
    

    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        prefs = scene.my_prefs
        
        
        asset_folder_set = bpy.path.abspath(addon_asset_folder())
        assets_set = 1 if assets_installed() else 0
        
                        
        ######### Wraith #########
        row = layout.row()
        icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_wraith else 'RIGHTARROW'
        row.prop(context.scene, 'subpanel_effects_wraith', icon=icon, icon_only=True)
        row.label(text='Wraith')
        # some data on the subpanel
        if context.scene.subpanel_effects_wraith:
            box = layout.box()
            
            # Wraith subpanel 1
            box.operator("object.wr_button_portal", text = "Spawn Portal")
            
            try:
                obj = bpy.data.objects['wraith_portal']
            except:
                pass
            else:
                obj = 'wraith_portal'
                portal_0 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[0]
                portal_1 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[1]
                portal_2 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[2]
                portal_3 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[3]
                portal_4 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[4]
                portal_5 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[5]
                portal_6 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[6]
                portal_7 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[7]
                portal_8 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[8]
                portal_9 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[9]
                portal_10 = bpy.data.objects[obj].active_material.node_tree.nodes['Wraith Portal'].inputs[10]
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Center Transparency:')
                split.prop(portal_0, "default_value", text = "")
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Outer Ring-1:')
                split.prop(portal_1, "default_value", text = "")
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Brightness:')
                split.prop(portal_2, "default_value", text = "")
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Outer Ring-2:')
                split.prop(portal_3, "default_value", text = "")
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Brightness:')
                split.prop(portal_4, "default_value", text = "")  
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Outer Ring-3:')
                split.prop(portal_5, "default_value", text = "")
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Brightness:')
                split.prop(portal_6, "default_value", text = "")  
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Inner Ring-1:')
                split.prop(portal_7, "default_value", text = "")
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Brightness:')
                split.prop(portal_8, "default_value", text = "")  
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Inner Ring-2:')
                split.prop(portal_9, "default_value", text = "")
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Brightness:')
                split.prop(portal_10, "default_value", text = "")                                                                                

            """
            # Wraith subpanel 2
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_wraith_prop1 else 'RIGHTARROW'
            box.prop(context.scene, 'subpanel_effects_wraith_prop1', icon=icon, icon_only=False, text='Wraith with properties')
            # some data on the subpanel
            if context.scene.subpanel_effects_wraith_prop1:
                split = box.split(factor = 0.08)
                col = split.column(align = True)
                col.label(text='1.')
                split.operator("object.wr_button_portal", text = "Spawn Portal") 
            """           

        ######### Gibraltar #########
        row = layout.row()
        icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_gibby else 'RIGHTARROW'
        row.prop(context.scene, 'subpanel_effects_gibby', icon=icon, icon_only=True)
        row.label(text='Gibraltar')
        # some data on the subpanel
        if context.scene.subpanel_effects_gibby:
            box = layout.box()
            
            # Gibraltar subpanel 1
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_gibby_prop1 else 'RIGHTARROW'
            box.prop(context.scene, 'subpanel_effects_gibby_prop1', icon=icon, icon_only=False, text='Dome Shield                          ')
            # some data on the subpanel
            if context.scene.subpanel_effects_gibby_prop1:
                split = box.split(factor = 0.08)
                col = split.column(align = True)
                col.label(text='')
                split.operator('object.gb_button_items', text = "Friendly").gibby = "Gibby bubble friendly"
                split.operator('object.gb_button_items', text = "Enemy").gibby = "Gibby bubble enemy"
                
                

        ######### Mirage #########
        row = layout.row()
        icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_mirage else 'RIGHTARROW'
        row.prop(context.scene, 'subpanel_effects_mirage', icon=icon, icon_only=True)
        row.label(text='Mirage')
        # some data on the subpanel
        if context.scene.subpanel_effects_mirage:
            box = layout.box()
            
            # Mirage subpanel 1
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_mirage_prop1 else 'RIGHTARROW'
            box.prop(context.scene, 'subpanel_effects_mirage_prop1', icon=icon, icon_only=False, text='Decoy                                    ')
            # some data on the subpanel
            if context.scene.subpanel_effects_mirage_prop1:
                split = box.split(factor = 0.08)
                col = split.column(align = True)
                col.label(text='')
                split.operator('object.mr_button_decoy', text = "Add Effect").mr_decoy = "Decoy"
                split.operator('object.mr_button_decoy', text = "Parent it").mr_decoy = "Decoy_parent" 
                box.label(text='*Sel Legend before add Effect')
                box.label(text='*Sel Model Bones before Parenting')
                
            
            """
            # Mirage subpanel 2
            box.operator("object.wr_button_portal", text = "Spawn Portal")
            """     


        ######### Valkyrie #########
        row = layout.row()
        icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_valkyrie else 'RIGHTARROW'
        row.prop(context.scene, 'subpanel_effects_valkyrie', icon=icon, icon_only=True)
        row.label(text='Valkyrie')
        # some data on the subpanel
        if context.scene.subpanel_effects_valkyrie:
            box = layout.box()
            
            # Mirage subpanel 1
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_valkyrie_prop1 else 'RIGHTARROW'
            box.prop(context.scene, 'subpanel_effects_valkyrie_prop1', icon=icon, icon_only=False, text='Flames                                    ')
            # some data on the subpanel
            if context.scene.subpanel_effects_valkyrie_prop1:
                split = box.split(factor = 0.08)
                col = split.column(align = True)
                col.label(text='')
                split.operator('object.vk_button_items', text = "Add Flames").valk = "Flames"
                split.operator('object.vk_button_items', text = "Parent them").valk = "Flames_parent" 
                box.label(text='*Sel Model Bones before Parenting')
                
            
            """
            # Mirage subpanel 2
            box.operator("object.wr_button_portal", text = "Spawn Portal")
            """    
            

        ######### Seer #########
        row = layout.row()
        icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_seer else 'RIGHTARROW'
        row.prop(context.scene, 'subpanel_effects_seer', icon=icon, icon_only=True)
        row.label(text='Seer')
        # some data on the subpanel
        if context.scene.subpanel_effects_seer:
            box = layout.box()
            
            # Seer subpanel 1
            for n in range(len(all_seer_items)):
                if n == 0:
                    box.operator('object.seer_button_spawn', text = all_seer_items.get(str(n))).lgnd_effect = all_seer_items.get(str(n)) 
            
            try:
                obj = bpy.data.objects['Seer Ultimate']
                obj2 = bpy.data.objects['Seer ult circle']
            except:
                pass
            else:
                obj = 'Seer Ultimate'
                obj2 = 'Seer ult circle'
                seer_ult_0 = bpy.data.objects[obj].material_slots[0].material.node_tree.nodes['Mix.001'].inputs['Color1'] 
                seer_ult_1 = bpy.data.objects[obj].material_slots[0].material.node_tree.nodes['Emission'].inputs['Strength'] 
                seer_ult_2 = bpy.data.objects[obj2].active_material.node_tree.nodes['Mix.001'].inputs['Color1'] 
                seer_ult_3 = bpy.data.objects[obj2].active_material.node_tree.nodes['Emission'].inputs['Strength']
                seer_ult_4 = bpy.data.objects[obj].material_slots[1].material.node_tree.nodes['Mix.001'].inputs['Color1']
                seer_ult_5 = bpy.data.objects[obj].material_slots[1].material.node_tree.nodes['Emission'].inputs['Strength']

                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Cage Color:')
                split.prop(seer_ult_0, "default_value", text = "")
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Brightness:')
                split.prop(seer_ult_1, "default_value", text = "")
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Cage Bottom Color:')
                split.prop(seer_ult_4, "default_value", text = "")
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Brightness:')
                split.prop(seer_ult_5, "default_value", text = "")                  
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Node Color:')
                split.prop(seer_ult_2, "default_value", text = "") 
                split = box.split(factor = 0.6)
                col = split.column(align = True)
                col.label(text='Brightness:')
                split.prop(seer_ult_3, "default_value", text = "")                                                                                         


            """
            # Wraith subpanel 2
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_wraith_prop1 else 'RIGHTARROW'
            box.prop(context.scene, 'subpanel_effects_wraith_prop1', icon=icon, icon_only=False, text='Wraith with properties')
            # some data on the subpanel
            if context.scene.subpanel_effects_wraith_prop1:
                split = box.split(factor = 0.08)
                col = split.column(align = True)
                col.label(text='1.')
                split.operator("object.wr_button_portal", text = "Spawn Portal") 
            """     
            
            
        ######### Weapons #########
        row = layout.row()
        icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_weapons else 'RIGHTARROW'
        row.prop(context.scene, 'subpanel_effects_weapons', icon=icon, icon_only=True)
        row.label(text='Weapons')
        # some data on the subpanel
        if context.scene.subpanel_effects_weapons:
            box = layout.box()
            
            
            # Laser subpanel
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_weapons_laser else 'RIGHTARROW'
            box.prop(context.scene, 'subpanel_effects_weapons_laser', icon=icon, icon_only=False, text='Weapon Laser                        ')
            # some data on the subpanel
            if context.scene.subpanel_effects_weapons_laser:
                box.operator('object.wpn_button_spawn', text = "Add Laser").weapon = "Laser"
                try:
                    obj = bpy.data.objects['Laser_pt1']
                except:
                    pass
                else:
                    laser_color = bpy.data.objects['Laser_pt1'].active_material.node_tree.nodes['Mix'].inputs['Color1']
                    laser_emis = bpy.data.objects['Laser_pt1'].active_material.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Set Color:')
                    split.prop(laser_color, "default_value", text = "")
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Emissive:')
                    split.prop(laser_emis, "default_value", text = "")                                     
                split = box.split(factor = 0.3)
                col = split.column(align = True)
                col.label(text='')
                split.operator('object.wpn_button_spawn', text = "1. Parent Laser").weapon = "Laser_parent"
                split = box.split(factor = 0.3)
                col = split.column(align = True)
                col.label(text='')
                split.operator('object.wpn_button_spawn', text = "2. Adjust Laser").weapon = "Laser_move" 
                box.label(text='*Select weapon bones for 1 & 2') 
                
          
    
               

            # Flatline subpanel 1
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_weapons_prop1 else 'RIGHTARROW'
            box.prop(context.scene, 'subpanel_effects_weapons_prop1', icon=icon, icon_only=False, text='Flatline Flames (v20_assim)')
            # some data on the subpanel
            if context.scene.subpanel_effects_weapons_prop1:
                box.operator('object.wpn_button_spawn', text = "Add Normal gun Effect (w)").weapon = "flatline_s4_glow_hex_LOD0_SEModelMesh.125"
                try:
                    obj = bpy.data.objects['flatline_s4_glow_hex_LOD0_SEModelMesh.125']
                except:
                    pass
                else:
                    obj = 'flatline_s4_glow_hex_LOD0_SEModelMesh.125'
                    w_flames_color = bpy.data.objects[obj].active_material.node_tree.nodes['Group'].inputs['Color']
                    w_flames_emis = bpy.data.objects[obj].active_material.node_tree.nodes['Group'].inputs['Flames Emission']
                    w_bloom_emis = bpy.data.objects[obj].active_material.node_tree.nodes['Group'].inputs['Bloom Emission']
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Color:')
                    split.prop(w_flames_color, "default_value", text = "")
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Flames Emission:')
                    split.prop(w_flames_emis, "default_value", text = "")
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Bloom Emission:')
                    split.prop(w_bloom_emis, "default_value", text = "")                 
                split = box.split(factor = 0.5)
                col = split.column(align = True)
                col.label(text='')
                split.operator('object.wpn_button_spawn', text = "Parent Flames").weapon = "flatline_parent_flame"
                
                #box.label(text='    ')
                box.operator('object.wpn_button_spawn', text = "Add POV gun Effect (v)").weapon = "flatline_s4_glow_hex_LOD0_SEModelMesh.001" 
                try:
                    obj = bpy.data.objects['flatline_s4_glow_hex_LOD0_SEModelMesh.001']
                except:
                    pass
                else:
                    obj = 'flatline_s4_glow_hex_LOD0_SEModelMesh.001'
                    v_flames_color = bpy.data.objects[obj].active_material.node_tree.nodes['Group'].inputs['Color']
                    v_flames_emis = bpy.data.objects[obj].active_material.node_tree.nodes['Group'].inputs['Flames Emission']
                    v_bloom_emis = bpy.data.objects[obj].active_material.node_tree.nodes['Group'].inputs['Bloom Emission']
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Color:')
                    split.prop(v_flames_color, "default_value", text = "")
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Flames Emission:')
                    split.prop(v_flames_emis, "default_value", text = "")
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Bloom Emission:')
                    split.prop(v_bloom_emis, "default_value", text = "")  
                                    
                split = box.split(factor = 0.5)
                col = split.column(align = True)
                col.operator('object.wpn_button_spawn', text = "Add POV Anim").weapon = "idle_reactive_layer_3_Fixed"
                split.operator('object.wpn_button_spawn', text = "Parent Flames").weapon = "flatline_pov_parent_flame"                                                                 
                            
            
        if assets_set == 1:
            row = layout.row()
            row.label(text='*** Spawn Items ***')


            ######### Heirloom Items #########         
            row = layout.row()
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_heirloom else 'RIGHTARROW'
            row.prop(context.scene, 'subpanel_effects_heirloom', icon=icon, icon_only=True)
            row.label(text='Heirloom Items')
            # some data on the subpanel
            if context.scene.subpanel_effects_heirloom:
                row = layout.row()
                row.label(text='Animation is just to open heirloom')
                box = layout.box()
                for n in range(len(all_heirloom_items)):
                    box.operator('object.hl_button_spawn', text = all_heirloom_items.get(str(n))).heirloom = all_heirloom_items.get(str(n))
                            
                                        
            ######### Badges #########
            row = layout.row()
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_badges else 'RIGHTARROW'
            row.prop(context.scene, 'subpanel_effects_badges', icon=icon, icon_only=True)
            row.label(text='Badges (3D)')
            # some data on the subpanel
            if context.scene.subpanel_effects_badges:
                box = layout.box()
                # Badges
                box.operator('object.bdg_button_spawn', text = "4K Badge").badge = "Badge - 4k Damage"
                box.operator('object.bdg_button_spawn', text = "20 Bomb Badge").badge = "Badge - 20 Bombs"
                box.operator('object.bdg_button_spawn', text = "20 Bomb Badge (v2)").badge = "Badge - 20 Bombs (v2)"
                box.operator('object.bdg_button_spawn', text = "Predator S3 Badge").badge = "Badge - Predator S3"
                
                
            ######### Loot Items #########
            row = layout.row()
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_loot else 'RIGHTARROW'
            row.prop(context.scene, 'subpanel_effects_loot', icon=icon, icon_only=True)
            row.label(text='Loot Items')
            # some data on the subpanel
            if context.scene.subpanel_effects_loot:
                box = layout.box()
                
                # Body Armor subpanel 1
                icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_loot_prop1 else 'RIGHTARROW'
                box.prop(context.scene, 'subpanel_effects_loot_prop1', icon=icon, icon_only=False, text='Body Armor                          ')
                # some data on the subpanel
                if context.scene.subpanel_effects_loot_prop1:
                    for n in range(len(all_loot_items)):
                        if n in range(*armor_range):
                            box.operator('object.lt_button_spawn', text = all_loot_items.get(str(n))).loot = all_loot_items.get(str(n))
                    
                # Helmet subpanel 2
                icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_loot_prop2 else 'RIGHTARROW'
                box.prop(context.scene, 'subpanel_effects_loot_prop2', icon=icon, icon_only=False, text='Helmet                                 ')
                # some data on the subpanel
                if context.scene.subpanel_effects_loot_prop2:
                     for n in range(len(all_loot_items)):
                        if n in range(*helmet_range):
                            box.operator('object.lt_button_spawn', text = all_loot_items.get(str(n))).loot = all_loot_items.get(str(n)) 
                    
                # Heals subpanel 3
                icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_loot_prop3 else 'RIGHTARROW'
                box.prop(context.scene, 'subpanel_effects_loot_prop3', icon=icon, icon_only=False, text='Heals                                    ')
                # some data on the subpanel
                if context.scene.subpanel_effects_loot_prop3:
                    for n in range(len(all_loot_items)):
                        if n in range(*meds_range):
                            box.operator('object.lt_button_spawn', text = all_loot_items.get(str(n))).loot = all_loot_items.get(str(n))
                            
                # Nades subpanel 4
                icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_loot_prop4 else 'RIGHTARROW'
                box.prop(context.scene, 'subpanel_effects_loot_prop4', icon=icon, icon_only=False, text='Nades                                    ')
                # some data on the subpanel
                if context.scene.subpanel_effects_loot_prop4:
                    for n in range(len(all_loot_items)):
                        if n in range(*nades_range):
                            box.operator('object.lt_button_spawn', text = all_loot_items.get(str(n))).loot = all_loot_items.get(str(n)) 
                            
                # Ammo subpanel 5
                icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_loot_prop5 else 'RIGHTARROW'
                box.prop(context.scene, 'subpanel_effects_loot_prop5', icon=icon, icon_only=False, text='Ammo                                    ')
                # some data on the subpanel
                if context.scene.subpanel_effects_loot_prop5:
                    for n in range(len(all_loot_items)):
                        if n in range(*ammo_range):
                            box.operator('object.lt_button_spawn', text = all_loot_items.get(str(n))).loot = all_loot_items.get(str(n))                               
                            
                # Backpacks subpanel 6
                icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_loot_prop6 else 'RIGHTARROW'
                box.prop(context.scene, 'subpanel_effects_loot_prop6', icon=icon, icon_only=False, text='Backpacks                              ')
                # some data on the subpanel
                if context.scene.subpanel_effects_loot_prop6:
                    for n in range(len(all_loot_items)):
                        if n in range(*bag_range):
                            box.operator('object.lt_button_spawn', text = all_loot_items.get(str(n))).loot = all_loot_items.get(str(n))  
                            
                # Others subpanel 7
                icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_loot_prop7 else 'RIGHTARROW'
                box.prop(context.scene, 'subpanel_effects_loot_prop7', icon=icon, icon_only=False, text='Other                                       ')
                # some data on the subpanel
                if context.scene.subpanel_effects_loot_prop7:
                    for n in range(len(all_loot_items)):
                        if n in range(*other_range):
                            box.operator('object.lt_button_spawn', text = all_loot_items.get(str(n))).loot = all_loot_items.get(str(n))    
              
                            
                            
            ######### Lobby Items #########
            row = layout.row()
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_lobby else 'RIGHTARROW'
            row.prop(context.scene, 'subpanel_effects_lobby', icon=icon, icon_only=True)
            row.label(text='Lobby Items')
            # some data on the subpanel
            if context.scene.subpanel_effects_lobby:
                box = layout.box()
                for n in range(len(all_lobby_other_items)):
                    if n in range(*lobby_lobby_range):
                        box.operator('object.lb_button_spawn', text = all_lobby_other_items.get(str(n))).lobby_other = all_lobby_other_items.get(str(n))

            
            ######### Other Items #########
            def holo():
                try:
                    obj = bpy.data.objects['goblin_dropship_holo_LOD0_skel']
                except:
                    pass
                else:
                    obj = 'goblin_dropship_holo_LOD0_SEModelMesh.002'
                    obj1 = 'goblin_dropship_holo_LOD0_SEModelMesh.001'
                    obj2 = 'Respawn Hologram'
                    holo_0 = bpy.data.objects[obj].active_material.node_tree.nodes['Mix.001'].inputs['Color2'] 
                    holo_1 = bpy.data.objects[obj].active_material.node_tree.nodes['Emission'].inputs['Strength']                     
                    holo_2 = bpy.data.objects[obj1].active_material.node_tree.nodes['Mix'].inputs['Color2'] 
                    holo_3 = bpy.data.objects[obj1].active_material.node_tree.nodes['Emission'].inputs['Strength']               
                    holo_4 = bpy.data.objects[obj2].active_material.node_tree.nodes['Respawn Hologram'].inputs[0]
                    holo_5 = bpy.data.objects[obj2].active_material.node_tree.nodes['Respawn Hologram'].inputs[1] 
                    holo_6 = bpy.data.objects[obj2].active_material.node_tree.nodes['Respawn Hologram'].inputs[2] 
                    holo_7 = bpy.data.objects[obj2].active_material.node_tree.nodes['Respawn Hologram'].inputs[3] 
                    holo_8 = bpy.data.objects[obj2].active_material.node_tree.nodes['Respawn Hologram'].inputs[4]  
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Ship Top Color:')
                    split.prop(holo_0, "default_value", text = "")
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Emissive:')
                    split.prop(holo_1, "default_value", text = "") 
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Ship Bottom Color:')
                    split.prop(holo_2, "default_value", text = "") 
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Emissive:')
                    split.prop(holo_3, "default_value", text = "") 
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Strips Color:')
                    split.prop(holo_4, "default_value", text = "") 
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Strips Height:')
                    split.prop(holo_5, "default_value", text = "") 
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Strips Brightness:')
                    split.prop(holo_6, "default_value", text = "") 
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Cone Color:')
                    split.prop(holo_7, "default_value", text = "") 
                    split = box.split(factor = 0.6)
                    col = split.column(align = True)
                    col.label(text='Cone Brightness:')
                    split.prop(holo_8, "default_value", text = "")  
                                   
            
            row = layout.row()
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_other else 'RIGHTARROW'
            row.prop(context.scene, 'subpanel_effects_other', icon=icon, icon_only=True)
            row.label(text='Other Items')
            # some data on the subpanel
            if context.scene.subpanel_effects_other:
                box = layout.box()
                for n in range(len(all_lobby_other_items)):
                    if n in range(*lobby_other_range):
                        box.operator('object.lb_button_spawn', text = all_lobby_other_items.get(str(n))).lobby_other = all_lobby_other_items.get(str(n))                
                        if all_lobby_other_items.get(str(n)) == 'Respawn Beacon Hologram': 
                            holo()
                                                                                                                                  
                        


        ######### Skydive #########
        row = layout.row()
        icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_sky else 'RIGHTARROW'
        row.prop(context.scene, 'subpanel_effects_sky', icon=icon, icon_only=True)
        row.label(text='Skydive (Experimental)')
        # some data on the subpanel
        if context.scene.subpanel_effects_sky:
            box = layout.box()

            for n in range(len(all_skydive_items)):
                split = box.split(factor = 0.08)
                col = split.column(align = True)
                col.label(text='')
                split.operator('object.sky_button_spawn', text = all_skydive_items.get(str(n))).sky_effect = all_skydive_items.get(str(n))
            split = box.split(factor = 0.6)
            col = split.column(align = True)
            col.label(text='')         
            split.operator('object.sky_button_spawn', text = "Parent it").sky_effect = "Skydive_parent" 
            box.label(text='*Sel Model Bones before Parenting') 
            box.label(text='*Parent before import animation')           


            """
            # Wraith subpanel 2
            icon = 'DOWNARROW_HLT' if context.scene.subpanel_effects_wraith_prop1 else 'RIGHTARROW'
            box.prop(context.scene, 'subpanel_effects_wraith_prop1', icon=icon, icon_only=False, text='Wraith with properties')
            # some data on the subpanel
            if context.scene.subpanel_effects_wraith_prop1:
                split = box.split(factor = 0.08)
                col = split.column(align = True)
                col.label(text='1.')
                split.operator("object.wr_button_portal", text = "Spawn Portal") 
            """ 
             

######### Scene helpers ###########
class APEX_PT_scene_utils(ApexPanel, bpy.types.Panel):
    """Staging, lighting and the wireframe look"""

    bl_label = "Scene Utilities"
    bl_idname = "APEX_PT_scene_utils"
    bl_parent_id = "APEX_PT_effects"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        column = layout.column(align=True)
        column.operator('object.lb_button_spawn',
                        text="Animated Staging + Camera",
                        icon='CAMERA_DATA').lobby_other = 'Animated Staging'
        if bpy.data.objects.get('Staging Camera') is not None:
            column.operator('object.ef_button_spawn',
                            text="Make Staging Camera Active",
                            icon='OUTLINER_OB_CAMERA').cool_effect = 'Staging Camera'

        layout.separator()
        layout.operator('object.ef_button_spawn', text="Basic Lights Setup",
                        icon='LIGHT_AREA').cool_effect = 'basic lights'

        layout.separator()
        column = layout.column(align=True)
        column.operator('object.ef_button_spawn', text="Add Wireframe Effect",
                        icon='MOD_WIREFRAME').cool_effect = 'wireframe'
        column.operator('object.ef_button_spawn', text="Remove Wireframe Effect",
                        icon='X').cool_effect = 'wireframe_clear'


class APEX_PT_health(ApexPanel, bpy.types.Panel):
    """Find problems before texturing or rendering"""
    bl_label = 'Scene Health'
    bl_idname = 'APEX_PT_health'
    bl_order = 6

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        prefs = context.scene.my_prefs
        layout.prop(prefs, 'health_scope', text='Scope')
        layout.operator('object.apex_check_scene', text='Check Scene Health', icon='VIEWZOOM')
        if prefs.health_report:
            draw_wrapped(layout, prefs.health_summary, context)
            layout.label(text='Last check · rerun after edits', icon='INFO')
            if prefs.health_issues:
                layout.template_list('APEX_UL_health_issues', '', prefs, 'health_issues',
                                     prefs, 'health_index', rows=4)
                index = min(prefs.health_index, len(prefs.health_issues) - 1)
                issue = prefs.health_issues[index]
                box = layout.box()
                draw_wrapped(box, issue.detail, context)
                if issue.object:
                    box.operator('object.apex_select_issues', text='Select This Issue Type',
                                 icon='RESTRICT_SELECT_OFF').code = issue.code
                layout.operator('object.apex_select_issues', text='Select All Affected Meshes',
                                icon='RESTRICT_SELECT_OFF').code = ''
            draw_report_actions(layout, 'health')
        else:
            draw_wrapped(layout, 'Check missing textures, materials, UV maps and rig targets.', context)


class APEX_PT_repair(ApexPanel, bpy.types.Panel):
    """Reconnect moved textures without replacing your shaders"""
    bl_label = 'Repair Missing Textures'
    bl_idname = 'APEX_PT_repair'
    bl_parent_id = 'APEX_PT_health'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        prefs = context.scene.my_prefs
        layout.prop(prefs, 'repair_folder', text='Texture Folder')
        layout.prop(prefs, 'repair_subfolders', text='Subfolders')
        row = layout.row()
        row.enabled = bool(prefs.repair_folder)
        row.operator('object.apex_repair_textures', text='Repair Missing Textures', icon='FILE_REFRESH')
        draw_wrapped(layout, 'Uses the scope above. Unique filenames only; shader links stay intact.', context)
        if prefs.repair_report:
            draw_wrapped(layout, prefs.repair_summary, context)
            draw_report_actions(layout, 'repair')


######### About / Help ###########
class APEX_PT_about(ApexPanel, bpy.types.Panel):
    """Documentation, links and the asset pack"""

    bl_label = "About & Help"
    bl_idname = "APEX_PT_about"
    bl_order = 7
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        extended = assets_installed()

        column = layout.column(align=True)
        column.operator('object.lgndtranslate_url', text='Workflow Guide',
                        icon='HELP').link = 'workflow_guide'
        column.operator('object.lgndtranslate_url',
                        text="Instructions & Credits",
                        icon='HELP').link = "instructions"
        column.operator('object.lgndtranslate_url', text="Version Log",
                        icon='TEXT').link = "version"
        layout.label(text="Original author: Random Blender Dude")
        layout.label(text="Maintained release: ALR")

        if not extended:
            box = layout.box()
            box.label(text="Extended assets not installed", icon='INFO')
            box.label(text="Adds HDRI themes, loot, badges,")
            box.label(text="heirlooms and lobby items.")
            box.operator('object.lgndtranslate_url', text="Download Assets Pack",
                         icon='IMPORT').link = "asset_file"
            box.label(text="Then set the folder below.")
        prefs = addon_prefs()
        if prefs is not None:
            layout.prop(prefs, "asset_folder")

        layout.separator()
        column = layout.column(align=True)
        column.operator('object.lgndtranslate_url',
                        text="Original Apex Toolbox",
                        icon='URL').link = "upstream"


######### Updates Tracker ###########
class APEX_PT_updates(ApexPanel, bpy.types.Panel):
    """Versions of Legion+ and the companion import add-ons"""

    bl_label = "Updates"
    bl_idname = "APEX_PT_updates"
    bl_parent_id = "APEX_PT_about"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        prefs = addon_prefs()

        ####   Read the installed Legion+ version once   ####
        legion_folder = bpy.path.abspath(addon_legion_folder())
        global legion_cur_ver, legion_folder_exist
        if legion_folder_exist == 0 and os.path.isdir(legion_folder):
            try:
                entries = os.listdir(legion_folder)
            except OSError:
                entries = []
            for entry in entries:
                if entry.startswith("Legion+"):
                    legion_cur_ver = entry.split("+", 1)[1]
                    legion_folder_exist = 1
                    break
            else:
                legion_folder_exist = 2

        column = layout.column(align=True)
        if legion_cur_ver != '0':
            split = column.split(factor=0.6)
            split.label(text="Legion+")
            split.label(text="v." + legion_cur_ver)
            if newer_version(legion_lts_ver, legion_cur_ver):
                column.operator(
                    'object.lgndtranslate_url',
                    text="Legion+ v." + str(legion_lts_ver) + " available",
                    icon='IMPORT').link = "legion_update"

        for index, name in enumerate(addon_name):
            split = column.split(factor=0.6)
            split.label(text=name)
            split.label(text="v." + addon_ver[index])
            latest, link = _addon_update_info(name)
            if latest and newer_version(latest, addon_ver[index]):
                column.operator(
                    'object.lgndtranslate_url',
                    text=name + " v." + str(latest) + " available",
                    icon='IMPORT').link = link

        layout.separator()
        layout.operator('object.lgndtranslate_url', text="Check for Updates",
                        icon='FILE_REFRESH').link = "check_update"

        if prefs is not None:
            box = layout.box()
            box.label(text="Legion+ parent folder:")
            box.prop(prefs, "legion_folder", text="")
            if legion_folder_exist == 2:
                box.label(text="No 'Legion+<version>' folder inside",
                          icon='ERROR')


def _addon_update_info(name):
    """``(latest version, url key)`` for a tracked companion add-on."""
    return {
        'io_anim_seanim': (io_anim_lts_ver, "io_anim_seanim"),
        'io_scene_cast': (cast_lts_ver, "cast"),
        'io_model_semodel': (semodel_lts_ver, "io_model_semodel"),
        'ApexMapImporter': (mprt_lts_ver, "mprt"),
    }.get(name, ('0', "update"))


    #CLASS REGISTER 
##########################################
classes = (
        apexToolsPreferences,
        APEX_PG_health_issue,
        PROPERTIES_CUSTOM,
        LGNDTRANSLATE_URL,
        BUTTON_CUSTOM,
        APEX_OT_report,
        APEX_OT_xyz_euler,
        APEX_OT_check_scene,
        APEX_OT_select_issues,
        APEX_OT_repair_textures,
        APEX_UL_health_issues,
        APEX_OT_forget_texture_roots,
        BUTTON_TOON,
        BUTTON_SHADOW,
        BUTTON_CUSTOM2,
        BUTTON_SHADERS,
        BUTTON_HDRIFULL,
        BUTTON_IKBONE,
        WR_BUTTON_PORTAL,
        SEER_BUTTON_SPAWN,
        SKY_BUTTON_SPAWN,
        GB_BUTTON_ITEMS,
        MR_BUTTON_DECOY,
        VK_BUTTON_ITEMS,
        BDG_BUTTON_SPAWN,
        WPN_BUTTON_SPAWN,
        LT_BUTTON_SPAWN,
        LB_BUTTON_SPAWN,
        HL_BUTTON_SPAWN,
        EF_BUTTON_SPAWN,
        # Panels, in the order they appear in the sidebar.
        APEX_PT_main,
        APEX_PT_model,
        APEX_PT_materials,
        APEX_PT_autotex,
        APEX_PT_autotex_search,
        APEX_PT_recolour,
        APEX_PT_toon,
        APEX_PT_toon_settings,
        APEX_PT_toon_render,
        APEX_PT_environment,
        APEX_PT_rigging,
        APEX_PT_effects,
        APEX_PT_shadow,
        APEX_PT_apex_effects,
        APEX_PT_scene_utils,
        APEX_PT_health,
        APEX_PT_repair,
        APEX_PT_about,
        APEX_PT_updates,
        )

#: Fold-out state used inside the Apex Effects panel.  The seven booleans the
#: old hand-rolled main panel needed are gone: those sections are real Blender
#: sub-panels now and Blender stores their state itself.
_SCENE_TOGGLES = (
    "subpanel_effects_wraith", "subpanel_effects_wraith_prop1",
    "subpanel_effects_gibby", "subpanel_effects_gibby_prop1",
    "subpanel_effects_mirage", "subpanel_effects_mirage_prop1",
    "subpanel_effects_valkyrie", "subpanel_effects_valkyrie_prop1",
    "subpanel_effects_seer", "subpanel_effects_weapons",
    "subpanel_effects_weapons_laser", "subpanel_effects_weapons_prop1",
    "subpanel_effects_heirloom", "subpanel_effects_badges",
    "subpanel_effects_loot", "subpanel_effects_loot_prop1",
    "subpanel_effects_loot_prop2", "subpanel_effects_loot_prop3",
    "subpanel_effects_loot_prop4", "subpanel_effects_loot_prop5",
    "subpanel_effects_loot_prop6", "subpanel_effects_loot_prop7",
    "subpanel_effects_lobby", "subpanel_effects_other",
    "subpanel_effects_sky",
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.my_prefs = bpy.props.PointerProperty(type=PROPERTIES_CUSTOM)
    for name in _SCENE_TOGGLES:
        setattr(Scene, name, BoolProperty(default=False))


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.my_prefs
    for name in _SCENE_TOGGLES:
        if hasattr(Scene, name):
            delattr(Scene, name)


if __name__ == "__main__":
    register()
