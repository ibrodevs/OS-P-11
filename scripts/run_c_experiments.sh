#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p results
make -C c all
./c/page_faults --mode anon --pattern sequential --mb 32 --passes 3 > results/c_anon_sequential.csv
./c/page_faults --mode file --pattern sequential --mb 32 --passes 3 > results/c_file_sequential.csv
./c/page_faults --mode file --pattern random --mb 32 --passes 3 > results/c_file_random.csv
./c/page_faults --mode file --pattern local --mb 32 --passes 3 > results/c_file_local.csv
./c/matrix_bench --size 2048 --repeats 3 > results/c_matrix.csv
echo "Saved measured data to results/c_*.csv (host-dependent)."
