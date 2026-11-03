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
    "version": (3, 14, 0),
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar > Apex Tools",
    "description": "Blender tools for Apex Legends models, materials, shaders and RSX/CAST workflows",
    "warning": "Animation names depend on the available RSX export data",
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
import json
from bpy_extras.io_utils import ImportHelper

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
from .apex_tex import workflows as apex_workflows
from .apex_tex import model_files as apex_model_files
from .apex_tex import animations as apex_animations
from .apex_tex import auto_rigs as apex_auto_rigs
from .apex_tex import import_plan as apex_import_plan
from .apex_tex import relink as apex_relink
from .apex_tex import animation_layers as apex_layers
from .apex_tex import attachments as apex_attachments
from .apex_tex.versions import newer_version

#: The apex_tex API revision this file is written against.  If the two ever
#: disagree at register() time, a stale module survived the reload above and
#: the add-on says so instead of failing later with a TypeError.
APEX_TEX_API_VERSION = 20


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
ver = "v" + ".".join(map(str, bl_info["version"]))
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


def draw_wrapped(layout, text, context, max_width=None):
    scale = max(1.0, getattr(context.preferences.system, 'ui_scale', 1.0))
    pixels = getattr(context.region, 'width', 300)
    if max_width is not None:
        pixels = min(pixels, max_width * scale)
    width = max(18, int((pixels - 40) / (7.5 * scale)))
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


def select_pose_bone(armature, bone_name):
    """Select a pose bone with Blender 4.2 and 5.2's respective APIs."""
    pose_bone = armature.pose.bones[bone_name]
    if hasattr(pose_bone, 'select'):
        pose_bone.select = True
    else:
        pose_bone.bone.select = True


def attachment_armature_poll(_self, obj):
    return obj.type == 'ARMATURE'


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


class APEX_PG_animation_clip(bpy.types.PropertyGroup):
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    offset: bpy.props.IntProperty(min=0)
    fps: FloatProperty(default=30)
    additive: BoolProperty()
    action: bpy.props.PointerProperty(type=bpy.types.Action)
    stamp: bpy.props.StringProperty()
    favourite: BoolProperty(default=False)
    recent_order: bpy.props.IntProperty(default=0, min=0)
    guid: bpy.props.StringProperty()
    sequence_hash: bpy.props.StringProperty()
    menu_name: bpy.props.StringProperty()
    menu_role: bpy.props.StringProperty()
    menu_source: bpy.props.StringProperty()
    external: BoolProperty(name='Imported Animation', default=False)


def animation_filter_changed(library, context):
    apex_animations.ensure_visible_selection(library)


class APEX_PG_animation_library(bpy.types.PropertyGroup):
    rig_file: bpy.props.StringProperty(name='Linked Rig', subtype='FILE_PATH',
                                      description='Linked RSX rig export; use Change Rig to choose another file')
    clips: bpy.props.CollectionProperty(type=APEX_PG_animation_clip)
    index: bpy.props.IntProperty(default=0, min=0)
    browse_mode: bpy.props.EnumProperty(name='Show', default='ALL', update=animation_filter_changed,
                                       items=[('ALL', 'All', 'Show the full linked animation library'),
                                              ('FAVOURITES', 'Favourites', 'Show clips starred for this model'),
                                              ('RECENT', 'Recent', 'Last 20 loaded clips, newest first')])
    filter_text: bpy.props.StringProperty(name='Search Animations', options={'TEXTEDIT_UPDATE'},
                                         update=animation_filter_changed)
    category: bpy.props.EnumProperty(name='Category', default='ALL', update=animation_filter_changed,
                                    description='Filter by words in the exported animation names',
                                    items=[('ALL', 'All Animations', 'Show every exported animation'),
                                           ('GLADCARD', 'Gladcard / Banner', 'Names containing gladcard, glad_card or banner'),
                                           ('EMOTE', 'Emote', 'Names containing emote'),
                                           ('LOBBY', 'Lobby', 'Names containing lobby'),
                                           ('FINISHER', 'Finishers', 'Names containing finisher, execution or execute'),
                                           ('MOVEMENT', 'Movement', 'Walk, run, sprint, jump, slide, crouch, mantle, climb or swim')])
    summary: bpy.props.StringProperty()
    show_name_options: BoolProperty(name='Options & Details', default=False,
                                   description='Playback settings, in-game names and linked export details')
    show_menu_names: BoolProperty(name='Show In-Game Names', default=True,
                                 description='Use included English names or imported names when available; search accepts both names')
    names_file: bpy.props.StringProperty(subtype='FILE_PATH')
    names_summary: bpy.props.StringProperty()
    has_rest_rotation: BoolProperty()
    rest_rotation_mode: bpy.props.StringProperty(default='XYZ')
    rest_rotation: bpy.props.FloatVectorProperty(size=4)
    fit_timeline: BoolProperty(name='Match Timeline and FPS', default=True,
                              description='Set the scene frame range and playback rate to this clip')
    allow_missing: BoolProperty(name='Allow Missing Bones', default=True,
                               description='Load matching bone tracks even when some animated bones are absent')
    show_layers: BoolProperty(name='Animation Layers', default=False)
    layer_influence: FloatProperty(name='Strength', default=1.0, min=0.0, max=1.0)
    layer_offset: bpy.props.IntProperty(name='Frame Offset', default=0)


BATCH_LAYOUT_ITEMS = [
    ('ROW', 'Row', 'Place models side by side along X'),
    ('GRID', 'Grid', 'Place models in rows without overlapping'),
    ('NONE', 'Original positions', 'Keep the positions from each export')]


def draw_import_layout(layout, settings):
    box = layout.box()
    box.label(text='Layout')
    box.prop(settings, 'placement')
    if settings.placement == 'GRID':
        box.prop(settings, 'columns')
    if settings.placement != 'NONE':
        box.prop(settings, 'gap')
    box.prop(settings, 'separate_collections')


class PROPERTIES_CUSTOM(bpy.types.PropertyGroup):
    workspace_tab: bpy.props.EnumProperty(name='Tools', default='MODEL', items=[('MODEL', 'Model', 'Import and materials', 'OUTLINER_OB_MESH', 0), ('ANIMATION', 'Animate', 'Animations and item pairing', 'ACTION', 1), ('SCENE', 'Scene', 'Lighting and effects', 'SCENE_DATA', 2), ('TOOLS', 'Tools', 'Repair and help', 'TOOL_SETTINGS', 3)])
    use_alpha: BoolProperty(name='Use Transparency', default=True, description='Connect albedo alpha and opacity maps. Disable for opaque models with unwanted cutouts')
    import_summary: bpy.props.StringProperty()
    model_parent_folder: bpy.props.StringProperty(subtype='DIR_PATH')
    animation_parent_folder: bpy.props.StringProperty(subtype='DIR_PATH')
    texture_on_import: BoolProperty(name='Texture Models', default=True)
    auto_link_rigs: BoolProperty(default=True)
    import_placement: bpy.props.EnumProperty(items=BATCH_LAYOUT_ITEMS, default='ROW')
    import_columns: bpy.props.IntProperty(default=5, min=1, max=50)
    import_gap: FloatProperty(default=0.25, min=0.0, max=100.0, subtype='DISTANCE')
    import_collections: BoolProperty(default=False)
    relink_old_root: bpy.props.StringProperty(subtype='DIR_PATH')
    relink_new_root: bpy.props.StringProperty(subtype='DIR_PATH')
    relink_summary: bpy.props.StringProperty()
    include_model_meshes: BoolProperty(
        name='Include Whole Model', default=True,
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
        description = "Shader used when recolouring a model",
        default='OP1',
        items = [('OP1', "Apex Shader", ""),
                 ('OP2', "Apex Shader+_v3.4", ""),
                 ('OP3', "S/G-Blender", "")    
                ]
        )
        
    autotex_folder: bpy.props.StringProperty(name="Textures Folder",
                                        description="Optional texture folder. Leave empty to find textures automatically beside the export or in remembered folders",
                                        default="",
                                        maxlen=1024,
                                        subtype="DIR_PATH")
                                        
    aut_subf : BoolProperty(
    name="Search Subfolders",
    description="Also search folders inside the chosen texture folder",
    default = False
    )                                                
    
    ### For Recolor ####    
    cust_enum2 : bpy.props.EnumProperty(
        name = "Shader",
        description = "Shader used when texturing a model",
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
            plug_alpha=prefs.use_alpha,
            append_node_group=append_apex_node_group,
            texture_folder=prefs.autotex_folder,
            search_subfolders=prefs.aut_subf,
            operator=self,
            remembered_roots=remembered_texture_roots(),
            remember_callback=store_texture_roots,
            objects=texture_targets(context),
            report_callback=lambda *args: capture_texture_report(context, *args),
        )


class APEX_PG_import_folder(bpy.types.PropertyGroup):
    selected: BoolProperty(name='Import', default=False)


class APEX_UL_import_folders(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'selected', text=item.name)

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        return ([self.bitflag_filter_item if apex_model_files.folder_matches(
                     item.name, data.folder_search, data.folder_category,
                     data.folder_group) else 0
                 for item in items], [])


_import_folder_group_items = {
    'LEGENDS': [('NONE', 'Choose a legend', '')],
    'WEAPONS': [('NONE', 'Choose a weapon or item', '')],
    'MISC': [('NONE', 'Choose a group', '')],
}


def import_folder_group_items(self, context):
    return _import_folder_group_items.get(self.folder_category,
                                          _import_folder_group_items['LEGENDS'])


def import_folder_category_changed(self, context):
    self.folder_group = 'NONE'
    self.folder_search = ''


def refresh_import_folders(self, context):
    previous = {item.name: item.selected for item in self.folder_items}
    self.folder_items.clear()
    folder = bpy.path.abspath(self.parent_folder)
    root = str(apex_model_files.model_root(folder))
    if os.path.normcase(os.path.normpath(root)) != os.path.normcase(os.path.normpath(folder)):
        self.parent_folder = root
        return
    if not os.path.isdir(folder):
        return
    try:
        with os.scandir(folder) as entries:
            names = sorted((entry.name for entry in entries
                            if entry.is_dir(follow_symlinks=False)
                            and not entry.name.lower().startswith('anims_')),
                           key=str.casefold)
    except OSError:
        return
    for name in names:
        item = self.folder_items.add()
        item.name = name
        item.selected = previous.get(name, False)
    for category, prompt in (('LEGENDS', 'Choose a legend'),
                             ('WEAPONS', 'Choose a weapon or item'),
                             ('MISC', 'Choose a group')):
        options = apex_model_files.model_group_options(names, category)
        _import_folder_group_items[category] = [('NONE', prompt, '')] + [
            (group, '%s (%d)' % (label, count), '')
            for group, label, count in options]
    self.folder_group = 'NONE'
    if context and context.scene:
        context.scene.my_prefs.model_parent_folder = folder


class APEX_OT_import_texture(bpy.types.Operator, ImportHelper):
    """Import CAST files or model folders, prepare models and connect textures"""
    bl_idname = 'object.apex_import_texture'
    bl_label = 'Import & Texture'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ''
    filter_glob: bpy.props.StringProperty(default='*.cast', options={'HIDDEN'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement,
                                        options={'HIDDEN', 'SKIP_SAVE'})
    directory: bpy.props.StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    source_mode: bpy.props.EnumProperty(name='Import', items=[
        ('FOLDERS', 'Model folders', 'Choose models from separate RSX folders'),
        ('FILES', 'CAST files', 'Choose one or more CAST files from one folder')],
        default='FOLDERS')
    parent_folder: bpy.props.StringProperty(name='Parent folder', subtype='DIR_PATH',
                                            update=refresh_import_folders)
    folder_items: bpy.props.CollectionProperty(type=APEX_PG_import_folder,
                                               options={'HIDDEN', 'SKIP_SAVE'})
    folder_index: bpy.props.IntProperty(options={'HIDDEN', 'SKIP_SAVE'})
    folder_search: bpy.props.StringProperty(name='Search',
                                           description='Match any words in the folder name, in any order')
    folder_category: bpy.props.EnumProperty(name='Models', items=[
        ('LEGENDS', 'Legends', 'Legend skins and pilot models'),
        ('WEAPONS', 'Weapons', 'Weapons, heirlooms and held items'),
        ('MISC', 'Misc', 'Props, environment models and other exports')],
        default='LEGENDS', update=import_folder_category_changed)
    folder_group: bpy.props.EnumProperty(name='Show', items=import_folder_group_items)
    change_parent: BoolProperty(name='Change folder', default=False)
    ui_stage: bpy.props.EnumProperty(items=[('DIRECT', 'Direct', ''),
                                            ('CHOOSE', 'Choose', ''),
                                            ('FILES', 'Files', '')],
                                     default='DIRECT', options={'HIDDEN', 'SKIP_SAVE'})
    texture: BoolProperty(name='Texture Models', default=True, description='Apply Apex shaders and find textures during import. Turn off for a faster model-only import')
    prepare: BoolProperty(name='Prepare Model', default=True,
                          description='Apply Apex model size/orientation and XYZ Euler to unanimated transforms')
    auto_link: BoolProperty(name='Auto-Link Animation Rig', default=True,
                            description='Find this legend\'s exported animation rig beside the models or in your last animation folder')
    placement: bpy.props.EnumProperty(name='Placement', items=BATCH_LAYOUT_ITEMS, default='ROW')
    columns: bpy.props.IntProperty(name='Columns', default=5, min=1, max=50)
    gap: FloatProperty(name='Minimum Gap', default=0.25, min=0.0, max=100.0, subtype='DISTANCE')
    separate_collections: BoolProperty(name='One Collection per Model', default=False)
    review_before_import: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    shader: bpy.props.EnumProperty(name='Shader', default='OP1', items=[
        ('OP1', 'Apex Shader', ''), ('OP2', 'Apex Shader+_v3.4', ''), ('OP3', 'S/G-Blender', '')])
    texture_folder: bpy.props.StringProperty(name='Texture Folder', subtype='DIR_PATH',
                                             description='Optional override; otherwise search beside the CAST export')

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT' and _active_animation_scan is None)

    def invoke(self, context, event):
        self.texture = context.scene.my_prefs.texture_on_import
        self.shader = context.scene.my_prefs.cust_enum2
        self.auto_link = context.scene.my_prefs.auto_link_rigs
        prefs = context.scene.my_prefs
        self.placement, self.columns = prefs.import_placement, prefs.import_columns
        self.gap, self.separate_collections = prefs.import_gap, prefs.import_collections
        self.review_before_import = False
        self.ui_stage = 'CHOOSE'
        folder = context.scene.my_prefs.model_parent_folder
        if not folder or not os.path.isdir(bpy.path.abspath(folder)):
            bookmarks = bpy.utils.user_resource('CONFIG', path='bookmarks.txt')
            folder = apex_model_files.bookmarked_mdl(bookmarks)
        if folder:
            self.parent_folder = folder
        self.folder_group = 'NONE'
        return context.window_manager.invoke_props_dialog(
            self, width=540, confirm_text='Import Models')

    def draw(self, context):
        if self.ui_stage == 'CHOOSE':
            self.layout.prop(self, 'source_mode', expand=True)
            if self.source_mode == 'FOLDERS':
                if self.folder_items and not self.change_parent:
                    self.layout.label(text='Model folders in ' + os.path.basename(
                        os.path.normpath(self.parent_folder)), icon='FILE_FOLDER')
                    self.layout.prop(self, 'change_parent', text='Change folder')
                else:
                    self.layout.prop(self, 'parent_folder')
                if self.folder_items:
                    self.layout.label(text='Select the models to import.', icon='INFO')
                    self.layout.prop(self, 'folder_category', expand=True)
                    self.layout.prop(self, 'folder_group', text='Show')
                    if self.folder_group != 'NONE':
                        self.layout.prop(self, 'folder_search', text='Search', icon='VIEWZOOM')
                        self.layout.template_list('APEX_UL_import_folders', '', self,
                                                  'folder_items', self, 'folder_index', rows=10)
                    count = sum(item.selected for item in self.folder_items)
                    visible = sum(apex_model_files.folder_matches(
                        item.name, self.folder_search, self.folder_category,
                        self.folder_group)
                        for item in self.folder_items)
                    if self.folder_group == 'NONE':
                        self.layout.label(text='Choose a group to see its folders.')
                    else:
                        self.layout.label(text='%d shown · %d selected (maximum 50)' % (
                            visible, count))
                else:
                    self.layout.label(text='Choose a model folder or a parent folder.', icon='INFO')
            else:
                self.layout.label(text='Next, select CAST files in one folder.', icon='INFO')
        box = self.layout.box()
        box.label(text='Model Setup')
        box.prop(self, 'prepare')
        box.prop(self, 'auto_link')
        box = self.layout.box()
        box.label(text='Textures')
        box.prop(self, 'texture')
        box.prop(self, 'shader')
        box.prop(self, 'texture_folder', text='Folder (optional)')
        box.prop(context.scene.my_prefs, 'use_alpha')
        draw_import_layout(self.layout, self)
        if self.ui_stage == 'FILES':
            self.layout.label(text='Select one or more CAST files.', icon='INFO')

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        context.scene.my_prefs.texture_on_import = self.texture
        context.scene.my_prefs.auto_link_rigs = self.auto_link
        prefs = context.scene.my_prefs
        prefs.import_placement, prefs.import_columns = self.placement, self.columns
        prefs.import_gap, prefs.import_collections = self.gap, self.separate_collections
        if self.ui_stage == 'CHOOSE' and self.source_mode == 'FILES':
            self.ui_stage = 'FILES'
            self.files.clear()
            self.filepath = ''
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        if self.ui_stage == 'CHOOSE':
            parent = bpy.path.abspath(self.parent_folder)
            if not os.path.isdir(parent):
                self.report({'ERROR'}, 'Choose a valid model folder.')
                return {'CANCELLED'}
            chosen = [os.path.join(parent, item.name) for item in self.folder_items
                      if item.selected]
            if not chosen:
                try:
                    chosen = [parent] if apex_model_files.model_cast(parent) else []
                except (OSError, ValueError) as error:
                    self.report({'ERROR'}, str(error))
                    return {'CANCELLED'}
            if not chosen:
                self.report({'ERROR'}, 'Select at least one model folder from the list.')
                return {'CANCELLED'}
            if self.review_before_import and not bpy.app.background:
                context.scene.my_prefs.model_parent_folder = parent
                return self.review_selection(context, apex_import_plan.inspect(
                    folders=chosen, texture_folder=bpy.path.abspath(self.texture_folder) if self.texture_folder else ''))
            try:
                paths = apex_model_files.batch_model_casts(chosen)
            except (OSError, ValueError) as error:
                self.report({'ERROR'}, str(error))
                return {'CANCELLED'}
            context.scene.my_prefs.model_parent_folder = parent
            return self.import_paths(context, paths)
        directory = bpy.path.abspath(self.directory or os.path.dirname(self.filepath))
        selected = ([os.path.join(directory, item.name) for item in self.files]
                    if self.files else [bpy.path.abspath(self.filepath or directory)])
        folders = [path for path in selected if os.path.isdir(path)]
        paths = [path for path in selected if not os.path.isdir(path)]
        if self.review_before_import and not bpy.app.background:
            return self.review_selection(context, apex_import_plan.inspect(
                folders=folders, files=paths,
                texture_folder=bpy.path.abspath(self.texture_folder) if self.texture_folder else ''))
        if folders:
            try:
                paths.extend(apex_model_files.batch_model_casts(folders))
            except (OSError, ValueError) as error:
                self.report({'ERROR'}, str(error))
                return {'CANCELLED'}
        return self.import_paths(context, paths)

    def review_selection(self, context, plan):
        if not plan.paths:
            message = '\n'.join([plan.summary, *plan.issues])
            context.scene.my_prefs.import_summary = plan.summary
            save_tool_report(context.scene.my_prefs, 'texture', plan.summary, message)
            self.report({'ERROR'}, plan.issues[0] if plan.issues else plan.summary)
            return {'CANCELLED'}
        bpy.ops.object.apex_review_model_import(
            'INVOKE_DEFAULT', files=[{'name': path} for path in plan.paths],
            issues=[{'name': issue} for issue in plan.issues],
            texture_warnings=[{'name': warning} for warning in plan.texture_warnings],
            fingerprints_json=json.dumps(plan.fingerprints),
            summary=plan.summary, shader=self.shader, prepare=self.prepare,
            auto_link=self.auto_link, texture_folder=self.texture_folder,
            placement=self.placement, columns=self.columns, gap=self.gap,
            separate_collections=self.separate_collections)
        return {'FINISHED'}

    def import_paths(self, context, paths):
        paths = list(dict.fromkeys(paths))
        paths = sorted(paths, key=lambda path: os.path.basename(path).casefold())
        if not paths or not all(path.lower().endswith('.cast') for path in paths):
            self.report({'ERROR'}, 'Choose one or more CAST model files.')
            return {'CANCELLED'}
        if len(paths) > apex_model_files.MAX_BATCH_MODELS:
            self.report({'ERROR'}, 'Choose at most 50 models per import.')
            return {'CANCELLED'}
        if len(paths) > 1:
            return self.import_batch(context, paths)
        filepath = paths[0]
        original_collections = set(bpy.data.collections)
        try:
            created = apex_workflows.import_model(context, filepath, self.prepare, self)
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        prefs = context.scene.my_prefs
        prefs.cust_enum2 = self.shader
        meshes = [obj for obj in created if obj.type == 'MESH']
        prefs.import_summary = 'Imported %d mesh%s. ' % (len(meshes), '' if len(meshes) == 1 else 'es')
        if not self.texture:
            apex_import_plan.arrange(context, [created], layout=self.placement, columns=self.columns, gap=self.gap, separate_collections=self.separate_collections, import_collections=set(bpy.data.collections) - original_collections)
            prefs.import_summary += 'Textures skipped. Use Materials > Auto Texture when ready.'
            if self.auto_link:
                start_auto_rig_links(context, created, self)
            return {'FINISHED'}
        prefs.texture_summary = ''
        prefs.texture_report = None
        try:
            result = apex_autotex.run(
                context, shader_key=self.shader, append_node_group=append_apex_node_group,
                plug_alpha=prefs.use_alpha,
                texture_folder=self.texture_folder or os.path.dirname(bpy.path.abspath(filepath)),
                search_subfolders=True, objects=meshes,
                remembered_roots=remembered_texture_roots(), remember_callback=store_texture_roots,
                report_callback=lambda *args: capture_texture_report(context, *args))
            if result == {'CANCELLED'}:
                raise RuntimeError('Texturing could not finish; see Materials > Auto Texture.')
            prefs.import_summary += prefs.texture_summary
            self.report({'INFO'}, prefs.import_summary)
        except Exception as error:
            prefs.import_summary += 'Model kept; texturing needs attention: %s' % error
            self.report({'WARNING'}, prefs.import_summary)
        # Keep a usable imported model and its Undo step even if textures are missing.
        apex_import_plan.arrange(context, [created], layout=self.placement, columns=self.columns,
                                 gap=self.gap, separate_collections=self.separate_collections,
                                 import_collections=set(bpy.data.collections) - original_collections)
        if self.auto_link:
            start_auto_rig_links(context, created, self)
        return {'FINISHED'}

    def import_batch(self, context, paths):
        prefs = context.scene.my_prefs
        prefs.cust_enum2 = self.shader
        original_selection = list(context.selected_objects)
        original_active = context.active_object
        original_collections = set(bpy.data.collections)
        groups = []
        failures = texture_warnings = mesh_count = 0
        report_lines = ['Batch Import & Texture', '']
        for filepath in paths:
            filename = os.path.basename(filepath)
            report_lines.append('=== %s ===' % filename)
            try:
                created = apex_workflows.import_model(context, filepath, self.prepare, self)
            except Exception as error:
                failures += 1
                report_lines.extend(('Import failed: %s' % error, ''))
                continue
            groups.append(created)
            meshes = [obj for obj in created if obj.type == 'MESH']
            mesh_count += len(meshes)
            if not self.texture:
                report_lines.extend(('Model imported; texturing skipped.', ''))
                continue
            file_report = []

            def capture(batch, definition, outcomes):
                summary, body = apex_diagnostics.texture_report(batch, definition, outcomes)
                file_report[:] = [summary, body]

            try:
                result = apex_autotex.run(
                    context, shader_key=self.shader, append_node_group=append_apex_node_group,
                plug_alpha=prefs.use_alpha,
                    texture_folder=self.texture_folder or os.path.dirname(bpy.path.abspath(filepath)),
                    search_subfolders=True, objects=meshes,
                    remembered_roots=remembered_texture_roots(),
                    remember_callback=store_texture_roots, report_callback=capture)
                if result == {'CANCELLED'}:
                    raise RuntimeError('Texturing could not finish.')
                if file_report:
                    report_lines.extend((file_report[1], ''))
                else:
                    report_lines.extend(('Imported %d mesh%s; no texture report.' % (
                        len(meshes), '' if len(meshes) == 1 else 'es'), ''))
            except Exception as error:
                texture_warnings += 1
                report_lines.extend(('Model kept; texturing needs attention: %s' % error, ''))
                if file_report:
                    report_lines.extend((file_report[1], ''))

        if not groups:
            apex_workflows.select_objects(context, original_selection, original_active)
            prefs.import_summary = 'No models imported. See Materials > Auto Texture report.'
            save_tool_report(prefs, 'texture', '%d files failed to import.' % failures,
                             '\n'.join(report_lines))
            self.report({'ERROR'}, prefs.import_summary)
            return {'CANCELLED'}

        apex_import_plan.arrange(context, groups, layout=self.placement, columns=self.columns,
                                 gap=self.gap, separate_collections=self.separate_collections,
                                 import_collections=set(bpy.data.collections) - original_collections)
        selected = [obj for group in groups for obj in group]
        first_rig = next((obj for obj in groups[0] if obj.type == 'ARMATURE'), groups[0][0])
        apex_workflows.select_objects(context, selected, first_rig)
        placement = {'ROW': 'in a row', 'GRID': 'in a grid', 'NONE': 'at their export positions'}[self.placement]
        summary = 'Imported %d model%s' % (len(groups), '' if len(groups) == 1 else 's')
        if len(groups) > 1:
            summary += ' ' + placement
        summary += ' (%d mesh%s).' % (mesh_count, '' if mesh_count == 1 else 'es')
        if failures:
            summary += ' %d file%s skipped.' % (failures, '' if failures == 1 else 's')
        if texture_warnings:
            summary += ' %d model%s need texturing attention.' % (
                texture_warnings, '' if texture_warnings == 1 else 's')
        prefs.import_summary = summary + ' See Materials > Auto Texture report.'
        save_tool_report(prefs, 'texture', prefs.import_summary, '\n'.join(report_lines))
        self.report({'WARNING'} if failures or texture_warnings else {'INFO'},
                    prefs.import_summary)
        if self.auto_link:
            start_auto_rig_links(context, selected, self)
        return {'FINISHED'}


class APEX_OT_review_model_import(bpy.types.Operator):
    """Review checked CAST exports before importing any models"""
    bl_idname = 'object.apex_review_model_import'
    bl_label = 'Check Model Import'
    bl_options = {'INTERNAL', 'UNDO'}
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement,
                                        options={'HIDDEN', 'SKIP_SAVE'})
    issues: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement,
                                         options={'HIDDEN', 'SKIP_SAVE'})
    texture_warnings: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement,
                                                   options={'HIDDEN', 'SKIP_SAVE'})
    summary: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    fingerprints_json: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    shader: bpy.props.EnumProperty(name='Shader', default='OP1', items=[
        ('OP1', 'Apex Shader', ''), ('OP2', 'Apex Shader+_v3.4', ''), ('OP3', 'S/G-Blender', '')])
    prepare: BoolProperty(default=True)
    auto_link: BoolProperty(default=True)
    texture_folder: bpy.props.StringProperty(subtype='DIR_PATH')
    placement: bpy.props.EnumProperty(name='Placement', items=BATCH_LAYOUT_ITEMS, default='ROW')
    columns: bpy.props.IntProperty(name='Columns', default=5, min=1, max=50)
    gap: FloatProperty(name='Minimum Gap', default=0.25, min=0.0, max=100.0, subtype='DISTANCE')
    separate_collections: BoolProperty(name='One Collection per Model', default=False)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and _active_animation_scan is None

    def invoke(self, context, event):
        if not self.fingerprints_json:
            checked = apex_import_plan.inspect(files=[item.name for item in self.files])
            self.fingerprints_json = json.dumps(checked.fingerprints)
        return context.window_manager.invoke_props_dialog(self, width=600, confirm_text='Import Models')

    def draw(self, context):
        layout = self.layout
        draw_wrapped(layout, self.summary, context, max_width=600)
        box = layout.box()
        box.label(text='%d model%s ready' % (len(self.files), '' if len(self.files) == 1 else 's'), icon='CHECKMARK')
        for item in list(self.files)[:5]:
            box.label(text=os.path.join(os.path.basename(os.path.dirname(item.name)),
                                       os.path.basename(item.name)), icon='MESH_DATA')
        if len(self.files) > 5:
            box.label(text='And %d more' % (len(self.files) - 5))
        if self.issues:
            box = layout.box()
            box.label(text='Skipped', icon='ERROR')
            for item in list(self.issues)[:2]:
                draw_wrapped(box, item.name, context, max_width=600)
            if len(self.issues) > 2:
                box.label(text='And %d more issues' % (len(self.issues) - 2))
        if self.texture_warnings:
            box = layout.box()
            box.label(text='Texture check', icon='TEXTURE')
            for item in list(self.texture_warnings)[:2]:
                draw_wrapped(box, item.name, context, max_width=600)
            if len(self.texture_warnings) > 2:
                box.label(text='And %d more texture warnings' % (len(self.texture_warnings) - 2))
            draw_wrapped(box, 'Import will also search your texture folders.', context, max_width=600)
        draw_import_layout(layout, self)

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        paths = [item.name for item in self.files]
        checked = apex_import_plan.inspect(
            files=paths, texture_folder=bpy.path.abspath(self.texture_folder) if self.texture_folder else '')
        if (set(checked.paths) != set(paths) or checked.issues
                or (self.fingerprints_json and checked.fingerprints != json.loads(self.fingerprints_json))):
            self.report({'WARNING'}, 'The exports changed after checking. Open Import & Texture and check them again.')
            return {'CANCELLED'}
        result = bpy.ops.object.apex_import_texture(
            'EXEC_DEFAULT', files=[{'name': path} for path in checked.paths],
            shader=self.shader, prepare=self.prepare, auto_link=self.auto_link,
            texture_folder=self.texture_folder, placement=self.placement,
            columns=self.columns, gap=self.gap, separate_collections=self.separate_collections)
        if result == {'FINISHED'} and self.issues:
            prefs = context.scene.my_prefs
            summary = prefs.import_summary + ' %d issue%s skipped before import.' % (
                len(self.issues), '' if len(self.issues) == 1 else 's')
            body = prefs.texture_report.as_string() if prefs.texture_report else prefs.texture_summary
            save_tool_report(prefs, 'texture', summary, body + '\n\nSkipped before import:\n' +
                             '\n'.join(item.name for item in self.issues))
            prefs.import_summary = summary
        return result


class APEX_OT_relink_rsx(bpy.types.Operator):
    """Find saved RSX paths inside a moved export library"""
    bl_idname = 'object.apex_relink_rsx'
    bl_label = 'Relink RSX Library'
    bl_options = {'REGISTER'}
    old_root: bpy.props.StringProperty(name='Previous Export Folder', subtype='DIR_PATH')
    new_root: bpy.props.StringProperty(name='New Export Folder', subtype='DIR_PATH')

    @classmethod
    def poll(cls, context):
        return _active_animation_scan is None

    def invoke(self, context, event):
        prefs = context.scene.my_prefs
        self.old_root = apex_relink.suggest_old_root(context) or prefs.relink_old_root
        self.new_root = prefs.relink_new_root
        return context.window_manager.invoke_props_dialog(self, width=620, confirm_text='Check Paths')

    def draw(self, context):
        self.layout.prop(self, 'old_root')
        self.layout.prop(self, 'new_root')
        draw_wrapped(self.layout, 'Choose the same export folder at its old and new locations. The check covers saved model, animation and texture paths in this blend file.', context, max_width=620)

    def execute(self, context):
        try:
            if not require_fresh_modules(self):
                return {'CANCELLED'}
            result = bpy.ops.object.apex_apply_rsx_relink('INVOKE_DEFAULT', old_root=self.old_root, new_root=self.new_root)
            return {'CANCELLED'} if result == {'CANCELLED'} else {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class APEX_OT_apply_rsx_relink(bpy.types.Operator):
    """Apply verified replacements for saved RSX paths"""
    bl_idname = 'object.apex_apply_rsx_relink'
    bl_label = 'Review RSX Paths'
    bl_options = {'REGISTER', 'UNDO'}
    old_root: bpy.props.StringProperty(subtype='DIR_PATH', options={'HIDDEN'})
    new_root: bpy.props.StringProperty(subtype='DIR_PATH', options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return _active_animation_scan is None

    def invoke(self, context, event):
        try:
            self._plan = apex_relink.build(context, self.old_root, self.new_root)
            return context.window_manager.invoke_props_dialog(self, width=660, confirm_text='Relink Verified Files')
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

    def draw(self, context):
        plan = self._plan
        draw_wrapped(self.layout, plan.summary, context, max_width=660)
        if plan.changes:
            box = self.layout.box()
            for change in plan.changes[:6]:
                draw_wrapped(box, '%s: %s' % (change.kind, change.label), context, max_width=660)
            if len(plan.changes) > 6:
                box.label(text='And %d more paths' % (len(plan.changes) - 6))
        for title, entries in (('Missing files', plan.missing), ('Warnings', plan.warnings)):
            if entries:
                box = self.layout.box()
                box.label(text=title, icon='ERROR')
                for message in entries[:2]:
                    draw_wrapped(box, message, context, max_width=660)
                if len(entries) > 2:
                    box.label(text='And %d more' % (len(entries) - 2))
        draw_wrapped(self.layout, 'Missing files keep their saved paths. Actions, poses and favourites are kept.', context, max_width=660)

    def execute(self, context):
        try:
            if not require_fresh_modules(self):
                return {'CANCELLED'}
            plan = getattr(self, '_plan', None)
            # Redo follows Undo, which restores RNA data but not this Python plan.
            if plan is None or plan.applied:
                plan = apex_relink.build(context, self.old_root, self.new_root)
            self._plan = plan
            message, warning = apex_relink.apply(plan)
            prefs = context.scene.my_prefs
            prefs.relink_old_root, prefs.relink_new_root = self.old_root, self.new_root
            prefs.relink_summary = message
            self.report({'WARNING'} if warning else {'INFO'}, message)
            redraw_animation_panels(context)
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


_active_animation_scan = None


def redraw_animation_panels(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


@bpy.app.handlers.persistent
def cancel_animation_scan(_=None):
    global _active_animation_scan
    if bpy.app.timers.is_registered(advance_animation_scan):
        bpy.app.timers.unregister(advance_animation_scan)
    if _active_animation_scan is not None:
        _active_animation_scan.job.close()
        _active_animation_scan = None


class ActiveAnimationScan:
    def __init__(self, rig, filepath, job_type=apex_animations.LibraryScan, **options):
        self.rig = rig
        self.job = job_type(rig, filepath, **options)
        self.error = ''


def advance_animation_scan():
    scan = _active_animation_scan
    if scan is None:
        return None
    try:
        if not getattr(scan.job, 'is_batch', False) and not scan.rig.is_editable:
            raise ValueError('The target rig is no longer editable.')
        done = scan.job.step()
    except Exception as error:
        scan.error = str(error)
        done = True
    if done:
        # Timers do not get the window manager's normal UI-operator Undo push.
        # Commit, then explicitly record exactly one step in a window context.
        windows = bpy.context.window_manager.windows
        if windows:
            area = next((area for area in windows[0].screen.areas if area.type == 'VIEW_3D'),
                        windows[0].screen.areas[0])
            region = next((region for region in area.regions if region.type == 'WINDOW'), None)
            with bpy.context.temp_override(window=windows[0], area=area, region=region):
                is_names = isinstance(scan.job, apex_animations.AnimationNamesScan)
                is_batch = getattr(scan.job, 'is_batch', False)
                if bpy.ops.object.apex_finish_animation_scan() == {'FINISHED'}:
                    message = ('Auto-Link Animation Libraries' if is_batch else
                               'Import In-Game Names' if is_names else 'Link Animation Library')
                    bpy.ops.ed.undo_push(message=message)
        else:
            cancel_animation_scan()
        return None
    redraw_animation_panels(bpy.context)
    return 0.02


class APEX_OT_finish_animation_scan(bpy.types.Operator):
    """Finish linking the indexed animation library"""
    bl_idname = 'object.apex_finish_animation_scan'
    bl_label = 'Link Animation Library'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return _active_animation_scan is not None

    def execute(self, context):
        scan = _active_animation_scan
        try:
            if scan.error:
                raise ValueError(scan.error)
            message, warning = scan.job.commit(scan.rig)
            self.report({'WARNING'} if warning else {'INFO'}, message)
            return {'FINISHED'}
        except Exception as error:
            self.report({'WARNING'}, 'Animation indexing failed: %s' % error)
            return {'CANCELLED'}
        finally:
            cancel_animation_scan()
            redraw_animation_panels(context)


def start_auto_rig_links(context, objects, operator):
    """Queue legend libraries without changing selection or loading an Action."""
    global _active_animation_scan
    if _active_animation_scan is not None:
        operator.report({'WARNING'}, 'Finish the current animation scan before auto-linking.')
        return {'CANCELLED'}
    job = None
    try:
        rigs = [obj for obj in objects if obj.type == 'ARMATURE' and obj.is_editable]
        targets, notices = apex_auto_rigs.plan(context, rigs)
        if not targets:
            if notices:
                operator.report({'INFO'}, notices[0])
            redraw_animation_panels(context)
            return {'CANCELLED'}
        rig, filepath = targets[0]
        if bpy.app.background or context.window is None:
            job = apex_auto_rigs.BatchScan(rig, filepath, targets=targets)
            while not job.step():
                pass
            message, warning = job.commit(rig)
            operator.report({'WARNING'} if warning else {'INFO'}, message)
        else:
            _active_animation_scan = ActiveAnimationScan(
                rig, filepath, apex_auto_rigs.BatchScan, targets=targets)
            bpy.app.timers.register(advance_animation_scan, first_interval=0.02)
            operator.report({'INFO'}, 'Auto-linking animation rigs for %d model%s.' % (
                len(targets), '' if len(targets) == 1 else 's'))
        redraw_animation_panels(context)
        return {'FINISHED'}
    except Exception as error:
        cancel_animation_scan()
        operator.report({'WARNING'}, 'Models kept; animation auto-linking could not finish: %s' % error)
        return {'CANCELLED'}
    finally:
        if job is not None:
            job.close()


class APEX_OT_auto_link_animation_rig(bpy.types.Operator):
    """Find the selected legend's exported animation rig"""
    bl_idname = 'object.apex_auto_link_animation_rig'
    bl_label = 'Auto-Link Animation Rig'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return (context.mode in {'OBJECT', 'POSE'} and rig is not None and rig.is_editable
                and not rig.apex_animation_library.rig_file
                and _active_animation_scan is None)

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        return start_auto_rig_links(context, [apex_workflows.selected_rig(context)], self)


class AnimationScanOperator:
    def start_scan(self, context, filepath, job_type=apex_animations.LibraryScan, **options):
        global _active_animation_scan
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        rig = apex_workflows.selected_rig(context)
        try:
            if bpy.app.background or context.window is None:
                job = job_type(rig, filepath, **options)
                try:
                    while not job.step():
                        pass
                    message, warning = job.commit(rig)
                finally:
                    job.close()
                self.report({'WARNING'} if warning else {'INFO'}, message)
                return {'FINISHED'}
            if _active_animation_scan is not None:
                self.report({'WARNING'}, 'Wait for the current animation scan or cancel it first.')
                return {'CANCELLED'}
            _active_animation_scan = ActiveAnimationScan(rig, filepath, job_type, **options)
            bpy.app.timers.register(advance_animation_scan, first_interval=0.02)
            redraw_animation_panels(context)
            return {'FINISHED'}
        except Exception as error:
            cancel_animation_scan()
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


def refresh_animation_rigs(self, context):
    self.rig_items.clear()
    folder = bpy.path.abspath(self.parent_folder)
    names = [name for name, _ in apex_model_files.legend_animation_rigs(folder)]
    for name in names:
        self.rig_items.add().name = name
    _animation_rig_legend_items[:] = [('NONE', 'Choose a legend', '')] + [
        (legend, '%s (%d)' % (label, count), '')
        for legend, label, count in apex_model_files.animation_rig_legend_options(names)]
    self.rig_legend = 'NONE'
    self.rig_index = 0


_animation_rig_legend_items = [('NONE', 'Choose a legend', '')]


def animation_rig_legend_items(self, context):
    return _animation_rig_legend_items


def animation_rig_legend_changed(self, context):
    self.rig_search = ''
    self.rig_index = next((i for i, item in enumerate(self.rig_items)
                           if apex_model_files.animation_rig_matches(
                               item.name, self.rig_legend)), 0)


def animation_rig_search_changed(self, context):
    query = self.rig_search.strip().casefold()
    if query and self.rig_items and (not 0 <= self.rig_index < len(self.rig_items)
                                     or not apex_model_files.animation_rig_matches(
                                         self.rig_items[self.rig_index].name,
                                         self.rig_legend, query)):
        self.rig_index = next((i for i, item in enumerate(self.rig_items)
                               if apex_model_files.animation_rig_matches(
                                   item.name, self.rig_legend, query)), self.rig_index)


class APEX_UL_animation_rigs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name, icon='ARMATURE_DATA')

    def filter_items(self, context, data, propname):
        return ([self.bitflag_filter_item if apex_model_files.animation_rig_matches(
                     item.name, data.rig_legend, data.rig_search) else 0
                 for item in getattr(data, propname)], [])


def preferred_animation_rig_folder(candidates):
    existing = [path for path in candidates if path and os.path.isdir(path)]
    return next((path for path in existing
                 if apex_model_files.legend_animation_rigs(path)),
                existing[0] if existing else '')


class APEX_OT_link_animation_rig(AnimationScanOperator, bpy.types.Operator, ImportHelper):
    """Choose an RSX rig exported as CAST with Export Rig Sequences enabled and animation format CAST"""
    bl_idname = 'object.apex_link_animation_rig'
    bl_label = 'Link Animation Rig'
    bl_options = {'REGISTER'}
    filename_ext = '.cast'
    filter_glob: bpy.props.StringProperty(default='*.cast', options={'HIDDEN'})
    source_mode: bpy.props.EnumProperty(name='Choose', items=[
        ('LEGENDS', 'Legend rigs', 'Choose an exported legend rig from the list'),
        ('FILE', 'Other CAST', 'Browse to any exported animation rig CAST')],
        default='LEGENDS')
    parent_folder: bpy.props.StringProperty(name='Animation rigs folder', subtype='DIR_PATH',
                                            update=refresh_animation_rigs)
    rig_items: bpy.props.CollectionProperty(type=APEX_PG_import_folder,
                                            options={'HIDDEN', 'SKIP_SAVE'})
    rig_index: bpy.props.IntProperty(options={'HIDDEN', 'SKIP_SAVE'})
    rig_legend: bpy.props.EnumProperty(name='Legend', items=animation_rig_legend_items,
                                      update=animation_rig_legend_changed)
    rig_search: bpy.props.StringProperty(name='Search rigs',
                                        update=animation_rig_search_changed)
    change_parent: BoolProperty(name='Change folder', default=False)
    ui_stage: bpy.props.EnumProperty(items=[('DIRECT', 'Direct', ''),
                                            ('CHOOSE', 'Choose', ''),
                                            ('FILE', 'File', '')],
                                     default='DIRECT', options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return (not _active_animation_scan and context.mode in {'OBJECT', 'POSE'}
                and rig is not None and rig.is_editable)

    def invoke(self, context, event):
        self.ui_stage = 'CHOOSE'
        prefs = context.scene.my_prefs
        rig = apex_workflows.selected_rig(context)
        linked = rig.apex_animation_library.rig_file
        candidates = [prefs.animation_parent_folder,
                      os.path.dirname(bpy.path.abspath(linked)) if linked else '']
        candidates = [os.path.dirname(path) if path and
                      os.path.basename(os.path.normpath(path)).casefold().startswith('pilot_') else path
                      for path in candidates]
        model_root = bpy.path.abspath(prefs.model_parent_folder) if prefs.model_parent_folder else ''
        if model_root and os.path.basename(os.path.normpath(model_root)).casefold() == 'mdl':
            candidates.append(os.path.join(os.path.dirname(model_root), 'animrig'))
        bookmarks = bpy.utils.user_resource('CONFIG', path='bookmarks.txt')
        candidates.append(apex_model_files.bookmarked_animrig(bookmarks))
        self.parent_folder = preferred_animation_rig_folder(candidates)
        self.rig_legend = 'NONE'
        return context.window_manager.invoke_props_dialog(
            self, width=540, confirm_text='Link Selected Rig')

    def draw(self, context):
        if self.ui_stage != 'CHOOSE':
            return
        self.layout.prop(self, 'source_mode', expand=True)
        if self.source_mode == 'FILE':
            self.layout.label(text='Next, choose an exported rig CAST.', icon='INFO')
            return
        if self.rig_items and not self.change_parent:
            self.layout.label(text='Legend rigs in ' + os.path.basename(
                os.path.normpath(self.parent_folder)), icon='FILE_FOLDER')
            self.layout.prop(self, 'change_parent', text='Change folder')
        else:
            self.layout.prop(self, 'parent_folder')
        if self.rig_items:
            self.layout.prop(self, 'rig_legend', text='Legend')
            if self.rig_legend != 'NONE':
                self.layout.prop(self, 'rig_search', text='Search', icon='VIEWZOOM')
                self.layout.template_list('APEX_UL_animation_rigs', '', self,
                                          'rig_items', self, 'rig_index', rows=10)
            else:
                self.layout.label(text='Choose a legend to see its rigs.', icon='INFO')
        else:
            self.layout.label(text='Choose an RSX animrig folder containing legend exports.', icon='INFO')

    def execute(self, context):
        if self.ui_stage == 'CHOOSE' and self.source_mode == 'FILE':
            self.ui_stage = 'FILE'
            self.filepath = ''
            if self.parent_folder:
                self.directory = self.parent_folder
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        if self.ui_stage == 'CHOOSE':
            if (not self.rig_items or not 0 <= self.rig_index < len(self.rig_items)
                    or not apex_model_files.animation_rig_matches(
                        self.rig_items[self.rig_index].name,
                        self.rig_legend, self.rig_search)):
                self.report({'ERROR'}, 'Choose a legend rig from the list.')
                return {'CANCELLED'}
            name = self.rig_items[self.rig_index].name
            candidates = dict(apex_model_files.legend_animation_rigs(
                bpy.path.abspath(self.parent_folder)))
            filepath = candidates.get(name)
            if not filepath:
                self.report({'ERROR'}, 'That rig export is no longer available. Choose another rig.')
                return {'CANCELLED'}
            context.scene.my_prefs.animation_parent_folder = self.parent_folder
            return self.start_scan(context, filepath)
        return self.start_scan(context, self.filepath)


class APEX_OT_import_animation_cast(bpy.types.Operator, ImportHelper):
    """Apply one CAST animation sequence to the selected armature"""
    bl_idname = 'object.apex_import_animation_cast'
    bl_label = 'Import Animation CAST'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = '.cast'
    filter_glob: bpy.props.StringProperty(default='*.cast', options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return bool(not _active_animation_scan and context.mode in {'OBJECT', 'POSE'}
                    and rig and rig.is_editable and rig.data.is_editable and not apex_layers.can_remove(rig))

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        try:
            rig = apex_workflows.selected_rig(context)
            item, missing = apex_animations.import_single_clip(context, rig, self.filepath, self)
            message = 'Imported %s.' % apex_animations.clip_label(item, rig.apex_animation_library)
            if missing:
                message += ' Skipped %d missing bones.' % missing
            if item.additive:
                message += ' To layer this clip, load a base animation, then select this clip and use Add Animation Layer.'
            self.report({'WARNING'} if missing or item.additive else {'INFO'}, message)
            redraw_animation_panels(context)
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class APEX_OT_refresh_animations(AnimationScanOperator, bpy.types.Operator):
    """Read the linked rig export again after adding or replacing animation files"""
    bl_idname = 'object.apex_refresh_animations'
    bl_label = 'Refresh Animations'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return bool(not _active_animation_scan and context.mode in {'OBJECT', 'POSE'}
                    and rig and rig.is_editable and rig.apex_animation_library.rig_file)

    def execute(self, context):
        rig = apex_workflows.selected_rig(context)
        return self.start_scan(context, rig.apex_animation_library.rig_file, force=True)


class APEX_OT_cancel_animation_scan(bpy.types.Operator):
    """Cancel indexing and keep the previously linked animation list"""
    bl_idname = 'object.apex_cancel_animation_scan'
    bl_label = 'Cancel Indexing'

    @classmethod
    def poll(cls, context):
        return _active_animation_scan is not None

    def execute(self, context):
        cancel_animation_scan()
        redraw_animation_panels(context)
        self.report({'INFO'}, 'Indexing cancelled; the previous animation list was kept.')
        return {'FINISHED'}


class APEX_OT_import_animation_names(AnimationScanOperator, bpy.types.Operator, ImportHelper):
    """Match menu names using your RSX language export and animation item settings"""
    bl_idname = 'object.apex_import_animation_names'
    bl_label = 'Import Other Names / Language'
    bl_options = {'REGISTER'}
    filename_ext = '.locl'
    filter_glob: bpy.props.StringProperty(default='*.locl', options={'HIDDEN'})
    settings_folder: bpy.props.StringProperty(name='Settings Folder', subtype='DIR_PATH',
        description='Optional override; normally settings/itemflav beside the localization folder')

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return bool(not _active_animation_scan and rig and rig.is_editable and rig.apex_animation_library.clips)

    def invoke(self, context, event):
        library = apex_workflows.selected_rig(context).apex_animation_library
        self.filepath = library.names_file
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        draw_wrapped(self.layout, 'Choose the localization .locl exported by RSX. Keep the '
                     'exported settings/itemflav folder beside the localization folder.', context)
        self.layout.prop(self, 'settings_folder')

    def execute(self, context):
        return self.start_scan(context, self.filepath, apex_animations.AnimationNamesScan,
                               settings_folder=self.settings_folder)


class APEX_OT_builtin_animation_names(bpy.types.Operator):
    """Use the included English names, replacing imported name overrides for this model"""
    bl_idname = 'object.apex_builtin_animation_names'
    bl_label = 'Use Included English Names'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return bool(not _active_animation_scan and rig and rig.is_editable and rig.apex_animation_library.clips)

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        try:
            message = apex_animations.use_bundled_names(apex_workflows.selected_rig(context).apex_animation_library)
            self.report({'INFO'}, message)
            redraw_animation_panels(context)
            return {'FINISHED'}
        except (OSError, ValueError, TypeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class APEX_OT_remove_animation(bpy.types.Operator):
    """Keep the action for reuse and return all bones to the model's rest pose (T-pose)"""
    bl_idname = 'object.apex_remove_animation'
    bl_label = 'Remove Animation / T-Pose'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return bool(not _active_animation_scan and context.mode in {'OBJECT', 'POSE'}
                    and rig and rig.is_editable and rig.data.is_editable and not apex_layers.can_remove(rig))

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        try:
            apex_animations.remove_animation(context, apex_workflows.selected_rig(context))
            self.report({'INFO'}, 'Animation removed; the model is back in its rest pose.')
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class APEX_OT_favourite_animation(bpy.types.Operator):
    """Add or remove this clip from the selected model's favourites; saved in the blend file"""
    bl_idname = 'object.apex_favourite_animation'
    bl_label = 'Toggle Animation Favourite'
    bl_options = {'UNDO'}
    index: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return bool(not _active_animation_scan and rig and rig.is_editable and rig.apex_animation_library.clips)

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        library = apex_workflows.selected_rig(context).apex_animation_library
        if not 0 <= self.index < len(library.clips):
            return {'CANCELLED'}
        item = library.clips[self.index]
        item.favourite = not item.favourite
        apex_animations.ensure_visible_selection(library)
        redraw_animation_panels(context)
        return {'FINISHED'}


class APEX_OT_clear_recent_animations(bpy.types.Operator):
    """Clear this model's recent list while keeping its actions and favourites"""
    bl_idname = 'object.apex_clear_recent_animations'
    bl_label = 'Clear Recent List'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return bool(not _active_animation_scan and rig and rig.is_editable
                    and any(item.recent_order for item in rig.apex_animation_library.clips))

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        apex_animations.clear_recent(apex_workflows.selected_rig(context).apex_animation_library)
        redraw_animation_panels(context)
        return {'FINISHED'}


class APEX_OT_load_animation(bpy.types.Operator):
    """Load the clip using quaternion channels and reset the armature's rotation; keep its position, scale and previous action"""
    bl_idname = 'object.apex_load_animation'
    bl_label = 'Load Animation'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return bool(not _active_animation_scan and context.mode in {'OBJECT', 'POSE'} and rig and rig.is_editable
                    and rig.apex_animation_library.clips and not apex_layers.can_remove(rig))

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        rig = apex_workflows.selected_rig(context)
        library = rig.apex_animation_library
        if library.index >= len(library.clips):
            return {'CANCELLED'}
        item = library.clips[library.index]
        if library.index not in apex_animations.visible_clip_indices(library):
            self.report({'WARNING'}, 'Select an animation from the filtered list first.')
            return {'CANCELLED'}
        try:
            missing = apex_animations.load_clip(context, rig, item, library.fit_timeline,
                                                library.allow_missing, self)
            message = 'Loaded %s; armature rotation reset.' % apex_animations.clip_label(item, library)
            if missing:
                message += ' Skipped %d missing bones.' % missing
            if item.additive:
                message += ' To layer this clip, load a base animation, then select this clip and use Add Animation Layer.'
            self.report({'WARNING'} if missing or item.additive else {'INFO'}, message)
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class APEX_OT_add_animation_layer(bpy.types.Operator):
    """Layer the selected additive clip over the model's base animation"""
    bl_idname = 'object.apex_add_animation_layer'
    bl_label = 'Add Animation Layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        if _active_animation_scan is not None or rig is None or not rig.is_editable:
            return False
        library = rig.apex_animation_library
        return (context.mode in {'OBJECT', 'POSE'} and library.index in apex_animations.visible_clip_indices(library)
                and apex_layers.can_add(rig, library.clips[library.index]))

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        rig = apex_workflows.selected_rig(context)
        library = rig.apex_animation_library
        try:
            message = apex_layers.add(context, rig, library.clips[library.index],
                                      library.layer_influence, library.layer_offset, self)
            self.report({'INFO'}, message)
            redraw_animation_panels(context)
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class APEX_OT_remove_animation_layers(bpy.types.Operator):
    """Remove Toolbox's additive layers and restore the base animation"""
    bl_idname = 'object.apex_remove_animation_layers'
    bl_label = 'Remove Animation Layers'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return (context.mode in {'OBJECT', 'POSE'} and _active_animation_scan is None
                and rig is not None and rig.is_editable and apex_layers.can_remove(rig))

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        try:
            self.report({'INFO'}, apex_layers.remove(context, apex_workflows.selected_rig(context)))
            redraw_animation_panels(context)
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class APEX_OT_adjust_animation_layer(bpy.types.Operator):
    """Set the strength of one Toolbox animation layer"""
    bl_idname = 'object.apex_adjust_animation_layer'
    bl_label = 'Animation Layer Strength'
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(min=0, options={'HIDDEN'})
    strength: FloatProperty(name='Strength', default=1.0, min=0.0, max=1.0)

    @classmethod
    def poll(cls, context):
        rig = apex_workflows.selected_rig(context)
        return _active_animation_scan is None and rig is not None and rig.is_editable and apex_layers.can_remove(rig)

    def invoke(self, context, event):
        strips = apex_layers.layers(apex_workflows.selected_rig(context))
        if self.index >= len(strips):
            return {'CANCELLED'}
        self.strength = apex_layers.influence(strips[self.index])
        return context.window_manager.invoke_props_dialog(self, width=320)

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        try:
            apex_layers.set_influence(context, apex_workflows.selected_rig(context), self.index, self.strength)
            redraw_animation_panels(context)
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


def draw_animation_layers(layout, context, rig):
    library = rig.apex_animation_library
    strips = apex_layers.layers(rig)
    box = layout.box()
    title = 'Animation Layers' + (' (%d)' % len(strips) if strips else '')
    box.prop(library, 'show_layers', text=title, emboss=False,
             icon='TRIA_DOWN' if library.show_layers else 'TRIA_RIGHT')
    if not library.show_layers:
        if strips:
            box.operator('object.apex_remove_animation_layers', icon='X')
        return
    selected = (library.clips[library.index]
                if library.index in apex_animations.visible_clip_indices(library) else None)
    if selected is None or not selected.additive:
        draw_wrapped(box, 'Load a base animation, then select an additive clip from the list.', context)
    else:
        draw_wrapped(box, 'Add the selected clip over the base animation.', context)
    box.prop(library, 'layer_influence')
    box.prop(library, 'layer_offset')
    box.operator('object.apex_add_animation_layer', icon='NLA')
    for index, strip in enumerate(strips):
        row = box.row(align=True)
        # The final token identifies managed strips internally, but is not
        # useful when choosing a layer's strength.
        row.label(text=strip.name.rsplit(' ', 1)[0])
        row.operator('object.apex_adjust_animation_layer', text='%.0f%%' % (
            apex_layers.influence(strip) * 100)).index = index
    if apex_layers.can_remove(rig):
        box.operator('object.apex_remove_animation_layers', icon='X')


def draw_current_animation(layout, context, rig):
    action = apex_layers.base_action(rig)
    if action is None:
        return
    library = rig.apex_animation_library
    playing = next((item for item in library.clips if item.action == action), None)
    label = apex_animations.clip_label(playing, library) if playing else action.name
    prefix = 'Base: ' if apex_layers.can_remove(rig) else 'Current: '
    draw_wrapped(layout, prefix + label, context)


class APEX_UL_animations(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.operator('object.apex_favourite_animation', text='', emboss=False,
                     icon='SOLO_ON' if item.favourite else 'SOLO_OFF').index = index
        row.label(text=apex_animations.clip_label(item, data), icon='ACTION')
        if item.additive:
            layout.label(text='Additive')

    def filter_items(self, context, data, propname):
        visible = apex_animations.visible_clip_indices(data)
        visible_set = set(visible)
        items = getattr(data, propname)
        flags = [self.bitflag_filter_item if i in visible_set else 0 for i in range(len(items))]
        order = []
        if data.browse_mode == 'RECENT':
            sorted_indices = visible + [i for i in range(len(items)) if i not in visible_set]
            order = [0] * len(items)
            for position, index in enumerate(sorted_indices):
                order[index] = position
        return flags, order


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
                            select_pose_bone(sel_objects[0], nose_bone.name)
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
                            select_pose_bone(bpy.data.objects[sel_names[0]], boneToSelect2.name)
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
        if any(name in arm.data.bones for name in ik_bone_names + ik_pole_names) or any(
                constraint.type == 'IK'
                for name in constr_bones
                for constraint in arm.pose.bones[name].constraints):
            self.report({'WARNING'}, "IK controls are already present on this rig.")
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
                select_pose_bone(arm, ik_bone.name)
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
                    
                    
            # Keep pole controls independent of their IK chains. Constraining a
            # pole to the driven wrist or ankle creates a dependency cycle and
            # makes the solver's result depend on evaluation order.


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

    @classmethod
    def poll(cls, context):
        if cls.__name__ == 'APEX_PT_main':
            return True
        root = cls
        while getattr(root, 'bl_parent_id', ''):
            root = globals()[root.bl_parent_id]
        groups = {'APEX_PT_model': 'MODEL', 'APEX_PT_materials': 'MODEL',
                  'APEX_PT_animations': 'ANIMATION', 'APEX_PT_rigging': 'ANIMATION',
                  'APEX_PT_environment': 'SCENE', 'APEX_PT_effects': 'SCENE',
                  'APEX_PT_health': 'TOOLS', 'APEX_PT_about': 'TOOLS'}
        return context.scene.my_prefs.workspace_tab == groups.get(root.__name__, 'TOOLS')


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
        prefs = addon_prefs()
        if prefs is not None:
            layout.prop(prefs, 'asset_folder', text='Assets Folder')
            if prefs.asset_folder and not assets_installed():
                layout.label(text='Choose the folder containing Assets.blend', icon='ERROR')
        layout.row(align=True).prop(context.scene.my_prefs, 'workspace_tab', expand=True)


class APEX_PT_model(ApexPanel, bpy.types.Panel):
    """Preparing a freshly imported model"""

    bl_label = "Model"
    bl_idname = "APEX_PT_model"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        layout.operator('object.apex_import_texture', icon='IMPORT')
        if context.mode != 'OBJECT':
            layout.label(text='Switch to Object Mode to import', icon='INFO')
        if context.scene.my_prefs.import_summary:
            draw_wrapped(layout, context.scene.my_prefs.import_summary, context)


class APEX_PT_model_adjustments(ApexPanel, bpy.types.Panel):
    """Optional preparation tools for models imported separately"""

    bl_label = 'Manual Adjustments'
    bl_idname = 'APEX_PT_model_adjustments'
    bl_parent_id = 'APEX_PT_model'
    bl_order = 0
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        column.operator('object.ef_button_spawn',
                        text="Set Correct Model Size",
                        icon='FULLSCREEN_ENTER').cool_effect = 'adjust_model'
        column.operator('object.apex_xyz_euler', text='Use XYZ Euler Rotation',
                        icon='DRIVER_ROTATIONAL_DIFFERENCE')


class APEX_PT_animations(ApexPanel, bpy.types.Panel):
    bl_label = 'Animations'
    bl_idname = 'APEX_PT_animations'
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        if _active_animation_scan is not None:
            box = layout.box()
            draw_wrapped(box, 'Indexing: ' + _active_animation_scan.job.path.stem, context)
            draw_wrapped(box, _active_animation_scan.job.status, context)
            box.operator('object.apex_cancel_animation_scan', icon='CANCEL')
        rig = apex_workflows.selected_rig(context)
        if rig is None:
            draw_wrapped(layout, 'Select a legend or its armature to begin.', context)
            return
        library = rig.apex_animation_library
        layout.label(text=rig.name, icon='ARMATURE_DATA')
        row = layout.row(align=True)
        if not library.rig_file:
            row.operator('object.apex_auto_link_animation_rig', text='Auto-Link', icon='LINKED')
        row.operator('object.apex_link_animation_rig',
                     text='Change Rig' if library.rig_file else 'Link Animation Rig', icon='LINKED')
        if library.rig_file:
            row.operator('object.apex_refresh_animations', text='', icon='FILE_REFRESH')
        layout.operator('object.apex_import_animation_cast', text='Import Animation CAST', icon='IMPORT')
        if not library.clips:
            if library.summary:
                draw_wrapped(layout, library.summary, context)
            draw_wrapped(layout, 'Link an RSX rig or import one CAST animation.', context)
            layout.operator('object.lgndtranslate_url', text='Export Setup Guide', icon='HELP').link = 'workflow_guide'
            draw_current_animation(layout, context, rig)
            layout.operator('object.apex_remove_animation', icon='LOOP_BACK')
            if apex_layers.can_remove(rig):
                draw_animation_layers(layout, context, rig)
            return
        # Keep actionable scan warnings visible even with the details folded away.
        if 'warning' in library.summary.lower():
            box = layout.box()
            draw_wrapped(box, library.summary, context)
        layout.row(align=True).prop(library, 'browse_mode', expand=True)
        layout.prop(library, 'category')
        layout.prop(library, 'filter_text', text='Search', icon='VIEWZOOM')
        visible = apex_animations.visible_clip_indices(library)
        count = len(visible)
        layout.label(text=('%d animations' % count if count == len(library.clips)
                           else '%d of %d animations' % (count, len(library.clips))))
        layout.template_list('APEX_UL_animations', '', library, 'clips', library, 'index', rows=6)
        if not visible:
            if library.category != 'ALL' or library.filter_text:
                message = 'No matches. Clear the search or change the filters.'
            elif library.browse_mode == 'FAVOURITES':
                message = 'Star animations in All to save them here.'
            elif library.browse_mode == 'RECENT':
                message = 'Loaded animations will appear here.'
            else:
                message = 'No animations linked. Refresh the exported rig.'
            draw_wrapped(layout, message, context)
        if library.browse_mode == 'RECENT':
            layout.operator('object.apex_clear_recent_animations', icon='X')
        row = layout.row()
        row.scale_y = 1.25
        row.enabled = library.index in visible
        row.operator('object.apex_load_animation', icon='ACTION')
        layout.operator('object.apex_remove_animation', icon='LOOP_BACK')
        draw_current_animation(layout, context, rig)
        if apex_layers.can_remove(rig):
            draw_wrapped(layout, 'Remove layers to load another clip or return to T-pose.', context)
        draw_animation_layers(layout, context, rig)
        box = layout.box()
        box.prop(library, 'show_name_options', emboss=False,
                 icon='TRIA_DOWN' if library.show_name_options else 'TRIA_RIGHT')
        if library.show_name_options:
            box.label(text='Playback')
            box.prop(library, 'fit_timeline')
            box.prop(library, 'allow_missing')
            box.separator()
            box.label(text='Names')
            box.prop(library, 'show_menu_names')
            if library.names_summary:
                draw_wrapped(box, library.names_summary, context)
            box.operator('object.apex_builtin_animation_names', text='Use Included English Names', icon='FILE_REFRESH')
            box.operator('object.apex_import_animation_names', text='Import Names / Language', icon='IMPORT')
            box.separator()
            box.label(text='Linked Export')
            path_row = box.row()
            path_row.enabled = False
            path_row.prop(library, 'rig_file', text='Rig')
            if library.index in visible:
                draw_wrapped(box, 'Export: ' + library.clips[library.index].name, context)


class APEX_PT_materials(ApexPanel, bpy.types.Panel):
    """Texturing and shading the imported model"""

    bl_label = "Materials"
    bl_idname = "APEX_PT_materials"
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

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
        layout.prop(prefs, "autotex_folder", text="Folder (optional)")
        layout.prop(prefs, "use_alpha")
        layout.operator("object.apex_check_transparency", icon="VIEWZOOM")

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

        layout.prop(prefs, "aut_subf", text="Search Subfolders")

        column = layout.column(align=True)
        column.use_property_split = False
        remembered = remembered_texture_roots()
        if remembered:
            column.label(text="%d folder(s) remembered" % len(remembered),
                         icon='CHECKMARK')


class APEX_PT_recolour(ApexPanel, bpy.types.Panel):
    """Re-texture the model from a different skin's texture folder"""

    bl_label = "Recolour"
    bl_idname = "APEX_PT_recolour"
    bl_parent_id = "APEX_PT_materials"
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        prefs = context.scene.my_prefs

        layout.prop(prefs, 'recolor_folder', text="Skin Folder")
        layout.prop(prefs, 'cust_enum', text="Shader")
        layout.prop(prefs, 'rec_alpha', text="Use Transparency")

        column = layout.column()
        column.use_property_split = False
        column.scale_y = 1.3
        column.enabled = bool(prefs.recolor_folder)
        column.operator("object.button_custom2", text="Recolour Model",
                        icon='NODE_TEXTURE')


class APEX_PT_shader_library(ApexPanel, bpy.types.Panel):
    """Add shader node groups without texturing a model"""
    bl_label = 'Shader Library'
    bl_idname = 'APEX_PT_shader_library'
    bl_parent_id = 'APEX_PT_materials'
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(context.scene.my_prefs, 'cust_enum_shader', text='Shader')
        layout.operator('object.button_shaders', text='Add Shader', icon='NODE_MATERIAL')


class APEX_PT_environment(ApexPanel, bpy.types.Panel):
    """World lighting, HDRI and scene setup"""

    bl_label = "Lighting & Scene"
    bl_idname = "APEX_PT_environment"
    bl_order = 5
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        prefs = context.scene.my_prefs
        extended = assets_installed()

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
            strength, rotation = background
            column.prop(strength, "default_value", text="Brightness")
            if rotation is not None:
                column.prop(rotation, "default_value", text="Rotation")


class APEX_PT_rigging(ApexPanel, bpy.types.Panel):
    """Bone display, IK helpers and item pairing"""

    bl_label = "Rigging"
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


def selected_attachment_rigs(context):
    rigs = []
    for obj in context.selected_objects:
        rig = obj if obj.type == 'ARMATURE' else (obj.find_armature() if obj.type == 'MESH' else None)
        if rig is not None and rig not in rigs:
            rigs.append(rig)
    return rigs


class APEX_OT_use_selected_attachment_rigs(bpy.types.Operator):
    """Use the two selected armatures as the legend and item rigs"""
    bl_idname = 'object.apex_use_selected_attachment_rigs'
    bl_label = 'Use Selected Rigs'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and len(selected_attachment_rigs(context)) == 2

    def execute(self, context):
        rigs = selected_attachment_rigs(context)
        active = context.active_object
        active = active if active and active.type == 'ARMATURE' else (active.find_armature() if active and active.type == 'MESH' else None)
        legends = [rig for rig in rigs if any(apex_attachments.socket_bone(rig, socket)
                                               for socket in apex_attachments.SOCKET_BONES)]
        if len(legends) == 1:
            legend = legends[0]
        elif active in rigs:
            legend = active
        else:
            self.report({'ERROR'}, 'Make the legend rig active, then try again.')
            return {'CANCELLED'}
        context.scene.apex_attachment_legend = legend
        context.scene.apex_attachment_item = next(rig for rig in rigs if rig != legend)
        return {'FINISHED'}


class APEX_OT_pair_item(bpy.types.Operator):
    """Snap an imported item rig to a legend's attachment bone"""
    bl_idname = 'object.apex_pair_item'
    bl_label = 'Pair Item to Bone'
    bl_options = {'REGISTER', 'UNDO'}

    socket: bpy.props.EnumProperty(items=[
        ('LEFT_HAND', 'Left Hand', 'Attach to the left prop-hand bone'),
        ('RIGHT_HAND', 'Right Hand', 'Attach to the right prop-hand bone'),
        ('WEAPON', 'Weapon', 'Attach to the prop-gun bone'),
        ('CUSTOM', 'Other Bone', 'Attach to the bone chosen below'),
    ])

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return bool(context.mode in {'OBJECT', 'POSE'} and scene and
                    scene.apex_attachment_legend and scene.apex_attachment_item)

    def execute(self, context):
        if not require_fresh_modules(self):
            return {'CANCELLED'}
        scene = context.scene
        legend = scene.apex_attachment_legend
        item = scene.apex_attachment_item
        if self.socket == 'CUSTOM':
            bone_name = scene.apex_attachment_bone
            if not bone_name:
                self.report({'ERROR'}, 'Choose a bone from the legend rig first.')
                return {'CANCELLED'}
        else:
            bone = apex_attachments.socket_bone(legend, self.socket)
            if bone is None:
                self.report({'ERROR'}, 'This legend rig has no %s attachment bone. '
                            'Choose Other Bone instead.' % self.socket.lower().replace('_', ' '))
                return {'CANCELLED'}
            bone_name = bone.name
        try:
            apex_attachments.attach_item(context, item, legend, bone_name)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, "%s paired to %s. Adjust its position or rotation if needed." %
                    (item.name, bone_name))
        return {'FINISHED'}


class APEX_OT_check_transparency(bpy.types.Operator):
    """Report connected opacity sources and their pixel range without changing materials"""
    bl_idname = 'object.apex_check_transparency'
    bl_label = 'Check Transparency'

    def execute(self, context):
        from array import array
        lines = ['Transparency check', '', 'Connections and pixel values show what Blender uses, not whether the game intended it as opacity.', '']
        materials = apex_autotex.material_slots(texture_targets(context))
        for material in materials:
            lines.append(material.name)
            found = False
            if not material.use_nodes:
                lines.append('  No node-based transparency.')
                continue
            for node in material.node_tree.nodes:
                names = ['Alpha'] if node.type == 'BSDF_PRINCIPLED' else []
                if node.type == 'GROUP' and node.node_tree:
                    definition = next((d for d in apex_shaders.SHADER_DEFS.values() if d.group_name == node.node_tree.name), None)
                    if definition:
                        names = [definition.sockets[apex_roles.OPACITY]]
                for name in names:
                    socket = node.inputs.get(name)
                    if socket is None or not socket.is_linked:
                        continue
                    found = True
                    link = socket.links[0]
                    source = link.from_node
                    lines.append('  Connected: %s / %s' % (source.name, link.from_socket.name))
                    image = getattr(source, 'image', None)
                    if image is None:
                        lines.append('  Pixel range unavailable; inspect the node chain or load the image.')
                        continue
                    count = len(image.pixels)
                    if count > 64 * 1024 * 1024:
                        lines.append('  Large image: pixel scan skipped. Inspect in Image Editor.')
                        continue
                    pixels = array('f', [0.0]) * count
                    image.pixels.foreach_get(pixels)
                    values = pixels[3::4] if link.from_socket.name == 'Alpha' else pixels[0::4]
                    if not values:
                        lines.append('  Pixel data unavailable.')
                    if values:
                        low, high = min(values), max(values)
                        lines.append('  %s: %.4f to %.4f%s' % ('Alpha' if link.from_socket.name == 'Alpha' else 'Red channel', low, high, ' (fully opaque)' if low >= 0.9999 else ' (contains non-opaque values)'))
            if not found:
                lines.append('  No supported alpha/opacity input is connected.')
        save_tool_report(context.scene.my_prefs, 'texture', 'Transparency checked for %d materials. Open Report for details.' % len(materials), '\n'.join(lines))
        self.report({'INFO'}, context.scene.my_prefs.texture_summary)
        return {'FINISHED'}


class APEX_OT_item_rotation(bpy.types.Operator):
    """Adjust the paired item's local rotation without moving its attachment"""
    bl_idname = 'object.apex_item_rotation'
    bl_label = 'Rotate Item X + Z 90°'
    bl_options = {'REGISTER', 'UNDO'}
    reset: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        item = context.scene.apex_attachment_item
        return bool(item and item.is_editable and item.parent_type == 'BONE' and item.parent)

    def execute(self, context):
        from mathutils import Matrix, Quaternion
        from math import pi
        item = context.scene.apex_attachment_item
        location, rotation, scale = item.matrix_basis.decompose()
        if self.reset:
            stored = item.get('_apex_pair_rotation')
            if stored is None:
                self.report({'WARNING'}, 'Pair the item again before resetting its rotation.')
                return {'CANCELLED'}
            rotation = Quaternion(stored)
        else:
            rotation = rotation @ Quaternion((1, 0, 0), pi / 2) @ Quaternion((0, 0, 1), pi / 2)
        item.matrix_basis = Matrix.LocRotScale(location, rotation, scale)
        return {'FINISHED'}


class APEX_PT_attachments(ApexPanel, bpy.types.Panel):
    """Pair imported item rigs to the legend's hand or weapon bones"""
    bl_label = 'Pair Items'
    bl_idname = 'APEX_PT_attachments'
    bl_parent_id = 'APEX_PT_rigging'
    bl_order = 2
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        draw_wrapped(layout, 'Select both rigs, then use Use Selected Rigs. Make the legend active if both have hand sockets.', context)
        layout.prop(scene, 'apex_attachment_legend', text='Legend Rig')
        layout.prop(scene, 'apex_attachment_item', text='Item Rig')
        layout.operator('object.apex_use_selected_attachment_rigs',
                        text='Use Selected Rigs', icon='RESTRICT_SELECT_OFF')
        column = layout.column(align=True)
        column.enabled = bool(scene.apex_attachment_legend and scene.apex_attachment_item)
        row = column.row(align=True)
        row.operator('object.apex_pair_item', text='Left Hand').socket = 'LEFT_HAND'
        row.operator('object.apex_pair_item', text='Right Hand').socket = 'RIGHT_HAND'
        column.operator('object.apex_pair_item', text='Weapon').socket = 'WEAPON'
        item = scene.apex_attachment_item
        if item and item.parent_type == 'BONE' and item.parent:
            layout.separator()
            draw_wrapped(layout, 'Paired to: ' + item.parent_bone, context)
            layout.operator('object.apex_item_rotation', icon='DRIVER_ROTATIONAL_DIFFERENCE')
            layout.operator('object.apex_item_rotation', text='Reset Pair Rotation', icon='LOOP_BACK').reset = True
        if scene.apex_attachment_legend:
            column.prop_search(scene, 'apex_attachment_bone',
                               scene.apex_attachment_legend.data, 'bones', text='Other Bone')
            column.operator('object.apex_pair_item', text='Pair to Other Bone').socket = 'CUSTOM'


class APEX_PT_effects(ApexPanel, bpy.types.Panel):
    """Shadow squad, legend effects and scene helpers"""

    bl_label = "Effects"
    bl_idname = "APEX_PT_effects"
    bl_order = 6
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        pass


class APEX_PT_shadow(ApexPanel, bpy.types.Panel):
    """Turn a legend into a Shadow Squad shadow"""

    bl_label = "Shadow Squad"
    bl_idname = "APEX_PT_shadow"
    bl_parent_id = "APEX_PT_effects"
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

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

    bl_label = "Legend & Weapon Effects"
    bl_idname = "APEX_PT_apex_effects"
    bl_parent_id = "APEX_PT_effects"
    bl_order = 0
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

    bl_label = "Scene Tools"
    bl_idname = "APEX_PT_scene_utils"
    bl_parent_id = "APEX_PT_environment"
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
    bl_label = 'Troubleshooting'
    bl_idname = 'APEX_PT_health'
    bl_order = 7
    bl_options = {'DEFAULT_CLOSED'}

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
                    box.operator('object.apex_select_issues', text='Select Matching Issues',
                                 icon='RESTRICT_SELECT_OFF').code = issue.code
                layout.operator('object.apex_select_issues', text='Select All Affected Meshes',
                                icon='RESTRICT_SELECT_OFF').code = ''
            draw_report_actions(layout, 'health')
        else:
            draw_wrapped(layout, 'Check missing textures, materials, UV maps and rig targets.', context)
        layout.separator()
        layout.operator('object.apex_relink_rsx', icon='FILE_REFRESH')
        if prefs.relink_summary:
            draw_wrapped(layout, prefs.relink_summary, context)


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
        if prefs.repair_report:
            draw_wrapped(layout, prefs.repair_summary, context)
            draw_report_actions(layout, 'repair')


######### About / Help ###########
class APEX_PT_about(ApexPanel, bpy.types.Panel):
    """Documentation, links and the asset pack"""

    bl_label = "About & Help"
    bl_idname = "APEX_PT_about"
    bl_order = 8
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
            draw_wrapped(box, 'Optional HDRIs, loot, badges and props.', context)
            box.operator('object.lgndtranslate_url', text="Download Assets Pack",
                         icon='IMPORT').link = "asset_file"
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
        APEX_PG_animation_clip,
        APEX_PG_animation_library,
        PROPERTIES_CUSTOM,
        LGNDTRANSLATE_URL,
        BUTTON_CUSTOM,
        APEX_PG_import_folder,
        APEX_UL_import_folders,
        APEX_UL_animation_rigs,
        APEX_OT_import_texture,
        APEX_OT_review_model_import,
        APEX_OT_relink_rsx,
        APEX_OT_apply_rsx_relink,
        APEX_OT_auto_link_animation_rig,
        APEX_OT_link_animation_rig,
        APEX_OT_import_animation_cast,
        APEX_OT_import_animation_names,
        APEX_OT_builtin_animation_names,
        APEX_OT_refresh_animations,
        APEX_OT_cancel_animation_scan,
        APEX_OT_finish_animation_scan,
        APEX_OT_load_animation,
        APEX_OT_add_animation_layer,
        APEX_OT_remove_animation_layers,
        APEX_OT_adjust_animation_layer,
        APEX_OT_remove_animation,
        APEX_OT_use_selected_attachment_rigs,
        APEX_OT_pair_item,
        APEX_OT_item_rotation,
        APEX_OT_check_transparency,
        APEX_OT_favourite_animation,
        APEX_OT_clear_recent_animations,
        APEX_UL_animations,
        APEX_OT_report,
        APEX_OT_xyz_euler,
        APEX_OT_check_scene,
        APEX_OT_select_issues,
        APEX_OT_repair_textures,
        APEX_UL_health_issues,
        APEX_OT_forget_texture_roots,
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
        APEX_PT_model_adjustments,
        APEX_PT_materials,
        APEX_PT_autotex,
        APEX_PT_autotex_search,
        APEX_PT_recolour,
        APEX_PT_shader_library,
        APEX_PT_animations,
        APEX_PT_rigging,
        APEX_PT_attachments,
        APEX_PT_environment,
        APEX_PT_scene_utils,
        APEX_PT_effects,
        APEX_PT_apex_effects,
        APEX_PT_shadow,
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
    bpy.types.Object.apex_animation_library = bpy.props.PointerProperty(type=APEX_PG_animation_library)
    bpy.types.Scene.apex_attachment_legend = bpy.props.PointerProperty(
        name='Legend Rig', type=bpy.types.Object, poll=attachment_armature_poll)
    bpy.types.Scene.apex_attachment_item = bpy.props.PointerProperty(
        name='Item Rig', type=bpy.types.Object, poll=attachment_armature_poll)
    bpy.types.Scene.apex_attachment_bone = bpy.props.StringProperty(name='Other Bone')
    for handlers in (bpy.app.handlers.save_pre, bpy.app.handlers.load_pre,
                     bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        handlers.append(cancel_animation_scan)
    for name in _SCENE_TOGGLES:
        setattr(Scene, name, BoolProperty(default=False))


def unregister():
    cancel_animation_scan()
    for handlers in (bpy.app.handlers.save_pre, bpy.app.handlers.load_pre,
                     bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        if cancel_animation_scan in handlers:
            handlers.remove(cancel_animation_scan)
    del bpy.types.Object.apex_animation_library
    del bpy.types.Scene.apex_attachment_legend
    del bpy.types.Scene.apex_attachment_item
    del bpy.types.Scene.apex_attachment_bone
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.my_prefs
    for name in _SCENE_TOGGLES:
        if hasattr(Scene, name):
            delattr(Scene, name)


if __name__ == "__main__":
    register()
