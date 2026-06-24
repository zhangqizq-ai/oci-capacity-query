---
name: oci-capacity-checker
description: Check OCI Compute host capacity and service-limit availability for a requested compute shape, OCPU total, memory total, instance count, region, and optional availability domain. Use when an end user asks whether OCI has capacity for a specific VM or bare metal shape such as VM.Standard.E5.Flex or VM.Standard.E6.Flex in a region or AD, including natural queries like "vm e5 500 ocpus in ashburn", wants to compare capacity across ADs, or needs quota-versus-host-capacity evidence from the local authenticated OCI CLI.
---

# OCI Capacity Checker

## Core Rules

- Use the local `oci` CLI and the user's configured authentication. Do not ask for keys or tokens.
- If `oci` is not installed or the local CLI is not authenticated, stop and tell the user to install/configure it first:
  - Install: `brew install oci-cli` on macOS, or follow Oracle's OCI CLI install guide for their OS.
  - Authenticate/configure: `oci setup config`, then verify with `oci iam region list`.
- Treat capacity reports as live OCI API calls; request approval when the current environment requires network or credential access.
- Use the root compartment/tenancy OCID for capacity reports and limit checks. If the user does not provide it, read `tenancy=` from the selected OCI CLI config profile.
- Check every availability domain in the region unless the user names one or more specific ADs.
- Report host capacity separately from service limits. A request can have enough quota but still fail host capacity.
- Do not claim a precise available instance count when OCI returns `available-count: null`; say that OCI reports status only.
- If the user does not know the OCI region name or compute shape name, guide them with discovery commands before checking capacity.

## Quick Start

Run the bundled helper for the common workflow:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py \
  --region us-ashburn-1 \
  --shape VM.Standard.E6.Flex \
  --ocpus 16 \
  --memory-gb 128 \
  --instances 16
```

For natural requests that provide total OCPUs but not a VM split, use `--total-ocpus`.
The helper normalizes common aliases such as `asburn`/`ashburn` to `us-ashburn-1`
and `vm e5`/`e5` to `VM.Standard.E5.Flex`.

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py \
  --region asburn \
  --shape "vm e5" \
  --total-ocpus 500
```

For a single AD:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py \
  --region us-ashburn-1 \
  --availability-domain 'SaZl:US-ASHBURN-AD-1' \
  --shape VM.Standard.E6.Flex \
  --ocpus 16 \
  --memory-gb 128 \
  --instances 16
```

If the user does not know the region name:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py --list-regions
```

If the user knows the region but not the exact shape name:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py \
  --region us-ashburn-1 \
  --list-shapes \
  --shape-filter E6
```

## Workflow

1. Parse the user request into:
   - `region`
   - `shape`
   - total OCPUs, or per-instance `ocpus` plus `instances`
   - total or per-instance memory, if provided
   - optional `availability-domain`
2. Normalize common shorthand before asking questions:
   - `ashburn`, `asburn`, or `iad` -> `us-ashburn-1`
   - `phoenix` or `phx` -> `us-phoenix-1`
   - `vm e5`, `e5 vm`, or `e5` -> `VM.Standard.E5.Flex`
   - `vm e6`, `e6 vm`, or `e6` -> `VM.Standard.E6.Flex`
3. If the user gives total OCPUs but not a VM size, prefer `--total-ocpus`.
   - The helper defaults to about 50 OCPUs per VM and rounds up the instance count.
   - For `VM.Standard.E5.Flex`, the helper defaults memory to 12 GB per OCPU.
   - For `VM.Standard.E6.Flex`, the helper defaults memory to 8 GB per OCPU.
   - State these assumptions in the answer.
4. If region is missing or ambiguous, list available regions and ask the user to choose one.
5. If shape is missing or ambiguous, list shapes in the chosen region and ask the user to choose one. Use `--shape-filter` for partial names like `E6`, `GPU`, or `A1`.
6. Run the helper script with the chosen values.
7. Summarize:
   - target total OCPUs and memory
   - per-instance split used for the check
   - each AD's capacity status
   - relevant quota availability when quota names are discoverable
   - the safest AD recommendation
8. Include caveats:
   - capacity is point-in-time
   - `AVAILABLE` is not a reservation
   - quota does not guarantee host capacity
   - `available-count: null` means OCI did not provide an exact count

## Interpretation

- Prefer ADs where host capacity is `AVAILABLE` and both OCPU and memory quota meet or exceed the requested totals.
- Treat `OUT_OF_HOST_CAPACITY` as not suitable for the requested shape config even if quota is sufficient.
- Treat missing quota data as unknown, not as zero.
- If all ADs are unavailable, suggest trying a different AD, shape family, smaller per-instance size, smaller batch, or requesting/reserving capacity through the normal OCI process.
- When presenting region or shape options, keep the list scoped and readable. For shapes, filter by the family the user mentioned when possible.

## Resource

- `scripts/check_oci_capacity.py`: checks AD-level compute capacity and relevant service-limit availability using the OCI CLI.
