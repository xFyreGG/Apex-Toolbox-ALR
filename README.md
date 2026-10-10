# Apex Toolbox

Apex Toolbox is a Blender add-on for working with Apex Legends models exported through RSX and CAST. It helps with model scale, texturing, materials, rigging and scene setup.

**Public release: 3.9.1.** [Download the installable ZIP](https://github.com/xFyreGG/Apex-Toolbox-ALR/releases/tag/v3.9.1). This version supports Blender 4.0 or newer and was checked with Blender 4.2. It includes automatic RSX/CAST texturing, Apex shaders, recolour and toon tools, rig helpers, lighting and effects. Version 3.9.1 adds scene health checks, missing-texture repair, texturing reports and XYZ Euler rotation conversion.

**Early access: 3.11.0.** The tested build is available to all ALR supporter tiers through [Creator Tools](https://apexlegendsrenders.com/creator-tools). It adds Import & Texture for one or several RSX model folders, with models placed side by side. You can browse model exports by legend, weapon or group, find animation rigs by legend, search named animation clips, import a single animation CAST, and pair items to a character rig. We checked the build in Blender 4.2.2 and 5.2.2. These tools are **not in the public 3.9.1 ZIP**. Public 3.11.0 is being held to give early access time before the stable release.

To try 3.11.0, link an active Patreon membership to your ALR account, then choose **Experimental** on Creator Tools. Install the ZIP through Blender's **Install from Disk**; it replaces an older Apex Toolbox installation. The add-on contains no Apex models, textures or animations. Export your own files with RSX. The add-on source is included in the ZIP; the [3.9.1 tag](https://github.com/xFyreGG/Apex-Toolbox-ALR/tree/v3.9.1) remains the source for the public release.

## Install the public release

1. Download `Apex-Toolbox-ALR-3.9.1.zip` from the [3.9.1 release](https://github.com/xFyreGG/Apex-Toolbox-ALR/releases/tag/v3.9.1). Keep the ZIP intact.
2. In Blender, open **Edit → Preferences → Add-ons → Install from Disk**, select the ZIP, and enable **Apex Toolbox**.
3. Open the 3D View sidebar and select **Apex Tools**.

For RSX exports, install the [CAST Blender importer](https://github.com/dtzxporter/cast). Export the model as CAST with material textures, then import it into Blender. In Apex Tools, use **Model → Set Correct Model Size** and **Materials → Auto Texture → Texture Model**. Texture discovery usually finds the RSX export automatically; if it does not, set **Texture Folder** under Search Options.

See the [RSX compatibility notes](Apex_toolbox/RSX_COMPATIBILITY.md) for export settings. The [workflow guide](Apex_toolbox/WORKFLOW_GUIDE.md) and [release notes](RELEASE_NOTES.md) cover the code in this branch. Current early-access setup steps and version details are on [Creator Tools](https://apexlegendsrenders.com/creator-tools).

## Credits and licence

The original Apex Toolbox was created by **Random Blender Dude / Gl2imm**. This is a maintained, modified release by Apex Legends Renders (ALR), distributed under **GPL-3.0-or-later**. See the [licence](LICENSE), [original project](https://github.com/Gl2imm/Apex-Toolbox), and [full credits](Apex_toolbox/Credits%20and%20Instructions.txt).

The ZIP contains the plugin only. Optional Extended Assets from the original project are separate and are not bundled here.
