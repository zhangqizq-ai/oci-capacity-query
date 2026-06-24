# OCI Capacity Query

Check Oracle Cloud Infrastructure (OCI) Compute host capacity and service-limit quota from natural-language requests.

This repository contains an agent skill for checking OCI capacity. It is designed for Codex, and the same skill structure can also be used by other agents that support filesystem-based skills with a `SKILL.md` entry point. The skill uses a bundled Python helper and your local authenticated `oci` CLI.

Useful requests include:

- "Check the capacity of VM E6 with total 1000 OCPUs in Ashburn region."
- "Can I launch VM.Standard.E5.Flex with 500 total OCPUs in Phoenix?"
- "Which availability domain has capacity for E6 in Ashburn?"

## Disclaimer

This is an independent, unofficial project. It is not created, maintained, endorsed, supported, or certified by Oracle. It uses OCI APIs through the local OCI CLI, but it is not an Oracle official tool or Oracle official capacity signal.

Capacity results are point-in-time checks only. `AVAILABLE` does not reserve capacity and does not guarantee a future launch will succeed.

## What's Included

- `skills/oci-capacity-checker/SKILL.md` - Agent instructions for natural-language OCI capacity checks.
- `skills/oci-capacity-checker/scripts/check_oci_capacity.py` - CLI helper that calls OCI APIs and prints a Markdown or JSON report.
- `skills/oci-capacity-checker/agents/openai.yaml` - Optional UI metadata for skill-aware agent interfaces.

## Repository Layout

```text
skills/
└── oci-capacity-checker/
    ├── SKILL.md
    ├── agents/
    │   └── openai.yaml
    └── scripts/
        └── check_oci_capacity.py
```

## Installation

### 1. Install prerequisites

Install and configure the OCI CLI before using the skill:

```bash
brew install oci-cli
oci setup config
oci iam region list
```

The helper reads the tenancy OCID from your OCI CLI config by default. You can also pass a compartment or tenancy OCID explicitly with `--compartment-id`.

### 2. Install the skill in Codex

Install from this GitHub repository by pointing Codex at the skill folder:

```bash
install-skill-from-github.py --repo <owner>/oci-capacity-query --path skills/oci-capacity-checker
```

Replace `<owner>` with the GitHub owner or organization that hosts this repo.

After installing, restart Codex so it can load the new skill.

### 3. Use with other agents

For other agents that support skills, install or copy the `skills/oci-capacity-checker` folder into that agent's skills directory. The required entry point is:

```text
skills/oci-capacity-checker/SKILL.md
```

The agent must be able to run the bundled Python script and access the local `oci` CLI.

## Example Skill Prompts

These examples are prompts you can ask Codex or another skill-aware agent. The sample output is illustrative; real values depend on your tenancy, quota, region, availability domains, and live OCI capacity.

### Example 1: Total OCPU Request

Prompt:

```text
Check the capacity of VM E6 with total 1000 OCPUs in Ashburn region.
```

What the skill does:

- Normalizes `VM E6` to `VM.Standard.E6.Flex`.
- Normalizes `Ashburn` to `us-ashburn-1`.
- Splits 1000 total OCPUs into a practical VM count when no per-instance size is provided.
- Checks each availability domain for host capacity and quota.

Sample output:

```markdown
# OCI capacity check: VM.Standard.E6.Flex in us-ashburn-1

- Per instance: 50 OCPUs, 400 GB memory
- Instances: 20
- Required total: 1,000 OCPUs, 8,000 GB memory

| Availability domain | Host capacity | Available count | OCPU quota available | Memory quota available | Quota can fit | Capacity can fit |
|---|---:|---:|---:|---:|---:|---:|
| example:US-ASHBURN-AD-1 | AVAILABLE | unknown | 1,500 | 12,000 | Yes | Status only |
| example:US-ASHBURN-AD-2 | OUT_OF_HOST_CAPACITY | 0 | 1,500 | 12,000 | Yes | No |
| example:US-ASHBURN-AD-3 | AVAILABLE | 24 | 1,500 | 12,000 | Yes | Yes |

Quota limits checked: `standard-e6-core-count`, `standard-e6-memory-count`.

Caveats: capacity is point-in-time, `AVAILABLE` is not a reservation, and quota does not guarantee host capacity.
```

### Example 2: Specific Instance Size

Prompt:

```text
Check whether I can launch 16 VM.Standard.E6.Flex instances with 16 OCPUs and 128 GB memory each in Ashburn.
```

Sample output:

```markdown
# OCI capacity check: VM.Standard.E6.Flex in us-ashburn-1

- Per instance: 16 OCPUs, 128 GB memory
- Instances: 16
- Required total: 256 OCPUs, 2,048 GB memory

| Availability domain | Host capacity | Available count | OCPU quota available | Memory quota available | Quota can fit | Capacity can fit |
|---|---:|---:|---:|---:|---:|---:|
| example:US-ASHBURN-AD-1 | AVAILABLE | 31 | 500 | 4,096 | Yes | Yes |
| example:US-ASHBURN-AD-2 | AVAILABLE | unknown | 500 | 4,096 | Yes | Status only |
| example:US-ASHBURN-AD-3 | OUT_OF_HOST_CAPACITY | 0 | 500 | 4,096 | Yes | No |

Quota limits checked: `standard-e6-core-count`, `standard-e6-memory-count`.

Caveats: capacity is point-in-time, `AVAILABLE` is not a reservation, and quota does not guarantee host capacity.
```

### Example 3: Compare Availability Domains

Prompt:

```text
Find the best Ashburn availability domain for VM E5 with total 500 OCPUs.
```

Sample output:

```markdown
# OCI capacity check: VM.Standard.E5.Flex in us-ashburn-1

- Per instance: 50 OCPUs, 600 GB memory
- Instances: 10
- Required total: 500 OCPUs, 6,000 GB memory

| Availability domain | Host capacity | Available count | OCPU quota available | Memory quota available | Quota can fit | Capacity can fit |
|---|---:|---:|---:|---:|---:|---:|
| example:US-ASHBURN-AD-1 | AVAILABLE | 18 | 700 | 8,000 | Yes | Yes |
| example:US-ASHBURN-AD-2 | AVAILABLE | 7 | 700 | 8,000 | Yes | Unknown |
| example:US-ASHBURN-AD-3 | OUT_OF_HOST_CAPACITY | 0 | 700 | 8,000 | Yes | No |

Quota limits checked: `standard-e5-core-count`, `standard-e5-memory-count`.

Safest recommendation: use example:US-ASHBURN-AD-1 because both quota and reported host capacity appear to fit the request.
```

## Manual CLI Usage

You can also run the helper directly from the repo root.

Check a total OCPU request:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py \
  --region ashburn \
  --shape "vm e6" \
  --total-ocpus 1000
```

Check a specific shape configuration:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py \
  --region us-ashburn-1 \
  --shape VM.Standard.E6.Flex \
  --ocpus 16 \
  --memory-gb 128 \
  --instances 16
```

Check a single availability domain:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py \
  --region us-ashburn-1 \
  --availability-domain 'example:US-ASHBURN-AD-1' \
  --shape VM.Standard.E5.Flex \
  --ocpus 16 \
  --memory-gb 192 \
  --instances 10
```

Emit JSON instead of Markdown:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py \
  --region us-ashburn-1 \
  --shape VM.Standard.E5.Flex \
  --ocpus 16 \
  --memory-gb 192 \
  --instances 10 \
  --json
```

## Discovery Commands

List regions available to your tenancy:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py --list-regions
```

List shapes in a region:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py \
  --region us-ashburn-1 \
  --list-shapes \
  --shape-filter E5
```

## Supported Aliases

The helper normalizes common shorthand:

| Input | Normalized value |
|---|---|
| `ashburn`, `asburn`, `iad` | `us-ashburn-1` |
| `phoenix`, `phx` | `us-phoenix-1` |
| `vm e5`, `vm.e5`, `e5 vm`, `e5` | `VM.Standard.E5.Flex` |
| `vm e6`, `vm.e6`, `e6 vm`, `e6` | `VM.Standard.E6.Flex` |

## How To Read Results

The report shows:

- Per-instance OCPU and memory configuration.
- Total requested OCPUs and memory.
- Host capacity status for each checked availability domain.
- Available service-limit quota for matching OCPU and memory limits when discoverable.
- Whether quota and host capacity appear able to fit the request.

Capacity and quota are separate checks. You may have enough quota but still hit host-capacity limits, or capacity may be available while quota is too low.

## Caveats

- Capacity reports are point-in-time and do not reserve capacity.
- `AVAILABLE` is not a launch guarantee.
- OCI may return `available-count` as `null`; in that case, the helper reports status only.
- Quota names are discovered from OCI shape metadata. If OCI does not return matching quota names, quota availability is reported as unknown.

## Development

This project intentionally has no third-party Python package dependencies. The helper uses the standard library and shells out to the local `oci` CLI.

Run the helper help text:

```bash
python3 skills/oci-capacity-checker/scripts/check_oci_capacity.py --help
```
