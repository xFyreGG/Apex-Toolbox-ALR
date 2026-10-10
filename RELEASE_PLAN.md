# Apex Toolbox 3.11.0 stable release plan

Proposed public release: **Friday 23 October 2026**, only if the gates below pass.
Current public stable is **3.9.1** on GitHub. Current supporter experimental build is
**3.10.21** on R2. Keep the public stable ZIP on GitHub and experimental ZIPs on R2.
All supporter tiers retain experimental access.

Local candidate status on 10 October: **3.11.0** is packaged and has passed
the automated, real-export and installation checks recorded in `TESTING.md`.
The current public and supporter downloads have not changed. Next, upload the
candidate to R2, verify its gated download, and run the external supporter
test period before publishing the same ZIP and source on GitHub.

## Schedule

| Date | Work | Result |
| --- | --- | --- |
| 10-12 Oct | Freeze the feature list, preserve the exact 3.10.21 source and ZIP, and collect issues in one list. | A reproducible baseline and a short blocker list. |
| 12-16 Oct | Fix bugs and test the real RSX workflows below. Add regression tests for each confirmed failure. | A candidate build, with no new features added. |
| Fri 16 Oct | Finish validation and publish the 3.11.0 candidate to the supporter experimental channel. | One candidate ZIP, versioned notes and a rollback to 3.10.21. |
| 16-21 Oct | Run a minimum 72-hour supporter test with at least two users besides the maintainer. Triage reports daily. | A go/no-go decision on Wed 21 Oct. |
| Fri 23 Oct | If all gates pass, publish the exact tested ZIP and matching source on GitHub, then update the site's stable picker. | Public stable release and announcement. |
| 24-30 Oct | Watch feedback and download failures. Issue a patch only for a confirmed defect. | First-week support and a documented patch decision. |

If a release blocker is found during candidate testing, fix it, increment the
version, repeat the automated and real-export checks, and restart the 72-hour
candidate period. The date moves; the gate does not.

## What to harden first

1. **Model import:** Test one legend, one weapon, one Misc prop, and a batch of
   at least three differently sized models from separate RSX folders. Check
   search, group changes, selection persistence, side-by-side placement,
   textures, Undo, and a bad or missing CAST in the same batch.
2. **Animation rigs:** Test the Axle/Overdrive, Mirage/Holo and Horizon/Nova
   mappings, an ordinary `pilot_medium` rig, and an unrecognized rig under
   Other. Check linking, search, loading, removing, refresh, and save/reopen.
3. **Single animation:** Import an `animseq` CAST from `animrig` onto a selected
   armature. Check matched and missing bones, the default Allow Missing Bones
   setting, repeated loading, failed imports, Undo, and save/reopen.
4. **Scale and compatibility:** Try a large `mdl` folder and a large animation
   library. Confirm the picker stays usable and cancellation leaves the scene
   intact. Run the same smoke flow in Blender 4.2.2 and 5.2.2. Review older
   bone-selection operators in Blender 5.2, where pose selection uses
   `PoseBone.select` instead of `Bone.select`.
   The legacy IK helper must keep pole controls independent of the driven
   bones. Verify the hand and foot controls on a real legend in both versions.

Use disposable Blender files for this pass. For every failure, record the
Blender and Toolbox versions, RSX folder layout, exact steps, expected and
actual results, and the console error. Keep raw game exports out of the public
repository.

## Release gates

- No known crash, data loss, damaged `.blend`, broken installation, or regression
  in single-model import, batch import, rig linking, or animation loading.
- All automated checks pass on the exact candidate ZIP in Blender 4.2.2 and
  5.2.2. A fix gets a regression test when the case can be reproduced safely.
- The real-export matrix above passes, including one non-default RSX path.
- At least two external supporters complete the main model and animation flows.
  The candidate then runs for at least 72 hours without a release blocker.
- Documentation, version number, credits, GPL licence, archive filename, file
  size and SHA-256 match the actual ZIP. No user-supplied RSX exports or private
  files are included in the public source or archive.
- The Creator Tools page shows the correct details for the selected version.
  Legend, Kill Leader, Champion and Apex Predator can get the experimental
  candidate; signed-out users cannot. The public stable download remains open.

Minor cosmetic issues can be listed in release notes. Do not promote a build
with a known import, animation, access-control or download failure.

## Candidate and public release procedure

1. Commit the exact source used for the candidate. Bump `bl_info["version"]`,
   update `RELEASE_NOTES.md`, `README.md` and `TESTING.md`, then build one ZIP
   with `py -3 tools/build_release.py`. Never replace a published ZIP at the
   same version.
2. Run the checks below against source and the extracted release ZIP. Check
   archive contents and compute its SHA-256. Test the UI with real exports.
3. Upload the candidate to R2 at
   `apex-toolbox/Apex-Toolbox-ALR-<version>.zip`. Add only that tested version
   to the site's experimental picker and metadata. Verify the live listing
   reports the correct filename and byte size. Keep 3.10.21 available as a
   fallback during candidate testing.
4. Put one feedback post in the Toolbox feedback forum with the candidate
   version, test steps and the issue-report format above. Fix only confirmed
   blockers or high-impact regressions during the candidate period.
5. On a go decision, tag the exact tested source and publish the **same ZIP**
   as a public GitHub release. Update the site's stable picker, details and
   GitHub URL. When stable catches up to experimental, show a clear "No newer
   experimental build" state rather than leaving an older build behind the
   supporter gate. Check that behaviour before the public release.
6. Verify the live stable download, old stable versions, supporter access and
   version-specific text. Then publish the Discord and social announcements.

## Supporter candidate check

Ask at least two supporters to try the exact 3.11.0 ZIP in their own Blender
projects. They should report their Blender version and RSX export layout.

1. Install the ZIP and confirm the Apex Tools sidebar opens.
2. Import and texture a legend, weapon and prop from separate `mdl` folders.
   Check the legend selector, search and side-by-side placement.
3. Link a legend animation rig from `animrig`, load a clip, remove it to return
   to the rest pose, then import one `animseq` CAST directly.
4. Save and reopen the `.blend`, reload the clip, and check the model and
   textures still look correct. Try the same on a second legend if available.
5. Post any failure in Toolbox feedback with the Toolbox and Blender versions,
   the export folder names, steps to repeat it, expected and actual results,
   and the console error. Do not attach raw game exports publicly.

## Local automated checks

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

`TESTING.md` contains the optional real-export, animation-scan and Cycles
render checks. Run them before the candidate is promoted, and record the
results in its release notes.
