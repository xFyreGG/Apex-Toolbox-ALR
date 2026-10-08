## Apex Toolbox 3.9.0

Upgrade date: **2026-09-08**

- Added persistent, copyable per-scene reports after texturing.
- Removed the obsolete Discord, Garlicus skins, Biast12 assets and donation buttons.
- Added Scene Health checks with explanations and selection by issue type.
- Added missing-texture repair with exact-name matching, ambiguity handling,
  candidate validation and preserved shader links and relative paths.
- Added armature/empty model scope for Auto Texture and Scene Health.
- Made model preparation repeatable without rescaling prepared rigs or changing selection.
- Fixed stale/unrelated loaded images overriding the current export.
- Preserved partially resolved materials when a referenced texture is unavailable.
- Strengthened shader rollback, active output restoration and repeated node naming.
- Fixed the PNG-only Recolour gate, folder normalisation and shared-material repeats.
- Bounded recursive searches by files, entries, directories and depth; surfaced incomplete scans.
- Fixed Lite staging's unnecessary Extended pack requirement; recognise Extended
  packs by `Assets.blend` instead of their folder name.
- Removed the third-party HTTP dependency and fixed numeric release comparisons.
- Added Blender integration tests, a three-shader render fixture, workflow guidance
  and a reproducible installable ZIP builder.

Original authorship, GPL licensing, all bundled assets and the existing tools remain intact.
See [TESTING.md](TESTING.md) for verification commands and coverage boundaries.

---

---

# Apex Toolbox 3.8.0

Release date: **2026-08-28**

This is a modified and maintained release by **Apex Legends Renders (ALR)**, based on the original Apex Toolbox by **Random Blender Dude / Gl2imm**. It remains distributed under GPL-3.0 or later.

Completed release work:

- Modern RSX / CAST support with maintained Legion+ compatibility.
- Auto Texture resolver improvements.
- Automatic texture-folder discovery.
- Blender 4.x repairs.
- Cleaned and reorganised UI.
- Repairs to older Toolbox utilities.
- Release maintenance by ALR.

The optional upstream Extended Assets remain separate and are not included in this repository or the plugin ZIP.

- Maintained source: https://github.com/xFyreGG/Apex-Toolbox-ALR
- Original project: https://github.com/Gl2imm/Apex-Toolbox
