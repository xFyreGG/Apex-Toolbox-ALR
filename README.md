# Apex Toolbox 3.9.0 — ALR maintained release

Apex Toolbox is a Blender add-on that collects tools for working with Apex Legends models, materials, shaders, rigs, effects, and render staging.

The original Apex Toolbox was created by **Random Blender Dude / Gl2imm**. This repository contains a **maintained and modified release by Apex Legends Renders (ALR)**; ALR did not create the original project.

- Maintained version: **3.9.0**
- Blender: **4.0 or newer**
- Verified with: **Blender 4.2**
- Licence: **GNU GPL-3.0 or later**
- Maintained source: https://github.com/xFyreGG/Apex-Toolbox-ALR
- Original upstream project: https://github.com/Gl2imm/Apex-Toolbox

## What is included

Apex Toolbox 3.9.0 includes modern RSX / CAST workflows, automatic texturing and texture-folder discovery, Legion+ compatibility, Apex shaders, recolour and toon tools, rigging helpers, effects, lighting and staging utilities. It adds texturing reports, scene health checks and missing-texture repair.

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
3. Import the `.cast` file into Blender and select its armature.
4. In **Apex Tools → Model**, click **Set Correct Model Size**.
5. Select the model meshes, open **Materials → Auto Texture**, choose a supported Apex shader, and click **Texture Model**.

Texture discovery is normally automatic. If it cannot locate the export, set **Texture Folder** under **Search Options** and run Texture Model again. See [Apex_toolbox/RSX_COMPATIBILITY.md](Apex_toolbox/RSX_COMPATIBILITY.md) for the complete compatibility notes.

## Lite and Extended Assets

This repository and the 3.9.0 plugin ZIP are the **plugin-only Lite release**. The original project keeps its larger optional Extended Assets as a separate download. Those assets can unlock additional HDRI themes, badges, loot items, heirlooms, and other content, but they are **not included or repackaged here**.

## Licence and attribution

This modified maintained release remains distributed under the **GNU General Public License v3.0 or later**. The complete licence is included at [LICENSE](LICENSE) and inside the installable add-on at [Apex_toolbox/LICENSE](Apex_toolbox/LICENSE).

Original authorship, upstream links, and contributor credits—including llenoco and the community contributors credited by the original project—are preserved in [Apex_toolbox/Credits and Instructions.txt](Apex_toolbox/Credits%20and%20Instructions.txt).
