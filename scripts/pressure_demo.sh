#!/usr/bin/env bash
# Только Linux с systemd --user и доступным memory controller cgroup v2.
# Запуск — вручную, в отдельной ограниченной cgroup (не на общем/продакшен сервере).
set -euo pipefail
cd "$(dirname "$0")/.."
make -C c all
mkdir -p results
if ! systemctl --user show-environment >/dev/null 2>&1; then
  echo 'Нет активного user-systemd: создайте собственную ограниченную cgroup v2 или выполните на Linux с systemd --user.' >&2
  exit 2
fi
printf 'Baseline with no explicit per-process memory limit (host-dependent)\n'
./c/page_faults --mode file --pattern random --mb 192 --passes 4 > results/c_pressure_baseline.csv
printf 'Pressure test in MemoryMax=96M cgroup; working set=192 MiB\n'
systemd-run --quiet --user --scope -p MemoryMax=96M -- \
  "$(pwd)/c/page_faults" --mode file --pattern random --mb 192 --passes 4 \
  > results/c_pressure_limited.csv
printf 'Saved: results/c_pressure_baseline.csv and results/c_pressure_limited.csv\n'
