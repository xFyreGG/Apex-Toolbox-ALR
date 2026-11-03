# Apex Toolbox 3.14.3: Experimental candidate (local)

- Recognised eyecornea materials now use a clear reflective surface instead of treating their black placeholder albedo as an opaque tint. The eye underneath remains visible.
- Reconstruct the missing blue channel of Apex packed RG cornea normals. Use a neutral normal when the texture is absent.
- Keep albedo and normal bindings discoverable through repeated Auto Texture, Recolour and shader changes. Other eye/head materials retain their existing shaders.
- This is a thin-surface approximation, not a recreation of the game's eye shader. Existing models need Auto Texture rerun after installation.

# Apex Toolbox 3.14.2: Experimental candidate (local)

- Correct Wattson onesie suit and gear materials: their opacityMultiply maps no longer remove solid details such as straps, zipper, gloves and knee equipment.
- This is a targeted exception for the two inspected texture names, not a new global opacity heuristic. Other opacity maps and hair transparency retain their existing behavior.
- The maps remain in the material, and the texture report explains why they were disconnected. To force one back on, set the material custom property `apex_force_opacity_map` to True and retexture.
- Existing models need Auto Texture rerun after installation. Source textures are unchanged.

# Apex Toolbox 3.14.1: Experimental candidate (local)

- Auto Texture and Recolour now skip sparse, fragmented albedo alpha that causes tiny holes on opaque surfaces, including the reported Ash head texture. Explicit opacity maps and scatter alpha retain their existing wiring.
- Hair, lash, fur and lace materials are exempt. The texture report explains skipped alpha. For intentional speckled cutouts, add the material custom property `apex_force_albedo_alpha` set to True and retexture.
- This is a conservative heuristic, not game material metadata. Images outside 65,536 to 4,194,304 pixels are left unchanged.

# Apex Toolbox 3.14.0: Experimental candidate (local)

Update date: **2026-11-03**

- Model, Animate, Scene and Tools tabs group the sidebar by task. Assets Folder is back at the top.
- Import Models proceeds directly from selection, without the review screen.
- Texture Models can be switched off during import. Auto-Link Animation Rig can also be disabled for a model-only import.
- Use Transparency now controls both albedo alpha and explicit opacity maps. Check Transparency reports connected sources and their pixel ranges without changing materials. It cannot determine artistic intent from pixels alone.
- Hair materials with a cavity map receive two Multiply nodes: albedo in A and cavity in B, then specular in A and cavity in B, both at factor 1. Hair is identified by the material name containing `hair`.
- Pairing accepts selected meshes bound to rigs as well as armatures. Paired items have X + Z 90-degree correction and Reset Pair Rotation controls.
- Local candidate only; public and supporter releases have not been changed.

---

# Apex Toolbox 3.13.2: Experimental candidate (local)

Update date: **2026-10-11**

- Animations has its own main section. The browser and loading controls come
  first, with optional Animation Layers below them. The base animation stays
  visible while layers are active, and their removal remains available when
  the layer controls are folded away.
- Rigging keeps bone display, IK and item pairing together. Materials starts
  collapsed; import handles the usual texturing step. Relink RSX Library is
  under Troubleshooting, alongside texture repair.
- Import settings are grouped into Model Setup, Textures and Layout. Texture
  folders are labelled optional, and animation options are grouped into
  Playback, Names and Linked Export.
- Shadow Squad is directly under Effects. Labels, shader tooltips and additive
  instructions have been tidied up; internal layer identifiers are hidden.
- Local only. Supporter downloads remain at 3.11.0; public stable remains 3.9.1.

---

# Apex Toolbox 3.13.1: Experimental candidate (local)

Update date: **2026-10-11**

- Single-frame additive poses now stay active over the base animation. They
  start at the chosen frame offset and keep applying afterward. Previously,
  they stopped after one frame and appeared to have no effect later in a clip.
- Animated additive layers still play for their original duration. Strength
  controls and removal work the same for both types of layer.
- After updating, remove and re-add existing single-frame layers to apply the fix.
- Local only. Supporter downloads remain at 3.11.0; public stable remains 3.9.1.

---

# Apex Toolbox 3.13.0: Experimental candidate (local)

Update date: **2026-10-11**

- Import & Texture checks the selected folders or CAST files before importing.
  Review the usable models, skipped files and nearby texture hints, then click
  **Import Models**. Missing textures are warnings and do not block a model.
- Choose **Row**, **Grid** or **Original positions** for batch imports. Grid
  supports a column count; row and grid spacing uses mesh bounds and a minimum
  gap. The first model stays in place. **One Collection per Model** keeps each
  imported model together in the Outliner.
- **Relink RSX Library** checks saved model, rig, clip, texture and browser paths
  against a new export location before changing them. It preserves Actions,
  poses and favourites, and keeps paths whose replacements are missing or do
  not match. The operation supports Undo.
- **Animation Layers** puts compatible additive clip channels over a loaded
  base animation. Set strength and frame offset before adding a layer; adjust
  a layer's strength afterward. **Remove Animation Layers** restores the base
  animation. Existing unrelated NLA tracks, constraints or drivers require the
  normal Blender animation workflow.
- Automatic legend rig linking and saved animation indexes remain included.
  Animation Preview, Apply and Revert remain removed.
- Local only. Supporter downloads remain at 3.11.0; public stable remains 3.9.1.

---

# Apex Toolbox 3.12.2: Experimental candidate (local)

Update date: **2026-10-11**

- Removed temporary animation Preview, Apply and Revert. Select a clip and use
  **Load Animation** to apply it; Blender Undo restores the previous animation.
- Faster repeat indexing and automatic legend rig linking remain available.
- Local only. Supporter downloads remain at 3.11.0; public stable remains 3.9.1.

---

# Apex Toolbox 3.12.1: Experimental candidate (local)

Update date: **2026-10-11**

- Import & Texture now links each legend's matching animation rig automatically,
  including batch imports. The option is enabled by default and remembered in
  the scene. Linking makes the animation list available without applying a clip.
- Searches the model export's sibling `animrig` folder first, then the last
  animation folder used and Blender's RSX bookmarks/recent folders. No fixed
  export path is required.
- Known RSX legend aliases are supported. Base pilot rigs take precedence over
  variants; ambiguous matches, weapons, props and incompatible skeletons are
  skipped. Existing manual links are kept.
- Auto-Link is also available for an already imported model. Indexing runs in
  short batches and shares the scan between skins using the same rig. Cancel,
  saving or Undo stops unfinished linking and keeps the imported models.
- Local only. Supporter downloads remain at 3.11.0; public stable remains 3.9.1.

---

# Apex Toolbox 3.12.0: Experimental candidate (local)

Update date: **2026-10-11**

- Preview a selected animation, scrub it, then Apply or Revert. Trying several
  clips keeps one original baseline. Revert restores the action, pose,
  orientation and timeline; Apply adds only the accepted clip to Recent.
- Saving, changing files, Undo and disabling Toolbox cancel temporary previews.
  Undo and Redo also recover previews captured by unrelated Blender edits.
- Repeat animation links reuse a saved file index in Blender's user data
  directory. Changed exports are reread; Refresh always performs a full scan.
  Cached indexes contain metadata only and are optional if storage is unavailable.
- Changed exports cannot silently substitute another animation at an old
  offset. Exports modified during indexing are rejected without replacing the
  previous library.
- This is a local experimental candidate. Supporter downloads remain at
  3.11.0 and the public stable download remains at 3.9.1.

---

# Apex Toolbox 3.11.0: Supporter preview of the next stable release

Update date: **2026-10-10**

- Brings the tested 3.10 experimental model, animation and item-pairing work
  together under a new stable version number. The public download remains 3.9.1
  until the later public release.
- **Import & Texture** accepts selected RSX model folders from Legends, Weapons
  and Misc, then places imported models side by side. Search and group changes
  keep checked folders selected. The legend selector covers all 28 legends on
  the current official roster; the training dummy stays in Misc.
- Animation tools can link a legend rig or import one `animseq` CAST directly.
  The library supports searching, in-game names where known, removal to rest
  pose and saved links. Allow Missing Bones is enabled by default.
- The rig picker finds the RSX `animrig` library even when the current model has
  an unrelated old CAST link. Legacy IK pole controls no longer create a
  Blender dependency cycle, and a second IK setup is rejected cleanly.
- The 3.11.0 ZIP passed internal testing and a hands-on check by the
  maintainer. It is available to all supporter tiers through Creator Tools.
  The public release is being held to give early access time for
  demonstrations and discovery.

---

# Apex Toolbox 3.10.23: Experimental candidate (local)

Update date: **2026-10-10**

- The animation rig picker now prefers a valid RSX `animrig` library when an
  already linked CAST file lives in an unrelated folder. This prevents the
  picker opening an empty legend list despite a discoverable library.
- Checked the model picker in Blender 5.2 with a foreground batch selected
  across Legends, Weapons and Misc. All three real exports imported together.
- This candidate is local. The supporter experimental download remains 3.10.21.

---

# Apex Toolbox 3.10.22: Experimental candidate (local)

Update date: **2026-10-10**

- Fixed bone selection in older rig and effect tools on Blender 5.2. Blender
  4.2 keeps using its original Bone selection API. The pose-bone selection
  check now runs on both versions.
- Checked the packaged model-folder import against three real RSX exports and
  direct animation import against a real Wraith `animrig` clip. These checks
  are repeatable with the optional scripts in `tests/`.
- This candidate is being hardened locally. The latest uploaded supporter
  experimental build remains 3.10.21.

---

# Apex Toolbox 3.10.21 — Experimental (in development)

Update date: **2026-10-08**

- Group Overdrive rigs under **Axle**, Holo rigs under **Mirage**, and Nova rigs
  under **Horizon**. Matching Holo and Nova companion rigs now appear in the
  picker when they contain a CAST rig and sequence folder.
- The model-folder picker also recognizes Overdrive and Nova character skins as
  Axle and Horizon.

---

# Apex Toolbox 3.10.20 — Experimental (in development)

Update date: **2026-10-08**

- The animation rig picker now lets you choose a legend before listing its
  exported rigs. Unrecognized pilot rigs remain under **Other rigs**, and
  **Other CAST** still opens the file browser for a rig outside the list.

---

# Apex Toolbox 3.10.19 — Experimental (in development)

Update date: **2026-10-08**

- Choose a legend, weapon or other group before browsing its model folders.
  Search applies to that group, and checked folders stay selected when you
  switch groups.

---

# Apex Toolbox 3.10.18 — Experimental (in development)

Update date: **2026-10-08**

- The model-folder picker now shows **Legends**, **Weapons**, and **Misc** views
  instead of one long list. Search narrows the current view, and checked folders
  remain selected when switching views. Exports that do not match a known legend
  or weapon name stay available under Misc.

---

# Apex Toolbox 3.10.17 — Experimental

Update date: **2026-10-08**

- The model-folder picker now supports a multiword search.
- With Allow Missing Bones enabled, CAST receives only tracks for bones on the
  selected model. The Toolbox still reports the number skipped, without
  printing a warning for every unmatched track.

---

# Apex Toolbox 3.10.16 — Experimental

Update date: **2026-10-08**

- **Import Animation CAST** now applies a single exported animseq CAST directly
  to the selected armature, without linking an animation rig. The clip stays
  in the browser for reuse and survives linking or refreshing a full rig.
- Standalone imports use the existing bone checks, missing-bone option,
  temporary-rig import and undo handling. Files containing zero or several
  sequences are rejected with an explanation.

---

# Apex Toolbox 3.10.15 — Experimental (in development)

Update date: **2026-10-08**

- Link Animation Rig now opens a searchable list of exported legend rigs from
  RSX's `animrig` folder. It finds the folder beside a remembered or bookmarked
  `mdl` export, remembers a changed folder, and keeps **Other CAST** for rigs
  outside the `pilot_*` legend folders.
- **Allow Missing Bones** is enabled by default for new animation libraries.
  A clip still reports how many bone tracks were skipped; turn the option off
  in **Options & Details** to require a full match.

---

# Apex Toolbox 3.10.14 — Experimental (in development)

Update date: **2026-10-08**

- Fixed Import & Texture failing after installing a new ZIP while Blender is
  still open. The model-folder helper now reloads with the rest of the add-on,
  so the folder list and import button use the same version.

---

# Apex Toolbox 3.10.13 — Experimental (in development)

Update date: **2026-10-08**

- Model-folder import now opens the bookmarked RSX `mdl` folder list directly.
  Select several model rows there and click **Import Selected Models**. This
  avoids Blender's native file-browser **Accept** action, which opens a
  highlighted directory rather than passing the folder selection to the add-on.
- Fixed the folder list staying empty when Blender added a trailing slash to
  the `mdl` path.

---

## Apex Toolbox 3.10.12 — Experimental

Update date: **2026-10-08**

- The folder dialog now stays at the RSX `mdl` directory even if Blender's
  browse control opens a highlighted model folder. Tick the model folders in
  the list and import them together; the dialog remembers `mdl` next time.

---

## Apex Toolbox 3.10.11 — Experimental

Update date: **2026-10-08**

- The single **Import & Texture** button now asks for CAST files or model
  folders. For folders, choose a parent and tick the models to import; Blender's
  file browser no longer opens the first highlighted folder instead of importing.

---

## Apex Toolbox 3.10.10 — Experimental

Update date: **2026-10-08**

- Combined CAST file and model-folder importing into one **Import & Texture**
  button. It handles one model, several CAST files from one folder, or model
  folders under a common parent.

---

## Apex Toolbox 3.10.9 — Experimental

Update date: **2026-10-08**

- **Import Model Folders** handles RSX exports where each model is in a separate
  folder. Choose their parent folder (or selected sibling folders); it takes one
  LOD0 CAST per model, skips animation folders, and uses the same side-by-side
  import. The batch is limited to 50 models to avoid importing an entire library.

---

## Apex Toolbox 3.10.8 — Experimental

Update date: **2026-10-08**

- Import & Texture now accepts several model CAST files from one folder. Each
  model is prepared and textured independently, then placed in a row with spacing
  based on its mesh bounds. The first model keeps its imported position.
- A bad or rig-only CAST is skipped without losing the other imports. A combined
  report identifies each file and any texture warnings. Existing scene objects
  are not moved; Undo removes the batch.

---

## Apex Toolbox 3.10.7 — Experimental

Update date: **2026-09-28**

- Added **Rigging & Animation → Pair Items** for imported item armatures. Choose the legend and item rigs, then snap to the left prop-hand, right prop-hand or prop-gun bone.
- Added a searchable bone picker for other attachment points and a shortcut to fill both rig fields from two selected armatures.
- Pairing parents the item rig to the pose bone, so its child meshes and own animation remain together. Missing bones, circular parenting and active object constraints stop with an explanation instead of changing the item.

---

## Apex Toolbox 3.10.6 — Experimental

Update date: **2026-09-28**

- Moved Animations into Rigging & Animation, above the collapsed Rig Tools panel.
- Simplified animation browsing to link, filter, choose and load. Playback options,
  name overrides and export details are in a single Options & Details foldout.
  Scan progress, cancellation and file warnings remain visible.
- Moved the shader library into Materials, and grouped HDRI, lighting and staging
  in Lighting & Scene. Optional checks and repairs are under Troubleshooting.
- Made the texture folder available beside the shader choice, shortened labels
  and removed repeated status/help text. Export setup remains in the workflow guide.
- Kept the Experimental release status in the main header and add-on details.
  Animation matching and loading are unchanged from 3.10.5.

---

## Apex Toolbox 3.10.5 — Experimental

Update date: **2026-09-28**

**Experimental release.** Animation tools and automatic in-game names have been
tested against the available exports, not every legend/skin/game version or
every animation. Unknown names keep their export labels. Check the supplied
coverage report for missing exports and known limitations.

- Included an English animation name catalogue, applied automatically when
  linking or refreshing a rig. No language/settings import is needed for normal
  use. The catalogue is loaded lazily from the plugin, with no game or network
  access at runtime.
- Catalogue contains 1,249 named sequence references from 1,003 animation item
  settings, plus unresolved identifiers that must not be guessed. Only short
  labels, identifiers and variant roles are included, not raw game exports.
- Kept language/newer-name imports as advanced options. Existing imported names
  survive refresh for unchanged clips; Use Included English Names resets those
  overrides with Undo. New clips receive included names automatically.
- Handled RSX's inline comments in modded settings JSON, found while expanding
  the catalogue beyond Wraith.
- Audited 15,627 clips across 31 supplied legend/variant folders, with 1,082 exact
  name matches. All 105 sampled load/remove/reload checks passed across 27 rig
  libraries in Blender 4.2.2. This samples playback rather than testing every clip.
- Rampart's standalone rig is missing and one clip is truncated; Lifeline's
  mythic export is empty. Two small variants had no named cosmetic clips to
  sample. See `Apex_toolbox/ANIMATION_NAME_COVERAGE.md` for the full coverage table.

---

## Apex Toolbox 3.10.4

Update date: **2026-09-28**

- Added per-model favourites and the 20 most recently loaded animations. Star,
  unstar and clear-history support Undo. Category and text filters work in each
  view. Clearing history keeps the actions and favourites.
- Refresh preserves bookmarks for uniquely named clips in the same export,
  including changed CAST byte offsets. Selected clips follow their names rather
  than a reused offset. Bookmarks and recent history persist in the blend file.
- Added optional In-Game Names import from RSX localization and item settings.
  Exact sequence identifiers connect menu names to CAST clips, with separate
  Still/Animated, Loop and Preview labels. Both names are searchable; the original
  remains visible. Unknown and ambiguous names are not guessed.
- Name imports run in cancellable batches, with atomic application and Undo.
  Failed, cancelled or zero-match imports retain previous names. Refresh retains
  names only when the same clip's sequence identifiers still match.
- Fixed timer-completed scans to explicitly record their Undo step, including
  animation refresh. Verified both Undo and Redo in Blender's foreground loop.
- No game text, settings or animations are included in the plugin ZIP.

---

## Apex Toolbox 3.10.3

Update date: **2026-09-28**

- Added Remove Animation / T-Pose, preserving the action for reuse and resetting
  all pose bones. Restores the pre-load armature orientation for new loads;
  supports Undo, mesh selection and Pose Mode without changing scene timing.
- Removed animation indexing's ten-second deadline and file-count/depth cutoffs.
  Scans yield within CAST files, show progress and support cancellation. The
  existing library is kept until scanning completes; invalid files are reported.
- Reduced indexing memory by retaining clip metadata rather than whole curve
  trees, and optimized CAST string reads.
- Added animation category filters for Gladcard / Banner, Emote, Lobby, Finishers
  and Movement, combined with name search and matching counts.

---

## Apex Toolbox 3.10.2

Update date: **2026-09-28**

- Load Animation now resets the selected armature's local object rotation on
  successful imports and cached-action switches. Position, scale, rotation mode
  and bone animation are preserved. Failed loads keep the original rotation;
  Undo restores it alongside the previous action.

---

## Apex Toolbox 3.10.1

Update date: **2026-09-28**

- Moved Set Correct Model Size and Quaternion to XYZ Euler into a collapsed
  Manual Adjustments panel below Import & Texture. Their behaviour is unchanged.

---

## Apex Toolbox 3.10.0

Update date: **2026-09-28**

- Added Import & Texture for CAST models, with optional preparation, shader choice,
  automatic texture discovery, existing-material isolation and failed-import cleanup.
- Added per-model animation rig links for RSX exports, searchable CAST clip lists,
  compatibility checks, action reuse and preservation of previous actions.
- Animation imports are staged on a temporary rig; failures preserve the model's
  pose, action, timeline and selection. Links and loaded actions survive saving.
- Removed Toon shader controls/operators and moved Auto Shadow under Apex Effects.
- Version bumped to 3.10.0. No raw game files or third-party importers are bundled.

---

## Apex Toolbox 3.9.1

Update date: **2026-09-28**

- Added Quaternion to XYZ Euler for selected models or pose bones, also applied
  during model preparation. Preserves transforms and skips animated, driven,
  constrained and read-only targets.
- Kept the displayed version and release archive checks tied to the add-on version.

---

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

## Apex Toolbox 3.8.0

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
