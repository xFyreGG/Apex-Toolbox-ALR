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

## Run the checks

Pure Python (no Blender dependency):

```text
python Apex_toolbox/apex_tex/tests/run_tests.py
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
```

The archive is written to `dist/`, takes its version from `bl_info`, preserves the
`Apex_toolbox/` root and bundled assets, and omits test files and Python caches.
The build verifies the archive contents and CRCs. It does not install, publish
or change the user's Blender preferences.

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
