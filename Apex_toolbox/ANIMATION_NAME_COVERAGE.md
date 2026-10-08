# Apex Toolbox v3.10.5 — Experimental animation name validation

English names are supplied by the plugin when linking or refreshing a rig. The playback test never imports a language file or item settings.

- Export folders audited: **31**
- Animation clips indexed: **15,627**
- Exact named clips: **1,082**
- Conflicting/unresolved name matches: **9** (export names retained)
- Rig libraries with successful sample playback: **27**
- Successful load → rest pose → cached reload samples: **105**
- Playback failures: **0**

Coverage is limited to the supplied exports. Names were checked for every indexed clip; playback sampled one named clip per available category (ground emote, skydive, banner and finisher). A passing sample does not verify every animation in that library.

| Export folder | Clips | Named | Playback samples | Result |
| --- | ---: | ---: | ---: | --- |
| pilot_heavy_caustic | 628 | 41 | 4 | Passed |
| pilot_heavy_gibraltar | 557 | 47 | 4 | Passed |
| pilot_heavy_newcastle | 681 | 34 | 4 | Passed |
| pilot_heavy_pathfinder | 652 | 51 | 4 | Passed |
| pilot_heavy_revenant | 740 | 46 | 4 | Passed |
| pilot_light_conduit | 588 | 31 | 4 | Passed |
| pilot_light_lifeline | 595 | 54 | 4 | Passed |
| pilot_light_lifeline_mythic | 0 | 0 | 0 | Incomplete export; playback untested |
| pilot_light_lifeline_op | 4 | 0 | 0 | Index only; no named cosmetic clips |
| pilot_light_wattson | 709 | 37 | 4 | Passed |
| pilot_light_wraith | 573 | 46 | 4 | Passed |
| pilot_medium_alter | 503 | 28 | 4 | Passed |
| pilot_medium_ash | 615 | 50 | 4 | Passed |
| pilot_medium_ballistic | 352 | 31 | 4 | Passed |
| pilot_medium_bangalore | 508 | 35 | 4 | Passed |
| pilot_medium_bloodhound | 422 | 47 | 4 | Passed |
| pilot_medium_bloodhound_old_ways | 4 | 0 | 0 | Index only; no named cosmetic clips |
| pilot_medium_catalyst | 447 | 34 | 4 | Passed |
| pilot_medium_crypto | 793 | 39 | 4 | Passed |
| pilot_medium_holo | 564 | 49 | 4 | Passed |
| pilot_medium_horizon | 593 | 41 | 4 | Passed |
| pilot_medium_loba | 481 | 46 | 4 | Passed |
| pilot_medium_madmaggie | 352 | 36 | 4 | Passed |
| pilot_medium_mirage_mythic | 1 | 1 | 1 | Passed |
| pilot_medium_overdrive | 367 | 28 | 4 | Passed |
| pilot_medium_rampart | 943 | 35 | 0 | Incomplete export; playback untested |
| pilot_medium_seer | 565 | 44 | 4 | Passed |
| pilot_medium_sparrow | 728 | 27 | 4 | Passed |
| pilot_medium_stim | 506 | 49 | 4 | Passed |
| pilot_medium_valkyrie | 649 | 41 | 4 | Passed |
| pilot_medium_vantage | 507 | 34 | 4 | Passed |

## Incomplete exports and notes

- **pilot_light_lifeline_mythic:** No exported animation clips; rig playback was not tested.
- **pilot_light_lifeline_op:** Index verified; no named cosmetic clips to sample in this variant.
- **pilot_medium_bloodhound_old_ways:** Index verified; no named cosmetic clips to sample in this variant.
- **pilot_medium_rampart:** TMP_mp_pt_crouch_grenade_aims_0.cast: Truncated CAST header. Re-export this file from RSX.
- **pilot_medium_rampart:** Standalone rig CAST is missing; names were audited but rig loading was not tested.

The source exports and the user’s working Blender scene were not modified. Tests ran in separate factory-startup Blender 4.2.2 processes.
