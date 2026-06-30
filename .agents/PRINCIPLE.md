# General principles for AGENT, codex

* generate concise, short solutions for new modules or code.
* watch over engineering, oversized files needing refactor.
* watch for weird sytanx/style mismatching rest of codebase.
* watch for obvious bugs.
* prioritize concise, precise code and docs changes.
* no emojis or special characters in comments.
* write activity log md in /docs refer back if confused.
* make to-do list, run major changes by userfirst.
* review existing files before refactor or change.
* markdown files use name (ex. some-description-changes.md).
* don't auto-commit activity logs and docs.
* comments: one liner, one sentences.

# Code Quality

* right data structure and algorithms for problem.
* don't expose data needlessly (least privilege).
* no external libraries unless absolutely necessary.
* use project dependency file for correct versions.
* avoid redundancy unless improve usability.

# Version Control

* commit after significant changes, clear messages.
* keep commits focused, atomic.
* no auto-push any branch.
* access only these two connections client micro site and connections service micro site.

# AI Restrictions

* no customer personal data -names contacts account numbers transactions unless approved exemption.
* no credentials password api keys tokens connection strings.
