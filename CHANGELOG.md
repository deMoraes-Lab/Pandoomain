# Changelog

All notable changes to *Pandoomain* are documented in this file.

This project follows [Semantic Versioning](https://semver.org/).

---

## [2.0.1] — 2026-08-29

Bug-fix release focused on **Pandoomain Browser**. The visualizer drew
overlapping features on top of one another, which hid genes in the
neighborhood track and hid domains in the protein track. Nothing in the
pipeline itself changed, so existing `results/` directories work unmodified.

### Fixed

#### Domain panel: signatures no longer occlude each other

`showFocusedGene` drew every InterProScan signature as an absolutely
positioned, full-height bar on one shared backbone. Because `iscan.db` stores
signatures from *every* InterProScan member database — not only Pfam, despite
the column being named `pfam` — full-length hits from PANTHER, TIGRFAM and
Gene3D were painted over the Pfam domains underneath.

Measured on `results/browser_files` (*P. aeruginosa* PAO1, protein
`NP_248767.1`, IcmF/TssM, 1101 aa): of 9 signatures, `TIGR03348` (8–1099) and
`PTHR36153` (10–1101) span the whole protein, and **7 of 9 signatures — every
Pfam domain — were completely buried.**

Signatures are now classified by member database and drawn on **one stacked
track per database**, with greedy interval packing inside each track, so no
feature can hide another. Additions:

- A per-database filter. Pfam, NCBIfam and CDD are shown by default, since the
  architecture encoding in `workflow/scripts/archs.R` is built from Pfam IDs.
- An amino-acid ruler above the tracks.
- A subtitle reporting gene name, locus tag, protein length, and the signature
  and database counts.
- A two-column legend, and tooltips carrying accession, description and
  residue range.

#### Neighborhood track: genes no longer collide

Two separate defects in `renderGenes`:

1. **Genes crossing a line boundary were relocated.** A gene that did not fit
   in the remaining width was moved wholesale to the start of the next line
   (`line_index++; start_pos_on_line = 0`). This drew it at the wrong
   coordinate *and* made it collide with the gene that genuinely began there.
   Genes are now **clipped against each line and drawn as one segment per
   line**, each at its true coordinate, with `«`/`»` marking continuation.
2. **All genes shared one row.** Every gene was placed at a fixed `top-8`, so
   genes overlapping in coordinates — common in operons — were drawn on top of
   each other.
   Genes are now separated by **strand** (forward above the axis, reverse
   below) and packed into **lanes** within each strand. Abutting genes
   (`end == next start`) stay on one lane; only genuinely overlapping genes are
   pushed to a new lane. Line height adapts to the lane count.
3. **Coordinate labels sat on the genes of the line above.** The ruler was
   drawn outside its line box with a negative offset, so the clearance it
   relied on came from the box's top margin. The canvas carries Tailwind's
   `space-y-2`, whose `> * + *` rule outranks the element's `mt-8`, collapsing
   that margin from 32 px to 8 px on every line after the first and leaving the
   labels 8 px on top of the previous line's reverse-strand genes.
   Each line box now **reserves a ruler band inside itself** (`RULER_H`), so the
   geometry no longer depends on any external margin, and the inter-line gap is
   set inline so it cannot be overridden by a utility class.

On PAO1 neighborhood 1 (25 genes, 34 kb, 3 lines) this removed **7 rendered
gene collisions**, 2 of which were gross mispositionings from defect 1.

#### Domain colours

`stringToColor` packed a string hash directly into RGB, which produced
near-white and near-black bands that were invisible against the track. Replaced
by `domainColor`, which hashes into hue only and pins saturation (62–79%) and
lightness (55–66%). `stringToColor` is retained as an alias.

#### Header: title no longer overflows into the Load Data column

The branding column and the upload column sat in the same flex row, but the
upload column carried `flex-grow max-w-4xl w-full`. The `w-full` made it demand
the container's whole width, squeezing the branding column below its content
width; the `<h1>` then overflowed its own column and ran into the upload area.
Measured between 1024 px and 1280 px, the title's right edge reached 359 px
while its column ended at 271-312 px, crossing into an upload column that began
at 303 px.

The branding column is now `lg:shrink-0` so it keeps its content width, and the
upload column is `flex-grow min-w-0 max-w-4xl` rather than `w-full`. The title
also scales (`text-3xl xl:text-4xl`) and the logo is slightly smaller. Checked
at 768, 900, 1024, 1100, 1200, 1280, 1366, 1440, 1600, 1900 and 2100 px: no
overflow and no column overlap at any width, in both the stacked and side-by-side
layouts.

### Added

- The published reference, in two places in the browser and as a `Citation`
  section in the README. Both browser links point at
  <https://doi.org/10.1128/msystems.00427-26>.

  Short form, in the header beside the repository link:

  > Cite: Soto EB, Oliver AJ, de Moraes MH. 2026, mSystems 11:e00427-26.

  Full form, in the footer:

  > Reference: Soto EB, Oliver AJ, de Moraes MH. 2026. Pandoomain, a scalable
  > pipeline for genomic and protein domain context analysis, reveals widespread
  > PT-TG domain architectural diversity and novel polymorphic toxins. mSystems

  The branding column is capped at `lg:max-w-sm` so the header citation wraps
  within the column instead of widening it and squeezing the Load Data area,
  which is the failure this release fixed. Re-checked at 768, 1024, 1280 and
  1900 px with real viewport resizes: no overflow, no column overlap and no
  horizontal page scroll at any of them.

- Optional **"Show Pfam domains inside gene arrows"** toggle in the Explore
  header. This implements the `// Render domains inside gene block` block that
  was present but dead — `geneDomains` was computed and never used. Domain
  coordinates are mapped from amino-acid to base-pair space with strand
  awareness (protein N-terminus is at `gene.end` on the reverse strand). Off by
  default, so the neighborhood view stays legible.
- Gene tooltips now also report gene name and genomic location.

#### `utils/hmm_curator.py`

A tool to add the fields `hmmbuild` does not write. `hmmbuild` emits no `ACC`
and no bit-score cutoffs, while Pfam-distributed profiles carry both, which is
why Pfam HMMs work as queries and freshly built ones do not.
`workflow/scripts/hmmer.py` requires exactly two of them, confirmed against
pyhmmer 0.10.14:

| Profile state | Result |
|---|---|
| Raw `hmmbuild` output | `MissingCutoffs: Model 'aln' is missing 'trusted' bitscore cutoff` |
| `TC` added, no `ACC` | Search runs, then `AttributeError: 'NoneType' object has no attribute 'decode'` |
| `TC` + `ACC` added | Works |

`TC` is needed because the search runs with `bit_cutoffs="trusted"`; `ACC` is
read as `hits.query_accession` and becomes the `query` column of `hmmer.tsv`.
`GA`, `NC`, `DESC`, `BM` and `SM` are Pfam convention, are not read by the
pipeline, and are written only when supplied.

```sh
utils/hmm_curator.py TssM.hmm --acc TssM.1 --tc 24.6 -o queries/TssM.hmm
```

Both values are required arguments. `TC` sets the sensitivity of the entire
search and is curated per family in Pfam, so the tool has no default for it.

The tool re-curates cleanly: fields it owns are replaced rather than duplicated,
and it warns when an existing one is being dropped. It writes to standard output
by default, or to `-o`, or over the input with `--in-place` (keeping a `.bak`).
It curates exactly one profile per run: a file holding several is refused, since
one accession cannot describe more than one model. When pyhmmer is available it
verifies the result after writing, reporting the recorded accession and cutoff.

This replaces an earlier draft kept outside the repository, which hardcoded
`GA/TC/NC 24.6/24.6/24.5` for every profile, appended fields without removing
existing ones (so re-running duplicated them), and carried a regular expression
intended to rewrite the emission header that never matched HMMER3 output.

### Removed

- The `browser/` directory. It was a byte-identical duplicate of
  `pandoomain_browser/` (including the misspelled `pandoomain-broswer.html`)
  and nothing referenced it. Keeping it would have left an unfixed second copy
  of the visualizer in the tree.

### Documentation

- `README.md`: the browser section pointed at
  `pandoomain_browser/pandoomain_browser.html`, which does not exist — the file
  is `pandoomain-browser.html`. Corrected, and expanded to describe the strand
  lanes and the per-database domain tracks.

### Verification

Validated against real pipeline output pulled from the production VM, not
synthetic fixtures. Both `results/browser_files` and `tests/results/browser_files`
were exercised by driving the page directly and auditing the rendered DOM
geometry.

| Dataset | Neighborhoods | Gene panels | Segments | Gene collisions | Line spills | Domain occlusions | JS errors |
|---|---|---|---|---|---|---|---|
| `results` | 6 | 150 | 27/view | 0 | 0 | 0 | 0 |
| `tests/results` | 24 | 509 | 537 | 0 | 0 | 0 | 0 |

Checks performed per view: no two gene segments sharing a lane overlap
horizontally; no line's genes spill into the next line's box; no coordinate
label touches the genes of its own or the preceding line (76 rendered lines
checked across both datasets); no two domain bands sharing a track row
overlap. Stress case `NP_248780.1` (31 signatures
across 10 database groups, 902 aa) renders all 31 bands with zero occlusion.
68 proteins carrying no domain annotation render the empty-state message
without error.

### Build / installation

#### `make install-iscan` now performs a real installation

The rule defaulted to `ISCAN_DRY = --dry`, so the invocation documented in the
README only ever printed the steps. Installing for real required discovering
and passing `ISCAN_DRY=''`.

`ISCAN_DRY` now defaults to empty, so `make install-iscan` installs. The
preview is still available and is now an explicit target:

```sh
make install-iscan       # real installation
make install-iscan-dry   # print the steps, change nothing
```

The real path first reports the version, destination and footprint (~7 GB
downloaded, ~60 GB installed). The dry flag is now spelled `--dry-run`, which
is what the script actually declares; `--dry` worked only via argparse prefix
matching and would have broken silently had another `--dry*` option been added.

#### No shell configuration needed after installing InterProScan

The installer told the user to add the installation directory to `~/.bashrc`,
even though it had just created a working symlink at `~/.local/bin/interproscan.sh`.
The warning was a false alarm: it tested `os.environ["PATH"]`, but the stock
`~/.profile` only adds `~/.local/bin` to PATH `if [ -d "$HOME/.local/bin" ]` at
*login*. On a fresh machine the directory does not exist yet, so the installer
created it and then checked a PATH that was fixed before it existed. The link
worked in every later shell regardless.

`setup_path_access` now:

- Also links into `$CONDA_PREFIX/bin` when a conda environment is active. This
  is the dependable location for the pipeline, since the environment supplies
  `java`, `snakemake` and R and therefore has to be active anyway, and its `bin`
  is always first on PATH while it is. (The link belongs to the environment, so
  recreating the environment means re-running `make install-iscan`.)
- Determines reachability from the PATH a *new login shell* would see, rather
  than the current process's, so the "ACTION REQUIRED" banner appears only when
  the command genuinely cannot be found.

Linking is safe: `interproscan.sh` resolves its own symlinks, walking
`BASH_SOURCE` and `cd`-ing to the real installation directory before locating
`interproscan-5.jar` and its data.

Verified on the deployment VM: with the environment active, `interproscan.sh`
resolves to `$CONDA_PREFIX/bin` and `interproscan.sh --version` runs correctly
from an unrelated working directory with no shell rc changes.

#### `utils/install_iscan.py` is executable

The file was recorded in git as mode `100644`, while every other script the
pipeline executes directly (`install_Rlibs.R`, `hmmer.py`, `neighbors.R`) is
`100755`. Because the rule invokes it as `$<`, a fresh clone failed with
`permission denied` until the user ran `chmod +x` by hand. Now recorded as
`100755`.

#### Makefile `.PHONY` declarations

Twelve declarations were written `.PHONY target:` instead of `.PHONY: target`.
The former declares a target *named* `.PHONY` whose prerequisite is the real
target, so nothing was ever marked phony and a stray file matching a target
name would have silently disabled that rule.

#### `.DS_Store`

macOS Finder metadata had been committed to the repository. It is now untracked
and listed in `.gitignore`.

---

### Known issues / not addressed in this release

The following items from the v2.0.1 plan are **not** included here:

- An option to select which InterProScan member databases are searched
  (`--applications`). This is the upstream half of the occlusion problem: the
  browser fix makes the signature soup readable, but restricting it at search
  time would also cut InterProScan runtime substantially.

---

## [2.0.0]

- Interactive browser visualization
  - New web-based visualizer (`pandoomain-browser.html`) for interactively
    exploring pipeline outputs.
  - The pipeline now generates SQLite databases (`iscan.db`, `metadata.db`,
    `neighbors.db`) natively supported by the browser interface.
- `utils/install_Rlibs.R` updated to use `pak` to install R packages.
- Enhanced protein domain encoding
  - Upgraded the domain architecture encoding in `archs.R` to support a large
    number of unique protein domains.
  - Replaced the single-letter code with a high-contrast Unicode pool
    prioritizing geometric shapes and multiple alphabets (Latin, Greek,
    Cyrillic, Armenian, Devanagari), ensuring left-to-right reading stability
    across large datasets.
- Improved InterProScan execution
  - Rewrote the InterProScan logic in the Snakemake workflow, moving from a
    Python-wrapped execution to direct bash execution over chunks of `.faa`
    files, with error handling for missing files and failed jobs.

---

## [0.0.2]

- Removal of the `hmmer_input` rule; `genomes.tsv` is used directly as input to
  the `hmmer` rule.
- Removal of the preprocessing rule for `genomes.txt`; dependent rules parse it
  directly.
- Fixed a taxallnomy bug caused by an updated database (43 columns instead of 42).
- Removal of `utils.py`.
