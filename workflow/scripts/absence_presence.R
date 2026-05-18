#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(tidyverse)
})

argv <- commandArgs(trailingOnly = TRUE)

TAXA <- argv[[1]]
HITS <- argv[[2]]
ARCHS <- argv[[3]]
OUT_TGPD <- argv[[4]]
OUT_ABSENCE_PRESENCE <- argv[[5]]

# TAXA <- "tests/results/genomes_ranks.tsv"
# HITS <- "tests/results/hmmer.tsv"
# ARCHS <- "tests/results/archs.tsv"


TAXA_SEL <- c(
  "genome", "tax_id",
  "superkingdom",
  "phylum", "class", "order",
  "family", "genus", "species"
)


ranks <- read_tsv(TAXA, show_col_types = FALSE) |>
  select(all_of(TAXA_SEL))
hits <- read_tsv(HITS, show_col_types = FALSE) |>
  select(genome, pid)
archs <- read_tsv(ARCHS, show_col_types = FALSE) |>
  select(pid, archPF)


archsNF <- archs |>
  filter(!is.na(archPF)) |>
  group_by(pid) |>
  reframe(pfam = str_split_1(archPF, pattern = "\\|"))

TGPD <- ranks |>
  select(tax_id, genome) |>
  left_join(hits, join_by(genome),
    relationship = "many-to-many"
  ) |>
  left_join(archsNF, join_by(pid),
    relationship = "many-to-many"
  ) |>
  rename(domain = pfam)


genome_pfam <- left_join(hits, archsNF, join_by(pid)) |>
  group_by(genome) |>
  summarize(pfams = str_flatten(sort(unique(pfam)), collapse = "|"))

absence_presence <- left_join(genome_pfam, ranks)

write_tsv(TGPD, OUT_TGPD)
write_tsv(absence_presence, OUT_ABSENCE_PRESENCE)
