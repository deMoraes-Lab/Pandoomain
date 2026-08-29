# `hmm_curator.py`

Adds the two fields that *Pandoomain* needs to an HMM profile built with
`hmmbuild`.

---

## Contents

- [Why it is needed](#why-it-is-needed)
- [Quick start](#quick-start)
- [Choosing TC](#choosing-tc)
- [Options](#options)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Why it is needed

Profiles downloaded from Pfam or InterPro work as *Pandoomain* queries with no
extra steps. Profiles you build yourself do not, because `hmmbuild` does not
write two fields that the pipeline reads:

| Field | What it is | Where the pipeline uses it |
|---|---|---|
| `TC` | Trusted cutoff, a bit score | The search runs with `bit_cutoffs="trusted"` |
| `ACC` | Accession | Read as `hits.query_accession`; becomes the `query` column of `hmmer.tsv` |

Without them the run stops:

```
MissingCutoffs: Model 'TssX' is missing 'trusted' bitscore cutoff required by pipeline
```

and, if only `TC` is supplied:

```
AttributeError: 'NoneType' object has no attribute 'decode'
```

The second one is the more confusing failure, because the search itself
succeeds and the error appears only when the hit is parsed.

`GA`, `NC`, `DESC`, `BM` and `SM` are Pfam convention. *Pandoomain* does not
read them. They are written only if you ask for them.

---

## Quick start

Build a profile from an alignment, then curate it into `queries/`:

```sh
hmmbuild --amino -n TssX TssX.hmm TssX_alignment.fasta
utils/hmm_curator.py TssX.hmm --acc TssX.1 --tc 28.0 -o queries/TssX.hmm
```

The result carries what the pipeline needs:

```
NAME  TssX
ACC   TssX.1
TC    28 28;
```

`--acc` and `--tc` are the only required options.

---

## Choosing TC

`TC` is not boilerplate. It is the bit score below which a hit is **not**
counted as a member of the family, so it sets the sensitivity of the entire
search. Too low and unrelated proteins enter your neighborhoods; too high and
real members are missed.

Pfam curates it per family, usually as the score of the lowest-scoring sequence
still considered a true member. Different families get different values —
`PF05638` (Hcp) uses `23.5`, others do not.

There is deliberately no default. A practical way to pick one:

```sh
hmmsearch --max -o TssX_search.txt TssX.hmm reference_proteome.faa
```

Look at where the score distribution separates known members from the rest, and
set `TC` in that gap.

> **Note**
> Using one shared value across every profile is a scientific choice, not a
> formatting detail. It is worth revisiting per family before a large run.

---

## Options

```
utils/hmm_curator.py HMM --acc ACC --tc SCORE [SCORE] [options]
```

| Option | Required | Meaning |
|---|---|---|
| `HMM` | yes | The `.hmm` file to curate |
| `--acc ACC` | yes | Accession. A single token, no whitespace |
| `--tc SCORE [SCORE]` | yes | Trusted cutoff. One value sets sequence and domain thresholds together; two set them separately |
| `--ga SCORE [SCORE]` | no | Gathering cutoff |
| `--nc SCORE [SCORE]` | no | Noise cutoff |
| `--desc TEXT` | no | Description line |
| `--bm TEXT` | no | Build method line |
| `--sm TEXT` | no | Search method line |
| `-o PATH` | no | Write here |
| `--in-place` | no | Overwrite the input, keeping a `.bak` |

With neither `-o` nor `--in-place`, the profile is written to standard output
and no file is touched.

One profile per run. A file containing several is refused, because a single
`--acc` cannot describe more than one model.

---

## Examples

### Minimum

```sh
utils/hmm_curator.py TssX.hmm --acc TssX.1 --tc 28.0 -o queries/TssX.hmm
```

### With the optional Pfam fields

```sh
utils/hmm_curator.py TssX.hmm \
    --acc TssX.1 --tc 28.0 --ga 28.0 --nc 27.5 \
    --desc 'Type VI secretion protein TssX' \
    --bm 'hmmbuild TssX.hmm TssX_alignment.fasta' \
    -o queries/TssX.hmm
```

```
NAME  TssX
ACC   TssX.1
DESC  Type VI secretion protein TssX
GA    28 28;
TC    28 28;
NC    27.5 27.5;
BM    hmmbuild TssX.hmm TssX_alignment.fasta
```

### Separate sequence and domain thresholds

```sh
utils/hmm_curator.py TssX.hmm --acc TssX.1 --tc 31.2 18.7 -o queries/TssX.hmm
```

```
TC    31.2 18.7;
```

### Changing the cutoff on a profile that was already curated

```sh
utils/hmm_curator.py queries/TssM.hmm --acc TssM.1 --tc 31.5 --in-place
```

Values are replaced, not duplicated. The original is kept as
`queries/TssM.hmm.bak`.

### Inspecting without writing

```sh
utils/hmm_curator.py TssX.hmm --acc TssX.1 --tc 28.0 | head -20
```

---

## Troubleshooting

### `warning: removing existing GA, NC, BM, SM`

The tool owns `ACC`, `DESC`, `GA`, `TC`, `NC`, `BM` and `SM`. It clears all of
them before writing, so re-curating cannot leave stale or duplicated values.
Anything you do not pass is therefore dropped. To keep a field, pass its option:

```sh
utils/hmm_curator.py TssM.hmm --acc TssM.1 --tc 31.5 --ga 24.6 --nc 24.5 --in-place
```

### `<file> holds N profiles`

The file contains more than one model. Split it first:

```sh
hmmfetch --index profiles.hmm
hmmfetch profiles.hmm TssX > TssX.hmm
```

### `not a HMMER3 profile`

The file does not begin with a `HMMER3/` header. Check you passed the `.hmm`
file and not the alignment.

### `accession must be a single token with no whitespace`

`ACC` is written to a tab-separated table, so it cannot contain spaces. Use
`TssX.1`, not `Tss X 1`.

### Confirming a profile is ready

Run inside the `pandoomain` environment and the tool checks its own output:

```
Wrote queries/TssX.hmm  [TssX: ACC=TssX.1 TC=28/28]
```

Outside the environment pyhmmer is unavailable, so the check is skipped and the
line reads `Wrote queries/TssX.hmm`. To verify by hand:

```sh
grep -E '^(NAME|ACC|TC) ' queries/TssX.hmm
```

### Whole numbers lose their decimal

`--tc 28.0` is written as `TC 28 28;`. This matches how HMMER itself formats
whole numbers and is not a loss of precision. `24.6` stays `24.6`.
