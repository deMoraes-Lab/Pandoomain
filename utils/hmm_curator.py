#!/usr/bin/env python3
"""Add the metadata that pandoomain requires to a raw hmmbuild profile.

`hmmbuild` does not write an accession or bit-score cutoffs. Pfam-distributed
profiles carry both, which is why they work out of the box and freshly built
ones do not. `workflow/scripts/hmmer.py` needs exactly two of those fields:

- `TC`, the trusted cutoff. The search runs with `bit_cutoffs="trusted"`, so a
  profile without it fails with
  `MissingCutoffs: Model '<name>' is missing 'trusted' bitscore cutoff`.
- `ACC`, the accession. It is read as `hits.query_accession` and becomes the
  `query` column of `hmmer.tsv`, which flows into the `queries` column of
  `neighbors.tsv`. Without it the search succeeds and then dies with
  `AttributeError: 'NoneType' object has no attribute 'decode'`.

`GA`, `NC`, `DESC`, `BM` and `SM` are optional here. They are Pfam convention
and are written only when supplied.

`TC` is a scientific parameter, not boilerplate: it is the score below which a
hit is not considered a true member of the family. In Pfam it is curated per
family, typically the score of the lowest-scoring known true positive. Choose
it from your own alignment; there is no sensible default, so this tool requires
you to state it.

Examples:
    hmm_curator.py TssM.hmm --acc TssM.1 --tc 24.6 -o TssM.curated.hmm
    hmm_curator.py TssM.hmm --acc TssM.1 --tc 31.2 18.7 --in-place
    hmm_curator.py TssM.hmm --acc TssM.1 --tc 24.6 --ga 24.6 --nc 24.5 \\
        --desc 'Type VI secretion protein IcmF/TssM'
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Written after NAME, in Pfam's field order.
IDENTITY_FIELDS = ("ACC", "DESC")
# Written after CKSUM, in Pfam's field order.
CUTOFF_FIELDS = ("GA", "TC", "NC", "BM", "SM")
MANAGED_FIELDS = IDENTITY_FIELDS + CUTOFF_FIELDS

# HMMER pads the key to six columns, e.g. "ACC   PF05638.17".
KEY_WIDTH = 6

MODEL_START = "HMMER3/"
MODEL_END = "//"


def bitscore(text: str) -> float:
    """Parses a bit-score threshold.

    Args:
        text: The value given on the command line.

    Returns:
        The value as a float.

    Raises:
        argparse.ArgumentTypeError: If it is not a number.
    """
    try:
        return float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a bit score: {text!r}")


def accession(text: str) -> str:
    """Validates an accession.

    HMMER stores the accession as a single whitespace-free token, and pandoomain
    uses it verbatim as a column value in tab-separated output.

    Args:
        text: The value given on the command line.

    Returns:
        The accession unchanged.

    Raises:
        argparse.ArgumentTypeError: If it is empty or contains whitespace.
    """
    if not text or text.split() != [text]:
        raise argparse.ArgumentTypeError(
            f"accession must be a single token with no whitespace: {text!r}"
        )
    return text


def format_field(key: str, value: str) -> str:
    """Formats one HMMER header line.

    Args:
        key: The field name, such as "ACC".
        value: The field value.

    Returns:
        The formatted line, newline included.
    """
    return f"{key:<{KEY_WIDTH}}{value}\n"


def format_cutoff(scores: Tuple[float, float]) -> str:
    """Formats a bit-score cutoff the way HMMER writes it.

    Args:
        scores: The sequence and domain thresholds.

    Returns:
        The value portion of the line, e.g. "24.6 24.6;".
    """
    sequence, domain = scores
    return f"{sequence:g} {domain:g};"


def count_models(lines: List[str]) -> int:
    """Counts the profiles in an HMM file.

    Args:
        lines: The file's lines.

    Returns:
        How many models the file holds.
    """
    return sum(1 for line in lines if line.startswith(MODEL_START))


def split_models(lines: List[str]) -> List[List[str]]:
    """Splits an HMM file into its individual profiles.

    Args:
        lines: The file's lines.

    Returns:
        One list of lines per profile. Anything before the first profile header
        is attached to the first profile.
    """
    models: List[List[str]] = []
    for line in lines:
        if line.startswith(MODEL_START) or not models:
            models.append([])
        models[-1].append(line)
    return models


def field_of(line: str) -> Optional[str]:
    """Returns the header field a line defines, if any.

    Args:
        line: A line from the HMM file.

    Returns:
        The field name, or None if the line is not a header field.
    """
    key = line[:KEY_WIDTH].strip()
    return key if key else None


def curate(
    lines: List[str],
    acc: str,
    tc: Tuple[float, float],
    ga: Optional[Tuple[float, float]] = None,
    nc: Optional[Tuple[float, float]] = None,
    desc: Optional[str] = None,
    bm: Optional[str] = None,
    sm: Optional[str] = None,
) -> List[str]:
    """Inserts the requested metadata into one HMM profile.

    Any field this tool manages is dropped before insertion, so curating an
    already-curated profile replaces the old values instead of duplicating the
    lines. Everything else, including the model itself, is passed through
    untouched.

    Args:
        lines: The profile's lines.
        acc: The accession to record.
        tc: The trusted cutoff, as (sequence, domain).
        ga: The gathering cutoff, if it should be written.
        nc: The noise cutoff, if it should be written.
        desc: The description, if it should be written.
        bm: The build-method line, if it should be written.
        sm: The search-method line, if it should be written.

    Returns:
        The curated lines.

    Raises:
        ValueError: If the profile has no NAME line, or no place to put the
            cutoffs.
    """
    identity = {"ACC": acc}
    if desc is not None:
        identity["DESC"] = desc

    cutoffs = {"TC": format_cutoff(tc)}
    if ga is not None:
        cutoffs["GA"] = format_cutoff(ga)
    if nc is not None:
        cutoffs["NC"] = format_cutoff(nc)
    if bm is not None:
        cutoffs["BM"] = bm
    if sm is not None:
        cutoffs["SM"] = sm

    replacing = set(identity) | set(cutoffs)
    dropped = sorted(
        {
            key
            for line in lines
            if (key := field_of(line)) in MANAGED_FIELDS and key not in replacing
        }
    )
    if dropped:
        print(
            f"warning: removing existing {', '.join(dropped)} "
            "(this tool owns those fields; pass the matching option to keep them)",
            file=sys.stderr,
        )

    kept = [line for line in lines if field_of(line) not in MANAGED_FIELDS]

    out: List[str] = []
    placed_identity = False
    placed_cutoffs = False

    for line in kept:
        key = field_of(line)

        # The cutoffs belong after CKSUM and before STATS, which is where HMMER
        # and Pfam put them. If a profile somehow has no CKSUM, fall back to the
        # start of the STATS block, then to the start of the model proper.
        if not placed_cutoffs and key in ("STATS", "HMM"):
            out.extend(format_field(k, cutoffs[k]) for k in CUTOFF_FIELDS if k in cutoffs)
            placed_cutoffs = True

        out.append(line)

        if not placed_identity and key == "NAME":
            out.extend(format_field(k, identity[k]) for k in IDENTITY_FIELDS if k in identity)
            placed_identity = True

        if not placed_cutoffs and key == "CKSUM":
            out.extend(format_field(k, cutoffs[k]) for k in CUTOFF_FIELDS if k in cutoffs)
            placed_cutoffs = True

    if not placed_identity:
        raise ValueError("no NAME line found; is this a HMMER3 profile?")
    if not placed_cutoffs:
        raise ValueError("found no CKSUM, STATS or HMM line to anchor the cutoffs")

    return out


def verify(path: Path) -> Optional[str]:
    """Checks that a curated profile satisfies the pandoomain search.

    Loads the profile the way `workflow/scripts/hmmer.py` does and confirms that
    the two fields it depends on are readable. Skipped when pyhmmer is absent.

    Args:
        path: The curated HMM file.

    Returns:
        A human-readable status line, or None if pyhmmer is unavailable.
    """
    try:
        from pyhmmer.plan7 import HMMFile
    except ImportError:
        return None

    with HMMFile(path) as handle:
        models = list(handle)

    notes = []
    for model in models:
        name = model.name.decode() if model.name else "<unnamed>"
        if model.cutoffs.trusted is None:
            notes.append(f"{name}: TC still missing")
        elif model.accession is None:
            notes.append(f"{name}: ACC still missing")
        else:
            sequence, domain = model.cutoffs.trusted
            notes.append(
                f"{name}: ACC={model.accession.decode()} TC={sequence:g}/{domain:g}"
            )
    return "; ".join(notes)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Builds and runs the command-line parser.

    Args:
        argv: Arguments to parse. Defaults to sys.argv.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Add the ACC and TC fields that pandoomain requires to a raw "
            "hmmbuild profile."
        ),
        epilog=(
            "TC is the trusted cutoff: the bit score below which a hit is not "
            "a true member of the family. Pick it from your own alignment; "
            "there is deliberately no default."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("hmm", type=Path, help="raw .hmm file from hmmbuild")
    parser.add_argument(
        "--acc",
        type=accession,
        required=True,
        help="accession to record; becomes the 'query' column of hmmer.tsv",
    )
    parser.add_argument(
        "--tc",
        type=bitscore,
        nargs="+",
        required=True,
        metavar="SCORE",
        help=(
            "trusted cutoff, required by the search. One value sets the "
            "sequence and domain thresholds together; two set them separately."
        ),
    )
    parser.add_argument(
        "--ga", type=bitscore, nargs="+", metavar="SCORE",
        help="gathering cutoff (optional; Pfam convention, unused by pandoomain)",
    )
    parser.add_argument(
        "--nc", type=bitscore, nargs="+", metavar="SCORE",
        help="noise cutoff (optional; Pfam convention, unused by pandoomain)",
    )
    parser.add_argument("--desc", help="description line (optional)")
    parser.add_argument("--bm", help="build method line (optional)")
    parser.add_argument("--sm", help="search method line (optional)")

    where = parser.add_mutually_exclusive_group()
    where.add_argument(
        "-o", "--output", type=Path, help="write here (default: standard output)"
    )
    where.add_argument(
        "--in-place",
        action="store_true",
        help="overwrite the input, keeping a .bak copy",
    )

    parser.add_argument(
        "--allow-multi",
        action="store_true",
        help=(
            "permit a file holding several profiles. Refused by default: one "
            "accession cannot describe more than one model."
        ),
    )
    return parser.parse_args(argv)


def as_pair(scores: Optional[List[float]], flag: str) -> Optional[Tuple[float, float]]:
    """Normalises a cutoff given as one or two numbers.

    Args:
        scores: The values supplied, or None.
        flag: The originating option name, for error messages.

    Returns:
        The (sequence, domain) pair, or None.

    Raises:
        SystemExit: If more than two values were given.
    """
    if scores is None:
        return None
    if len(scores) == 1:
        return (scores[0], scores[0])
    if len(scores) == 2:
        return (scores[0], scores[1])
    sys.exit(f"{flag} takes one or two values, got {len(scores)}")


def main() -> None:
    """Curates one HMM profile."""
    args = parse_args()

    if not args.hmm.is_file():
        sys.exit(f"no such file: {args.hmm}")

    lines = args.hmm.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        sys.exit(f"empty file: {args.hmm}")
    if not lines[0].startswith(MODEL_START):
        sys.exit(f"not a HMMER3 profile (first line is {lines[0].strip()!r})")

    models = count_models(lines)
    if models > 1 and not args.allow_multi:
        sys.exit(
            f"{args.hmm} holds {models} profiles, but --acc gives a single "
            "accession. Split the file, or pass --allow-multi to write the "
            "same accession and cutoffs into every model."
        )

    curated: List[str] = []
    for index, model in enumerate(split_models(lines), start=1):
        try:
            curated.extend(
                curate(
                    model,
                    acc=args.acc,
                    tc=as_pair(args.tc, "--tc"),
                    ga=as_pair(args.ga, "--ga"),
                    nc=as_pair(args.nc, "--nc"),
                    desc=args.desc,
                    bm=args.bm,
                    sm=args.sm,
                )
            )
        except ValueError as error:
            sys.exit(f"{args.hmm}: profile {index}: {error}")

    text = "".join(curated)

    if args.in_place:
        shutil.copyfile(args.hmm, args.hmm.with_suffix(args.hmm.suffix + ".bak"))
        args.hmm.write_text(text, encoding="utf-8")
        destination = args.hmm
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        destination = args.output
    else:
        sys.stdout.write(text)
        return

    status = verify(destination)
    if status is None:
        print(f"Wrote {destination}", file=sys.stderr)
    else:
        print(f"Wrote {destination}  [{status}]", file=sys.stderr)


if __name__ == "__main__":
    main()
