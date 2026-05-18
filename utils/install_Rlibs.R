#!/usr/bin/env Rscript

# Install 'pak' if it isn't already available
if (!requireNamespace("pak", quietly = TRUE)) {
    install.packages("pak", repos = "http://cran.us.r-project.org")
}

# pak automatically handles github repos using the "user/repo" format
pak::pak(c("raim/segmenTools", "sfirke/janitor"))

