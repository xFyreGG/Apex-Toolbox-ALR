# Testing and project map

The Blender add-on entry point is `Apex_toolbox/__init__.py`: preferences,
operators, bundled-asset actions, UI panels and registration. `ApexShader.blend`,
`img/` and `anim/` hold the Lite assets. The optional Extended asset pack is external.

`apex_tex/` separates texture naming, roles, root discovery and resolution from
Blender graph inspection and shader construction. Auto Texture and Recolour
share that resolver. `diagnostics.py` formats texture reports; `health.py` handles
model scope, scene checks and image repair. `versions.py` compares release tags.
Package reload order and its API version are checked when the add-on is reloaded.

`cast_index.py` reads bounded CAST metadata without decoding mesh or animation
buffers. `workflows.py` adapts the installed CAST importer and isolates imported
models. `animations.py` indexes RSX sequence folders and builds Actions against
a disposable rig before assigning them to the selected model.
`animation_cache.py` stores validated per-file metadata in Blender's user data
folder.
`auto_rigs.py` discovers matching legend exports and queues animation libraries
without changing imported models or applying an Action.
`import_plan.py` validates chosen model exports before import and arranges the
successful imports in rows, grids or their original positions. `relink.py`
checks and replaces paths to a moved RSX export library. `animation_layers.py`
manages additive channels over a base Action through Blender NLA.

## Run the checks

Pure Python (no Blender dependency):

```text
python Apex_toolbox/apex_tex/tests/run_tests.py
python tests/animation_cache.py
python tests/auto_rig_matching.py
```

Blender integration, using factory settings and temporary files:

```text
blender --background --factory-startup --python-exit-code 1 --python tests/blender_integration.py
```

A single integration case can be selected with `-- test_method_name` after the
script argument. The suite creates its own scenes and should run in a separate
Blender process. It tests all three bundled shaders, repeated conversion,
rollback, missing/corrupt/ambiguous files, search limits, packed and relative
images, nested groups, shared materials, model scope, scene health selection,
saved reports, preparation, Lite staging and unregister/re-register/reload.
Rotation checks cover quaternion-to-Euler conversion of objects and selected
pose bones, parented meshes, nonuniform/negative scales, delta rotation,
selection preservation, repeat preparation and skipping Actions, NLA, drivers
and constraints.
Item-pairing checks cover snapping an imported prop armature to a pose bone,
keeping child meshes with it, following subsequent poses, and leaving the item
unchanged when the requested attachment bone is absent.

For Import & Texture and the animation selector, enable/install `io_scene_cast`
on the test host, then run:

```text
blender --background --factory-startup --python-exit-code 1 --python tests/workflow_integration.py
```

This creates synthetic model and multi-clip exports with CAST's own writer and
uses the actual installed importer. It verifies material isolation, failure
cleanup, compatibility checks, cached actions, timing, selection, Object/Pose
Mode, saved links, save/reopen and missing-importer handling. No game files or
user scenes are used. `tests/workflow_ui.py` provides a disposable UI fixture.

Repeat-index checks, also with synthetic exports:

```text
blender --background --factory-startup --python-exit-code 1 --python tests/animation_index_scan.py
```

Append `-- --release` to check the extracted current ZIP. Index checks count
parser calls, verify per-file invalidation,
forced Refresh, interrupted scans, saved browser state and source replacement
with a preserved file size and timestamp. The cache uses temporary test storage.

Run `tests/auto_rig_integration.py` in background Blender, optionally with
`-- --release` for the ZIP. Run `tests/foreground_auto_rigs.py` without
`--background` to check timer completion and Undo in a disposable process.
Add `--require-auto-links` to the real-model folder check below to require
animation libraries on every recognized legend model.

Import checks, batch layout, moved export paths and additive layers:

```text
blender --background --factory-startup --python-exit-code 1 --python tests/import_plan.py
blender --background --factory-startup --python-exit-code 1 --python tests/relink.py
blender --background --factory-startup --python-exit-code 1 --python tests/animation_layers.py
```

Append `-- --release` to verify the extracted current ZIP. These suites use
temporary synthetic CAST files and disposable Blender data. Import checks cover
LOD0 selection, partial failures, the 50-model cap, texture hints, varied model
bounds and collection membership. Relink checks cover preserved scene and
animation state, missing replacements and changes between review and apply.
Layer checks exercise evaluated motion, strength, timing, save/reopen, action
preservation and removal, including unsupported rigs and clips.

Run `tests/foreground_release_tools.py` without `--background`, optionally with
`-- --release`, for relink, layer strength/removal and reviewed grid-import
Undo/Redo, plus a native review-popup draw check. It closes only its own
disposable Blender process and writes an explicit result under `artifacts`.

### 3.14.0 local candidate, 2026-11-03

- 43 Blender integration checks passed on 4.2.2 and 5.2.2, including hair multiply inputs and factor, repeated rebuilding, explicit opacity disabled, transparency audit preserving materials, paired rotation/reset and tab visibility.
- 56 packaged workflow checks passed on 5.2.2. 125 Python checks passed. Enable/disable/reload passed on 4.2.2.
- A disposable fresh-process Wraith import took 2.31 seconds: CAST import 0.58, texturing 1.26 and animation linking 0.47. A separate model-only run took 0.40 seconds with both optional steps disabled. These are local measurements with OS caches uncontrolled, not a universal performance guarantee.
- Source game exports and user scenes were not modified. Transparency intent remains a manual judgement; the checker reports connections and pixel ranges. Hair matching currently uses material names containing `hair`.

### 3.13.2 interface refinement, 2026-10-11

- 125 Python checks passed. Packaged workflow checks passed all 56 cases on
  Blender 4.2.2 and 5.2.2. Layering passed all 34 checks on 5.2.2; 33 passed
  with the expected Action-slot skip on 4.2.2. Existing stack/removal checks
  now also verify the base Action remains available for the UI to identify.
- Enable, disable and changed-on-disk reload passed three cycles on both
  Blender versions. The internal API revision is 19 for the new base-Action
  lookup used by the animation panel.
- Packaged foreground checks passed relinking, Add Layer, Adjust Strength,
  Remove Layers and reviewed batch import Undo/Redo on both versions, plus
  the native import review popup.
- Native 5.2.2 visual checks used disposable scenes at the default narrow
  sidebar width. Checked the main animation browser, grouped options,
  import dialog, Rigging, Effects and Troubleshooting. With a packaged active
  layer, the base animation stayed visible, loading was disabled, and the
  collapsed section's Remove Animation Layers button restored the base.
  No user project or preferences were saved.
- ZIP: 4,774,469 bytes, 48 files. SHA-256:
  `2554ed20e01b0fab5cf5b7d2015bc886a4e28ccc9e1e63c2100349915a60c449`.
  Archive integrity passed and every packaged file matches the source.
  This build is local; public and supporter downloads remain 3.9.1 and 3.11.0.

### 3.13.1 single-frame layer fix, 2026-10-11

- Source and extracted ZIP passed 34 layer checks on Blender 5.2.2; 33 passed
  and the Action-slot-specific check skipped on 4.2.2. Five new regressions
  cover true single-key additive poses over a long base, strength, positive
  offset, preserved root motion, save/reopen and removal. Animated clips still
  end at their original duration.
- The packaged build was checked against Sparrow's actual Cool Cats animated
  gladcard, four single-frame crouch aim poses and two animated fire clips.
  Held poses affect frames 0, 68 and 100; zero strength restores the base,
  half strength works, and a frame-25 offset has no effect before frame 25.
  Removing the layers restores the original Action and pose. Source exports
  stayed unchanged.
- Packaged foreground checks passed Add Layer, Adjust Strength and Remove
  Layers Undo/Redo on 5.2.2, along with relink and reviewed batch import checks.
- ZIP: 4,774,071 bytes, 48 files. SHA-256:
  `d21977aea148a74985dc485c8fd4a62aba38c43987ff430ab94ac9a2300f3408`.
  Archive integrity passed and every packaged file matches the source.
  This fix is local; public and supporter downloads remain 3.9.1 and 3.11.0.

### 3.13.0 local candidate validation, 2026-10-11

- 125 texture/resolution checks, 18 animation-cache checks and 13 legend-matching
  checks passed in Python.
- The extracted ZIP passed 56 workflow, 34 import/preflight/layout, 25 relink,
  19 automatic rig-link and 15 repeat-index checks on Blender 4.2.2 and 5.2.2.
  Animation layering ran 29 checks: all passed on 5.2.2; 28 passed and the
  Action-slot-specific check skipped on 4.2.2.
- Add-on enable/disable and changed-on-disk reload passed on both versions.
  Packaged foreground checks passed relink, Add Layer, Adjust Strength,
  Remove Layers and reviewed batch import Undo/Redo on both versions. The
  native review popup imported nothing before confirmation.
- Packaged automatic-link foreground checks passed on 5.2.2, including timer
  completion, index reuse, Undo/Redo, cancellation, saving, changed selection
  and removal of the initiating model.
- Actual native import buttons were checked on 5.2.2. Selecting folders,
  Check Import and Import Models worked; one Undo removed the whole batch.
  The final package also passed collection cleanup Undo/Redo and its warnings
  wrapped within the dialog.
- A packaged real-export check imported two Wraith skins into a one-column
  grid, textured all 15 meshes and created exactly two model collections.
  Existing objects and collections stayed intact; the source exports stayed
  unchanged. The quick import check took 0.071 seconds in this local run.
- ZIP: 4,773,783 bytes, 48 files. SHA-256:
  `f9154a3414e9f06609665e83c3241c57521e8e2d53ae801c969f05d5f829fc96`.
  Archive integrity passed and every packaged file matches the source.
  This candidate is local; public and supporter downloads remain 3.9.1 and
  3.11.0 respectively.

### 3.12.2 local candidate validation, 2026-10-11

Temporary animation Preview, Apply and Revert have been removed. The active
checks above cover animation loading, repeat indexing and automatic rig linking.

- 125 pure Python checks passed. All 56 existing workflow checks passed in
  Blender 4.2.2 and 5.2.2, including loading, changing and removing animations,
  saved browser state and missing-bone handling.
- The extracted ZIP passed 19 automatic rig-link and 15 repeat-index checks
  on both Blender versions. Add-on enable/disable/reload passed on 5.2.2.
- The packaged foreground auto-link check passed on 5.2.2, including batch
  completion, Undo/Redo, cancellation, saving and changing the selected model.
- ZIP: 4,753,642 bytes, 45 files. SHA-256:
  `dcf967b278d5de9d8dfbc484b005f1594027bcb8b27226260d399606aae00e9b`.
  The archive matches the current source and no longer contains the preview
  module. This candidate is local; public and supporter downloads are unchanged.

### 3.12.1 local candidate validation, 2026-10-11

- 125 existing pure Python checks and 13 new name/alias checks passed.
- Blender 4.2.2 and 5.2.2 passed 56 existing workflow checks and all 19 new
  automatic rig-link checks. The extracted ZIP passed the 19 new checks on
  both versions. The 19 packaged animation-preview checks passed on 5.2.2.
- Disposable foreground sessions on both Blender versions passed automatic
  batch linking, link Undo/Redo, cancellation, cancel-on-save, changed selection
  and removal of the initiating model while other models continued linking.
- The packaged real-export check imported two Wraith skins, textured all 15
  meshes, kept the models side by side and linked all 573 clips to each model.
  No animation was applied. The source exports and user scenes were not modified.
- The matching checks cover all 28 supported legends, known RSX aliases,
  base-rig preference and ambiguous/missing rigs. Integration also checks custom
  paths, incompatible skeletons, changed exports, existing manual links and
  reuse of one scan across multiple skins. Add-on reload checks passed on 5.2.2.
- ZIP: 4,757,797 bytes, 46 files. SHA-256:
  `a885972c549234d87fa30883683c6ed94faf4444ca0ae1bf652aa059857611c2`.
  This candidate is local; the available downloads remain unchanged.

### 3.12.0 local candidate validation, 2026-10-11

- 125 existing pure Python checks and 18 cache checks passed.
- In Blender 4.2.2 and 5.2.2, the source and extracted ZIP passed 56 workflow
  checks, 19 preview checks (one slot-specific check skips on 4.2) and 15 index
  checks. Package registration and add-on reload checks passed on both versions.
- Foreground tests passed preview switching, Revert, Apply, exact Undo/Redo,
  previous Action retention and recovery after unrelated edits. Native buttons
  were also checked for Preview, Apply and Undo in Blender 5.2.2.
- The packaged real Wraith check passed on both versions: 573 clips, all 573
  sequence parses skipped on repeat, no warnings or missing bones in the three
  sampled clips. First/repeat scan times observed were 9.63/0.40 seconds on 4.2
  and 8.31/0.39 seconds on 5.2. These are local measurements, not a speed guarantee.
- ZIP: 4,752,207 bytes, 45 files. SHA-256:
  `ab362dbef91ee924c6ee9960e4671e25ccbc747cc794274e2475c84d856bfb11`.
  This candidate is local; the website still offers 3.11.0 to supporters and
  3.9.1 as the public stable release.

For a read-only check with exported game files, run `tests/real_single_animation.py`
with `-- --rig <rig.cast> --clip <anims_rig/sequence.cast>`. Add `--release`
to check the built experimental ZIP instead of the source tree.

For a real batch import check, run `tests/real_model_folders.py` with
`-- --mdl <exported_files/mdl> --models <folder1> <folder2> [<folder3> ...]`.
It confirms that only the chosen model folders import and that their world-space
bounds do not overlap. Add `--release` to test the ZIP. Neither real-export
check saves a scene or copies game files into the repository.

Activation and reload:

```text
blender --background --factory-startup --python-exit-code 1 --python tests/enable_smoke.py
```

This uses `addon_utils.enable` and `disable`, including two simulated
changed-on-disk reloads. It verifies registration and cleanup under Blender's
restricted import context. To inspect an isolated UI session, omit
`--background` and add `-- --ui`. It does not save preferences or a project.

Render verification:

```text
blender --background --factory-startup --python-exit-code 1 --python tests/render_smoke.py
```

This creates `artifacts/shader-preview.png` and a sample `.blend`, rendering one
sphere with each shader in Cycles. To inspect the sidebar in a separate Blender
window, omit `--background` and add `-- --ui`; that fixture deliberately removes
one UV map so the health issue controls are visible.

## Build the installable ZIP

Increment `bl_info["version"]` for each plugin update (for example, 3.9.0 →
3.9.1 for a small update). Update the current-version documentation and add a
dated changelog entry, preserving older release history. The UI version, ZIP
filename and package smoke check derive their version from `bl_info`.

```text
python tools/build_release.py
python tools/verify_release.py
```

The archive is written to `dist/`, takes its version from `bl_info`, preserves the
`Apex_toolbox/` root and bundled assets, and omits test files and Python caches.
The build verifies the archive contents and CRCs. It does not install, publish
or change the user's Blender preferences.
The verification script checks that every ZIP entry matches the current add-on
tree and prints its byte size and SHA-256. `tests/install_zip_smoke.py` also
checks Blender's actual Install from Disk path; run it with
`BLENDER_USER_SCRIPTS` set to a disposable directory.

Verify the built archive in a fresh Blender process:

```text
blender --background --factory-startup --python-exit-code 1 --python tests/package_smoke.py
```

This extracts the ZIP to a temporary directory and runs conversion with all three
shaders, XYZ Euler conversion, texture reports, scene health and registration
checks against that exact copy.

The CAST workflow suite can also target the extracted archive:

```text
blender --background --factory-startup --python-exit-code 1 --python tests/workflow_integration.py -- --release
```

Validation host: Blender **4.2.2 LTS**, bundled Python **3.11**, Windows. The
suite uses representative synthetic meshes and actual bundled shaders. Optional
Extended assets and external CAST/SEModel importer implementations are not
included in this repository. CAST is exercised by the separate workflow suite;
SEModel and real legend animation exports are not covered by those fixtures.

The 3.9.0 validation on 2026-09-08 passed **101 pure Python tests** and **31
Blender integration tests**, plus the Cycles render and extracted release
checks. The sidebar was also inspected in Blender: readable
report opening, issue details and affected-mesh selection worked correctly.

The **3.9.1** rotation-mode update on 2026-09-28 passed **101 pure Python tests** and
**35 Blender integration tests**, plus checks of the rebuilt release archive.
After a reported activation freeze, the enable/reload test also passed in both
background and UI Blender sessions. The affected user's session enabled 3.9.1
successfully after restarting. A captured stack stopped in Blender's own
reload-message console output, before module reloading; the underlying cause
was not established. No add-on runtime change was made for that incident.

The **3.10.0** update passed **109 pure Python tests**, **34 Blender integration
tests**, and **14 CAST workflow tests against the extracted release archive**,
plus the package and enable/reload checks. The removed Toon workflow accounts for
the one fewer legacy integration case. CAST tests use generated fixtures through
the installed importer, including round-trip `.blend` saves; real RSX legend
exports still need user validation.
The Blender sidebar was inspected with the workflow fixture: animation loading
worked from the list, Undo restored the previous action, text wrapped at the
host's display scale, Toon controls were absent, and Auto Shadow appeared under
Apex Effects. The test session was closed without modifying the user's project.

The **3.10.1** panel reorganization passed the enable/reload and extracted-package
checks. A separate Blender UI session confirmed Manual Adjustments starts
collapsed below Import & Texture and expands to show both size and rotation tools.

The **3.10.2** animation rotation reset passed **15 CAST workflow tests** against
the extracted ZIP, plus package and enable/reload checks. Coverage includes fresh
and cached actions, Euler/quaternion/axis-angle modes, parented armatures,
nonuniform/negative scale, preserved placement and bone motion, mesh-selected
targets, and failed imports retaining the original rotation. In a separate UI
session, Load Animation changed the prepared armature from 90 degrees to zero;
Undo restored its original rotation, action state and timeline. The UI fixture
seeds an Undo baseline because startup-script changes do not create normal UI
history.

The **3.10.3** update passed **111 pure Python tests**, **34 Blender integration
tests** and **22 CAST workflow tests against the extracted ZIP**, plus package
and enable/reload checks. New coverage includes 4,100-file discovery, deep folders,
incremental CAST reads and cancellation, a simulated elapsed time beyond the old
deadline, category/text filtering, rest-pose removal, cached-action reuse, all
object rotation modes, Pose Mode, mesh selection and save/reopen restoration.

`tests/animation_scan.py` runs in a disposable foreground Blender event loop
(add `-- --release` to exercise the ZIP). It indexed **6,001 clips**, verified that
other timers kept running, retained the previous list during scanning/cancellation,
and checked cleanup on disable/re-enable and `.blend` load. The final source and
extracted-release runs exited cleanly. Scanning uses application timers; an earlier
modal prototype was replaced after lifecycle tests exposed stale Blender handlers.

The separate UI fixture confirmed the category dropdown and matching counts,
Remove Animation / T-Pose restoring the prepared orientation, and Undo restoring
the action. Refresh discovered an additional file (8 to 9 clips), and Undo restored
the 8-clip index. The test window was closed without touching the user's project.
Real RSX legend exports remain untested; the reported ten-second cutoff was
reproduced in the previous code and removed.

The **3.10.4** update passed **121 pure Python tests**, **34 Blender integration
tests** and **32 CAST workflow tests** (including the extracted ZIP), plus
package and enable/reload checks. New tests cover favourites, the 20-clip recent
limit, cached loads, filter selection and sorting, refresh after changed clip
offsets, duplicate names, relinking, and saving/reopening bookmarks.

Name tests cover known RTech hash vectors, Unicode and escaped text, exact CAST
identifiers, role labels, conflicting/missing translations, invalid/partial
metadata, cancellation, changed libraries, refresh and blend-file persistence.
`tests/animation_names_scan.py` exercises 1,000 synthetic settings files in a
foreground event loop: atomic completion, responsiveness, cancellation, Undo/Redo,
and cleanup on file load and disabling. Both source and ZIP runs passed.
`tests/animation_scan.py` additionally verifies Undo/Redo of a 6,001-clip refresh.
These checks exposed missing automatic Undo recording for timer-completed
operations; the timer now explicitly pushes one successful commit to history.

Optional `tools/inspect_animation_exports.py --rig <rig.cast> --names <file.locl>
--output <report.json>` reads real metadata without changing exports. The local
Wraith export had **573 clips, 217 bones and zero indexing warnings**; the user's
installed-game settings and English text produced **46 exact named matches**.
The string identifier was also checked against 509 RSX asset identifiers with
zero mismatches. Game data and these reports are not part of the release ZIP.

`tests/real_animation_exports.py` accepts `--rig`, `--names` and optional
`--release` after Blender's `--`. In a separate factory scene, the extracted ZIP
imported the real Wraith rig and played **Now You See Me**, **Flip the Rift** and
**Window to the Soul (Animated)**, with 1,519 animation curves each. Removing and
reloading each reused its Action successfully. This validates Wraith's sampled
clips; other legends, game versions and language exports were not tested.

The disposable UI fixture confirmed the named-clip label and original name,
starring/Favourites filtering, Recent, and Clear Recent with Undo restoring the
list while the current animation stayed assigned. The user's existing project
and installed add-on were left untouched.

The **3.10.5** included-name update passed **125 pure Python tests**, **34 Blender
integration tests** and **36 CAST workflow tests**, including extracted-ZIP
workflow and package checks. Tests cover automatic names on link/refresh without
localization files, imported-name preservation and reset, migration of 3.10.4
name overrides, a missing-catalogue fallback, catalogue validation/conflicts, and
RSX's inline settings comments. Enable/disable/reload passed; the catalogue is
loaded only when needed, never during registration.

Foreground checks passed the 6,001-clip scan with Undo/Redo and cancellation,
and the optional 1,000-file name import with custom-name source restored by
Undo/Redo. The UI fixture received its menu name from the included catalogue
without importing metadata; the included-name and advanced language controls
were inspected in a separate Blender window.

`tools/audit_animation_libraries.py` checks every CAST clip in the supplied
`pilot_*` export folders, including those missing a standalone rig. It writes a
JSON audit and CSV counts. `tests/real_animation_libraries.py` takes that audit
and tests actual rig linking plus one named clip per available cosmetic category
(ground emote, skydive emote, banner and finisher). Each sample is loaded, removed
to the rest pose and loaded again to verify Action reuse. Empty exports, missing
rigs and variants with no named cosmetic clips are reported separately, not as
successful playback tests. `tools/summarize_animation_validation.py` turns both
reports into a readable coverage table. These optional tests require local user
exports; none are checked in or included in the plugin ZIP.

Maintainers can regenerate `apex_tex/data/animation_names_en.json` with
`tools/build_animation_names.py --localization <English.locl> --settings
<settings/itemflav> --game-build <build-id>`. This retains only short menu names,
sequence identifiers and variant roles, plus blocked ambiguous identifiers.
The shipped snapshot was generated from 1,003 animation item settings for game
build 25358568: 1,249 named references and 10 unresolved identifiers. Future
content requires updating the snapshot or an optional user metadata import.

The real-export audit completed with **15,627 clips** in **31 legend/variant
folders**, including **1,082 exact named clips** and nine conflicting/unresolved
matches left with export labels. All **105 playback samples** across **27 rig
libraries** passed loading, removal to rest pose and cached reload using the
extracted 3.10.5 ZIP. There were no playback failures. Rampart lacks its standalone
rig and has one truncated clip; Lifeline mythic has no clips. Lifeline OP and
Bloodhound Old Ways each indexed four clips but had no named cosmetic clips to
sample. See `Apex_toolbox/ANIMATION_NAME_COVERAGE.md` for per-export results.
Coverage applies to these supplied exports and sampled clips only. The build is
explicitly marked Experimental in its add-on metadata, animation panel and docs.

The **3.10.6** menu cleanup passed all **36 CAST workflow tests against the
extracted ZIP**, the package smoke check and three enable/disable/reload cycles.
In a separate Blender 4.2.2 UI fixture, the animation browser appeared beneath
Rigging & Animation, advanced options expanded correctly, and Remove Animation
and Load Animation restored the rest pose and loaded action respectively. The
Materials/Shader Library and Lighting & Scene/Scene Tools panels were also
visually checked at the default sidebar width, with no drawing errors. The
Experimental status is now shown once in the main header. Animation logic and
the included name catalogue are unchanged; the 3.10.5 coverage report remains
the record of the real-export sampling. The installed add-on and user's scene
were not changed.

The **3.10.7** release pass on 2026-10-08 passed **125 pure Python tests**,
the Blender integration suite (including item pairing), the CAST workflow suite
against both source and the extracted ZIP, package smoke, three enable/reload
cycles, and a three-shader Cycles render in Blender 4.2.2. The release ZIP was
built again from the final source and its contents and CRCs were checked. The
user also confirmed the new item-pairing controls in their Blender workflow.

The **3.10.8** batch-import work was checked in Blender 4.2.2 with three
synthetic CAST models of different widths. The integration tests verify that
their world-space mesh bounds do not overlap, their centres and bottoms align,
and an existing scene object is not moved. Mixed valid/invalid files keep the
successful imports, while an all-invalid selection restores the previous
selection. The full source and extracted-ZIP CAST workflow suites, package
smoke, pure Python tests, Blender integration tests and add-on reload checks
passed. Real game exports still need a user workflow check.

The **3.10.9** folder-import path was checked in Blender 5.2.2 against source
and the installable ZIP. Tests cover choosing a parent folder or selected
sibling model folders, picking LOD0 over other LODs, skipping animation folders,
rejecting ambiguous folders and oversized batches, and placing the resulting
models side by side. The extracted-ZIP workflow suite (42 tests) and package
smoke passed. The live Blender file browser was checked for CAST file
multi-selection; folder selection in the new picker and the user's real RSX
exports still need a final workflow check.

The **3.10.10** picker combines the file and folder paths under the existing
Import & Texture operator. Blender 5.2.2 integration tests cover single CAST,
multiple CAST files, one model folder, a parent of model folders, and selected
siblings. The packaged ZIP is checked separately with the same workflow suite.

The **3.10.11** folder selection dialog was checked in Blender 5.2.2 with
three sibling model folders. Two checked folders imported while the unchecked
folder remained out of the scene. Source and extracted-ZIP workflow tests and
package smoke pass. The modal UI still needs a real Blender click-through.

The **3.10.12** folder-root correction was checked against nested RSX-style
`mdl/model/model/model_LOD0.cast` fixtures. Passing a highlighted model folder
normalizes the dialog to `mdl`; selecting another sibling imports only that
model and remembers the `mdl` directory.

The **3.10.13** change was checked against Blender's trailing-slash `mdl\`
format and a Blender 5.2 bookmark file, including the user's configured RSX
bookmark. The folder list now populates from the root without entering a
model folder; packaged integration and smoke tests pass. The native file
browser does not handle folder import and is no longer part of this path.

The **3.10.21** pre-stable baseline on 2026-10-10 passed **125 pure Python
tests**, **54 CAST workflow tests** and **37 Blender integration tests** in both
Blender 4.2.2 and 5.2.2. The workflow tests and package smoke used the exact
3.10.21 ZIP available through the experimental channel. Its 43 packaged files
match the current add-on source byte for byte. The Blender 5.2 integration test
for pose-bone selection was updated to use the API available in that version;
the add-on code was unchanged. Real RSX exports, foreground picker interaction
and a foreground maintainer check remained release gates at the time. The
3.11.0 plan no longer requires a supporter test.

A follow-up real-export check on 2026-10-10 imported three model folders from
the user's RSX `mdl` library through the packaged folder-selection path. All
three models and 19 meshes imported, with side-by-side placement and aligned
centres and bottoms. A direct Wraith `animrig` sequence import, remove and
reload also passed against the ZIP. Real Axle, Mirage and Horizon rig exports
linked 367, 564 and 623 clips respectively in Blender 5.2.2. These checks
still do not replace a foreground mouse-driven picker test.

The local **3.10.22** hardening ZIP passed 54 extracted-ZIP CAST workflow tests,
38 Blender integration tests and package smoke in both Blender 4.2.2 and
5.2.2. The real three-model folder batch passed in both versions (19 meshes,
about 4.4 seconds), as did direct import/remove/reload of a Wraith animation
from `animrig`. A controlled single-model folder import in Blender 5.2.2 took
1.50 seconds with 3.10.14 and 1.48 seconds with 3.10.21. Profiling attributed
about one second of the import to Blender validating 31 distinct texture
images, rather than folder selection or CAST loading. This is a one-model
measurement, not a guarantee for every export or storage device.
The legacy IK operator completed on a real Wraith rig in both Blender versions,
but both reported dependency-cycle warnings. Its visual behaviour has not yet
been verified and remains an open check in the release plan.
Another packaged 3.10.22 batch combined an Ash legend model, an R-301 weapon
and a bench prop. All three imported (24 meshes) and passed the same alignment
and non-overlap checks in Blender 5.2.2.

In a foreground Blender 5.2.2 session on 2026-10-10, the 3.10.22 source
picker retained selections while switching from Axle under Legends to R-301
under Weapons and Bench under Misc. One Import click brought in all three
real folders, adding 25 meshes to a disposable scene that already held one
synthetic mesh. Framing the result showed separate models. The animation rig
picker also displayed the real `animrig` library with Axle mapped to
`pilot_medium_overdrive`. The foreground click to link that rig did not
produce a confirmed list update in the fixture, so that specific UI action
needs another check before the release gate is closed.

The local **3.10.23** source fixes a picker default found in that session:
an unrelated previously linked CAST folder no longer takes precedence over
a valid RSX `animrig` library. The new regression test and all 55 CAST
workflow tests pass in Blender 4.2.2 and 5.2.2, both from source and from the
3.10.23 ZIP. Package smoke also passes in both versions. The live supporter
download remains 3.10.21.

The packaged 3.10.23 build also passed a real Axle, R-301 and bench batch in
Blender 5.2.2: three models, 25 meshes, aligned and without overlapping bounds.
The ZIP is 4,750,435 bytes with SHA-256
`c02114cf7aaa8d4051b5d23ceec88e42338102e89008b59f8df88d5f3126a43e`;
all packaged add-on files match the local source.

The local **3.11.0 stable candidate** on 2026-10-10 passed **125 pure Python
tests**, **38 Blender integration tests** and **56 CAST workflow tests** in both
Blender 4.2.2 and 5.2.2. The workflow tests ran against the extracted ZIP.
Package smoke, isolated ZIP installation and enablement, and a three-shader
Cycles render also passed in both Blender versions. The foreground packaged
rig-link path completed in both versions. The 6,001-clip scan and animation
name scan passed their event-loop, cancellation, Undo and cleanup checks in
Blender 5.2.2.

From the packaged ZIP, a real Axle, R-301 and bench batch imported 24 meshes
with aligned, non-overlapping bounds in both versions. A real Wraith `animrig`
clip imported, removed and reloaded in both versions. The Wraith IK helper
produced eight controls and four IK chains in both versions; moving hand and
foot controls moved the driven bones, repeated setup was rejected, and Blender
reported no dependency cycles. A disposable Blender 5.2 viewport check showed
the character posed without visible distortion.

The current official 28-legend roster was checked against the model picker and
the local RSX `mdl` library. All 28 have a group in the legend selector; none
of the character model folders were classified as Misc. The training dummy is
in Misc. Legend-themed props remain under Misc or Weapons as appropriate.

A read-only audit of 33 local `animrig` folders indexed **16,896 clips** and
found **1,183** built-in names. Full playback from the packaged ZIP passed in
29 libraries, covering 113 named clips. Two small variant libraries indexed
successfully but had no named cosmetic clips to sample. The Lifeline mythic
export has no clips, and the Rampart export has no standalone rig CAST and one
truncated sequence; those two variants were recorded as unavailable, not
passed. Axle, Mirage and Horizon playback samples also passed in Blender 4.2.2.

The 3.11.0 ZIP contains 43 files, is **4,750,445 bytes**, and has SHA-256
`b56eeb7aa513a265c2fb63255210f17e5d5a559becd3d822f83ec441086e3762`.
Every entry matches its add-on source file byte for byte. No local RSX exports,
test fixtures, private paths or other workspace artifacts are included.

### 3.14.1 local alpha fix, 2026-11-03

- Original Gl2imm/Apex-Toolbox alpha wiring reviewed. It connects albedo alpha without inspecting pixels; the historical Shader+ socket mismatch silently skipped that connection. We retain correct socket names.
- Blender integration: 44 tests passed on both 4.2.2 and 5.2.2. Includes fragmented alpha, coherent cutouts, hair-like masks, opaque/soft alpha, explicit opacity maps and forced alpha across all three shaders.
- Pure Python suite: 125 tests passed.
- Actual Ash opbundle head albedo checked in Blender 5.2.2: automatic rejection confirmed and alpha disconnected for all three shaders. Initial image load/read plus detection took approximately 0.26 seconds in this run.
- Heuristic intentionally retains alpha for unknown/large images and exempt hair/lash/fur/lace materials. Intentional sparse cutouts can use the material custom property `apex_force_albedo_alpha = True`. No claim of universal game-material classification.
- No source textures or user scenes modified. Existing scene materials need Auto Texture rerun. No rendered visual comparison performed for this candidate.
- Packaged ZIP workflow suite: 56 tests passed on Blender 5.2.2.

### 3.14.2 local Wattson opacity fix, 2026-11-03

- Inspected actual Wattson v24 onesie LOD0 CAST, imported material bindings, suit/gear opacity images and suit albedo. Opacity images have opaque alpha channels and black RGB masks over solid details.
- Before/after Cycles renders using Apex Shader+ confirm restoration of zipper, straps, gloves and knee equipment. Generated only isolated diagnostic scenes; source assets and user scenes unchanged.
- Scoped exception matches exact suit/gear opacity texture filenames; retained nodes allow manual use. Added regression coverage for all three shaders, repeated rebuilds, forced opacity override, renamed materials and an unrelated Wattson texture remaining connected.
- Blender integration: 45 tests passed on Blender 4.2.2 and 5.2.2, including previous Ash alpha regression. Packaged ZIP workflow suite: 56 tests passed on 5.2.2.
- Evidence: artifacts/wattson-inspection.log, wattson-render.log, wattson-before.png, wattson-fixed.png and 3.14.2 test logs.
