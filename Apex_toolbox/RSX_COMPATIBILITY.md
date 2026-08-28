# Auto_tex + RSX compatibility

Apex Toolbox v3.8.0

Auto_tex now understands both the classic **Legion+** export convention and
current **RSX → CAST** exports. Nothing was removed: the legacy behaviour is
one layer of the new resolver, not a thing that was replaced.

---

## 0. The workflow

1. In RSX, export the model as **CAST**.
2. Enable **Export Material Textures**.
3. Use these recommended settings:
   - Model Format: **CAST**
   - Material Texture Naming: **Text**
   - Texture: **PNG (Highest Mip)**
   - Normal Recalculation: **None**
   - Export full asset paths: **Off**
   - Disable CacheDB Loading: **Off**
4. Import the `.cast` file into Blender.
5. Select the imported armature.
6. Open **Apex Tools → Model**.
7. Click **Set Correct Model Size**.
8. Select the model meshes to texture.
9. Open **Materials → Auto Texture**.
10. Choose **Apex Shader**, **Apex Shader+ v3.4**, or **S/G-Blender**.
11. Click **Texture Model**.
12. Texture discovery should normally happen automatically.

No texture folder needs to be chosen. If automatic discovery cannot work out
where the export lives, open **Search Options**, set the *Texture Search
Folder*, and press *Texture Model* again — after that the folder is remembered
and later models from the same export resolve on their own.

## 1. Recommended RSX settings

These are the settings the standard Blender workflow is documented and tested
against.

| RSX setting | Recommended | Why |
|---|---|---|
| **Export → Export Material Textures** | **ON** | Auto_tex cannot recreate files RSX was told not to write. |
| **Export → Export full asset paths** | **OFF** | Keeps the export portable and self contained. Auto_tex works either way. |
| **Export → Disable CacheDB loading** | **OFF** | Lets RSX use real asset names where it has them. Auto_tex does not depend on it. |
| **Export (Textures) → Material Texture Naming** | **Text** | Keeps real names where available and falls back to a meaningful generated name. |
| **Export (Textures) → Normal Recalculation** | **None** | Texture discovery does not depend on this. See §7. |
| **Asset Settings → Model (mdl_) → Format** | **CAST** | The officially supported RSX → Blender path. |
| **Asset Settings → Texture (txtr) → Format** | **PNG (Highest Mip)** | Avoids mip variants entirely. Other Blender-readable formats still work. |

You do **not** need `Export asset dependencies`, full paths, standalone
material export, or any manual renaming of files or Blender materials.

### Alternative settings that are also supported

| Material Texture Naming | Status | How it resolves |
|---|---|---|
| **Text** | Recommended | Real names, or generated meaningful names → recognised directly. |
| **Real** | Supported | Original Apex asset names (`..._col`, `_nml`, `_spc`, `_gls`, `_ao`, `_cav`, `_ilm`). Recognised directly. |
| **Semantic** | Supported | `..._albedoTexture`, `_normalTexture`, ... Identical to the Legion+ convention, so this is also the fastest path. |
| **GUID** | Supported *via CAST semantics only* | See §5. |

Texture formats: `.png`, `.dds`, `.tga`, `.tif`/`.tiff`, `.jpg`/`.jpeg`,
`.bmp`, `.exr`, `.hdr`, `.webp` and a few more. `.png` is never hard coded.

---

## 2. Why the old Auto_tex failed with RSX

The previous resolver did, in effect:

```python
imageNode  = nodes["Image Texture"]              # or nodes["0"]
imageName  = <blender material name>
imageFormat= image.split('.')[1]
nodes.clear()                                    # before anything was resolved
texImageName = imageName + '_' + 'albedoTexture' + '.' + imageFormat
```

Six separate assumptions, each of which RSX breaks:

1. **A node literally called `Image Texture` exists.** With current RSX,
   Apex materials are exported as a *specular/gloss* material, and the CAST
   importer builds an `ShaderNodeEeveeSpecular` graph. When the CAST material
   carries no texture bindings at all — which is what an RSX export in
   `Real` naming mode produces — there is no image node in the material at
   all, so Auto_tex hit the `except`, printed the material name, and did
   nothing.
2. **The texture basename equals the Blender material name.** With `Real`
   naming the basename is the original Apex asset name, and with `GUID`
   naming it is `0x…`. On the `overdrive_base_w` export two materials are
   themselves named `0xE5E0D66DD62EE` and `0xF7343CCD5ED99`.
3. **Roles are spelled `_albedoTexture`, `_specTexture`, …** RSX `Real`
   naming uses `_col`, `_spc`, `_nml`, `_gls`, `_ao`, `_cav`, `_ilm`. None of
   those were in `texSets`, so nothing matched.
4. **`image.split('.')[1]` is the extension.** It is not, for any name with
   more than one period, and it silently produced garbage.
5. **`nodes.clear()` before resolution.** The imported material was destroyed
   *before* Auto_tex knew whether it could texture it — throwing away the only
   evidence that identified the textures, and leaving a blank material behind
   when it failed.
6. **Bare `except:` everywhere.** Which also hid a second, unrelated bug: the
   Apex Shader+ node group has no socket called `SSS Map` or `Alpha`, so those
   links had *never* worked. See §8.

---

## 3. The new resolver

Texture discovery is now separate from shader construction. Discovery runs
once per material and produces one `role -> Resolution` map; each shader
adapter then maps those roles onto its own sockets.

Resolution hierarchy, highest confidence first:

| # | Layer | Confidence | What it uses |
|---|---|---|---|
| 1 | **graph semantic** | 100 | Roles the CAST importer already established in the node graph. Independent of file names — this is what makes GUID naming work. |
| 2 | **existing image** | 90 | An image datablock Blender already has loaded. |
| 3 | **legacy exact** | 80 | `<material name>_<role>Texture.<ext>` — the historical Legion+ probe, unchanged. |
| 4 | **family match** | 55–70 | Normalised texture-family matching (see §4). |
| 5 | **ambiguous / unresolved** | — | Reported, never guessed. |

Sequencing is non destructive:

1. inspect the material,
2. capture its semantics,
3. resolve,
4. validate,
5. build the replacement shader and connect,
6. **only then** remove the old nodes.

If resolution finds nothing, or the rebuild raises, the imported material is
left exactly as it was and is still usable.

### Reading the graph

Nodes are found by `bl_idname`, never by display name, so `Image Texture`,
`Image Texture.001` and any name the user typed all work. Supported source
graphs:

* `ShaderNodeBsdfPrincipled` (CAST metal materials, most other importers)
* `ShaderNodeEeveeSpecular` (CAST Apex specular/gloss materials)
* Apex Toolbox's own node groups — so re-running Auto_tex, or switching from
  one Apex shader to another, keeps every texture
* anything else: a conservative structural fallback that only trusts
  unambiguous shapes such as `Image → Normal Map`

Socket→role mapping handles the Blender version differences
(`Specular` vs `Specular IOR Level`, `Emission` vs `Emission Color`).
An image reached through another map's **Alpha** output is ignored — that is
a channel of a colour map, not a texture of its own.

---

## 4. Texture-family matching

Every file name is normalised the same way: directory dropped, Blender `.001`
datablock suffix dropped, extension split with `os.path.splitext`, then the
stem is split on separators **and** camel-case humps and lower cased.
Trailing filler (`texture`, `map`), mip/LOD markers (`_001`, `_level1`,
`_mip2`) and binding indices (`albedoTexture1`, `normal2Texture`) are peeled
off and recorded as *variants*, never read as roles. What remains in front of
the role word is the **family**.

The family of the current material is seeded from, best first:

1. the basenames of images the graph already proved belong to this material,
2. other images present in the material,
3. the Blender material name.

Because seed 1 exists, the material name does **not** have to be the shared
prefix, and `characters_wraith_skin42_body_nml.png` can be matched to
`characters_wraith_skin42_body_spec.png` no matter what the material is called.

Grades, deliberately coarse:

| Grade | Score | Meaning |
|---|---|---|
| exact | 100 | identical family tokens |
| indexed | 80 | `…_gear` vs `…_gear_1` (a repeated RSX binding) |
| same tail | 60 | same length, same trailing part, ≥ 0.7 token overlap |
| loose | 35 | **rejected** |

Anything below 50 is never connected. A body material therefore cannot pick up
the head material's textures out of the same folder, which is the common
failure mode for characters, weapons, charms and layered skins.

Ties are broken deterministically: family grade → canonical spelling of the
role word (`albedoTexture` outranks `col`, which preserves legacy behaviour
when an export folder contains both) → fewer variant markers → lower binding
index → nearer search root → **larger file** (so a full resolution image
always beats a lower mip) → path. If the top two candidates are still equal
*and* come from different families, the role is reported **ambiguous** and
left unconnected.

### Search roots (automatic since beta 4)

Beta 3 resolved textures perfectly *once it had a directory*, but it could only
find one from images the CAST importer had already loaded. When an RSX CAST
carries no texture bindings at all — which is what `Real` and `GUID` naming
produce — the imported material holds no images, and the user had to pick the
folder by hand.

The CAST importer stores no source path on the objects or collections it
creates (checked against io_scene_cast 1.6.7). What it *does* leave behind is a
**collection named after the .cast file**, e.g. `wraith_v20_heist_w_LOD0`.
Strip the LOD suffix and that is exactly the name of both the RSX export folder
and the texture folder inside it:

```
<export library>/wraith_v20_heist_w/wraith_v20_heist_w_LOD0.cast
<export library>/wraith_v20_heist_w/wraith_v20_heist_w/*.png
```

So Auto Texture derives the model name from what the importer named things and
then *probes* a small set of known layouts under every base directory it has
reason to believe in. Probing is a handful of `os.path.isdir` calls; no
directory is walked unless a probe has already matched or the user explicitly
asked for a recursive search.

Roots, best first:

| # | Root | Where it comes from |
|---|---|---|
| 0 | directory of an image the material already references | the CAST import itself |
| 1 | model folders beside/below that directory | RSX nests textures one level in |
| 2 | the **Texture Search Folder**, if set | the user, as an override |
| 3 | model folders found by probing a known layout | the probes below |
| 4 | export folders a previous run succeeded in | remembered in the add-on preferences |
| 5 | folders Blender's file browser was recently in | `bookmarks.txt` in the user config, read-only |
| 6 | directories of any other image in the blend | |
| 7 | next to the .blend file | |

Bases that get probed for `<model>`: the parents of the material's own texture
directory, the Texture Search Folder, every remembered export folder, and every
recently browsed folder **plus its parent** — so browsing to one model of an
export tells Auto Texture where all the others live.

Layouts probed: `<base>/<model>/<model>`, `<base>/<model>`,
`<base>/<model>/Materials`, `<base>/<model>/_images`, `<base>/mdl/<model>/<model>`,
`<base>/mdl/<model>`.

**Learning.** Every run that resolves something records the export folder and
its library directory (`…/mdl`) in the add-on preferences, capped at 8 entries.
The second and every later model of the same export then resolves with no
interaction at all, even in a brand new Blender session. `Preferences → Add-ons
→ Apex Toolbox` lists what is remembered and can clear it.

**Ordering.** The position in that list *is* the trust order. If two copies of
the same model exist on disk — say an RSX export and an older Legion export —
the one the user just imported from wins, including against the legacy exact
filename probe, which is not allowed to reach past a nearer root.

**When automatic discovery fails.** With no bookmarks, no memory, no loaded
images and no saved .blend there is genuinely nothing to anchor to. Auto
Texture then prints

```
[Auto_tex] Automatic texture root unavailable and no Texture Search Folder is set.
```

and the *Texture Search Folder* under **Search Options** is the fallback. It is
optional: leave it empty and Auto Texture searches automatically.

There is a hard ceiling of 40 000 files and six directory levels so that
pointing Auto Texture at a large export tree cannot turn into a long walk.
Paths are built with `os.path`/`pathlib` — no hard coded `\`.

## 5. GUID naming

A file called `0x47BCE128CF.png` says nothing about what it is, and Auto_tex
will not pretend otherwise. GUID names are never parsed for a role.

* **With CAST semantics** — the importer bound that image to a shader socket,
  so the graph already knows it is, say, the normal map. Auto_tex uses that.
  The report line is legitimately `albedo -> 0x47BCE128CF.png [graph semantic]`.
* **Without CAST semantics** — nothing but anonymous GUID files. Auto_tex
  reports `unresolved`. That is the correct answer; guessing would connect the
  wrong texture.

---

## 6. RSX settings that reduce what Auto_tex can see

**Export Material Textures = OFF.** The CAST still names its bindings, so the
importer creates the texture nodes and links but the image load fails and the
node is left empty. Auto_tex detects this and prints

```
[Auto_tex] Material textures referenced by CAST but source files are
unavailable. Re-export from RSX with 'Export Material Textures' enabled, or
set a Texture Search Folder.
```

and **leaves the imported material untouched**. It never invents files and
never blanks a working material.

**CAST with no texture bindings at all.** Some RSX exports write materials
with a name and nothing else. Since beta 4 this resolves automatically: the
model name comes from the collection the CAST importer created, and the base
directory from the file browser history or a remembered export folder (see
§4). Validated on `wraith_v20_heist_w` (RSX, `Real` naming) with nothing
configured at all.

**CacheDB disabled.** Names may be generated, semantic, incomplete or
GUID-like. The CAST semantic relationship is unaffected, so the graph layer
keeps working.

---

## 7. Normal maps

The normal texture is identified by graph structure
(`Image → Normal Map → Normal`) or by its role word, never by handedness and
never by the RSX **Normal Recalculation** setting. Texture *discovery* and
normal *orientation* are separate concerns.

**No green-channel flip was added.** The Apex shader groups already expose
their own normal controls (`S/G-Blender` even has an explicit
`OpenGL N ------- DirectX N` input), so an automatic flip here would fight the
shader. Existing Apex Toolbox normal behaviour is unchanged.

---

## 8. Roughness vs gloss

All three Apex Toolbox shaders want **glossiness**. The resolver reports what
the image *is*; the shader adapter knows what its socket *wants*, and only the
mismatch is converted:

* source is a **gloss** map → connected straight to the glossiness socket.
  A gloss map is never inverted.
* source is a **roughness** map → a `ShaderNodeInvert` is inserted, giving
  `gloss = 1 - roughness`, in the node graph. The image on disk is never
  modified.
* a gloss map found alongside a roughness map wins; the roughness result is
  reported as superseded.

This also survives a second run: an `Image → Invert → Glossiness` chain is
read back as *a roughness map*, so re-running Auto_tex inverts it exactly once
again rather than double inverting.

---

## 9. Shader socket maps

| Role | Apex Shader | Apex Shader+_v3.4 | S/G-Blender |
|---|---|---|---|
| albedo | `Albedo Map` | `Albedo` | `Diffuse map` |
| specular | `Specular Map` | `Specular` | `Specular map` |
| emissive | `Emission` | `Emission` | `Emission input` |
| scatter/thickness | `SSS Map` | `Scatter Thickness (Radius)` | `Subsurface` |
| opacity | `Alpha` | `Alpha (Opacity Multiply)` | `Alpha input` |
| normal | `Normal Map` | `Normal Map` | `Normal map` |
| gloss | `Glossiness Map` | `Glossiness` | `Glossiness map` |
| ao | `AO` | `Ambient Occlusion` | `AO map` |
| cavity | — | `Cavity` | `Cavity map` |
| anisoSpecDir | node only | node only | node only |
| iridescenceRamp | node only | node only | node only |

Albedo's alpha channel drives the shader's alpha socket, and the scatter map's
alpha drives the scatter alpha socket where one exists — then an explicit
opacity map overrides, which is the order the operator has always used.

**Two socket names were corrected.** Apex Shader+ has no socket called
`SSS Map` or `Alpha`; the previous release asked for those names and the
failed links disappeared into a bare `except: pass`, so scatter/thickness,
opacity and alpha were never actually connected on that shader. S/G-Blender
had the same problem with `Alpha` vs `Alpha input` (Recolor already used the
correct name). Both now match the real groups. `Anis-Spec Dir` also exists on
Apex Shader+, but Auto_tex has never driven it and connecting it would change
how existing models shade, so its node is still created and left for manual
wiring.

---

## 10. Colour spaces

The historical rule ("everything past index 2 of `texSets` is `Non-Color`") is
preserved, expressed semantically:

* **scene colour space**: albedo, specular, emissive
* **`Non-Color`**: normal, gloss, roughness, AO, cavity, scatter/thickness,
  opacity, anisoSpecDir, iridescenceRamp

`alpha_mode = 'CHANNEL_PACKED'` is still applied to every texture.

---

## 11. Diagnostics

One concise block per material:

```
[Auto_tex] Material: wraith_lgnd_v20_boosted_body
[Auto_tex] Source: RSX/CAST specular material
[Auto_tex] albedo -> wraith_lgnd_v20_boosted_body_col.png [family match]
[Auto_tex] normal -> wraith_lgnd_v20_boosted_body_nml.png [family match]
[Auto_tex] gloss  -> wraith_lgnd_v20_boosted_body_gls.png [family match]
[Auto_tex] emissive -> unresolved (closest rejected: ..._gear_ilm.png)
[Auto_tex] cavity -> ambiguous: cavity_a.png, cavity_b.png
```

Sources are `graph semantic`, `existing image`, `legacy exact` and
`family match`. Unresolved lines name the closest candidate that was rejected,
so it is obvious *why* nothing was connected.

---

## 12. Shared discovery

Auto Texture, **Recolour** and the **Toon shader** all go through the same
`resolve_for_objects` / `resolve_from_folder` entry points, so there is exactly
one texture-discovery implementation in the add-on. Recolour keeps its own
skin-folder selection logic but no longer carries a second hardcoded
`<name>_<role>Texture.png` probe, which means an RSX-named recolour folder now
works too.

## 13. Tests

`Apex_toolbox/apex_tex/tests/` — pure Python, no Blender needed:

```
python Apex_toolbox/apex_tex/tests/run_tests.py
```

Blender integration and real-export validation scripts live alongside the
release notes.
