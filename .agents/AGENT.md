# AI Engineering Workflow & Development Rules

## Core Engineering Mindset

Think and execute as an engineering professional, not just an AI code generator. Every implementation must focus on maintainability, scalability, readability, performance, and long-term project stability. AI should assist development, but all generated solutions must pass engineering review standards before completion.

The goal is not only to make the feature work, but to ensure the system remains clean, understandable, reusable, optimized, and scalable for future development.

---

# Phase 1 — Planning & Architecture

Before writing any code, always analyze and define the structure of the system first.

## Architecture Planning

- Understand the feature scope completely before implementation.
- Define the responsibility of each layer clearly.
- Separate frontend, backend, services, utilities, and business logic properly.
- Avoid mixing responsibilities between components, views, services, and models.
- Make sure the architecture supports future scalability and feature expansion.

## Folder & File Structure

- Keep folder structures clean, organized, and easy to understand.
- Avoid deeply nested or overly complex structures unless necessary.
- Group files based on responsibility and feature domain.
- Make naming conventions consistent across the project.
- Avoid unnecessary files or duplicate folders.

## Reusability First

- Design reusable logic and components whenever possible.
- Avoid repetitive or redundant implementations.
- Centralize reusable utilities, constants, validators, types, and configurations.
- Build systems that can scale and adapt without rewriting core logic.

## Single Source of Truth

- Avoid duplicated state, configuration, validation, constants, and business rules.
- Shared logic should only exist in one reliable source.
- Prevent inconsistencies caused by duplicated implementations.

---

# Phase 2 — Implementation

Write clean, maintainable, and optimized code.

## Clean Code Principles

- Keep logic simple and easy to understand.
- Avoid unnecessary complexity.
- Prioritize readability over clever implementations.
- Use meaningful naming conventions.
- Keep functions and components focused on a single responsibility.

## Code Splitting & Modularity

- Split large logic into reusable modules or services.
- Prevent massive files that handle too many responsibilities.
- Separate business logic from UI logic.
- Keep APIs, services, serializers, schemas, hooks, and utilities modular.

## Dead Code Elimination

- Remove unused code, imports, files, variables, and functions.
- Do not leave experimental or abandoned logic in production code.
- Ensure the project remains clean and maintainable over time.

## Minimal Comments

- Avoid excessive comments.
- Code should explain itself through clean structure and naming.
- Add comments only when:
  - explaining complex business logic,
  - documenting important decisions,
  - or improving maintainability for other developers.
- Do not comment obvious code behavior.

---

# Phase 3 — Optimization & Performance

Every implementation must consider performance and system efficiency.

## Performance Optimization

- Avoid unnecessary API requests and database queries.
- Prevent duplicate rendering and expensive computations.
- Optimize loops, filtering, and data processing.
- Reduce large payloads and unnecessary state updates.
- Prevent N+1 database query problems.
- Optimize image handling, media delivery, and caching strategies when needed.

## Scalability Review

Before finalizing:

- Check if the implementation can scale with more users and data.
- Avoid tightly coupled systems.
- Make sure the feature can evolve without major rewrites.
- Design for maintainability and future extensibility.

---

# Phase 4 — Security & Reliability

Security must always be part of development.

## Security Rules

- Never trust frontend input directly.
- Validate and sanitize all incoming data.
- Protect sensitive endpoints and actions.
- Use proper authentication and authorization checks.
- Store secrets only in environment variables.
- Avoid exposing internal system details in error responses.
- Implement rate limiting where necessary.
- Handle file uploads securely.

## Reliability

- Handle edge cases properly.
- Prevent crashes caused by invalid states or unexpected input.
- Ensure graceful failure handling.
- Make sure systems remain stable under different conditions.

---

# Phase 5 — Testing & Validation

Never assume AI-generated code is correct without testing.

## AI Verification Rule

- Verify all AI-generated implementations manually.
- Validate library usage, APIs, dependencies, and documentation.
- Confirm generated logic matches actual project requirements.
- Never blindly trust generated code.

## Testing Standards

- Perform end-to-end testing for complete user flows.
- Ensure no broken logic, regressions, or hidden issues exist.
- Validate both successful and failing scenarios.
- Review edge cases and unexpected behaviors.
- Ensure all tests pass before considering implementation complete.

## Manual Review

- Review readability and maintainability.
- Review architecture consistency.
- Review developer experience.
- Confirm the implementation follows all engineering rules.

---

# Phase 6 — Documentation & Improvements

Development does not end after implementation.

## Improvement Tracking

- If there are future improvements or suggestions, document them properly.
- Organize suggestions clearly and separately.
- Avoid placing all future ideas in one large unstructured markdown file.
- Categorize technical debt, optimizations, scalability plans, and future enhancements.

## Feedback & Engineering Notes

Every implementation should include:

- what was implemented,
- how it was implemented,
- where the logic exists,
- why the approach was chosen,
- and what the expected output or behavior is.

This improves maintainability, onboarding, and future development decisions.

---

# Phase 7 — Final Engineering Review

Before considering the task complete, review the entire implementation against all engineering rules.

## Final Checklist

- Clean architecture
- Reusable logic
- No dead code
- No redundant implementation
- Organized folder structure
- Optimized performance
- Security validation
- Scalable implementation
- Minimal but useful comments
- Modular code splitting
- Passing e2e tests
- Verified AI-generated logic
- Organized documentation
- Maintainable developer experience

If all engineering standards pass successfully, then the implementation is considered production-ready.

---

# Final Principle

AI should accelerate engineering, not replace engineering thinking.

The objective is not to generate more code faster. The objective is to build systems that remain clean, scalable, understandable, maintainable, and reliable long after development is finished.

Every feature should leave the codebase better, not more complicated.
