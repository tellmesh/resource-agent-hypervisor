#!/usr/bin/env bash
# Resolve hypervisor monorepo root (sourced by tellmesh scripts).
if [[ -n "${HYPERVISOR_REPO_ROOT:-}" ]]; then
  HYPERVISOR_ROOT="$(cd "$HYPERVISOR_REPO_ROOT" && pwd)"
elif [[ -n "${TELLMESH_ROOT:-}" && -d "${TELLMESH_ROOT}/tellmesh" ]]; then
  HYPERVISOR_ROOT="$(cd "${TELLMESH_ROOT}/tellmesh" && pwd)"
elif [[ -d "/home/tom/github/tellmesh/tellmesh" ]]; then
  HYPERVISOR_ROOT="/home/tom/github/tellmesh/tellmesh"
elif [[ -d "/home/tom/github/wronai/hypervisor" ]]; then
  HYPERVISOR_ROOT="/home/tom/github/wronai/hypervisor"
else
  echo "hypervisor root not found (set HYPERVISOR_REPO_ROOT)" >&2
  exit 1
fi
