# Apex Toolbox 3.11.0: Early access preview

The tested 3.11.0 ZIP is available to all ALR supporter tiers through
[Creator Tools](https://apexlegendsrenders.com/creator-tools). Public stable
remains 3.9.1 while early access has time to run.

- Import and texture one or several RSX model folders. Browse Legends, Weapons
  and Misc, narrow the list by name, and place imported models side by side.
- Find animation rigs by legend, search clips with known English names, remove
  an animation to return to rest pose, or apply one animation CAST directly.
- Pair an imported item to a hand, weapon or other bone. The legend selector
  covers all 28 current legends. The rig picker handles old CAST links more
  reliably, and Blender 5.2 rig compatibility has been improved.
- Checked in Blender 4.2.2 and 5.2.2. The ZIP contains add-on source under
  GPL-3.0-or-later. It does not include game models, textures or animations.

---

# Apex Toolbox 3.10.8 — Experimental (in development)

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
