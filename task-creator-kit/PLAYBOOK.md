# Task creator playbook

## Workspace setup

Extract this kit outside the release repository. Install Git, Bash, Python 3.11+, Docker, and Harbor with a Docker provider. The scripts target Linux with GNU coreutils and tar. Harbor 0.27.0 was used locally. Enable fetch access for dependency installation during the Docker build. Use [the creator prompt](prompts/creator.md) in the new workspace and fill in the domain, repository and destination branch. Keep task authoring, blind workspaces, build caches and job logs outside the upload tree.

## Package format

Run `scripts/new-task.sh NEW_TASK_DIR NAMESPACE/SLUG` to create the layout and runtime starting point. Complete the public instructions, starter, reference and verifier before running the controls.

```text
my-task/
  task.toml                # Harbor schema, identity, version, limits, network
  instruction.md           # complete public contract
  README.md                # seven sections listed below
  environment/
    Dockerfile             # starter runtime and public assets only
    starter source and public fixtures
  solution/
    solve.sh               # executable setup and reference install
    reference and any required solution assets
  tests/
    test.sh                # executable verifier entry point
    verifier, fixture generators and private expected results
```

README headings are **Summary**, **What the agent sees**, **What the agent must get right**, **What makes it hard**, **How the answers are produced**, **Checks run**, and **Running it**. Include the commands, limits, versions and observed scores. Use a new task identity for an original task and bump the version each time you resubmit an existing package. Start from the example TOML. Its schema is 1.4, the environment uses `network_mode = "no-network"`, and CPU, RAM and verifier timeouts are declared there. Leave Compose network policy and Harbor’s egress sidecar under Harbor control. The example Dockerfiles install `tmux=3.3a-3` and check `command -v tmux && tmux -V`. This pin uses Debian Bookworm. Align the image with the target portal requirements. Fetch authorized large inputs in the Dockerfile with version and digest verification when possible. The ZIP budget is 2.5 MB. Keep the ZIP root at the task contents as shown above.

## Design and verification

1. Choose a fresh problem with a concrete user-visible result. Define the CLI, output schema, edge cases, tolerances and workload limits. Make every tested requirement discoverable from the instructions. A patch budget is optional. Where used, state exactly how additions and deletions are counted.
2. Make the public sample touch the new behavior. Build a reference and generate answers with an independent method. The shutter example pairs state-space filtering with high-precision dense Gaussian checks, plus a separate block oracle for large streams. The other examples show generated fixtures and fingerprint-based checks.
3. Give the verifier small exact cases, sensible regressions, adversarial valid inputs and stress at the stated limits. Derive expected answers independently of the submission. Test the reference at the largest valid workloads. Use an unprivileged verifier subprocess for candidate code and protect private input fixtures and expected answers. Write exactly `1` or `0` to `/logs/verifier/reward.txt`. Return 1 only if every required check passes. A missing reward, crashed harness or ambiguous test invalidates the trial.
4. Freeze the public inputs, build inputs, reference and suite. Record their revision and image digest. Run the controls with `scripts/controls.sh TASK_DIR NEW_JOBS_DIR`. The equivalent Harbor invocations are `harbor run -p TASK_DIR -e docker -a oracle` and the same with `-a nop`. Give timed runs a quiet host.

## Blind attempts and release gate

- Create five copies with `scripts/public-snapshot.sh TASK_DIR NEW_PUBLIC_DIR`. Put each copy in a separate workspace or container with private files unmounted and no inherited creator context. With shared-host subagents, a fresh context and a directory restriction are useful but are not filesystem isolation. Use the blind-solver prompt.
- Seal the final files with `scripts/seal.sh APP_OVERLAY NEW_SEAL_DIR` before showing any hidden results. This preserves the overlay and records hashes. Use the resulting `app/` directory for replay. Record source and sample hashes and retain stdout, model/version, duration and rewards. For patch-based tasks, grade the submitted edits and generated outputs exactly as saved. Label incomplete attempts and replace invalid trials without counting them as failures. Use fresh attempts on changed tasks.
- Grade against the same suite and runtime. If a portal/provider run is unavailable, for the example-style images use `docker build -t IMAGE TASK_DIR/environment` then `scripts/replay.sh TASK_DIR IMAGE oracle NEW_RESULT_DIR` or `nop`. For each blind replay, pass `blind NEW_RESULT_DIR SEALED_APP_OVERLAY`, where the overlay contains files relative to `/app`, including `output/sample.json` when required. Adapt the script for tasks with other paths or deletion-based patches. The NOP and Oracle Harbor runs are preferred release evidence.
- Require **Oracle reward 1, NOP reward 0, and 0 or 1 full pass out of five**. `scripts/gate.py` accepts the Oracle, NOP and five distinct trial reward files or directories. Use the logs to check that scores reflect genuine task outcomes. Retry timeout-only verdicts on a quiet runner before counting them. Try a harder, meaningful task requirement if two or more pass, then repeat the controls and fresh blind trials. Keep earlier versions and logs for comparison.
- Run `scripts/check-package.py TASK_DIR --zip FILE.zip`. Inspect the archive, commit the exact task tree and push to the authorized branch. Verify the remote SHA and return the commit and ZIP links.

## Local versus portal calibration

The stricter local 0–1/5 result is a release gate for the creation workflow. Portal calibration in this project allowed up to 3/10 full passes **per model**. Use the saved package version on the portal, get the required results for each model, and investigate genuine failure labels. Local and portal models, runners and attempt budgets can differ. One earlier shutter revision passed the local gate and later went 7/7 on the portal. The included v1.0.6 had Oracle 90/90, NOP 47/90 with zero reward, and 0/5 local full blind passes. Its portal result was pending at handoff. A new workspace can reproduce the protocol and frozen fixture results. Blind solver outcomes will vary.

## Provider fallback used here

When the local Harbor Docker provider could not apply its egress mode, we built the exact environment image first and used a temporary task copy with that prebuilt image and a local offline Docker override. The shipped task kept its network settings in task.toml. The local proxy certificate was provided as a build secret when needed. Keep provider overrides and machine credentials outside the upload. Historical wrappers and per-version edit scripts are documented in [history](history/README.md).
