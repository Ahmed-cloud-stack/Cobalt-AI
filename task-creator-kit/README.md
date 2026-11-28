# Task creator handoff

Start with [PLAYBOOK.md](PLAYBOOK.md), then paste [the creator prompt](prompts/creator.md) into the new workspace. This is a workspace kit. Each directory under `examples/` is a separate Harbor task package.

- `prompts/` contains the creator, blind solver and reviewer prompts.
- `scripts/` contains portable scaffolding, package checks, public-workspace setup, Harbor controls, Docker replay and the binary release gate.
- `examples/` contains three complete task trees, including the final supplied Exact Coating Map v1.0.1 upload, including their original instructions, Dockerfiles, reference solutions and fixture generators. Shutter Recorder Likelihood is v1.0.6 at commit `1b24b43e5a1e929a4ed51c0aefe98a7d3d76f7ca`.
- `history/` contains retained task-specific edit scripts and grading wrappers from the shutter workflow.
