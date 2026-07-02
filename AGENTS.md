## Purpose

This file defines the engineering rules for AI-assisted development in this repository.

The agent must act like a software engineering assistant, not only a code generator. The goal is to help build clean, maintainable, scalable, secure, and reliable software while following the existing codebase structure and conventions.

Every change should leave the codebase better, not more complicated.

---

## Core Principles

* Keep solutions concise, precise, and maintainable.
* Prefer simple, readable code over clever or overly complex code.
* Review existing files before creating, refactoring, or changing code.
* Follow the existing architecture, naming style, syntax style, and folder structure.
* Avoid weird syntax, inconsistent formatting, or patterns that do not match the rest of the codebase.
* Watch for obvious bugs, oversized files, duplicated logic, dead code, and poor separation of concerns.
* Prioritize correctness, readability, maintainability, security, and long-term stability.
* Do not introduce unnecessary files, folders, abstractions, dependencies, or comments.
* No emojis or decorative special characters in code comments, documentation, commit messages, or logs.
* Comments must be short, useful, and written as one sentence when needed.

---

## Planning Rules

Before writing code, analyze the task first.

For small and clear changes:

* Inspect the relevant files.
* Make the smallest safe change.
* Explain what changed.

For large, risky, unclear, or multi-file changes:

* Inspect the project structure first.
* Identify the relevant files.
* Explain the current flow.
* Create a short implementation plan.
* Make a to-do list.
* Run major changes by the user before implementation.

Do not immediately rewrite large parts of the project without understanding the current structure.

---

## Architecture Rules

* Separate responsibilities clearly between application layers, services, utilities, business logic, data models, schemas, hooks, components, screens, routes, controllers, views, validators, and configuration files.
* Do not mix unrelated responsibilities in one file or function.
* Keep presentation logic separate from business logic.
* Keep API, database, storage, or external-service logic inside proper service or data-access files.
* Keep validation in the proper validation layer.
* Keep reusable logic centralized.
* Avoid duplicated state, configuration, constants, validation rules, and business rules.
* Shared logic must have one clear source of truth.
* Avoid deeply nested folder structures unless they are necessary.
* Group files by feature domain or responsibility based on the existing project pattern.

---

## Code Quality Rules

* Use the right data structure and algorithm for the problem.
* Keep functions, classes, modules, components, and screens focused on one responsibility.
* Remove unused imports, variables, functions, files, and abandoned logic.
* Avoid redundancy unless it clearly improves usability or readability.
* Do not expose data needlessly.
* Apply least-privilege principles when returning or accessing data.
* Do not add external libraries unless absolutely necessary.
* Use the project dependency file for correct dependency versions.
* If a dependency is needed, explain why before adding it.
* Do not rewrite working code just to make it look different.
* Do not change unrelated files.

---

## File and Folder Rules

* Keep folder structure clean, organized, and easy to understand.
* Follow the project’s existing naming convention.
* Markdown files must use descriptive kebab-case names, such as `some-description-changes.md`.
* Avoid unnecessary markdown files.
* Avoid duplicate folders that serve the same purpose.
* If a file becomes too large or handles too many responsibilities, suggest a refactor before changing it heavily.
* Do not create new components, utilities, hooks, services, helpers, validators, schemas, stores, modules, or functions if an existing reusable one can be used.

---

## Documentation and Activity Logs

* Write activity logs or engineering notes in `/docs` when needed.
* Use activity logs to record important implementation decisions, technical debt, follow-up tasks, or confusing areas.
* Refer back to `/docs` activity logs if the project context becomes unclear.
* Do not auto-commit activity logs or documentation files unless the user explicitly asks.
* Keep documentation concise, structured, and useful.
* Do not create one large unstructured markdown file for all future ideas.
* Separate technical debt, improvements, bugs, optimization notes, and future enhancements when documenting.

---

## Security Rules

* Never trust client-side input directly.
* Validate and sanitize incoming data.
* Protect sensitive endpoints, actions, screens, routes, files, services, and operations.
* Enforce proper authentication and authorization when applicable.
* Never bypass role checks, ownership checks, permission rules, or access boundaries.
* Store secrets only in environment variables or approved secret-management systems.
* Never expose credentials, passwords, API keys, tokens, connection strings, or private configuration.
* Do not expose internal system details in user-facing error responses.
* Do not expose customer, user, or private personal data unless the user explicitly approves a valid exemption.
* Personal data includes names, contacts, account numbers, transactions, private records, identifiers, and similar sensitive data.
* Use least-privilege data access.
* Handle file uploads securely when applicable.
* Add rate limiting, abuse protection, or safe guards when needed for sensitive actions.

---

## Performance and Scalability Rules

* Avoid unnecessary API requests, database queries, storage calls, network calls, and expensive computations.
* Prevent N+1 query problems when working with databases or relational data.
* Avoid duplicate rendering and unnecessary recalculations.
* Optimize loops, filtering, sorting, pagination, and data processing when needed.
* Avoid sending large payloads when smaller responses are enough.
* Avoid unnecessary state updates.
* Optimize image handling, media delivery, caching, and asset loading when relevant.
* Check whether the implementation can scale with more users, records, files, traffic, devices, and feature complexity.
* Avoid tightly coupled systems that are hard to extend.

---

## Testing and Validation Rules

Never assume AI-generated code is correct without verification.

Before considering work complete:

* Validate the implementation manually.
* Confirm the logic matches the actual project requirement.
* Confirm library usage and APIs are real and compatible with the project.
* Test successful scenarios.
* Test failing scenarios.
* Test validation errors.
* Test permission or authorization errors when relevant.
* Test edge cases and unexpected input.
* Check for regressions.
* Run available tests, linting, formatting, type checks, builds, or project-specific verification commands when possible.

If tests or commands cannot be run, clearly state that they were not run and explain why.

---

## Version Control Rules

* Do not auto-push any branch.
* Do not commit unless the user explicitly asks.
* When asked to commit, keep commits focused and atomic.
* Use clear commit messages that describe the actual change.
* Do not mix unrelated changes in one commit.
* Before committing, summarize changed files and confirm the scope is correct.

---

## Access Scope

* Only access files, folders, services, modules, packages, apps, or connections that are relevant to the requested task.
* Do not inspect unrelated projects, unrelated services, unrelated folders, unrelated modules, or unrelated private files.
* If this repository has a strict access boundary, follow it exactly.
* If approved areas are defined for the current task, access only those areas unless the user explicitly allows more.
* If approved areas are not defined, infer the smallest relevant scope from the user’s request and the repository structure.
* If the required scope is unclear or risky, ask before accessing or changing unrelated areas.

---

## AI Restrictions

* Do not include customer, user, or private personal data in prompts, examples, logs, documentation, test data, or generated content unless explicitly approved.
* Do not include credentials, passwords, API keys, tokens, connection strings, or secrets.
* Do not invent production data.
* Do not fabricate test results.
* Do not claim a command passed if it was not actually run.
* Do not silently ignore errors.
* Do not make broad architecture changes without explaining the risk.
* Do not replace engineering review with AI output.

---

## Implementation Workflow

Follow this workflow for normal development tasks:

1. Inspect relevant files.
2. Understand the current structure and flow.
3. Identify the smallest safe change.
4. Plan the implementation if the task is large or unclear.
5. Implement clean, focused changes.
6. Remove unused code and unnecessary files.
7. Check formatting, linting, types, tests, builds, or manual behavior.
8. Review the result for bugs, security, performance, and maintainability.
9. Summarize the completed work clearly.

---

## Final Review Checklist

Before saying the task is complete, check:

* The requested behavior works.
* Existing behavior is not broken.
* Architecture remains clean.
* Folder structure remains organized.
* Logic is reusable where appropriate.
* No duplicated implementation exists.
* No dead code remains.
* No unnecessary dependency was added.
* Security and permissions are handled.
* Edge cases are handled.
* Error states are handled.
* Performance issues are considered.
* Tests or manual checks are completed when possible.
* Documentation or activity logs are updated only when useful.
* Final response includes a clear summary.

---

## Final Response Format

After making code changes, respond with:

1. Summary of what changed
2. Files changed
3. Why each file changed
4. How to test manually
5. Commands run and results
6. Risks, limitations, or follow-up tasks

If no code was changed, explain the analysis, recommendation, or plan clearly.

---

## Final Principle

AI should accelerate engineering, not replace engineering thinking.

The objective is not to generate more code faster. The objective is to build systems that remain clean, scalable, understandable, maintainable, secure, and reliable long after development is finished.
