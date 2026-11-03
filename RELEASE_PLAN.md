# Apex Toolbox 3.15.0 stable release plan

3.15.0 consolidates the model, animation and material work through 3.14.7.
It is being prepared locally for stable release. Preparation does not publish
anything or change the website. Keep existing downloads available until the
maintainer authorizes publication.

## Release gates

- Run the Python suites, Blender integration and exact-ZIP workflow suites on
  Blender 4.2.2 and 5.2.2. Check clean installation, enable/disable/reload,
  materials, model imports, saved animation indexes, automatic rig matching,
  row/grid placement, moved library paths and additive layers.
- Run disposable foreground checks for model-folder selection, direct import,
  Undo/Redo, animation layers and relinking. Test real RSX model exports.
- Record the exact ZIP size and SHA-256 in TESTING.md. Verify that the archive
  matches source and contains no exported game files or private artifacts.
- Keep documented limitations visible: game material intent cannot always be
  inferred from alpha pixels; corneas use an approximation; animation support
  depends on the exported rig and clips. No external supporter test is required.

## Publication, after maintainer approval

1. Publish the tested source and exact ZIP as GitHub release v3.15.0, with the
   consolidated notes in RELEASE_NOTES.md. Do not rebuild after recording its hash.
2. Add 3.15.0 to the website stable picker and make it the default. Keep older
   public releases selectable. Update selected-version features, compatibility
   and file size together. Stable downloads use GitHub.
3. Update the public README to describe 3.15.0 as available only once the release
   exists. Remove the old 3.11.0 early-access promotion. Older experimental builds
   must not be advertised as newer than stable. Future experimental builds remain
   on R2 behind the gate for all supporter tiers.
4. Verify the live ZIP hash and website links, then publish the approved
   announcements. Keep the previous stable available for rollback.

## Follow-up

Check feedback and download failures during the first week. Ship patches for
confirmed defects, with focused regression checks. Do not overwrite a released ZIP.
