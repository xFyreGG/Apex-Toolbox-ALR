# Apex Toolbox

A Blender add-on for Apex Legends models exported through RSX and CAST.

**Public stable: 3.10.0.** [Download the ZIP](https://github.com/xFyreGG/Apex-Toolbox-ALR/releases/tag/v3.10.0) or choose an older public version on [Creator Tools](https://apexlegendsrenders.com/creator-tools). Tested in Blender 4.2.2 and 5.2.2.

## What's included

- Import one or several model folders, filter by legend or weapon, and arrange models in a row or grid.
- Link matching animation rigs automatically, browse named clips, double-click to load, or import an individual animation CAST.
- Add optional animation layers, pair items to hands or weapons, and correct their rotation.
- Texture models, repair moved export paths and inspect scene problems.
- Use Model, Animate, Scene and Tools tabs, tidy shader graphs and optional manual hair fixes.
- Material fixes cover eyelash transparency, clear corneas and verified opaque-surface alpha issues.

## Install or update

1. Download `Apex-Toolbox-ALR-3.10.0.zip` and keep it intact.
2. In Blender, open **Edit → Preferences → Add-ons → Install from Disk**, select the ZIP and enable **Apex Toolbox**. Restart Blender after replacing an older installation.
3. Install the [CAST importer](https://github.com/dtzxporter/cast), export your models and material textures with RSX, then use **Apex Tools → Model → Import & Texture**.

Existing models can be retextured to apply the material fixes. Save a copy first if you have edited their shader nodes. The ZIP contains no game models, textures or animations; export your own files.

See the [workflow guide](Apex_toolbox/WORKFLOW_GUIDE.md), [RSX compatibility notes](Apex_toolbox/RSX_COMPATIBILITY.md) and [release notes](RELEASE_NOTES.md).

## Early access

The previous experimental features are now included in public 3.10.0. There is no newer experimental download currently available. Future early-access builds will use labels such as **3.11.0-beta.1** and remain available to all ALR supporter tiers through Creator Tools.

Older experimental versions used development numbers such as 3.11.0 and 3.14.7. They predate this stable release despite the higher numbers. Install 3.10.0 manually when moving from those builds. Historical versions and reports retain their original identifiers. See [version numbering](VERSIONING.md).

## Credits and licence

The original Apex Toolbox was created by **Random Blender Dude / Gl2imm**. This is a maintained, modified release by Apex Legends Renders (ALR), distributed under **GPL-3.0-or-later**. See the [licence](LICENSE), [original project](https://github.com/Gl2imm/Apex-Toolbox), and [full credits](Apex_toolbox/Credits%20and%20Instructions.txt).

The ZIP contains the plugin only. Optional Extended Assets from the original project are separate and are not bundled here.
