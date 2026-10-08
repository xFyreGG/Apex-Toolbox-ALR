# Apex Toolbox

Apex Toolbox is a Blender add-on for working with Apex Legends models exported through RSX and CAST. It helps with model scale, texturing, materials, rigging and scene setup.

**Public release: 3.8.0.** [Download the installable ZIP](https://github.com/xFyreGG/Apex-Toolbox-ALR/releases/tag/v3.8.0). This version supports Blender 4.0 or newer and was checked with Blender 4.2. It includes automatic RSX/CAST texturing, Apex shaders, recolour and toon tools, rig helpers, lighting and effects.

**Experimental build: 3.10.7.** [See the experimental build and access details](https://apexlegendsrenders.com/creator-tools) under Apex Toolbox. It adds one-click Import & Texture, animation browsing with built-in English in-game names, and item-to-bone pairing. These features are **not in the public 3.8.0 ZIP**. The default branch contains work on this newer build; use the tagged 3.8.0 release if you need the public version's source.

## Install the public release

1. Download `Apex_toolbox_v3.8.0.zip` from the [3.8.0 release](https://github.com/xFyreGG/Apex-Toolbox-ALR/releases/tag/v3.8.0). Keep the ZIP intact.
2. In Blender, open **Edit → Preferences → Add-ons → Install from Disk**, select the ZIP, and enable **Apex Toolbox**.
3. Open the 3D View sidebar and select **Apex Tools**.

For RSX exports, install the [CAST Blender importer](https://github.com/dtzxporter/cast). Export the model as CAST with material textures, then import it into Blender. In Apex Tools, use **Model → Set Correct Model Size** and **Materials → Auto Texture → Texture Model**. Texture discovery usually finds the RSX export automatically; if it does not, set **Texture Folder** under Search Options.

See the [RSX compatibility notes](Apex_toolbox/RSX_COMPATIBILITY.md) for export settings. The [workflow guide](Apex_toolbox/WORKFLOW_GUIDE.md) and [release notes](RELEASE_NOTES.md) cover the experimental features; those instructions apply to 3.10.7 unless stated otherwise.

## Credits and licence

The original Apex Toolbox was created by **Random Blender Dude / Gl2imm**. This is a maintained, modified release by Apex Legends Renders (ALR), distributed under **GPL-3.0-or-later**. See the [licence](LICENSE), [original project](https://github.com/Gl2imm/Apex-Toolbox), and [full credits](Apex_toolbox/Credits%20and%20Instructions.txt).

The ZIP contains the plugin only. Optional Extended Assets from the original project are separate and are not bundled here.
