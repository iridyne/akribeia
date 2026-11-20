---
name: Incident
about: Report a real failure with a trace excerpt and a localization
title: "[incident] "
labels: incident
---

## Observed failure

<!-- What happened, from the user's perspective. Redact prompts, paths, hosts, and credentials. -->

## Earliest unrecoverable event

<!-- Walk backward from the symptom. What is the first event execution did not recover from? -->

## Label

- Edge: model-owner / model-context / model-memory / model-tool / model-subagent / model-local-environment / model-external-environment / model-third-party / model-grader / unknown
- Fault: model / owner / harness / tool / environment / third-party / grader / unknown
- Mode:

## Evidence

<!-- A redacted excerpt, a command, a screenshot, or a timestamp. No raw transcript dumps. -->

## Proposed intervention

<!-- Which mapping ID, or "none yet". A rule without an experiment is a hypothesis. -->

## What would prove this label wrong?

<!-- The counter-evidence you would accept. -->