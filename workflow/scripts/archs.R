#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(tidyverse)
})


argv <- commandArgs(trailingOnly = TRUE)

ISCAN <- argv[[1]]
OUT <- argv[[2]]
OUT_PIDFOCUS <- argv[[3]]
OUT_CODE <- argv[[4]]

OFFSET <- 33
PF_INT_LEN <- 5
PF_LEAD_CHAR <- "PF"

# NEW: Prioritized left-to-right, high-stability character pool generator
generate_unicode_pool <- function(total_needed) {
  # 1. High-contrast solid geometric shapes go first
  geometric_ints <- c(0x25A0, 0x25B2, 0x25BC, 0x25B6, 0x25C0, 0x25C6, 0x25CF)
  
  # 2. Universal, left-to-right reading alphabets
  ranges <- list(
    c(0x0041, 0x005A), # U+0041 to U+005A (Latin A-Z)
    c(0x0061, 0x007A), # U+0061 to U+007A (Latin a-z)
    c(0x00C0, 0x0148), # U+00C0 to U+0148 (Latin Extended)
    c(0x014A, 0x024F), # U+014A to U+024F (Latin Extended-B)
    c(0x0391, 0x03FF), # U+0391 to U+03FF (Greek)
    c(0x0400, 0x0458), # U+0400 to U+0458 (Cyrillic)
    c(0x0531, 0x0556), # U+0531 to U+0556 (Armenian Uppercase)
    c(0x0562, 0x0588), # U+0562 to U+0588 (Armenian Lowercase)
    c(0x0905, 0x0939)  # U+0905 to U+0939 (Devanagari / Hindi)
  )
  

  preferred_ints <- unlist(lapply(ranges, function(r) r[1]:r[2]))
  set.seed(42)
  preferred_ints <- sample(preferred_ints)
  
  all_preferred <- c(geometric_ints, preferred_ints)
  
  # 3. Scale smoothly into CJK Unified Ideographs for the other 22,000+ domains
  if (length(all_preferred) < total_needed) {
    remainder <- total_needed - length(all_preferred)
    cjk_start <- 0x4E00
    cjk_ints <- cjk_start:(cjk_start + remainder - 1)
    all_preferred <- c(all_preferred, cjk_ints)
  }
  
  strsplit(intToUtf8(all_preferred), "")[[1]]
}

# UPDATED: Maps domains sequentially utilizing the pool engine
one_lettercode <- function(doms) {
  unique_doms <- unique(doms)
  num_unique <- length(unique_doms)
  
  char_pool <- generate_unicode_pool(num_unique)
  pfam_codes <- char_pool[1:num_unique]
  
  stopifnot("Pool allocation failed." = length(pfam_codes) == length(unique_doms))
  
  OUT <- as.list(pfam_codes)
  names(OUT) <- unique_doms
  OUT
}

# UPDATED: Uses your saved translation map file to reverse letters back to Pfam IDs
code_to_pfam <- function(codes, mapping_tibble) {
  TOTAL_LEN <- PF_INT_LEN + str_length(PF_LEAD_CHAR)
  
  matched_domains <- map_chr(codes, function(c) {
    res <- mapping_tibble$domain[mapping_tibble$letter == c]
    if(length(res) == 0) return(NA_character_) else return(res)
  })
  
  stopifnot("Bad PFAM ID decoding" = all(str_length(matched_domains) == TOTAL_LEN))
  matched_domains
}

replace_to_oneletter <- function(archs, code) {
  keys <- names(code)
  for (key in keys) {
    archs <- str_replace_all(archs, key, code[[key]])
  }
  str_replace_all(archs, ",", "")
}

get_arch_len <- function(arch) {
  str_split(arch, ",") |>
    map_int(length)
}


# Main ----

iscan <- read_tsv(ISCAN, show_col_types = FALSE)

iscan_summary <- iscan |>
  select(pid, memberDB, interpro, start, end, length, memberDB_txt) |>
  arrange(pid, start)

stopifnot("Separator is used by a memberDB ID." = all(!str_detect(iscan_summary$memberDB, "\\|")))
stopifnot("Unexpeted NA on memberDB field." = all(!is.na(iscan_summary$memberDB)))

is_unique <- function(x) {
  all(sort(unique(x)) == sort(x))
}

archsMEM <- iscan_summary |>
  group_by(pid) |>
  summarize(
    archMEM = str_flatten(memberDB, collapse = "|")
  )

# archs IPR ----

iscanIPR <- iscan_summary |>
  filter(!is.na(interpro))

delta_lag <- function(x) {
  abs(lag(x) - x)
}

deltaENDs <- iscanIPR |>
  group_by(pid, interpro) |>
  reframe(
    start = start,
    end = end,
    deltaS = delta_lag(start),
    deltaE = delta_lag(end)
  )

includeIPR <- function(dS, dE) {
  CUTOFF <- 36
  firstIPR <- is.na(dS) & is.na(dE)
  restIPR <- (dS > CUTOFF) | (dE > CUTOFF)
  restIPR[is.na(restIPR)] <- TRUE
  firstIPR & restIPR
}


archsIPR <- deltaENDs |>
  mutate(valid = includeIPR(deltaS, deltaE)) |>
  filter(valid) |>
  group_by(pid) |>
  arrange(start) |>
  summarize(
    archIPR = str_flatten(interpro, collapse = "|")
  )

# archs PFAM ----

archMEM_to_archPF <- function(arch_mem) {
  f <- function(x) {
    all_arch <- str_split_1(x, pattern = "\\|")
    PF_valid <- str_detect(all_arch, "^PF[:digit:]{5}")
    str_flatten(all_arch[PF_valid], collapse = "|")
  }
  map_chr(arch_mem, f)
}

archsPF <- archsMEM |>
  mutate(archPF = archMEM_to_archPF(archMEM))

# archs all ----

archs <- left_join(archsPF, archsIPR, join_by(pid))

write_tsv(archs, OUT)

# Legacy pidrow and code outputs

archs_legacy <- iscan |>
  filter(analysis == "Pfam") |>
  group_by(pid) |>
  reframe(
    domain = memberDB, start = start, end = end,
    length = length, domain_txt = memberDB_txt
  ) |>
  arrange(pid, start, end) |>
  mutate(
    start = as.integer(start),
    end = as.integer(end),
    length = as.integer(length)
  )

archs_legacy <- archs_legacy |>
  group_by(pid) |>
  reframe(order = 1:length(start), across(everything())) |>
  relocate(order, .after = domain)

pid_focus <- archs_legacy |>
  group_by(pid) |>
  summarize(
    pid = unique(pid),
    arch = str_flatten(domain, collapse = ",")
  )

ONE_LETTER <- one_lettercode(archs_legacy$domain)

pid_focus <- pid_focus |>
  left_join(
    distinct(archs_legacy, pid, length),
    join_by(pid)
  ) |>
  mutate(ndoms = get_arch_len(arch)) |>
  relocate(ndoms, .after = arch)

pid_focus <- pid_focus |>
  mutate(arch_code = replace_to_oneletter(arch, ONE_LETTER))

one_letter_chr <- ONE_LETTER |>
  unlist()

one_letter_tib <- tibble(
  domain = names(one_letter_chr),
  letter = one_letter_chr
)

write_tsv(pid_focus, OUT_PIDFOCUS)
write_tsv(one_letter_tib, OUT_CODE)