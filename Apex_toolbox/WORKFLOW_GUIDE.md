# Apex Toolbox 3.9.1 — daily workflows

All tools live in **3D View → Sidebar → Apex Tools**. The existing shaders,
effects, rig helpers, Recolour, Toon and Legion+/RSX workflows remain available.

## Prepare and texture a model

1. Import your CAST or SEModel using its usual importer.
2. Select its armature in Object Mode and use **Model → Set Correct Model Size**.
   The tool converts inches to metres and rotates the imported rig once. Repeating
   it leaves prepared rigs alone. It preserves the model's position and selection;
   Undo also restores the preparation marker. Rigs already scaled to 0.0254 are
   recognised, including those prepared with earlier Toolbox versions.
   Preparation also switches eligible model objects and bones from Quaternion
   to XYZ Euler, including when the rig was already sized correctly.
3. In **Materials → Auto Texture**, choose a shader. **Include Model Meshes**
   includes meshes below selected armatures/empties and meshes bound to their rigs,
   within the current view layer. Turn it off to process only selected meshes.
4. Click **Texture Model**. Textures are found and connected automatically, and
   a report records the result of each conversion.
   Materials with missing referenced textures are kept intact until repaired.
5. If textures weren't found, set **Search Options → Texture Folder**, enable
   subfolders if needed and run **Texture Model** again. The report lists searched
   folders, filenames, resolution sources and any search limits. Unresolved
   optional maps are normal.

**Shared materials:** conversion updates the material wherever it is used. If two
models need different looks, make their materials single-user in Blender first.
Linked materials must be made local before conversion. The new scope controls
apply to Auto Texture and Scene Health; Recolour and Toon still use selected meshes.

## Switch imported quaternion rotations to XYZ Euler

CAST sets imported model transforms to Quaternion (WXYZ). To change an existing
model without resizing it, use **Model → Quaternion to XYZ Euler**:

- In **Object Mode**, select the model's armature, mesh or parent empty. The
  tool includes its related rig, model descendants and pose bones in the current
  view layer.
- In **Pose Mode**, select the bones to change. Only those bones are converted.

The conversion preserves position, orientation, scale and the current pose,
including object delta rotations. It supports Undo. Existing Euler and
Axis Angle settings are left alone. Targets with Actions, NLA animation,
drivers, constraints or read-only data are skipped and reported; switching
their rotation mode alone could break their existing behaviour.

This is a Toolbox preparation step, not a change to the CAST importer. CAST
animation imports may set bones back to Quaternion to use their animation
channels. Converting an existing animation requires baking its rotation curves,
which this button does not do.

## Read and keep reports

The latest texture, scene health and repair reports are stored separately in the
scene and saved with the `.blend` file. **Copy** copies a full report without
leaving the viewport. **Open Report** opens Blender's Text Editor, starting at
the first line with word wrapping enabled. Return to the 3D View with **Shift+F5**
while the mouse is over that editor. The Text Editor's **Text → Save As** exports
the report to a text file. Reports are snapshots: run the relevant tool again
after changing the selection, scene or folders.

## Troubleshoot a model

Scene Health is optional troubleshooting for problems such as pink textures or
materials that fail to display. It isn't a required step in automatic texturing.
Use **Scene Health → Check Scene Health**. Choose **Selected Models** or **View
Layer**. The latter includes all meshes in that view layer, even hidden meshes,
and also checks the scene camera and environment images.

Checks cover missing external images (including nested shader groups), empty
image bindings, missing UVs, empty material slots, empty meshes, disconnected
surface outputs, zero scale and missing armature targets. Linked materials are
listed as information. A material without nodes is valid and isn't flagged just
for using Blender's basic shading.

Choose an issue to read its explanation. **Select This Issue Type** and **Select
All Affected Meshes** select the visible, selectable affected meshes. They don't
unhide objects, unlock selection or alter the scene. Hidden or removed objects
may still appear in an older report; run Check again to refresh it.

## Repair a moved texture library

1. Choose the desired Scene Health scope.
2. Expand **Repair Missing Textures**, choose the new texture folder and set
   whether to search subfolders.
3. Click **Repair Missing Textures**.

This relocates missing texture files; it does not rebuild or fix shader nodes.
Repair uses the original filename, including its extension. It reconnects only
unique exact matches, verifies that Blender can read the replacement and keeps
the shader links, image identity and existing relative/absolute path style.
Shared images are repaired for **all** their users. Existing files, generated
images and packed images are left alone. Duplicate filenames are listed in the
report; choose a narrower folder to disambiguate. Incomplete or unreadable
searches don't change any paths because they cannot establish uniqueness.

Image sequences, tiled images and linked images require manual repair. An empty
image node has no original filename to relocate; use Auto Texture or re-export
from RSX with **Export Material Textures** enabled instead. A scene may display
cached pixels from a missing file, but Scene Health still flags that reference
because those pixels may disappear on reopening the file.

## Recolour and optional assets

Recolour accepts classic Legion+ names, RSX `_col` / `_nml` / `_gls` names and
supported non-PNG formats. Select the meshes and choose the skin folder. Existing
model/part folders, `_images`, `base` fallbacks and the Titanfall skin fallbacks
remain supported. Each shared material is processed once.

The plugin remains the **Lite** edition. Animated Staging + Camera, Basic Lights
and the bundled effects work without the optional Extended pack. To enable
Extended content, choose the folder **containing `Assets.blend`** in add-on
preferences. Renaming that folder is no longer necessary.
