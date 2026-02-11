## Coding guidelines for suggested changes

- Do not use emojis.
- Keep code clean and minimal: no dead code, no unnecessary abstractions.
- Comments: no “commentary” comments. Add short, informative comments when needed to prevent misunderstanding (tricky logic, edge cases, invariants, security-sensitive parts). 
- Use clear naming of variables.
- If something is unclear, state assumptions in the response (not in code). Ask for clarification only if it materially affects the solution.
- Follow best practices where relevant: correctness and security first, explicit error handling, consistent style, maintain backwards compatibility unless told otherwise, avoid obvious performance pitfalls.
- Output:
  - Small refactor: only include the code that must change using “before/after” snippets.
  - Large refactor: provide complete updated file(s).
- End with a short summary of what changed and why.
- Sources: consult reputable web sources when needed for uncertain API/library behavior.