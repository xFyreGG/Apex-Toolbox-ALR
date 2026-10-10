# Apex Toolbox 3.11.0 public release plan

Release timing: publish after the maintainer's final hands-on check and the
website update are ready. There is no supporter trial or 72-hour waiting
period. The public stable is currently **3.9.1** on GitHub; the last supporter
experimental build is **3.10.21** on R2. Do not upload 3.11.0 to R2 as an
experimental build. All supporter tiers retain access when a newer
experimental build is available.

The local 3.11.0 ZIP passed the source, packaged add-on, real RSX export,
installation, animation and render checks recorded in `TESTING.md` on
10 October 2026. The current public and supporter downloads have not changed.

## Remaining release checks

1. Install `dist/Apex-Toolbox-ALR-3.11.0.zip` in a clean foreground Blender
   4.2.2 and 5.2.2 profile. Open the Apex Tools sidebar and use a disposable
   project for the following checks.
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
   release, and keep older public releases available. The current 3.10.21
   supporter build must not be presented as newer than stable 3.11.0. Show
   that no newer experimental build is available until one is published.

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
  experimental area accurately explains that no newer build is available.

There is no external tester requirement. Record any issue with the Blender and
Toolbox versions, RSX folder layout, steps to repeat it, expected and actual
results, and the console error. Keep raw game exports out of the public repo.

## Publication sequence

1. Confirm the release source commit and run `py -3 tools/verify_release.py`
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
