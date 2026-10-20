---
name: release-packaging-workflows
description: Use when packaging a release whose deliverable spans versioned docs, release notes, deployment artifacts, or large out-of-git binaries that must ship reproducibly.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [release, packaging, docs, artifacts, ci-cd, versioning]
    related_skills: [github-pr-workflow, vps-autodeploy-pipelines, hermes-agent-skill-authoring]
---

# Release Packaging Workflows

## Overview

This umbrella covers release packaging as a maintainer task: turning a set of changes into a coherent shipped surface.

Use it when the work is not just "write code" or "push a commit," but making sure version markers, release notes, artifacts, and deployment assumptions all line up.

## When to Use

- A docs-heavy repo needs a version bump, release note, and adoption-surface cleanup
- A deployment/release pipeline must ship a large binary artifact that intentionally stays out of git
- The release output spans source changes plus packaging metadata, notes, assets, or CI fetch logic
- A rollback must restore both code and attached artifacts coherently

## Core Maintainer Rule

Treat the release note, version markers, and shipped artifact source-of-truth as one package.
A release is incomplete if the docs say one thing, the CI pipeline builds another thing, and the runtime expects a third.

## Workflow

### 1. Inspect the existing release surface first
Check:
- visible version strings and badges
- release notes / changelog paths
- README adoption surfaces
- CI artifact fetch/build steps
- runtime expectations for bundled assets

### 2. Decide the packaging class

#### A. Documentation-heavy release
Use when the main change is docs, templates, examples, skills, or repo positioning.

Required outputs:
- coherent release note
- synchronized README / repo-map updates
- aligned version/status surfaces
- verified git scope matching the release note

#### B. Artifact-heavy release
Use when runtime needs a large binary (`.onnx`, `.bin`, `.pt`, `.safetensors`, etc.) that is intentionally excluded from git.

Required outputs:
- official artifact source (release asset or equivalent)
- CI fetch step before image/package build
- checksum/size verification
- stable runtime path preserved in the built artifact/image
- rollback path that resolves the matching artifact version

### 3. Prefer build-time packaging over hidden runtime state
If an app expects a file at a fixed runtime path, do not rely on a one-time manual server copy.
Prefer: fetch in CI -> verify -> build/package -> deploy the finished artifact.

### 4. Keep release communication aligned
For every packaged release, make sure these agree:
- what changed
- what ships
- how it is versioned
- how it is rolled back
- what was actually verified

## Absorbed sibling workflows

### Documentation release packaging
narrow sibling absorbed: `documentation-release-packaging`

Carry forward these rules:
- write the release note early as the packaging anchor
- update README/repo-map/adoption surfaces, not just the note itself
- verify staged paths and commit scope against the intended release package
- report whether the release is packaging-only or backed by runtime proof

### Large model / binary artifact packaging
narrow sibling absorbed: `release-artifact-model-packaging`

Carry forward these rules:
- keep large binaries out of git when appropriate, but never out of the official release path
- fetch the artifact into CI before `docker build` or equivalent packaging
- verify checksum, size, and runtime path before claiming success
- keep rollback symmetric with deploy so code and artifact versions do not drift

## Common Pitfalls

1. Bumping visible version strings without adding the release note that explains them.
2. Adding release notes without updating README/adoption surfaces users actually see.
3. Shipping CI/package logic that still depends on a manual artifact copy on one server.
4. Verifying only that a file exists, not that it is the right binary at the right path.
5. Letting rollback logic ignore artifact versioning while deploy logic depends on it.

## Verification Checklist

- [ ] Release note path exists if the change is versioned/documented
- [ ] README / public adoption surfaces reflect the packaged release
- [ ] Artifact source-of-truth is explicit
- [ ] CI/package flow fetches required binaries before build when needed
- [ ] Runtime path assumptions were checked
- [ ] Rollback path stays symmetric with deploy path
- [ ] Final report separates verified facts from packaging assumptions
