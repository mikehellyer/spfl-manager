# SPFL Manager

A modern tribute to the classic **C64 Football Manager 2**, set in Scottish football:
all 42 SPFL clubs (2026/27 line-up) from the Premiership right down to League Two,
with their real squads.

> Unofficial fan project, not affiliated with or endorsed by the SPFL, its clubs or Commodore.

## Install

Download the installer for your computer from the
[latest release](https://github.com/mikehellyer/spfl-manager/releases/latest):

- **Mac** (Apple Silicon): `SPFL-Manager-x.y.z-macOS.dmg`. Open it and drag *SPFL Manager* to
  Applications. The app isn't signed with an Apple developer certificate, so the first time you
  open it macOS will block it. Go to *System Settings → Privacy & Security* and click
  **Open Anyway**.
- **Windows**: `SPFL-Manager-x.y.z-Windows-Setup.exe`. It adds a Start Menu shortcut and,
  optionally, a desktop icon. If SmartScreen warns you, click *More info → Run anyway*.
- **Linux** (Pop!_OS / Ubuntu / Debian): `spfl-manager_x.y.z_amd64.deb`. Install it with
  `sudo apt install ./spfl-manager_x.y.z_amd64.deb`. It appears in your app menu.

When a new version comes out, the game's main menu shows **Update available**. Choosing it
downloads the installer for your computer.

## Run from source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python main.py
```

Controls: number keys / arrows + RETURN, or the mouse. Left-click selects, and **right-click (or ESC) goes back** on every screen. On the squad screen one click picks or drops a player. **F11** toggles fullscreen.
In the highlights, **SPACE** switches to fast-forward and **ESC** skips to full time.

## What's in v0.1

- C64 boot/loading intro, then a demo-style title screen (rasterbars, sine scroller, chiptune)
- Choose any club in any division (League Two is the classic "start at the bottom")
- Squad screen: pick your XI in any shape; defence/midfield/attack ratings, fitness, injuries
- 38-game Premiership with the real split: after 33 games it splits into a top six and a bottom
  six, each club plays the other five in its half once, and nobody can cross the split
- 36-game Championship, League One and League Two. Their play-offs start while the Premiership
  plays its last two rounds
- Scottish Cup (6 rounds, penalties for drawn ties)
- Transfer market (bid for players) and selling players
- Finances: gate receipts, TV money, wages, bank loans, board warnings and the sack
- Animated match highlights with club kits, goals, saves, misses and the woodwork
- Crowd sound: a background murmur, a roar for goals, an "oooh" for saves and near misses, and
  boos for refereeing decisions against the home side (offside goals, penalty appeals waved away,
  soft free kicks, bookings). When you're the away side your travelling fans boo too
- Promotion and relegation with the real SPFL play-offs (two legs, aggregate score, then penalties):
  - Premiership: Championship 2nd-4th fight it out, and the winner plays the Premiership's 11th
  - Championship and League One: the higher division's 9th plus the lower division's 2nd-4th
  - League Two: the bottom club plays the Highland/Lowland League play-off winner. Lose and you
    drop out of the SPFL, which ends the game. Clubs that drop out can come back up later.
- Season awards, ageing, retirements and a youth intake that tops squads up to 18
- Fitness matters: tired players play worse, so rotate your squad (the pre-match screen warns you)
- Autosave every week (`~/.spfl_manager/savegame.json`)
- Update checker: tells you when a newer release is out on GitHub (it never downloads anything by itself)

## Squad Editor

The editor works on two things:

- **Current save:** your career in progress. Open it with *Squad Editor* on the in-game main menu,
  or from the title screen. You can edit a player's name, position, skill, age, fitness and
  injury, and add, delete or move players. It works on a copy, so nothing changes until you
  press **S**, and choosing *Discard* leaves your career exactly as it was. Clubs must keep at
  least 13 players. The border is orange so you can tell you're editing a save.
- **Squad database:** the players every **new** game starts with (title screen → Squad Editor →
  Squad database):

- LEFT/RIGHT picks the division and RETURN opens a club. **+/-** changes a club's strength, which
  sets the estimated skill of any players you haven't rated yourself.
- In a club, RETURN edits a player (name, shirt number, position, skill, age, on loan), **N** adds a
  player, **D** deletes one, and **M** moves a player to another club.
- Values marked `~` are estimates. Once you set a value it turns green, and DEL on a skill or age
  field hands it back to the estimate.
- **S** saves to `~/.spfl_manager/squads.json`. The shipped Wikipedia data is never changed, and
  **R** on the club list throws away all your edits.

## Project layout

```
src/spfl_manager/core/   game logic (no pygame) - data, models, match engine, season
src/spfl_manager/ui/     pygame front end - intro, screens, highlights, sound
tests/                   pytest tests for the core
```

League membership, stadiums, kit colours and club strength are in
`src/spfl_manager/core/data.py`.

Real squads are in `src/spfl_manager/core/squads.json`: 1,064 players taken from each club's
Wikipedia "Current squad" section on 28 Sept 2026. That covers first-team players and loan
signings, but not players loaned out to other clubs. Real dates of birth (from Wikidata) are
included for about 650 of them. Skill ratings are game estimates based on the club's
strength, and players without a known date of birth get an estimated age. Edit the JSON to
correct anything, or use the Squad Editor.

## Sounds

The crowd effects are WAV files in `src/spfl_manager/assets/sounds/`, generated by
`tools/make_sounds.py` from dozens of synthesised voices shaped into vowels ("aah", "oo").
To tweak them, edit that script and run it (it needs numpy, which is in requirements-dev.txt):

```bash
.venv/bin/python tools/make_sounds.py
```

## Building installers

`tools/build.py` builds the installer for the computer it runs on, using PyInstaller plus
`hdiutil` (Mac), Inno Setup (Windows) or `dpkg-deb` (Linux). You don't normally run it
yourself: pushing a version tag makes GitHub Actions build all three, self-test each packaged
app and attach the installers to the release:

```bash
git tag v0.8.0 && git push origin v0.8.0
```

## Tests

```bash
.venv/bin/python -m pytest
```

## Credits

- Squad lists and player dates of birth come from [Wikipedia](https://en.wikipedia.org/) (each
  club's "Current squad" section) and [Wikidata](https://www.wikidata.org/), and are used under
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The squad data in
  `src/spfl_manager/core/squads.json` is shared under the same licence.
- Inspired by Kevin Toms' *Football Manager* series, especially *Football Manager 2* on the Commodore 64.
