# Repair the cause, keep the useful work

| Symptom | Likely investigation | Repair and evidence |
| --- | --- | --- |
| A duplicate roof or tree appears behind a moving cutout | Backing plate still contains the original object | Reconstruct the clean background; inspect camera extremes |
| A bright/dark halo appears around smoke | Matte contamination, alpha convention, resampling, or clipped translucency | Inspect on light/dark backgrounds; repair the derivative and preserve wisps |
| A visible checkerboard moves with the asset | Proofing pattern is baked into opaque pixels | Obtain or create real alpha; verify actual decoded alpha |
| A flame or smoke plume changes apparent size erratically | Each cel was independently fitted to its bounds | Register a common pivot/scale; preserve intended shape variation |
| A house wobbles while only its windows should move | Stable geometry changed across generated frames | Keep a fixed base and animate internal masked detail |
| Smoke drifts off its chimney | Parent/depth/coordinate mismatch | Attach to the same rig/socket; review the full cycle |
| Window animation barely shows | Bright base leaves no emissive range | Separate/dim the base and review lights off/on |
| A border strip appears midway through playback | Camera range exceeds painted coverage | Reduce motion or extend the backing/overscan; check all extremes |
| First/last states match, but the loop still jumps | Duplicated endpoint, stepped path, wrong phase, or cadence | Inspect N−1→0 and neighboring transitions; correct export/timing |
| Noise feels like static despite a smooth join | Continuous hiss/bright crackle dominates the sound design | Re-audition sources, preserve quiet, soften/replace the responsible layer |
| A bell becomes irritating | A distinctive event repeats every short picture loop | Use a longer sound master and sparser explicit cue schedule |
| Quiet effects produce sharp peaks after gain | High crest factor in an otherwise quiet source | Measure source levels; round isolated transients and set gain intentionally |
| Audio gets weak on a phone | Excessive width, bass reliance, masking, or phase cancellation | Check mono/small speaker; restore the focal sound in the midrange |
| Extracted audio is slightly longer than video | Codec padding/priming or edit-list interpretation | Compare actual presentation interval using a timeline-aware decoder |
| A generation seems missing | UI/navigation/retrieval failed; job may have succeeded | Reconcile the original request, then retrieve; avoid duplicate spending |
| An export action succeeds but no file is found | Browser download path or unsupported blob behavior | Verify the file; use a visible/copyable data fallback for scene JSON |
| A gate was passed before a source changed | Old review no longer matches current inputs | Use `status`, repair if needed, and record the affected review again |

A guessed cause is a hypothesis. Record the symptom and inspect before fixing. Change the smallest responsible source or recipe; preserve unrelated accepted work. Keep a short defect note with asset/layer/cue, timestamp, cause found, repair, and verification.
