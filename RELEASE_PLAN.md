# Apex Toolbox 3.11.0 public release plan

Release timing: **hold the public 3.11.0 release while the experimental channel
has an awareness window**. The build is ready for promotion, but readiness is
not a reason to publish it immediately. There is no supporter testing quota or
72-hour waiting period. The public stable is currently **3.9.1** on GitHub;
the latest supporter experimental build is **3.11.0** on R2 and Creator Tools.
All supporter tiers retain early access. Release 3.11.0 publicly when the
maintainer decides the preview has had enough exposure and the stable website
update is ready.

Development has now moved to **3.14.1 experimental**, adding import checks,
batch grid placement, separate model collections, export-library relinking and
additive animation layers. Saved animation indexes and automatic legend rig
linking remain included; temporary animation previews remain removed. This
candidate is local and does not change this
3.11.0 public release plan. Use the 3.11.0 source at commit `0431a99` when
preparing its public release; the current development checkout contains 3.14.1.

Before offering 3.14.1 to supporters, finish the checks recorded in `TESTING.md`,
including the exact ZIP on Blender 4.2.2 and 5.2.2. Check the import review,
row/grid placement, moved export paths and additive layer removal in a disposable
foreground scene. Then upload that ZIP to a new versioned R2 key and update its
Creator Tools entry with the matching features, size and version. Keep 3.11.0
available as the preceding supporter build. Publishing this candidate is a
separate step from preparing it locally.

The local 3.11.0 ZIP passed the source, packaged add-on, real RSX export,
installation, animation and render checks recorded in `TESTING.md` on
10 October 2026. The maintainer also reported that the installed build works
as intended in their Blender setup. The R2 listing reports the expected
3.11.0 filename and exact ZIP byte size. Public stable remains 3.9.1. The
3.11.0 ZIP includes the add-on source and licence for recipients.

## Awareness window

1. The public GitHub README and Creator Tools page now describe the available
   3.11.0 preview. Keep them aligned as builds change.
2. Record three short, practical demos: selecting several model folders and
   importing them side by side; finding a legend rig and a named animation;
   and importing a single animation CAST. Show the result in Blender, with
   captions and the Creator Tools URL.
3. Publish the demos over two to three weeks through ALR's Discord, X and
   short-form video accounts. Share in relevant creator communities where
   project posts are allowed. Lead with the free 3.9.1 download and show the
   supporter preview as the optional way to use the newer workflows now.
4. Track Creator Tools visits, clicks on the stable and experimental paths,
   completed downloads and supporter joins. Review which demo led to useful
   engagement. A small audience is not a reason to delay indefinitely; use
   the data to decide whether the next step is another demo, better onboarding
   or the public release.

## Checks before public release

1. The ZIP was installed and enabled in clean Blender 4.2.2 and 5.2.2
   profiles during internal testing. The maintainer has also used the build
   in Blender. Repeat these checks if the ZIP changes before public release.
2. Import and texture one legend, one weapon and one Misc prop from separate
   RSX model folders in one batch. Check group filters, search, selection
   persistence, side-by-side placement, textures and Undo. Repeat a single
   import using an RSX path outside the maintainer's usual library location.
3. Link a legend animation rig from `animrig`, load a clip, remove it to return
   to rest pose, then import one `animseq` CAST directly. Confirm Allow Missing
   Bones starts enabled. Save, reopen and reload the clip. Check the Axle,
   Mirage and Horizon rig mappings in the picker.
4. Confirm the version, ZIP size, SHA-256, release notes, credits and licence.
   The ZIP must contain the add-on only, with no game exports or private files.
5. Prepare and review the website's stable picker entry for 3.11.0. It must
   display the selected version's features and metadata, link to the GitHub
   release, and keep older public releases available. Older supporter builds
   must not be presented as newer than stable 3.11.0. If a newer experimental
   build has been published by then, keep it available to supporters; otherwise
   show that no newer experimental build is available.

The automated and real-export checks in `TESTING.md` already passed. Repeat
them only after a code or package change, or to investigate a specific failure.
If a blocker appears in the final hands-on check, fix it, build a new version,
and rerun the affected checks before publishing. Do not overwrite an already
published version's ZIP.

## Release gates

- No known crash, data loss, damaged `.blend`, broken installation, or
  regression in model import, batch import, rig linking or animation loading.
- The exact ZIP being published passes the packaged checks in Blender 4.2.2
  and 5.2.2, plus the maintainer's foreground workflow check above.
- Documentation, version number, filename, size and SHA-256 match the ZIP.
  No raw RSX exports or private files are included.
- The website update is ready to publish alongside the GitHub release.
  Stable 3.11.0 is public, older stable builds remain selectable, and the
  experimental area accurately reflects whether a newer build is available.

There is no external tester requirement. Record any issue with the Blender and
Toolbox versions, RSX folder layout, steps to repeat it, expected and actual
results, and the console error. Keep raw game exports out of the public repo.

## Publication sequence

1. After the awareness window, prepare the release from the matching 3.11.0
   source checkout (starting at `0431a99`, not the newer development checkout),
   confirm the release source commit and run
   `py -3 tools/verify_release.py`
   against `dist/Apex-Toolbox-ALR-3.11.0.zip`. Record its SHA-256. Publish the
   exact tested source and ZIP on GitHub as `v3.11.0`, using the prepared
   release notes. Do not rebuild the ZIP after this check.
2. Publish the website update: add 3.11.0 to the public stable picker with its
   GitHub download URL, version-specific details and file size. Keep 3.9.1,
   3.9.0 and 3.8.0 in the picker. Hide or clearly label the older 3.10.21
   experimental build until a newer experimental release exists.
3. Verify the live 3.11.0 GitHub ZIP download, its SHA-256 and the website
   link. Switch the website picker through each stable version and confirm the
   details change with it. Check the experimental state while signed out and
   signed in. Then post the Discord and social announcements.
4. During the first week, check download failures and Toolbox feedback daily.
   Publish a patch only for a confirmed defect. Keep the preceding stable
   version available for rollback; if 3.11.0 has a serious issue, remove it
   from the site's default selection and link to the previous stable release.

## Local checks

Run from the repository root in PowerShell. Use a fresh Blender process for
each integration suite. Repeat the Blender commands with the 4.2 executable.

```powershell
py -3 Apex_toolbox/apex_tex/tests/run_tests.py
$blenderExe = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $blenderExe --background --factory-startup --python-exit-code 1 --python tests/blender_integration.py
& $blenderExe --background --factory-startup --python-exit-code 1 --python tests/workflow_integration.py
py -3 tools/build_release.py
py -3 tools/verify_release.py
& $blenderExe --background --factory-startup --python-exit-code 1 --python tests/package_smoke.py
& $blenderExe --background --factory-startup --python-exit-code 1 --python tests/workflow_integration.py -- --release
& $blenderExe --background --factory-startup --python-exit-code 1 --python tests/enable_smoke.py
```

`TESTING.md` records the optional real-export, animation-scan and Cycles
render checks already completed for 3.11.0.
