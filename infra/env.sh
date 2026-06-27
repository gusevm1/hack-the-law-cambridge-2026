#!/usr/bin/env bash
# Single source of truth for the GCP account/project this repo deploys to.
# Account-portable: switch accounts by editing THIS file, or override any var in
# the environment — every value is `${VAR:-default}`, so a real env var always wins.
# Sourced by infra/bootstrap.sh, infra/deploy.sh and `just migrate`.
#
# Active account: devstar5221@gcplab.me  (Google-managed sandbox "Hack the Law-522").
# Switched off the old throwaway `hack-the-law-cambridge-2026` on 2026-06-27.
export PROJECT_ID="${PROJECT_ID:-llm-law-cambridge26cbx-522}"
export REGION="${REGION:-europe-west1}"
