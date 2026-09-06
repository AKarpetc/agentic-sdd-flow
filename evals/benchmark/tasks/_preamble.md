Non-interactive benchmark run. There is no human on the other side: never ask a question and never
wait for input. At every approval gate (design, spec, plan, branch finish) pick the recommended option
yourself, state the assumption in one line, and continue. Work only inside this repository: git is
initialised on branch `main`, commit there as you go, never push, never open a PR. The .NET SDK is on
PATH and packages restore from nuget.org only. Existing behaviour that contradicts the acceptance
criteria below is a defect to fix at its root, not to work around in the new code. The acceptance
criteria are checked by an external HTTP client against `dotnet run --project src/Orders.Api`, so the
routes, status codes and JSON shapes must be exactly as written.

End with a final message that contains exactly these three lines (and nothing after them):
STATUS: done|partial|blocked
COMMITS: <number of commits you made>
NOTES: <one line>
