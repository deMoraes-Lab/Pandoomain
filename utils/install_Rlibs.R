#!/usr/bin/env Rscript

# Ensure remotes is available (provided by conda env, but fallback here)
if (!requireNamespace("remotes", quietly = TRUE)) {
    install.packages("remotes", repos = "http://cran.us.r-project.org")
}

# Install segmenTools directly from GitHub source
# (dependencies like janitor and segmenTier are already safely provided by Conda)
remotes::install_github("raim/segmenTools", upgrade = "never")