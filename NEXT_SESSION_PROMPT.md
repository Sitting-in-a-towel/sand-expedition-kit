# First prompt for the dedicated SAND session

Paste into the session launched via `Claude-SAND.exe`. It's investigation-first — the goal is to learn what the game files allow before building anything.

---

This is the SAND community-tools project. Before any building:

1. Read `CLAUDE.md` and `RESEARCH_NOTES.md` in full.
2. **Confirmed decisions (don't re-litigate):**
   - The whole project is **100% OFFLINE / input-driven** — it never touches the running game or its memory (BattlEye = ban). All data = static file mining + user input.
   - SAND is **Unity (IL2CPP) + BattlEye**, NOT Unreal — so there's **no AES pak key**; use the Unity toolchain (AssetRipper, Il2CppDumper).
   - Game **launches 22 June 2026**; the local install at `H:\Steam Games\steamapps\common\Sand Playtest\` is the **PLAYTEST** (use it now for a head start).
   - NOT competitive — end goals: Discord bot, interactive map / seed-finder (Nightreign-style), build sharing.

3. **First job — the decisive investigation (present findings, don't build yet):** figure out which feasibility branch we're in by data-mining the playtest files:
   a. **COPY the files first — never touch the live install.** Copy `Sand_Data/`, `GameAssembly.dll`, and `Sand_Data/il2cpp_data/Metadata/global-metadata.dat` from `H:\Steam Games\steamapps\common\Sand Playtest\` into `SAND/datamine/gamefiles/` and run ALL extraction against that copy. (`datamine/` is gitignored — large/binary.) This guarantees we never read, modify, or run against the live game (BattlEye-safe).
   b. Set up **Il2CppDumper** (+ Il2CppInspector) on the copied `GameAssembly.dll` + `global-metadata.dat` → dump the C# class/struct/enum layout. Search for map/world **generation** logic and **seed** handling.
   c. Set up **AssetRipper** on the copied `Sand_Data/` → look for map/POI/loot/item ScriptableObjects.
   d. Answer the two questions that decide everything:
      - **Is the map seed-based (finite, predictable) or fully random per match?**
      - **Do POI types (lighthouse, fort, etc.) have SET loot tables + crafting recipes, or are they randomised per instance?** (Owner's leads: lighthouses → better loot, forts → crafting stations.) **Note:** the owner is separately testing this **in-game** by visiting POIs across matches — so the file-mining side is to find any fixed loot-table/recipe *definitions* in the data, which we then cross-reference against the owner's in-game observations.
   e. Report what's extractable + recommend the deliverable: seed-finder (branch 1), location/loot catalog (branch 2), or build-sharing focus (branch 3).

Save findings to `RESEARCH_NOTES.md` as you go (this PC can hard-crash at idle). Don't build the bot/site until we've confirmed the data we can actually get.

---
