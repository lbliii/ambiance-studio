# Amberwatch operator audit evidence

These eight scripts are preserved byte-for-byte from the Amberwatch production workspace for the [operator audit](../../architecture/AMBERWATCH-GLUE-AUDIT.md). They are historical evidence, not supported production commands or a runnable rebuild package. Do not execute them as a new workflow. Raw artwork, audio and the mutable production workspace are not bundled.

[script-identities.json](script-identities.json) records each script's SHA-256, creation/modification times and physical line count. Its `scripts[].file` paths resolve relative to this directory. Filesystem creation times establish when a script existed, not exact invocation times. The production checkout and inspected tracking ref are the identities from that earlier audit, not a claim about current main.

The [clean-component research](../clean-components-2026-09-12/report.md) separately preserves exact v3/v4 scene, raster and move-diagnostic evidence. Original paths within scripts and records describe historical provenance, not locations to resolve in a new checkout. No new operator, visual or listening trial is established by preserving these files.
