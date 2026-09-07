export const meta = {
  name: 'dotnet-sdd',
  description: 'Execute an implementation plan in a .NET repository: implement, test, review, verify findings, bounded fix loop, final review',
  whenToUse: 'After brainstorming + writing-plans produced a plan file for a .NET project. Usually launched by the dotnet-feature skill. mode: "review" gates a branch somebody else already wrote (no plan, no tasks), "light" a small single-project change, "standard" (default) a feature.',
  phases: [
    { title: 'Analyze', detail: 'split the plan into task briefs' },
    { title: 'Plan review', detail: 'plan-reviewer gates the plan against the spec and the conventions' },
    { title: 'Implement' },
    { title: 'Reconcile', detail: 'evidence-reconciler decides when the brief and the repository disagree' },
    { title: 'Tests' },
    { title: 'Debug', detail: 'debugger finds the root cause before another fix' },
    { title: 'Review' },
    { title: 'Verify', detail: 'findings-verifier filters noise' },
    { title: 'Fix' },
    { title: 'Final review' },
  ],
}

// Plugin agents resolve only with the plugin namespace; a bare name would hit a same-named project agent instead.
const PREFIX = 'agentic-sdd-flow:'
const AGENT = {
  implementer: PREFIX + 'dotnet-implementer',
  tests: PREFIX + 'tests-writer',
  reviewer: PREFIX + 'code-reviewer',
  verifier: PREFIX + 'findings-verifier',
  debugger: PREFIX + 'debugger',
  planReviewer: PREFIX + 'plan-reviewer',
  reconciler: PREFIX + 'evidence-reconciler',
}
// The default workflow agent does not receive the injected contract, so every prompt asks for it explicitly.
const RULES_PREAMBLE = 'Read the plugin rules contract (rules/RULES-CONTRACT.md under the agentic-sdd-flow plugin root, or the <rules-contract> block already in your context) before anything else.\n'

const SP_LOOKUP = 'SP=$(ls -d ~/.claude/plugins/cache/*/superpowers/*/skills/subagent-driven-development/scripts 2>/dev/null | sort -V | tail -1); [ -n "$SP" ] || { echo "superpowers SDD scripts not found under ~/.claude/plugins/cache"; exit 2; }'

// Optional-by-design: `baseSha` and `kind` are asked for in the prompt but not required by the schema —
// a model that omits one must not void the whole analysis. Both have a safe default below.
const TASKS = {
  type: 'object', required: ['tasks', 'conflicts'],
  properties: {
    baseSha: { type: 'string' },
    contextPack: { type: 'string' },
    tasks: { type: 'array', items: {
      type: 'object', required: ['id', 'title', 'briefPath', 'files'],
      properties: {
        id: { type: 'integer' },
        title: { type: 'string' },
        briefPath: { type: 'string' },
        kind: { enum: ['code', 'tests', 'verify'] },
        files: { type: 'array', items: { type: 'string' } },
        dependsOn: { type: 'array', items: { type: 'integer' } },
      } } },
    conflicts: { type: 'array', items: { type: 'string' } },
  },
}
const REPORT = {
  type: 'object', required: ['status', 'commits', 'headSha', 'files', 'concerns', 'questions', 'reportPath'],
  properties: {
    status: { enum: ['done', 'done_with_concerns', 'blocked', 'needs_context', 'escalate_model'] },
    commits: { type: 'array', items: { type: 'string' } },
    headSha: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } },
    concerns: { type: 'string' },
    questions: { type: 'array', items: { type: 'string' } },
    reportPath: { type: 'string' },
    contradictions: { type: 'array', items: {
      type: 'object', required: ['claim', 'observed'],
      properties: { claim: { type: 'string' }, observed: { type: 'string' }, sources: { type: 'array', items: { type: 'string' } } } } },
  },
}
const RECONCILIATION = {
  type: 'object', required: ['verdict', 'confidence', 'evidence', 'rationale', 'action', 'staleSources'],
  properties: {
    verdict: { enum: ['brief', 'code', 'undecided'] },
    confidence: { enum: ['high', 'medium', 'low'] },
    evidence: { type: 'array', items: { type: 'object', required: ['source', 'tier', 'supports'],
      properties: { source: { type: 'string' }, tier: { enum: ['executed', 'decided', 'descriptive', 'intent'] }, supports: { enum: ['brief', 'code'] }, date: { type: 'string' }, independent: { type: 'boolean' }, note: { type: 'string' } } } },
    rationale: { type: 'string' },
    action: { type: 'string' },
    staleSources: { type: 'array', items: { type: 'string' } },
    questions: { type: 'array', items: { type: 'string' } },
  },
}
// `kind` decides blocking independently of `severity`: a reproducible failure filed under a soft section
// used to arrive as a `minor` and be deferred for ever. See the severity floor in the dotnet-code-review skill.
const FINDING = {
  type: 'object', required: ['id', 'file', 'severity', 'issue'],
  properties: {
    id: { type: 'string' },
    file: { type: 'string' },
    line: { type: 'integer' },
    severity: { enum: ['critical', 'important', 'minor'] },
    kind: { enum: ['defect', 'convention', 'style'] },
    issue: { type: 'string' },
  },
}
const VERDICT = {
  type: 'object', required: ['approved', 'findings', 'addressed'],
  properties: {
    approved: { type: 'boolean' },
    findings: { type: 'array', items: FINDING },
    addressed: { type: 'array', items: {
      type: 'object', required: ['id', 'addressed'],
      properties: { id: { type: 'string' }, addressed: { type: 'boolean' } } } },
  },
}
const VERIFY = {
  type: 'object', required: ['real', 'confidence', 'evidence'],
  properties: {
    real: { type: 'boolean' },
    confidence: { enum: ['high', 'medium', 'low'] },
    severityAdjustment: { enum: ['critical', 'important', 'minor', 'none'] },
    evidence: { type: 'string' },
  },
}
const SHA = { type: 'object', required: ['sha'], properties: { sha: { type: 'string' } } }
const PLAN_VERDICT = {
  type: 'object', required: ['approved', 'findings', 'summary'],
  properties: {
    approved: { type: 'boolean' },
    findings: { type: 'array', items: {
      type: 'object', required: ['id', 'severity', 'area', 'issue'],
      properties: { id: { type: 'string' }, severity: { enum: ['critical', 'important', 'minor'] }, task: { type: 'integer' }, area: { type: 'string' }, issue: { type: 'string' } } } },
    coverage: { type: 'object' },
    summary: { type: 'string' },
  },
}
const DIAGNOSIS = {
  type: 'object', required: ['rootCause', 'confidence', 'evidence', 'fixBrief', 'files', 'verification'],
  properties: {
    rootCause: { type: 'string' },
    confidence: { enum: ['high', 'medium', 'low'] },
    evidence: { type: 'string' },
    fixBrief: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } },
    reproduction: { type: 'string' },
    verification: { type: 'string' },
    ruledOut: { type: 'array', items: { type: 'string' } },
  },
}
const TESTS_DONE = {
  type: 'object', required: ['status', 'summary'],
  properties: { status: { enum: ['done', 'done_with_concerns', 'blocked'] }, summary: { type: 'string' }, headSha: { type: 'string' } },
}

// Callers sometimes pass args as a JSON-encoded string; destructuring a primitive yields undefined
// for every field and the literal "undefined" leaks into every dispatch prompt. Normalise first,
// then fail fast when a required key is missing.
let workflowArgs = args
if (typeof workflowArgs === 'string') {
  try { workflowArgs = JSON.parse(workflowArgs) } catch { workflowArgs = null }
}
if (!workflowArgs || typeof workflowArgs !== 'object' || Array.isArray(workflowArgs)) workflowArgs = {}
const { project, projectDir, plan, taskKey, spec = '', maxFixRounds = 5, stallRounds = 2, answers = {}, mode = 'standard', truth = {} } = workflowArgs
// truth: { "<taskId>": "brief" | "code" } — the caller's ruling on a contradiction the reconciler could not
// settle on its own (a `code` verdict sends the brief back to its author; the caller decides, then reruns).
const reconciled = []
// light: one small single-project change — no plan review, no per-task review loop, one whole-branch
// review at the end. standard: the full per-task gate. The dotnet-feature skill sizes the change and picks.
const light = String(mode).toLowerCase() === 'light'
// review: the code already exists (the superpowers flow wrote it). No plan, no tasks, no implementer of ours
// until the review says so — just the whole-branch review, the verifier and one bounded fix wave.
const reviewOnly = String(mode).toLowerCase() === 'review'
const skipPlanReview = workflowArgs.skipPlanReview === true || light
const fixCap = light ? Math.min(2, maxFixRounds) : maxFixRounds
const rulings = [], deferred = [], done = [], openQuestions = [], minorDefects = []

const missingArgs = [['project', project], ['projectDir', projectDir], ...(reviewOnly ? [['base', workflowArgs.base]] : [['plan', plan]]), ['taskKey', taskKey]]
  .filter(([, value]) => !value).map(([name]) => name)
if (missingArgs.length) {
  log(`workflow args missing: ${missingArgs.join(', ')}`)
  return { status: 'blocked', mode: light ? 'light' : 'standard', done, rulings, deferred, openQuestions: [`Workflow args missing: ${missingArgs.join(', ')} — pass args as an object with project/projectDir/plan/taskKey`], finalVerdict: null, range: '' }
}

// Fallback only: the SHA normally rides along on the report of the agent that just committed.
// Four `git rev-parse` dispatches per task were 35 % of this workflow's tokens in the 0.2.7 benchmark.
const sha = (label) => agent(
  `Run \`git -C ${projectDir} rev-parse HEAD\` and return the SHA.`,
  { schema: SHA, effort: 'low', label, phase: 'Analyze' }).then(r => (r && r.sha) || 'HEAD')

// The one thing agents can share in this harness is a file. The pack is produced once in Analyze and
// replaces the project graph / package / endpoint / test-home orientation each agent would otherwise redo.
let contextPack = ''
const PACK = () => contextPack ? `Context pack (produced this run, authoritative for the solution layout, packages, endpoints, DI, the test project and the build/test commands): ${contextPack}. Read it before you touch the repository, and do not re-derive what it already states — spend your tool calls on the code this task is about. Report any line of it you find to be wrong.\n` : ''
const describe = (f) => `- [${f.id}] ${f.file}${f.line ? ':' + f.line : ''} — (${f.kind || 'defect'}/${f.severity}) ${f.issue}`
// A scoped re-review re-reads nothing: the rules digest is already injected into its context, and a fix diff
// of a dozen lines does not need the 326-line review skill plus the 225-line checklist read again.
const SCOPED = 'This is a scoped re-review of a small fix diff: work from the injected rules contract, the context pack and the diff. Do not read the full dotnet-code-review SKILL.md or the rule-compliance checklist — walk the changed lines against the contract you already have.\n'
const reviewPrompt = (base, head, extra, scoped) => `${RULES_PREAMBLE}${PACK()}${scoped ? SCOPED : ''}Working directory: ${projectDir}. Project: ${project}.
${plan ? `Run in Bash: ${SP_LOOKUP}; cd ${projectDir}; "$SP/review-package" ${plan} ${base} ${head}` : `Run in Bash: cd ${projectDir}; git diff --stat ${base}..${head} && git diff ${base}..${head} > .superpowers/review-${base}..${head}.diff (create .superpowers first)`}
Then review the printed diff file per the dotnet-code-review skill (Roslyn first via roslyn-query.py).
A violation of the conventions contract is at least Important. ${extra}
Every finding carries a \`kind\`: \`defect\` for a reproducible failure in changed code (race, lost update, overflow, wrong rounding, swallowed exception, resource leak, null dereference, wrong branch), \`convention\` for a rules-contract breach, \`style\` for taste. Apply the severity floor in the skill: a defect is never below \`important\` unless it truly cannot be reached.
approved=true only when no critical or important findings remain. Give every finding a short stable id (F1, F2, …); when re-reviewing, use the ids you were given in addressed[] verbatim. If this is not a re-review, return addressed as an empty array.`

phase('Analyze')
const analysis = reviewOnly ? { tasks: [], conflicts: [], baseSha: workflowArgs.base } : await agent(
  `${RULES_PREAMBLE}Plan file: ${plan}. Working directory: ${projectDir}.
   Run in Bash: ${SP_LOOKUP}; cd ${projectDir}; for every "### Task N" heading in the plan run "$SP/task-brief" ${plan} N
   and return the printed brief path for each task. In the same Bash call run \`git -C ${projectDir} rev-parse HEAD\` and return it as baseSha.

   Then build the **context pack** — this run's shared orientation, so that the twenty-odd agents after you do
   not each re-derive it. Write ${projectDir}/.superpowers/sdd/context-pack.md (create the directory) and return
   its path as contextPack. Produce every section from one pass of the tools, and write nothing you did not observe:
   - **Solution**: the .sln/.slnx path, the projects and their references, the target framework(s) — \`roslyn-query.py ${project} get_project_graph\`.
   - **Packages that decide conventions**: \`get_nuget_packages\` — Mediator vs MediatR, the FluentAssertions major, the mocking library, the xUnit major, the test SDK (VSTest or Microsoft.Testing.Platform, which changes the \`dotnet test\` filter syntax).
   - **Entry points**: \`get_endpoint_map\` (routes → handlers) and \`get_di_registrations\` for the projects the plan touches.
   - **Test home**: the test project the plan's tests belong in, its framework and package versions, and the path of one existing test file that is idiomatic for it (or "none — scaffold needed").
   - **Build & test commands** that work in this repository, verified once by running them: the build command, the full test command, and the narrow-filter form for a single class.
   - **The plan's Global Constraints** section, copied verbatim.
   - **Files the plan touches**, one line each: path → which task, and whether it exists today.
   Keep it under 200 lines and mark anything you could not determine as \`unknown\` rather than guessing.
   For each task list the files it touches (from its Files block), the ids it depends on, and its kind:
   \`code\` when it changes production code, \`tests\` when the task only adds or repairs tests, \`verify\` when it only runs
   or inspects something already built (a smoke run, a coverage check, a documentation sweep with no code change).
   Report conflicts between tasks (same file, contradictory instructions) as strings.`,
  { schema: TASKS, label: 'analyze' })
if (!analysis) {
  log('analyze agent returned nothing')
  return { status: 'blocked', mode: light ? 'light' : 'standard', done, rulings, deferred, openQuestions: ['The plan could not be analysed — check the plan path and rerun.'], finalVerdict: null, range: '' }
}
contextPack = analysis.contextPack || ''
const tasks = analysis.tasks.map(t => ({ ...t, kind: ['code', 'tests', 'verify'].includes(t.kind) ? t.kind : 'code' }))
if (!tasks.length && !reviewOnly) {
  log('no "### Task N" headings found in the plan')
  return { status: 'blocked', mode: light ? 'light' : 'standard', done, rulings, deferred, openQuestions: [{ task: 0, question: 'The plan has no "### Task N" headings — is the path right?' }], finalVerdict: null, range: '' }
}
for (const c of analysis.conflicts) rulings.push({ stage: 'preflight', note: c })
log(`${light ? 'light' : 'standard'} mode: ${tasks.length} tasks (${tasks.filter(t => t.kind !== 'code').length} test/verify-only), ${analysis.conflicts.length} preflight conflicts`)

// The plan is reviewed by its own reviewer before any code exists; critical or important findings send it back to the author.
let planVerdict = null
if (!skipPlanReview && !reviewOnly) {
  phase('Plan review')
  planVerdict = await agent(
    `${RULES_PREAMBLE}${PACK()}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}. Plan: ${plan}. ${spec ? 'Spec: ' + spec + '.' : 'No spec file was given: review against the plan\'s own Goal/Context sections.'}
     Review the plan per your agent instructions and return the JSON verdict.`,
    { agentType: AGENT.planReviewer, schema: PLAN_VERDICT, label: 'plan-review' })
  const blockingPlan = planVerdict ? planVerdict.findings.filter(f => f.severity !== 'minor') : []
  if (!planVerdict) rulings.push({ stage: 'plan-review', status: 'no_verdict' })
  if (blockingPlan.length) {
    log(`plan review: ${blockingPlan.length} blocking finding(s) — returning the plan to its author`)
    return { status: 'plan_rejected', mode: light ? 'light' : 'standard', done, rulings, deferred, openQuestions: blockingPlan.map(f => ({ task: f.task || 0, question: `[${f.id}] ${f.area}: ${f.issue}` })), planVerdict, finalVerdict: null, range: '' }
  }
  if (planVerdict) deferred.push(...planVerdict.findings.filter(f => f.severity === 'minor').map(f => ({ task: f.task || 0, file: plan, severity: 'minor', kind: 'style', issue: `[plan ${f.id}] ${f.issue}` })))
}

const baseSha = analysis.baseSha || await sha('base-sha')
let head = reviewOnly ? (workflowArgs.head || await sha('review-head')) : baseSha
let aborted = false

for (const t of tasks) {
  if (aborted) break
  let taskBase = head
  let report = null

  if (t.kind === 'code') {
    phase('Implement')
    for (let attempt = 0; attempt < 2 && !report; attempt++) {
      const r = await agent(
        `${RULES_PREAMBLE}${PACK()}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}.
         Task ${t.id}: ${t.title}. Brief: ${t.briefPath}. Report file: ${projectDir}/.superpowers/sdd/task-${t.id}-report.md.
         Commit on the branch that is already checked out — never create or switch a branch. Write only inside ${projectDir}.
         If the brief asserts a behaviour that the code, its tests, CI, an ADR, a doc or a consumer note contradicts, do not pick a side: stop before changing that behaviour, return status needs_context with the contradiction in \`contradictions\` (claim, observed with file:line, sources you saw) — the workflow reconciles it.
         ${answers[t.id] ? 'Answers to your earlier open questions: ' + JSON.stringify(answers[t.id]) : ''}
         ${attempt ? 'A prior run returned escalate_model; this run has higher effort — read the report file first.' : ''}`,
        { agentType: AGENT.implementer, schema: REPORT, label: `impl#${t.id}`, effort: attempt ? 'high' : undefined })
      if (r && r.status === 'escalate_model' && attempt === 0) { log(`task ${t.id}: escalate_model → retry with effort high`); continue }
      report = r
    }
    // The brief and the repository disagree: nobody guesses. The reconciler weighs every source of truth;
    // the code is fixed when the enforced record backs the brief, and the brief goes back to its author when
    // the record backs the code — unless the caller already ruled with args.truth[taskId].
    const contradictions = (report && report.contradictions) || []
    if (report && contradictions.length) {
      phase('Reconcile')
      const verdicts = await parallel(contradictions.map(c => () => agent(
        `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task ${t.id}: ${t.title}. Brief: ${t.briefPath}.
         Claim (what the brief says): ${c.claim}
         Observed (what the code does): ${c.observed}
         Sources already noticed: ${(c.sources || []).join('; ') || 'none'}
         Reconcile per your agent instructions and return the JSON.`,
        { agentType: AGENT.reconciler, schema: RECONCILIATION, label: `reconcile#${t.id}` })))
      const rulingsForTask = contradictions.map((c, i) => ({ task: t.id, claim: c.claim, observed: c.observed, verdict: verdicts[i] ? verdicts[i].verdict : 'undecided', confidence: verdicts[i] ? verdicts[i].confidence : 'low', evidence: verdicts[i] ? verdicts[i].evidence : [], rationale: verdicts[i] ? verdicts[i].rationale : 'reconciler returned nothing', action: verdicts[i] ? verdicts[i].action : '', staleSources: verdicts[i] ? verdicts[i].staleSources : [], questions: verdicts[i] ? (verdicts[i].questions || []) : [] }))
      reconciled.push(...rulingsForTask)
      const forced = truth[t.id]
      const settled = rulingsForTask.every(r => forced || (r.verdict === 'brief' && r.confidence !== 'low'))
      if (!settled) {
        // A `code` or `undecided` verdict is the caller's decision: return the evidence, do not implement a guess.
        rulings.push({ task: t.id, status: 'contradiction', reconciled: rulingsForTask })
        openQuestions.push(...rulingsForTask.filter(r => r.verdict !== 'brief' || r.confidence === 'low').map(r => ({ task: t.id, question: `[${r.verdict}/${r.confidence}] "${r.claim}" vs "${r.observed}" — ${r.rationale}${r.questions.length ? ' Questions: ' + r.questions.join(' | ') : ''} Rerun with args.truth["${t.id}"] = "brief" | "code".` })))
        log(`task ${t.id}: contradiction not settled (${rulingsForTask.map(r => r.verdict).join(', ')}) — stopping for the caller's ruling`)
        aborted = true
        break
      }
      const direction = forced || 'brief'
      const instruction = direction === 'brief'
        ? 'The reconciler ruled that the brief is right and the code drifted: fix the code at its root so the behaviour the brief states holds, and correct these stale sources in the same commit: '
        : 'The caller ruled that the recorded behaviour of the repository is right and the brief is wrong: keep the recorded behaviour, implement the rest of the task around it, and correct these stale sources (the text of the brief lives outside the repository — say so in your report): '
      phase('Implement')
      const redo = await agent(
        `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}.
         Task ${t.id}: ${t.title}. Brief: ${t.briefPath}. Report file: ${report.reportPath}. Read your report first — you stopped on a contradiction.
         ${instruction}${rulingsForTask.flatMap(r => r.staleSources).join('; ') || 'none named'}.
         Evidence: ${JSON.stringify(rulingsForTask.map(r => ({ verdict: r.verdict, rationale: r.rationale, action: r.action })))}
         Commit on the branch that is already checked out. Write only inside ${projectDir}.`,
        { agentType: AGENT.implementer, schema: REPORT, label: `impl#${t.id}.reconciled` })
      if (redo) { report = { ...redo, commits: [...(report.commits || []), ...(redo.commits || [])], contradictions: [] } }
    }
    if (!report || report.status === 'blocked' || report.status === 'needs_context' || report.status === 'escalate_model') {
      const status = report ? report.status : 'blocked'
      rulings.push({ task: t.id, status, concerns: report ? report.concerns : 'agent returned no report' })
      openQuestions.push(...(((report && report.questions) || []).map(question => ({ task: t.id, question }))))
      log(`task ${t.id}: ${status} — stopping for user input`)
      aborted = true
      break
    }
    if (report.status === 'done_with_concerns') rulings.push({ task: t.id, status: 'done_with_concerns', concerns: report.concerns })
    head = report.headSha || head
  } else {
    // A test-only or verification-only task has nothing to implement and nothing of its own to review.
    report = { status: 'done', commits: [], headSha: head, files: t.files, concerns: '', questions: [], reportPath: `${projectDir}/.superpowers/sdd/task-${t.id}-report.md` }
    log(`task ${t.id}: kind ${t.kind} — no implementer, no per-task review`)
  }

  const scope = t.kind === 'verify'
    ? `Do not add tests. Run the existing suite, confirm what task ${t.id} (${t.title}) asks to verify, and report the literal Passed/Failed/Skipped line.`
    : `Cover the changes of task ${t.id} (${t.title}; files: ${t.files.join(', ')}) with tests per the test conventions, run them, and commit as "${taskKey}: Add tests for ${t.title}".`
  const testsPrompt = (extra) => `${RULES_PREAMBLE}${PACK()}Working directory: ${projectDir}. Project: ${project}. ${scope}
     What the implementer just did, in its own words — read it instead of reconstructing the change from the diff: ${report.reportPath}.
     Test only the behaviour this task changed. Do not write tests for untouched members, for record/DTO equality, for DI registration, or for framework binding — the auditors count those as padding. One strong test per branch beats three duplicated happy paths; cover the endpoint or entry point of the change at least once.
     The solution was just built by the previous agent: prefer \`dotnet test --no-restore\` and rebuild only what you changed.
     Return status, the literal Passed/Failed/Skipped line as summary, and the commit SHA of HEAD as headSha (\`git -C ${projectDir} rev-parse HEAD\`). ${extra}`
  phase('Tests')
  let tests = await agent(testsPrompt(''), { agentType: AGENT.tests, schema: TESTS_DONE, label: `tests#${t.id}`, effort: t.kind === 'verify' ? 'low' : undefined })
  head = (tests && tests.headSha) || head
  if (!tests || tests.status !== 'done') {
    // Red tests are a symptom, not a task: diagnose to root cause, then hand the fix to the implementer once.
    phase('Debug')
    const diagnosis = await agent(
      `${RULES_PREAMBLE}${PACK()}Working directory: ${projectDir}. Project: ${project}. Task ${t.id}: ${t.title}. Brief: ${t.briefPath}. Implementer report: ${report.reportPath}.
       The tests-writer could not get the tests green: ${tests ? tests.summary : 'no report'}. Diagnose to root cause per your agent instructions, write ${projectDir}/.superpowers/sdd/task-${t.id}-diagnosis.md and return the DIAGNOSIS JSON.`,
      { agentType: AGENT.debugger, schema: DIAGNOSIS, label: `debug#${t.id}` })
    if (diagnosis && diagnosis.confidence !== 'low') {
      phase('Fix')
      const repair = await agent(
        `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}. Task ${t.id}: ${t.title}. Brief: ${t.briefPath}.
         Repair after diagnosis. Root cause: ${diagnosis.rootCause}. Fix brief: ${diagnosis.fixBrief}. Files: ${diagnosis.files.join(', ')}. Verify with: ${diagnosis.verification}${diagnosis.reproduction ? ' (reproduction test: ' + diagnosis.reproduction + ' — keep it, it must pass)' : ''}.
         Commit as "${taskKey}: Fix ${t.title} after diagnosis". Stay on the checked-out branch.`,
        { agentType: AGENT.implementer, schema: REPORT, label: `repair#${t.id}` })
      if (repair && repair.commits) report.commits.push(...repair.commits)
      if (repair && repair.headSha) head = repair.headSha
      phase('Tests')
      tests = await agent(testsPrompt(`A diagnosis-driven repair was just committed (${diagnosis.fixBrief}); re-run the suite and fill remaining gaps.`),
        { agentType: AGENT.tests, schema: TESTS_DONE, label: `tests#${t.id}.retry` })
      head = (tests && tests.headSha) || head
    }
    rulings.push({ task: t.id, stage: 'debug', rootCause: diagnosis ? diagnosis.rootCause : 'debugger returned nothing', confidence: diagnosis ? diagnosis.confidence : 'none', testsAfter: tests ? tests.status : 'no_report' })
  }
  const testsGreen = Boolean(tests && tests.status === 'done')
  if (!testsGreen) rulings.push({ task: t.id, stage: 'tests', status: tests ? tests.status : 'no_report', note: tests ? tests.summary : 'tests-writer returned nothing' })

  // In light mode, and for tasks that produced no production diff, the whole-branch final review is the only gate.
  if (light || t.kind !== 'code') {
    done.push({ task: t.id, rounds: 0, commits: report.commits })
    continue
  }

  let feedback = []
  let taskMinorDefects = []
  let stalled = 0
  let rounds = 0
  for (let round = 0; round <= fixCap; round++) {
    phase('Review')
    // Round 0 on a small, green task is a cheap pass: the whole-branch final review still runs at full effort.
    const cheapRound0 = testsGreen && (t.files || []).length <= 5
    const verdict = await agent(
      reviewPrompt(taskBase, head, round
        ? `This is a scoped re-review of a fix round. Prior findings:\n${feedback.map(describe).join('\n')}\nFirst verdict each prior finding as addressed true/false, then review only the fix diff.`
        : `Review against the brief ${t.briefPath}.`, Boolean(round)),
      { agentType: AGENT.reviewer, schema: VERDICT, label: `review#${t.id}.${round}`, effort: (round || cheapRound0) ? 'low' : undefined })
    if (!verdict) {
      rulings.push({ task: t.id, stage: 'review', status: 'no_verdict', round })
      log(`task ${t.id}: reviewer returned nothing, treating as unstable`)
      rulings.push({ task: t.id, status: 'unstable', parked: feedback })
      break
    }

    const addressedIds = new Set((verdict.addressed || []).filter(a => a.addressed).map(a => a.id))
    // Riders are carried in feedback so the re-review verdicts them, but an unclosed minor defect must not
    // become blocking on the next round: it stays in taskMinorDefects until the final wave.
    const open = feedback.filter(f => !addressedIds.has(f.id) && f.severity !== 'minor')
    taskMinorDefects = taskMinorDefects.filter(f => !addressedIds.has(f.id))

    phase('Verify')
    // Minor defects go through the verifier too: it may raise one to important, and only then does it block.
    const candidates = verdict.findings.filter(f => f.severity !== 'minor' || f.kind === 'defect')
    deferred.push(...verdict.findings.filter(f => f.severity === 'minor' && f.kind !== 'defect').map(f => ({ task: t.id, ...f })))
    const votes = await parallel(candidates.map(f => () => agent(
      `${RULES_PREAMBLE}${PACK()}Working directory: ${projectDir}. Diff range ${taskBase}..${head}. Verify this finding: ${JSON.stringify(f)}
       If it is real, also return severityAdjustment: the severity it deserves once you have seen the code (\`none\` to keep the reviewer's).`,
      { agentType: AGENT.verifier, schema: VERIFY, label: `verify#${t.id}.${round}`, effort: 'low' })))
    const real = candidates.map((f, i) => {
      const vote = votes[i]
      if (!vote || !vote.real) { rulings.push({ task: t.id, stage: 'verify', noise: f, evidence: vote ? vote.evidence : 'verifier returned nothing' }); return null }
      const adjusted = vote.severityAdjustment && vote.severityAdjustment !== 'none' ? vote.severityAdjustment : f.severity
      if (adjusted !== f.severity) rulings.push({ task: t.id, stage: 'verify', id: f.id, severity: f.severity, raisedTo: adjusted, evidence: vote.evidence })
      return { ...f, severity: adjusted }
    }).filter(Boolean)
    // A minor defect never opens a fix round of its own; it rides along with the next serious one.
    taskMinorDefects = [...taskMinorDefects, ...real.filter(f => f.severity === 'minor')]
      .filter((f, i, all) => all.findIndex(x => x.id === f.id) === i)
    const blocking = [...real.filter(f => f.severity !== 'minor'), ...open.filter(o => !candidates.some(c => c.id === o.id))]

    if (verdict.approved && blocking.length === 0) { done.push({ task: t.id, rounds, commits: report.commits }); log(`task ${t.id}: approved after ${rounds} fix round(s)${taskMinorDefects.length ? `, ${taskMinorDefects.length} minor defect(s) ride to the final wave` : ''}`); break }
    if (blocking.length === 0) {
      rulings.push({ task: t.id, stage: 'review', round, status: 'not_approved_without_findings', note: 'reviewer returned approved=false with no critical/important findings' })
      done.push({ task: t.id, rounds, commits: report.commits })
      log(`task ${t.id}: reviewer withheld approval without actionable findings — recorded and moving on`)
      break
    }
    if (round === fixCap) { rulings.push({ task: t.id, status: 'unstable', parked: blocking }); log(`task ${t.id}: fix cap reached, ${blocking.length} findings parked`); break }
    const closed = feedback.filter(f => addressedIds.has(f.id)).length
    stalled = feedback.length && closed === 0 ? stalled + 1 : 0
    if (stalled >= stallRounds) { rulings.push({ task: t.id, status: 'unstable', stalled: blocking }); log(`task ${t.id}: ${stallRounds} rounds without progress, stopping`); break }

    let diagnosisNote = ''
    if (stalled >= 1) {
      // A round that closed nothing means the implementer is fixing the wrong thing: diagnose before trying again.
      phase('Debug')
      const diagnosis = await agent(
        `${RULES_PREAMBLE}${PACK()}Working directory: ${projectDir}. Project: ${project}. Task ${t.id}: ${t.title}. Brief: ${t.briefPath}. Implementer report: ${report.reportPath}.
         The last fix round closed none of these review findings:\n${blocking.map(describe).join('\n')}
         Find out why (wrong root cause, wrong file, a test pinning the old behaviour, a finding that is not real) per your agent instructions, write ${projectDir}/.superpowers/sdd/task-${t.id}-r${round}-diagnosis.md and return the DIAGNOSIS JSON.`,
        { agentType: AGENT.debugger, schema: DIAGNOSIS, label: `debug#${t.id}.${round}` })
      if (diagnosis) {
        diagnosisNote = `Diagnosis (${diagnosis.confidence}): ${diagnosis.rootCause}. Fix brief: ${diagnosis.fixBrief}. Verify with: ${diagnosis.verification}.`
        rulings.push({ task: t.id, stage: 'debug', round, rootCause: diagnosis.rootCause, confidence: diagnosis.confidence })
      }
    }
    phase('Fix')
    feedback = blocking
    rounds = round + 1
    const escalate = rounds >= 4
    const riders = taskMinorDefects
    const fix = await agent(
      `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}. Task ${t.id}: ${t.title}. Brief: ${t.briefPath}.
       Fix round ${rounds}. Read your report file ${report.reportPath} first, then address exactly these findings:\n${blocking.map(describe).join('\n')}
       ${riders.length ? `Also fix these minor defects in the same pass — they do not get a round of their own:\n${riders.map(describe).join('\n')}` : ''}
       ${diagnosisNote}
       Re-run the tests that cover the changed files. Commit as "${taskKey}: Address review findings for ${t.title}". Stay on the checked-out branch.
       ${escalate ? 'Previous rounds did not close these findings; read what was tried in the report and take a different approach.' : ''}`,
      { agentType: AGENT.implementer, schema: REPORT, label: `fix#${t.id}.${rounds}`, effort: escalate ? 'high' : undefined })
    if (!fix || (fix.status !== 'done' && fix.status !== 'done_with_concerns')) {
      rulings.push({ task: t.id, stage: 'fix', status: fix ? fix.status : 'no_report', concerns: fix ? fix.concerns : '' })
      openQuestions.push(...(((fix && fix.questions) || []).map(question => ({ task: t.id, question }))))
      aborted = true
      break
    }
    // The riders were handed over with the round; the next re-review verdicts them along with the blocking ones.
    feedback = [...blocking, ...riders]
    report.commits.push(...(fix.commits || []))
    head = fix.headSha || head
    taskBase = head
  }
  minorDefects.push(...taskMinorDefects.map(f => ({ task: t.id, ...f })))
}

const unique = (list) => list.filter((d, i) => list.findIndex(x => x.file === d.file && x.issue === d.issue) === i)
const ridingDefects = unique(minorDefects)
let finalVerdict = null
let finalHead = head
if (!aborted) {
  phase('Final review')
  finalVerdict = await agent(
    reviewPrompt(baseSha, finalHead, `Whole-branch review. Deferred minor findings to triage (promote only if they matter now): ${JSON.stringify(unique(deferred))}.`),
    { agentType: AGENT.reviewer, schema: VERDICT, label: 'final-review' })
  if (finalVerdict && reviewOnly) {
    // In review mode this is the only review there is, so its findings go through the verifier before the fix wave.
    phase('Verify')
    const candidates = finalVerdict.findings.filter(f => f.severity !== 'minor' || f.kind === 'defect')
    const votes = await parallel(candidates.map(f => () => agent(
      `${RULES_PREAMBLE}Working directory: ${projectDir}. Diff range ${baseSha}..${finalHead}. Verify this finding: ${JSON.stringify(f)}
       If it is real, also return severityAdjustment: the severity it deserves once you have seen the code (\`none\` to keep the reviewer's).`,
      { agentType: AGENT.verifier, schema: VERIFY, label: 'verify#final', effort: 'low' })))
    const kept = candidates.map((f, i) => {
      const vote = votes[i]
      if (!vote || !vote.real) { rulings.push({ stage: 'verify', noise: f, evidence: vote ? vote.evidence : 'verifier returned nothing' }); return null }
      const adjusted = vote.severityAdjustment && vote.severityAdjustment !== 'none' ? vote.severityAdjustment : f.severity
      if (adjusted !== f.severity) rulings.push({ stage: 'verify', id: f.id, severity: f.severity, raisedTo: adjusted, evidence: vote.evidence })
      return { ...f, severity: adjusted }
    }).filter(Boolean)
    finalVerdict = { ...finalVerdict, findings: [...kept, ...finalVerdict.findings.filter(f => f.severity === 'minor' && f.kind !== 'defect')] }
  }
  if (!finalVerdict) {
    rulings.push({ stage: 'final', status: 'no_verdict' })
  } else {
    // Accumulated minor defects are fixed here, with the blocking findings when there are any and alone when there are none.
    const blocking = finalVerdict.findings.filter(f => f.severity !== 'minor')
    const finalMinorDefects = [...ridingDefects, ...finalVerdict.findings.filter(f => f.severity === 'minor' && f.kind === 'defect')]
      .filter((f, i, all) => all.findIndex(x => x.file === f.file && x.issue === f.issue) === i)
    deferred.push(...finalVerdict.findings.filter(f => f.severity === 'minor' && f.kind !== 'defect').map(f => ({ task: 0, ...f })))
    const wave = [...blocking, ...finalMinorDefects]
    if (wave.length) {
      phase('Fix')
      const fix = await agent(
        `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}. Final fix wave: address exactly these findings, re-run the covering tests, commit as "${taskKey}: Address final review findings". Stay on the checked-out branch.\n${wave.map(describe).join('\n')}`,
        { agentType: AGENT.implementer, schema: REPORT, label: 'final-fix' })
      if (!fix || (fix.status !== 'done' && fix.status !== 'done_with_concerns')) {
        rulings.push({ stage: 'final', status: fix ? fix.status : 'no_report', concerns: fix ? fix.concerns : '' })
      }
      finalHead = (fix && fix.headSha) || await sha('final-head-after-fix')
      phase('Final review')
      // Nothing serious was open: the wave only carried minor defects, so one scoped "addressed?" check closes the branch.
      const recheck = await agent(
        reviewPrompt(baseSha, finalHead, blocking.length
          ? `Scoped re-review: verdict each of these as addressed true/false, then review the fix diff only:\n${wave.map(describe).join('\n')}`
          : `Scoped check only — no new review. Verdict each of these minor defects as addressed true/false against the fix diff and return no new findings unless the fix broke something:\n${wave.map(describe).join('\n')}`, true),
        { agentType: AGENT.reviewer, schema: VERDICT, label: 'final-rereview', effort: 'low' })
      if (!recheck) {
        rulings.push({ stage: 'final', status: 'no_verdict' })
      } else {
        const recheckAddressed = new Set((recheck.addressed || []).filter(a => a.addressed).map(a => a.id))
        const stillOpen = wave.filter(f => !recheckAddressed.has(f.id))
        const open = [...recheck.findings.filter(f => f.severity !== 'minor'), ...stillOpen.filter(s => !recheck.findings.some(f => f.id === s.id))]
        if (open.length) { rulings.push({ stage: 'final', status: 'unstable', parked: open }); log(`final review: ${open.length} findings still open`) }
        finalVerdict = recheck
      }
    }
  }
}

const deferredUnique = unique(deferred)
const status = aborted ? 'blocked' : (rulings.some(r => r.status === 'unstable') ? 'unstable' : 'done')
log(`dotnet-sdd finished (${light ? 'light' : 'standard'}): ${status}, ${done.length}/${tasks.length} tasks approved, ${deferredUnique.length} minors deferred`)
return { status: status === 'blocked' && rulings.some(r => r.status === 'contradiction') ? 'contradiction' : status, mode: light ? 'light' : 'standard', done, rulings, reconciled, deferred: deferredUnique, openQuestions, planVerdict, finalVerdict, range: `${baseSha}..${finalHead}` }
