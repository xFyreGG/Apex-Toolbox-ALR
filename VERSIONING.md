# Toolbox release numbering

Public releases use normal versions: 3.9.1 -> 3.10.0 -> 3.10.1 (fixes),
then 3.11.0 for the next feature release.
Early access targets that next release: 3.11.0-beta.1, 3.11.0-beta.2, etc.
A beta is earlier than the public version with the same base number.

## Current transition

The prepared stable package is 3.10.0. It contains the work tested under the
unpublished 3.15.0 candidate, including the fixes through experimental 3.14.7.
3.15.0 is superseded, not a separate public release.
The first future early-access build will be 3.11.0-beta.1; it does not exist yet.

Previously distributed experimental versions keep their original numbers and
source tags. Label them legacy early access. Do not rename their internal version,
rewrite old release notes, or infer newness from their larger numeric versions.
Old bug reports and downloaded ZIPs must remain identifiable.

## Files and hosting

- Stable: Apex-Toolbox-ALR-3.10.0.zip on GitHub, tag v3.10.0.
- Future beta: Apex-Toolbox-ALR-3.11.0-beta.1.zip in private R2, key
  apex-toolbox/Apex-Toolbox-ALR-3.11.0-beta.1.zip.
- All supporter tiers retain early access. Public downloads stay on GitHub.
- An old experimental 3.10.0 ZIP already exists. Never overwrite it in R2.
  The new stable 3.10.0 is a different package on GitHub. Its SHA-256 is authoritative.
- The old local 3.10.0 ZIP was moved to dist/legacy-experimental/. Existing R2
  keys and public links remain unchanged. No server-side file rename is required
  for historical releases.

## Authoring a new build

Set bl_info.version to the three numeric components required by Blender.
Set RELEASE_SUFFIX to an empty string for public builds, or -beta.N for early
access. The sidebar version, ZIP builder, verifier and packaged tests use the
full label. Blender Preferences itself shows the numeric base version.

Rebuild and test after changing these values. A filename-only rename would leave
Blender reporting the wrong build. Keep historical testing records as history,
and record the new ZIP size and hash separately.

## Website release steps

The site accepts beta labels and orders beta.10 after beta.2. New beta builds
sort ahead of legacy development builds in the experimental picker. Only tested
versions explicitly approved in api/_shared/toolbox-beta-builds.js appear.
For each beta add matching notes in js/toolbox-build-info.mjs, update the verified
fallback metadata in api/_shared/creator-tools.js, upload the exact ZIP, then verify
listing and supporter download before deployment.

Publish stable 3.10.0 only after approval. Add its exact GitHub URL, size, hash and
feature notes to the stable registry and picker together. Update README availability
only after publication. Remove legacy experimental builds from promotion as the
latest early access; they are historical builds predating this stable release.
Do not advertise 3.11.0-beta.1 until it is built, tested and uploaded.

Users moving from a legacy experimental build with a higher numeric version
should install the stable ZIP manually and restart Blender. Version comparisons
cannot automatically infer this one-time numbering reset.
