# Apex Toolbox 3.10.8 — daily workflows

**Experimental release:** animation tools and automatic names are still being
validated across exports. Successful sample playback does not guarantee every
clip, skin or rig variant. Unknown/conflicting names retain their export labels.

All tools live in **3D View → Sidebar → Apex Tools**. The existing shaders,
effects, rig helpers, Recolour and Legion+/RSX workflows remain available.

## Sidebar layout

The sections follow the model workflow: **Model → Materials → Rigging & Animation
→ Lighting & Scene → Effects**. **Troubleshooting** and **About & Help** are
collapsed until needed. Add shader groups under **Materials → Shader Library**;
find staging, lights and wireframe tools under **Lighting & Scene → Scene Tools**.
Bone display and IK helpers are under **Rigging & Animation → Rig Tools**.
Imported prop rigs can be attached under **Rigging & Animation → Pair Items**.

## Import & Texture

Enable the [CAST Blender importer](https://github.com/dtzxporter/cast) first.
Export the model from RSX as CAST with material textures enabled. Click
**Model → Import & Texture**, choose one or several model CAST files from the
same folder, and select a shader.
**Prepare Model** applies the standard Apex size/orientation and converts
eligible unanimated transforms to XYZ Euler. Turn it off to keep export transforms.
The optional **Texture Folder** overrides the default search beside the CAST file.
The separate size and rotation tools are in **Model → Manual Adjustments**,
collapsed below Import & Texture for models that need manual preparation.

Each file is imported, prepared and textured separately. With multiple files,
models are placed side by side along the X axis in filename order. The first
model stays where CAST imported it; later models are spaced by their mesh bounds,
centred along Y and aligned at the bottom. Existing scene objects are not moved.
Files that fail to import are skipped without discarding successful models. The
combined texture report names each file and any import or texture problems.
Missing textures leave that model available. One Undo step removes the batch.
Select model CAST exports only; rig and animation CAST exports are reported as
failed imports. Other formats keep their usual import workflow.

## Link a legend's animation rig

1. In RSX, choose **CAST** for animation rig and animation sequence exports,
   enable **Export Rig Sequences**, and export the legend's rig.
2. Keep `<rig name>.cast` beside its `anims_<rig name>` folder. The rig CAST
   contains the skeleton; the companion folder contains the animation clips.
3. Select the legend's armature or one of its bound meshes in Blender.
4. Open **Rigging & Animation → Animations → Link Animation Rig** and select the rig CAST.
5. Wait for indexing to finish, choose an optional **Category**, search the list,
   select a clip, then click **Load Animation**.

The link belongs to that model and is saved in the `.blend`. The list includes
individual clips within multi-animation CAST files. **Refresh Animations** reads
new or replaced exports. Relink if the export folder moves. CAST must be installed
and enabled to load a clip; linking and browsing do not require it.

Indexing shows progress and works in short batches so Blender can keep responding.
It searches the complete companion folder, including nested folders, without a
ten-second deadline or a file-count/depth cutoff. **Cancel Indexing**
keeps the previous list and cached actions. Invalid/unreadable files and linked
folders are reported as warnings. Refresh an older incomplete list to rescan it.

**Category** filters use words in the exported animation names: Gladcard / Banner,
Emote, Lobby, Finishers (including execution/execute), and Movement. Text search
narrows the chosen category further; the count shows how many clips match. A clip
can match more than one category. **All Animations** includes names that do not
follow those conventions. Refresh keeps the category, search and selected clip
where possible.

Click the **star** beside a clip to add it to this model's **Favourites**. **Recent**
shows the last 20 successfully loaded clips, newest first; loading a cached clip
moves it to the top. Category and search also work in these views. **Clear Recent
List** clears only that model's history. Stars and clearing history support Undo;
actions and favourites are kept when history is cleared. Favourites and recents
are saved in the blend file. Refresh keeps them for uniquely named clips in the
same file and linked rig export, even when CAST offsets change. Relinking a
different rig export starts fresh; duplicate clip names are not guessed.

### Included in-game animation names

English menu names are included. **Link Animation Rig** and **Refresh Animations**
apply them automatically; no settings or language export is needed. For an older
saved library, click Refresh once after updating. The lookup runs locally and
does not need a game installation or internet connection.

**Show In-Game Names**, under the collapsed **Options & Details** section, changes the
list labels. Search always accepts both the menu and original export name. The
selected clip's original name is displayed there too. Still/Animated banner
poses, Loop clips and finisher Preview clips are labelled separately.

The included catalogue is a snapshot of known animation identifiers. It covers
ground emotes, skydive emotes, banner poses and attacker finishers across legends.
It contains short menu labels, identifiers and variant roles. It does not contain
raw settings, language packs, rigs or animation files.

Unknown clips, ordinary lobby/movement animations, lighting/effect tracks, victim
tracks and conflicting item references keep their export names. New game content
may require a later Toolbox catalogue update. Renamed CAST files still match when
their sequence identifiers are intact; non-RSX files without those identifiers
may remain unnamed. Favourites, recents and loaded actions are independent of names.

### Optional language or newer-name imports

To use another language or newer item data, expand **Options & Details** and use
**Import Names / Language**. These advanced steps are optional:

1. In RSX, load the game's `common.rpak` and the language pack, for example
   `localization_english.rpak`. Keep their patch files beside them. Allow settings,
   settings layouts and localization assets to load.
2. Export the **Settings (stgs)** assets under `settings/itemflav/character_emote`,
   `character_execution`, `gcard_stance` and `skydive_emote` for the desired legend(s).
   These export as JSON. Export the **Localization (locl)** language asset too.
   Loading settings layouts is necessary for RSX to decode settings.
3. Keep RSX's `settings/itemflav` and `localization` folders together in the same
   export directory. These are separate from the `animrig` folder.
4. In Blender, select the model, expand **Animations → Options & Details**, choose
   **Import Names / Language**, and select the exported `.locl` file.
5. If the folders are separated, set **Settings Folder** in the file picker to
   the export root, its `settings` folder, or its `itemflav` folder.

The import shows progress and can be cancelled. It applies names only after the
complete metadata scan succeeds, and supports Undo. Failed, cancelled and
zero-match imports retain the previous names. The resulting names are saved in
the blend file; the source files are only needed when importing names again.
Export settings and text from the same game version where possible.

Refresh retains imported names for unchanged clip identifiers and applies the
included English names to new clips. Reimport to translate those new clips too.
**Reset to Included Names** replaces this model's imported overrides with
the bundled catalogue and supports Undo. It does not change actions or favourites.

The export structures are documented in [RSX localization](https://github.com/r-ex/rsx/blob/main/docs/assets/rpak/Localization.md)
and implemented in [RSX's CAST exporter](https://github.com/r-ex/rsx/blob/main/src/core/mdl/modeldata.cpp).

### Playback and removal

Loading creates a Blender Action and retains the previous Action. Switching back
to an unchanged loaded clip reuses its Action. Previous actions remain available
in Blender's Action Editor, including after saving. Under **Options & Details**,
**Match Timeline and FPS** sets the scene range/rate to the selected clip;
turn it off to keep scene timing.
Each successful load resets the armature's local object rotation to zero,
including when reusing a loaded Action. Its position, scale, rotation mode and
selection are preserved. Parent transforms and delta transforms are unchanged.
Undo restores the previous action and object rotation. Failed loads leave the
original rotation intact.

**Remove Animation / T-Pose** detaches the active Action and resets every pose
bone to its rest transform. The clip stays in the list and its Action is kept for
reuse. For clips loaded with 3.10.3 or newer, it also restores the armature's
orientation from before the first load; switching clips keeps that original
orientation. Position, scale, timeline and selection are preserved. Undo restores
the action and pose. Older already-loaded actions have no saved pre-load
orientation, so removal keeps their current object rotation. The rest pose comes
from the model: an export with an A-pose returns to that pose rather than an
invented T-pose.

Animations use quaternion channels for playback. The unanimated XYZ Euler tool
does not convert animation curves. Additive clips are labelled and need a base
animation blended in Blender's NLA Editor. Animated bones must match by name;
**Allow Missing Bones** explicitly permits partial clips and reports skipped bones.
Matching names alone do not guarantee that two different legends have compatible
rest poses. Link the rig exported for your legend.

This first selector supports bone animation on imported rigs. It declines rigs
with constraints, drivers or NLA tracks, and clips with blend-shape tracks; use
the normal CAST importer for those advanced cases. A failed clip import preserves
the current pose and action. Malformed files and unusually large clips are rejected.
Individual malformed/oversized CAST files are still checked before import.

The rig/sequence distinction is described in [RSX's Animation Rig documentation](https://github.com/r-ex/rsx/blob/main/docs/assets/rpak/AnimationRig.md).
Raw game ARIG files are not imported directly.

## Pair an item with a legend

Import the legend and the item as separate armatures with their meshes. Under
**Rigging & Animation → Pair Items**, choose **Legend Rig** and **Item Rig**.
If both armatures are selected, **Use Selected Rigs** fills the fields; make the
legend active when both rigs have attachment bones. Click **Left Hand**,
**Right Hand** or **Weapon** to snap the item's rig origin to the matching
attachment bone on the legend. The item follows that bone when you pose or
animate the legend, while the item's own child meshes and bone animation remain
together. Adjust the item's local position and rotation afterwards if its grip
needs an offset.

For other attachment points, choose a bone in **Other Bone** and click
**Pair to Other Bone**. If the legend lacks a matching preset bone, the tool
asks you to choose one instead of guessing a nearby wrist or hand bone.
Pairing changes the item's parent and transform; Blender Undo restores them.

## Prepare and texture a model

1. Import your CAST or SEModel using its usual importer.
2. Select its armature in Object Mode and use **Model → Manual Adjustments → Set Correct Model Size**.
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
5. If textures weren't found, set **Auto Texture → Texture Folder**, enable
   subfolders if needed and run **Texture Model** again. The report lists searched
   folders, filenames, resolution sources and any search limits. Unresolved
   optional maps are normal.

**Shared materials:** conversion updates the material wherever it is used. If two
models need different looks, make their materials single-user in Blender first.
Linked materials must be made local before conversion. The new scope controls
apply to Auto Texture and Scene Health; Recolour still uses selected meshes.

## Switch imported quaternion rotations to XYZ Euler

CAST sets imported model transforms to Quaternion (WXYZ). To change an existing
model without resizing it, use **Model → Manual Adjustments → Use XYZ Euler Rotation**:

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
Use **Troubleshooting → Check Scene Health**. Choose **Selected Models** or **View
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

**Auto Shadow** is now inside **Effects → Apex Effects**. The Toon shader tool
and its settings have been removed. Existing materials saved in older scenes
are not modified by the update.

Recolour accepts classic Legion+ names, RSX `_col` / `_nml` / `_gls` names and
supported non-PNG formats. Select the meshes and choose the skin folder. Existing
model/part folders, `_images`, `base` fallbacks and the Titanfall skin fallbacks
remain supported. Each shared material is processed once.

The plugin remains the **Lite** edition. Animated Staging + Camera, Basic Lights
and the bundled effects work without the optional Extended pack. To enable
Extended content, choose the folder **containing `Assets.blend`** in add-on
preferences. Renaming that folder is no longer necessary.
