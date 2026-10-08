# Apex Toolbox 3.10.7 — Experimental

Apex Toolbox is a Blender add-on that collects tools for working with Apex Legends models, materials, shaders, rigs, effects, and render staging.

The original Apex Toolbox was created by **Random Blender Dude / Gl2imm**. This repository contains a **maintained and modified release by Apex Legends Renders (ALR)**; ALR did not create the original project.

- Maintained version: **3.10.7**
- Release status: **Experimental** — animation and name coverage varies by export; sample playback checks do not verify every clip.
- Blender: **4.0 or newer**
- Verified with: **Blender 4.2**
- Licence: **GNU GPL-3.0 or later**
- Maintained source: https://github.com/xFyreGG/Apex-Toolbox-ALR
- Original upstream project: https://github.com/Gl2imm/Apex-Toolbox

## What is included

Apex Toolbox includes modern RSX / CAST workflows, automatic RSX/CAST texturing, automatic texture-folder discovery, Legion+ compatibility, Apex material and shader tools, recolour, rigging helpers, effects, lighting, HDRI controls, and staging utilities.

New in **3.10.7**:

- **Pair Items** snaps an imported item rig to a legend's left hand, right hand or weapon attachment bone. A searchable bone picker covers other attachment points. The item's own rig and meshes remain intact.

Added in **3.10.6**:

- Animations now live in **Rigging & Animation**, with rig helpers in **Rig Tools**.
- A cleaner animation browser puts linking, filtering and loading first. Playback settings, name controls and export details are in **Options & Details**.
- Shaders live under **Materials → Shader Library**; HDRI, lights and staging are grouped under **Lighting & Scene**. Optional checks and repairs are under **Troubleshooting**.
- Shorter labels, fewer repeated messages and a single Experimental status in the header.

Added in **3.10.5**:

- **In-game names included**: linking or refreshing an animation rig automatically matches known English menu names. No name import, game installation or internet connection is needed.
- A compact catalogue covers emotes, skydive emotes, banner poses and finishers across legends. Unmatched or conflicting clips keep their export names. Other languages and newer metadata remain optional imports.

Added in **3.10.4**:

- **Favourites**: star clips for each model, then browse just those animations.
- **Recent**: the last 20 successfully loaded clips, newest first. Both lists survive saving and refreshing the same export.
- **In-Game Names**: optionally import RSX language text and animation item settings to display exact menu names. Search accepts both menu and export names; unmatched or conflicting clips keep their export names.

Added in **3.10.3**:

- **Remove Animation / T-Pose** detaches the current action and restores the model's rest pose. Clips stay available to reload; Undo restores the animation.
- Animation indexing runs in cancellable batches, with progress and no ten-second, file-count or folder-depth cutoff.
- Animation categories: **Gladcard / Banner, Emote, Lobby, Finishers and Movement**, combined with text search and a visible result count.

Added in **3.10.2**:

- Loading an animation also resets the armature's local object rotation to zero, keeping its position, scale and rotation mode. Undo restores the previous rotation and action.

Added in **3.10.1**:

- Moved the size and XYZ Euler tools into **Model → Manual Adjustments**, collapsed below Import & Texture.

Added in **3.10.0**:

- **Import & Texture** imports a CAST model, prepares its rig and textures only the newly imported meshes.
- **Animation Selector** links an RSX-exported rig to the selected model and provides a searchable list of its exported CAST sequences. Previous actions are retained and loaded clips can be reused.
- Removed the Toon shader tools and moved **Auto Shadow** into **Effects → Apex Effects**.

Added in **3.9.1**:

- **Quaternion to XYZ Euler** converts fresh model objects and bones while preserving their orientation; model preparation includes this step automatically. Existing animation, drivers and constraints are left alone.

Added in **3.9.0**:

- **Automatic texture reports** after conversion, with searched folders and per-material results.
- **Scene Health** checks missing images, UVs, material slots, rig targets and render setup, with buttons to select affected meshes.
- **Repair Missing Textures** reconnects moved files by unique exact filename while preserving shader links.
- **Model selection** includes meshes below a selected rig or empty; preparation safely skips already prepared rigs.
- Better RSX Recolour support, shader rollback, image reuse, search limits and Lite staging support.

Read the [workflow guide](Apex_toolbox/WORKFLOW_GUIDE.md) for these tools and their scope. [TESTING.md](TESTING.md) describes the architecture, checks and release build.

The full dated change summary is in [RELEASE_NOTES.md](RELEASE_NOTES.md) and the historical upstream log remains in [Apex_toolbox/Version_log.txt](Apex_toolbox/Version_log.txt).

## Install

1. Download the release ZIP without extracting it.
2. In Blender, open **Edit → Preferences → Add-ons**.
3. Choose **Install from Disk** and select the ZIP.
4. Enable **Apex Toolbox**.
5. Open the 3D View sidebar and select **Apex Tools**.

The installable archive must keep `Apex_toolbox/__init__.py` at its root.

## Modern RSX / CAST workflow

1. In RSX, export the model as CAST and enable **Export Material Textures**.
2. Use Text naming, PNG (Highest Mip), Normal Recalculation: None, full asset paths off, and CacheDB loading enabled.
3. Install and enable the [CAST Blender importer](https://github.com/dtzxporter/cast).
4. In **Apex Tools → Model**, click **Import & Texture**, choose the `.cast` model, and select a shader. Leave **Prepare Model** enabled for the standard Apex size and orientation.

Models imported separately can use **Model → Manual Adjustments → Set Correct Model Size** and **Materials → Auto Texture → Texture Model**.

For animations, export the legend's animation rig from RSX as CAST with **Export Rig Sequences** enabled and the animation sequence format set to CAST. Select the legend's rig or mesh in Blender, then use **Rigging & Animation → Animations → Link Animation Rig** and choose the exported rig CAST. Keep its companion `anims_<rig name>` folder beside it. Search the list and click **Load Animation**. See the workflow guide for compatibility and animation limits.

Texture discovery is normally automatic. If it cannot locate the export, set **Texture Folder** under **Auto Texture** and run Texture Model again. See [Apex_toolbox/RSX_COMPATIBILITY.md](Apex_toolbox/RSX_COMPATIBILITY.md) for the complete compatibility notes.

## Lite and Extended Assets

This repository and the 3.10.7 plugin ZIP are the **plugin-only Lite release**. The original project keeps its larger optional Extended Assets as a separate download. Those assets can unlock additional HDRI themes, badges, loot items, heirlooms, and other content, but they are **not included or repackaged here**.

## Licence and attribution

This modified maintained release remains distributed under the **GNU General Public License v3.0 or later**. The complete licence is included at [LICENSE](LICENSE) and inside the installable add-on at [Apex_toolbox/LICENSE](Apex_toolbox/LICENSE).

Original authorship, upstream links, and contributor credits—including llenoco and the community contributors credited by the original project—are preserved in [Apex_toolbox/Credits and Instructions.txt](Apex_toolbox/Credits%20and%20Instructions.txt).
