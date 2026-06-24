# Install To Codex

This guide shows how to install and validate the OCI Capacity Query skill in Codex.

The skill is designed for Codex, and it can also be used by other agents that support skills with a `SKILL.md` entry point. This repository contains one skill:

```text
skills/oci-capacity-checker
```

## Before You Start

Install and configure the OCI CLI first. The skill uses your local OCI CLI authentication and does not ask for cloud keys or tokens.

```bash
brew install oci-cli
oci setup config
oci iam region list
```

If `oci iam region list` succeeds, your local OCI CLI is ready.

## Step 1: Get The Repo Locally

Choose one option.

### Option A: Clone With Git

Use this option if you are comfortable with Terminal and want future updates to be easy.

GitHub copy-and-paste path:

1. Open the GitHub page for this repo.
2. Click `Code`.
3. Copy the HTTPS URL.
4. Open Terminal.
5. Type `git clone `, paste the URL, and press Enter.

Direct command:

```bash
git clone https://github.com/zhangqizq-ai/oci-capacity-query.git
```

This creates a local folder named `oci-capacity-query`.

To clone into a specific folder:

```bash
cd ~/Documents
git clone https://github.com/zhangqizq-ai/oci-capacity-query.git
```


### Option B: Download The ZIP

Use this option if you do not want to use Terminal.

1. Open the GitHub page for this repo.
2. Click `Code`.
3. Click `Download ZIP`.
4. Unzip the downloaded file.
5. Move the unzipped folder somewhere easy to find, such as `Documents`.


## Step 2: Open The Repo In Codex

1. Open Codex.
2. Click `Add project` or `Open folder`.
3. Select the cloned or downloaded `oci-capacity-query` folder.
4. Start a new thread in that project.

Codex automatically sees repo-local skills and You do not need to manually copy the skills for normal use inside this repo.

## Optional: Add The Skill Globally From A Local Copy

Use this only if you want the OCI Capacity Checker skill to appear in Codex projects outside this repo. Most users can skip this and use the GitHub install command above.

From inside the cloned or downloaded repo, run:

```bash
mkdir -p ~/.codex/skills
cp -R skills/oci-capacity-checker ~/.codex/skills/
```

Then start a new Codex session. The skill should be available from any project.

If you want the global install to track repo changes while you continue editing the skill, symlink instead of copying:

```bash
REPO_ROOT=/path/to/oci-capacity-query
mkdir -p ~/.codex/skills
ln -s "$REPO_ROOT/skills/oci-capacity-checker" ~/.codex/skills/oci-capacity-checker
```

Global install notes:

- The typical global location is `~/.codex/skills/`.
- Keep the directory name exactly `oci-capacity-checker`.
- This repo has one skill, so there are no shared skill folders to copy.
- If the skill does not appear immediately, start a new Codex session.

## Step 3: Validate The Skill Is Available

Start a Codex thread and ask:

```text
Check the capacity of VM E6 with total 1000 OCPUs in Ashburn region.
```

Codex should use the OCI Capacity Checker skill and run the bundled helper script:

```text
skills/oci-capacity-checker/scripts/check_oci_capacity.py
```

Expected behavior:

- Codex normalizes `VM E6` to `VM.Standard.E6.Flex`.
- Codex normalizes `Ashburn` to `us-ashburn-1`.
- Codex checks all availability domains in the region unless you name a specific one.
- Codex reports host capacity and service-limit quota separately.

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

Real output depends on your tenancy, region, quota, availability domains, and live OCI capacity.

## Troubleshooting

If Codex says the skill is unavailable:

- Restart Codex or start a new session.
- Confirm the folder exists at `~/.codex/skills/oci-capacity-checker` for global installs.
- Confirm the repo contains `skills/oci-capacity-checker/SKILL.md`.

If the helper cannot call OCI:

- Run `oci iam region list` in Terminal.
- If that fails, run `oci setup config` again.
- Confirm the same terminal environment can find `oci` with `which oci`.

## Disclaimer

This is an independent, unofficial project. It is not created, maintained, endorsed, supported, or certified by Oracle. It uses OCI APIs through the local OCI CLI, but it is not an Oracle official tool or Oracle official capacity signal.
