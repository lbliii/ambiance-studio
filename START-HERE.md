# Make your first ambiance film

This folder is a small studio you can hand to another person. For the current repository and CLI, start with [README.md](README.md) and the [CLI guide](docs/CLI.md). It contains the process, agent skills, an example asset library, a layer editor, and review tools. You bring an image or an idea and make the creative choices. The agent handles the production work that its connected tools can actually perform.

## The easiest first session

1. Open the **ambiance-studio repository folder itself** as the project in Codex. Keep its hidden `.agents` folder with it.
2. Attach the image you want to animate. A clear focal subject, room behind foreground elements, and coherent lighting make a useful starting point.
3. Paste the prompt below. Tell the agent your generation spending limit if you want it to use paid services.
4. Review the composition/style proof, a draft with sound, and the final file. You do not need to manage coordinates or approve every production step.

> Use $ambiance-produce and this studio's playbook to turn my attached image into a layered, looping ambiance film. Preserve the image's artistic identity. Deconstruct it into depth layers, plan clean backgrounds and attachments, and use painted cel sequences for the features that benefit from changing drawings. Develop a sound story with separate music and environmental sources. Start a new project, inspect available tools, and keep sources, scene data, reviews, and reusable assets organized. Make routine production decisions yourself. Show me the main creative checkpoints, and tell me which checks actually ran. My generation budget is [enter a limit, or say “planning and existing assets only”].

If a skill does not appear, ask: **“Read `.agents/skills/ambiance-produce/SKILL.md` in this folder and follow it for this project.”** The whole folder must travel with the skills because they link to the studio guides and tools. This package does not install global account configuration.

Codex documents repository-local skills in `.agents/skills`, with explicit invocation or automatic selection based on their descriptions. [Official skill guidance](https://learn.chatgpt.com/docs/build-skills). Verified September 10, 2026; exact UI labels may change.

## What you should expect

- **First:** a readable plan showing what will move, what stays fixed, what needs to be drawn behind objects, and the intended sound.
- **Then:** a draft whose individual layers and painted frame sequences can be inspected.
- **Then:** music and environmental details that support the same mood.
- **Finally:** the video, cover, audio masters/stems where requested, reusable assets, and a report of completed and open checks.

The full process is documented, but the packaged software is not yet a one-click image-to-video application. The editor supports placement, named attachments, cel playback, full-cycle preview checks, and project-specific loading through `ambiance preview`. A separate script registers and packs prepared transparent cels. General asset extraction and soundtrack generation use the agent's available production tools; the CLI provides shared-scene rendering, verification, and explicit PCM mixing. If a provider is unavailable, planning and local preparation can continue; the agent should identify the actual missing capability.

## Find your current movie

Run `./ambiance studio open` and bookmark `http://127.0.0.1:8783/`. Open a project and choose **Watch current version**. Score, effects-only and silent choices stay within that version; earlier versions and exact-version links remain available. The scene editor is a separate working view. See the [studio library guide](docs/STUDIO-LIBRARY.md).

## Try the existing scene without spending credits

Ask Codex:

> Run the studio's local layer editor so I can explore The Last Lantern. Explain how to select an object, adjust its depth, move an attached group, and change a sprite's cycle. Keep the original scene intact.

Or run these commands from this folder:

```sh
./ambiance doctor
./ambiance --project projects/last-lantern project check
./ambiance --project projects/last-lantern preview --port 8784
```

Open `http://127.0.0.1:8784/editor/`. Stop the server with Ctrl-C. It serves only local files. The editor includes copyable scene JSON if a browser download does not save normally.

See the [rig workbench guide](docs/RIG-WORKBENCH.md) for the new tools and a five-minute walkthrough.

## How to give useful feedback

Describe the feeling and the location of the issue: “The left branch moves too much,” “The house should feel warmer,” “The bell makes the loop obvious,” or “I can see a dark halo around the smoke.” A timestamp or selected layer helps. The agent should fix the responsible source or recipe and repeat the affected checks.

For the final check, play three repeats on your phone. Listen at a comfortable low volume. Say what device you used and which exact file you reviewed. “I like it” establishes a creative preference; it does not establish that you listened in mono or checked a phone speaker.

## Read only what you need

- [Studio map](README.md): what's included and where it lives.
- [Art and motion guide](docs/STYLE-GUIDE.md): the character we are trying to preserve.
- [Quality gates](docs/QUALITY-GATES.md): how we decide something is ready.
- [Operator commands](docs/OPERATIONS.md): project creation, review records, and recovery.
- [Last Lantern case study](examples/last-lantern/CASE-STUDY.md): concrete decisions and known limits.
- [Scaling roadmap](docs/SCALING.md): how this becomes a more capable production system.

The optional `last-lantern-production-reference.zip` contains the finished 48-second film, original production sources, sound session, and native scripts. The everyday studio does not require that larger archive to run its editor.
