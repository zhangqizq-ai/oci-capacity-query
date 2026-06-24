#!/usr/bin/env python3
"""Check OCI Compute host capacity and quota for a shape config."""

from __future__ import annotations

import argparse
import configparser
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REGION_ALIASES = {
    "ashburn": "us-ashburn-1",
    "asburn": "us-ashburn-1",
    "iad": "us-ashburn-1",
    "phoenix": "us-phoenix-1",
    "phx": "us-phoenix-1",
}

SHAPE_ALIASES = {
    "vm e5": "VM.Standard.E5.Flex",
    "vm.e5": "VM.Standard.E5.Flex",
    "e5 vm": "VM.Standard.E5.Flex",
    "e5": "VM.Standard.E5.Flex",
    "vm e6": "VM.Standard.E6.Flex",
    "vm.e6": "VM.Standard.E6.Flex",
    "e6 vm": "VM.Standard.E6.Flex",
    "e6": "VM.Standard.E6.Flex",
}

DEFAULT_MEMORY_PER_OCPU_GB = {
    "VM.Standard.E5.Flex": 12.0,
    "VM.Standard.E6.Flex": 8.0,
}


def run_oci(args: list[str]) -> dict[str, Any]:
    cmd = ["oci", *args, "--output", "json"]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        if any(token in detail.lower() for token in ("notauthenticated", "authentication", "config file", "profile")):
            detail += (
                "\n\nThe local OCI CLI does not appear to be configured/authenticated. "
                "Install the OCI CLI if needed, run `oci setup config`, and verify with `oci iam region list`."
            )
        raise RuntimeError(
            "OCI CLI command failed:\n"
            f"  {' '.join(cmd)}\n"
            f"{detail}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OCI CLI returned non-JSON output for {' '.join(cmd)}") from exc


def tenancy_from_config(profile: str, config_file: Path) -> str:
    parser = configparser.RawConfigParser()
    parser.read(config_file)
    if profile == parser.default_section:
        tenancy = parser.defaults().get("tenancy", "").strip()
    elif parser.has_section(profile):
        tenancy = parser.get(profile, "tenancy", fallback="").strip()
    else:
        raise RuntimeError(f"Profile {profile!r} was not found in {config_file}")
    if not tenancy:
        raise RuntimeError(f"Profile {profile!r} in {config_file} has no tenancy value")
    return tenancy


def base_args(region: str, profile: str | None) -> list[str]:
    args = ["--region", region]
    if profile:
        args.extend(["--profile", profile])
    return args


def normalize_region(region: str | None) -> str | None:
    if not region:
        return None
    return REGION_ALIASES.get(region.strip().lower(), region.strip())


def normalize_shape(shape: str | None) -> str | None:
    if not shape:
        return None
    return SHAPE_ALIASES.get(shape.strip().lower(), shape.strip())


def list_ads(region: str, compartment_id: str, profile: str | None) -> list[str]:
    response = run_oci(
        [
            *base_args(region, profile),
            "iam",
            "availability-domain",
            "list",
            "--compartment-id",
            compartment_id,
            "--all",
        ]
    )
    return [item["name"] for item in response.get("data", [])]


def list_regions(profile: str | None) -> list[dict[str, Any]]:
    response = run_oci([*(["--profile", profile] if profile else []), "iam", "region", "list"])
    return sorted(response.get("data", []), key=lambda item: item.get("name", ""))


def list_shapes(
    region: str,
    compartment_id: str,
    profile: str | None,
    shape_filter: str | None,
) -> list[dict[str, Any]]:
    response = run_oci(
        [
            *base_args(region, profile),
            "compute",
            "shape",
            "list",
            "--compartment-id",
            compartment_id,
            "--all",
        ]
    )
    rows = response.get("data", [])
    if shape_filter:
        needle = shape_filter.lower()
        rows = [row for row in rows if needle in row.get("shape", "").lower()]

    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        shape = row.get("shape")
        if shape and shape not in seen:
            seen[shape] = row
    return [seen[name] for name in sorted(seen)]


def capacity_report(
    region: str,
    compartment_id: str,
    ad: str,
    shape: str,
    ocpus: float,
    memory_gb: float,
    profile: str | None,
) -> dict[str, Any]:
    shape_availability = json.dumps(
        [
            {
                "instanceShape": shape,
                "instanceShapeConfig": {
                    "ocpus": ocpus,
                    "memoryInGBs": memory_gb,
                },
            }
        ]
    )
    response = run_oci(
        [
            *base_args(region, profile),
            "compute",
            "compute-capacity-report",
            "create",
            "--compartment-id",
            compartment_id,
            "--availability-domain",
            ad,
            "--shape-availabilities",
            shape_availability,
        ]
    )
    rows = response.get("data", {}).get("shape-availabilities", [])
    return rows[0] if rows else {}


def shape_quota_names(region: str, compartment_id: str, shape: str, profile: str | None) -> list[str]:
    response = run_oci(
        [
            *base_args(region, profile),
            "compute",
            "shape",
            "list",
            "--compartment-id",
            compartment_id,
            "--all",
        ]
    )
    names: set[str] = set()
    for item in response.get("data", []):
        if item.get("shape") == shape:
            names.update(item.get("quota-names") or [])
    return sorted(names)


def pick_quota_names(quota_names: list[str]) -> tuple[str | None, str | None]:
    core = None
    memory = None
    for name in quota_names:
        if name.endswith("-core-count") and "reserved" not in name and "reservable" not in name:
            core = core or name
        if name.endswith("-memory-count") and "reserved" not in name and "reservable" not in name:
            memory = memory or name
    return core, memory


def resource_availability(
    region: str,
    compartment_id: str,
    ad: str,
    limit_name: str,
    profile: str | None,
) -> dict[str, Any] | None:
    try:
        response = run_oci(
            [
                *base_args(region, profile),
                "limits",
                "resource-availability",
                "get",
                "--service-name",
                "compute",
                "--limit-name",
                limit_name,
                "--compartment-id",
                compartment_id,
                "--availability-domain",
                ad,
            ]
        )
    except RuntimeError:
        return None
    return response.get("data", {})


def fmt_number(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def status_for_count(status: str | None, available_count: Any, instances: int) -> str:
    if status != "AVAILABLE":
        return "No"
    if isinstance(available_count, int):
        return "Yes" if available_count >= instances else "Unknown"
    return "Status only"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region")
    parser.add_argument("--shape")
    parser.add_argument("--ocpus", type=float)
    parser.add_argument("--memory-gb", type=float)
    parser.add_argument("--instances", type=int, default=1)
    parser.add_argument("--total-ocpus", type=float, help="Requested total OCPUs across all instances.")
    parser.add_argument(
        "--memory-per-ocpu-gb",
        type=float,
        help="Memory ratio used with --total-ocpus when --memory-gb is omitted.",
    )
    parser.add_argument(
        "--target-instance-ocpus",
        type=float,
        default=50,
        help="Preferred per-instance OCPUs when splitting --total-ocpus.",
    )
    parser.add_argument("--availability-domain", action="append", default=[])
    parser.add_argument("--compartment-id", help="Root compartment/tenancy OCID. Defaults to tenancy from OCI config.")
    parser.add_argument("--profile", default="DEFAULT")
    parser.add_argument("--config-file", default=str(Path.home() / ".oci" / "config"))
    parser.add_argument("--list-regions", action="store_true", help="List region identifiers available to the tenancy.")
    parser.add_argument("--list-shapes", action="store_true", help="List compute shape names in a region.")
    parser.add_argument("--shape-filter", help="Filter --list-shapes output by partial shape name, such as E6 or GPU.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    args = parser.parse_args()

    if not shutil.which("oci"):
        raise RuntimeError(
            "The OCI CLI executable 'oci' was not found on PATH. "
            "Install the OCI CLI, configure authentication with `oci setup config`, "
            "then verify with `oci iam region list` before checking capacity."
        )
    if args.instances < 1:
        raise RuntimeError("--instances must be at least 1")
    if args.target_instance_ocpus <= 0:
        raise RuntimeError("--target-instance-ocpus must be greater than 0")

    profile = args.profile or None
    args.region = normalize_region(args.region)
    args.shape = normalize_shape(args.shape)

    if args.list_regions:
        regions = list_regions(profile)
        if args.json:
            print(json.dumps({"regions": regions}, indent=2, sort_keys=True))
        else:
            print("# OCI regions")
            print()
            for region in regions:
                print(f"- {region.get('name')} ({region.get('key')})")
        return 0

    if not args.region:
        raise RuntimeError("Missing --region. Use --list-regions if you do not know the OCI region name.")

    compartment_id = args.compartment_id or tenancy_from_config(args.profile, Path(args.config_file))

    if args.list_shapes:
        shapes = list_shapes(args.region, compartment_id, profile, args.shape_filter)
        if args.json:
            print(json.dumps({"region": args.region, "shapes": shapes}, indent=2, sort_keys=True))
        else:
            heading = f"# OCI compute shapes in {args.region}"
            if args.shape_filter:
                heading += f" matching {args.shape_filter!r}"
            print(heading)
            print()
            for row in shapes:
                shape = row.get("shape")
                ocpus = row.get("ocpus")
                memory = row.get("memory-in-gbs")
                flexible = "flex" if row.get("is-flexible") else "fixed"
                print(f"- {shape} ({flexible}, OCPUs: {fmt_number(ocpus)}, memory GB: {fmt_number(memory)})")
        return 0

    if args.total_ocpus is not None:
        if args.total_ocpus <= 0:
            raise RuntimeError("--total-ocpus must be greater than 0")
        if args.ocpus is None:
            args.instances = max(1, math.ceil(args.total_ocpus / args.target_instance_ocpus))
            args.ocpus = args.total_ocpus / args.instances
        elif args.instances == 1 and args.ocpus < args.total_ocpus:
            args.instances = math.ceil(args.total_ocpus / args.ocpus)

    if args.memory_gb is None and args.ocpus is not None and args.shape:
        memory_ratio = args.memory_per_ocpu_gb or DEFAULT_MEMORY_PER_OCPU_GB.get(args.shape)
        if memory_ratio:
            args.memory_gb = args.ocpus * memory_ratio

    missing = []
    for name, value in (("--shape", args.shape), ("--ocpus or --total-ocpus", args.ocpus), ("--memory-gb", args.memory_gb)):
        if value is None:
            missing.append(name)
    if missing:
        raise RuntimeError(
            f"Missing required capacity input(s): {', '.join(missing)}. "
            "Use --list-shapes with --region if you do not know the exact compute shape name."
        )

    ads = args.availability_domain or list_ads(args.region, compartment_id, profile)
    total_ocpus = args.ocpus * args.instances
    total_memory = args.memory_gb * args.instances

    quota_names = shape_quota_names(args.region, compartment_id, args.shape, profile)
    core_limit, memory_limit = pick_quota_names(quota_names)

    results = []
    for ad in ads:
        capacity = capacity_report(
            args.region,
            compartment_id,
            ad,
            args.shape,
            args.ocpus,
            args.memory_gb,
            profile,
        )
        core_quota = resource_availability(args.region, compartment_id, ad, core_limit, profile) if core_limit else None
        memory_quota = (
            resource_availability(args.region, compartment_id, ad, memory_limit, profile) if memory_limit else None
        )
        results.append(
            {
                "availability_domain": ad,
                "capacity_status": capacity.get("availability-status"),
                "available_count": capacity.get("available-count"),
                "core_limit_name": core_limit,
                "core_available": None if core_quota is None else core_quota.get("available"),
                "memory_limit_name": memory_limit,
                "memory_available": None if memory_quota is None else memory_quota.get("available"),
                "quota_can_fit": (
                    None
                    if core_quota is None or memory_quota is None
                    else core_quota.get("available", 0) >= total_ocpus
                    and memory_quota.get("available", 0) >= total_memory
                ),
                "capacity_can_fit": status_for_count(
                    capacity.get("availability-status"),
                    capacity.get("available-count"),
                    args.instances,
                ),
            }
        )

    output = {
        "region": args.region,
        "shape": args.shape,
        "per_instance": {"ocpus": args.ocpus, "memory_gb": args.memory_gb},
        "instances": args.instances,
        "required_total": {"ocpus": total_ocpus, "memory_gb": total_memory},
        "quota_names": quota_names,
        "results": results,
        "caveats": [
            "Capacity reports are point-in-time and do not reserve capacity.",
            "OCI may return available-count as null; in that case only status is known.",
            "Service-limit quota and host capacity are separate checks.",
        ],
    }

    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0

    print(f"# OCI capacity check: {args.shape} in {args.region}")
    print()
    print(f"- Per instance: {fmt_number(args.ocpus)} OCPUs, {fmt_number(args.memory_gb)} GB memory")
    print(f"- Instances: {args.instances:,}")
    print(f"- Required total: {fmt_number(total_ocpus)} OCPUs, {fmt_number(total_memory)} GB memory")
    print()
    print("| Availability domain | Host capacity | Available count | OCPU quota available | Memory quota available | Quota can fit | Capacity can fit |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for row in results:
        quota_can_fit = "Unknown" if row["quota_can_fit"] is None else ("Yes" if row["quota_can_fit"] else "No")
        print(
            "| {ad} | {status} | {count} | {core} | {memory} | {quota} | {capacity} |".format(
                ad=row["availability_domain"],
                status=row["capacity_status"] or "unknown",
                count=fmt_number(row["available_count"]),
                core=fmt_number(row["core_available"]),
                memory=fmt_number(row["memory_available"]),
                quota=quota_can_fit,
                capacity=row["capacity_can_fit"],
            )
        )
    print()
    if core_limit or memory_limit:
        print(f"Quota limits checked: `{core_limit or 'unknown'}`, `{memory_limit or 'unknown'}`.")
    else:
        print("Quota limits checked: unknown; shape quota names were not discoverable.")
    print()
    print("Caveats: capacity is point-in-time, `AVAILABLE` is not a reservation, and quota does not guarantee host capacity.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
