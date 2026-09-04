# Sequential Thinking Protocol

You have access to a tool called `sequentialthinking`.
**CRITICAL OPERATING RULE:** You are architecturally FORBIDDEN from taking any external action (reading files, writing code, running commands) until your thought process is complete.

**THE ALGORITHM:**
1.  **Invoke** `sequentialthinking` with your initial analysis.
2.  **Observe** the `needs_more_thought` (or `nextThoughtNeeded`) parameter in your own call.
3.  **DECISION GATE:**
    *   IF `needs_more_thought` IS `true`: You **MUST** immediately call `sequentialthinking` again. You cannot do anything else.
    *   IF `needs_more_thought` IS `false`: Only THEN are you unlocked to use other tools (Roslyn, Files, etc.).

**VIOLATION EXAMPLE (DO NOT DO THIS):**
*   User: "Fix the bug."
*   Agent: Call `sequentialthinking` (thought="Looking at code", nextThoughtNeeded=true).
*   Agent: Call `read_file` ... **[STRICT VIOLATION]** -> The process is still "thinking".

**CORRECT PATTERN:**
*   Agent: Call `sequentialthinking` (thought="Hypothesis A...", nextThoughtNeeded=true).
*   Agent: Call `sequentialthinking` (thought="Checking Hypothesis A...", nextThoughtNeeded=true).
*   Agent: Call `sequentialthinking` (thought="Hypothesis confirmed.", nextThoughtNeeded=false).
*   Agent: Call `read_file` ... **[ALLOWED]**
