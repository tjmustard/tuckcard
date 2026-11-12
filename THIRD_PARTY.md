<!-- generated, don't edit: run python tools/third_party.py -->

# Third-party notices

Tuckcard's own code, skills, docs, findings, rules, examples and layout prototypes are MIT; see `LICENSE`. This file lists everything else that ships or is installed for the tools, and the license each one carries.

## Fonts

All nine shipped font families are under the SIL Open Font License 1.1, and each folder carries its own `OFL.txt`.

| Family | Font files | License | License file |
| --- | ---: | --- | --- |
| archivo-black | 1 | SIL OFL 1.1 | `plugins/tuckcard/skills/cards-core/fonts/archivo-black/OFL.txt` |
| atkinson-hyperlegible | 4 | SIL OFL 1.1 | `plugins/tuckcard/skills/cards-core/fonts/atkinson-hyperlegible/OFL.txt` |
| caveat | 1 | SIL OFL 1.1 | `plugins/tuckcard/skills/cards-core/fonts/caveat/OFL.txt` |
| fraunces | 2 | SIL OFL 1.1 | `plugins/tuckcard/skills/cards-core/fonts/fraunces/OFL.txt` |
| liberation-sans | 4 | SIL OFL 1.1 | `plugins/tuckcard/skills/cards-core/fonts/liberation-sans/OFL.txt` |
| liberation-serif | 4 | SIL OFL 1.1 | `plugins/tuckcard/skills/cards-core/fonts/liberation-serif/OFL.txt` |
| literata | 2 | SIL OFL 1.1 | `plugins/tuckcard/skills/cards-core/fonts/literata/OFL.txt` |
| shantell-sans | 2 | SIL OFL 1.1 | `plugins/tuckcard/skills/cards-core/fonts/shantell-sans/OFL.txt` |
| source-serif-4 | 2 | SIL OFL 1.1 | `plugins/tuckcard/skills/cards-core/fonts/source-serif-4/OFL.txt` |

## Python dependencies

Each version below is the pin in the named requirements file. Each license was read from the installed distribution and checked against the allowed list; the check fails on a copyleft or unknown license.

| Package | Version | License | Pinned in |
| --- | --- | --- | --- |
| jsonschema | 4.25.1 | MIT | `requirements.txt` |
| Pillow | 11.3.0 | MIT-CMU | `requirements-dev.txt` |
| playwright | 1.60.0 | Apache-2.0 | `requirements-dev.txt` |
| pytest | 8.4.2 | MIT | `requirements.txt` |
| ruamel.yaml | 0.19.1 | MIT | `requirements.txt` |

## Node dependencies

None. The repository has no `package.json`.

## Word-familiarity list

No word-familiarity list is shipped. Every age band sets `familiarity_list: null`, so lint measures syllables and grade but does not check word familiarity.

If one is added later it needs its own license file and an entry here, and it must be permissive.

## Allowed licenses

An unfamiliar license is not treated as a pass. Each of these was added deliberately:

- `Apache-2.0`: permissive; attribution and patent grant
- `BSD-2-Clause`: permissive; attribution only
- `BSD-3-Clause`: permissive; attribution only
- `CC0-1.0`: public domain dedication
- `HPND`: historical permissive license; attribution only
- `ISC`: permissive; attribution only
- `MIT`: permissive; attribution only
- `MIT-0`: permissive; no attribution condition
- `MIT-CMU`: Pillow's MIT variant; permissive, attribution only
- `PSF-2.0`: Python Software Foundation license; permissive
- `Unlicense`: public domain dedication
- `Zlib`: permissive; attribution only
