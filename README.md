# gta6-trophy-rarity-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Anggit98tkj/gta6-trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Anggit98tkj/gta6-trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A forecaster for every Grand Theft Auto VI PlayStation 5 trophy's earn rate on Exophase at 2026-11-26T00:00:00Z. It is built around one fact the house baseline ignores: an Exophase rate is earners divided by players tracked, and when Exophase refreshes, the tracked base jumps and most rates fall. On launch night the base went from 638 to 3,868 players and every rate but the 100% one dropped, a median of 1.59 logit units. This program expects that: it sorts each trophy by kind from its description, climbs the already tracked players toward a ceiling for that kind, grows the tracked base, and dilutes the result by the newcomers, who arrive mostly empty handed. For a short horizon it mixes two worlds, no refresh and refresh, into wide honest quantiles; for the seven day horizon it widens the band with the square root of time. It is plain Python 3.13 standard library, offline, deterministic, and reads only the case files it is given.

## Run it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The program reads every `<id>.in` case file in the input directory and writes one `<id>.out` forecast per case to the output directory, with five quantiles per trophy. It needs no network, no packages, and no arguments, and it finishes in well under the 8 second limit.

<sub>Entered on [make.fun](https://make.fun/?ref=e5tq5tyr&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
