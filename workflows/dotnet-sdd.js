export const meta = {
  name: 'dotnet-sdd',
  description: 'Execute an implementation plan in a .NET repository: implement, test, review, verify findings, bounded fix loop, final review',
  whenToUse: 'After brainstorming + writing-plans produced a plan file for a .NET project. Usually launched by the dotnet-feature skill.',
  phases: [
    { title: 'Analyze', detail: 'split the plan into task briefs' },
    { title: 'Plan review', detail: 'plan-reviewer gates the plan against the spec and the conventions' },
    { title: 'Implement' },
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
}
// The default workflow agent does not receive the injected contract, so every prompt asks for it explicitly.
const RULES_PREAMBLE = 'Read the plugin rules contract (rules/RULES-CONTRACT.md under the agentic-sdd-flow plugin root, or the <rules-contract> block already in your context) before anything else.\n'

const SP_LOOKUP = 'SP=$(ls -d ~/.claude/plugins/cache/*/superpowers/*/skills/subagent-driven-development/scripts 2>/dev/null | sort -V | tail -1); [ -n "$SP" ] || { echo "superpowers SDD scripts not found under ~/.claude/plugins/cache"; exit 2; }'

const TASKS = {
  type: 'object', required: ['tasks', 'conflicts'],
  properties: {
    tasks: { type: 'array', items: {
      type: 'object', required: ['id', 'title', 'briefPath', 'files'],
      properties: {
        id: { type: 'integer' },
        title: { type: 'string' },
        briefPath: { type: 'string' },
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
  },
}
const FINDING = {
  type: 'object', required: ['id', 'file', 'severity', 'issue'],
  properties: {
    id: { type: 'string' },
    file: { type: 'string' },
    line: { type: 'integer' },
    severity: { enum: ['critical', 'important', 'minor'] },
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
  properties: { status: { enum: ['done', 'done_with_concerns', 'blocked'] }, summary: { type: 'string' } },
}

const { project, projectDir, plan, taskKey, spec = '', maxFixRounds = 5, stallRounds = 2, answers = {}, skipPlanReview = false } = args
const rulings = [], deferred = [], done = [], openQuestions = []

const sha = (label) => agent(
  `Run \`git -C ${projectDir} rev-parse HEAD\` and return the SHA.`,
  { schema: SHA, effort: 'low', label, phase: 'Analyze' }).then(r => (r && r.sha) || 'unknown')

const reviewPrompt = (base, head, extra) => `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}.
Run in Bash: ${SP_LOOKUP}; cd ${projectDir}; "$SP/review-package" ${plan} ${base} ${head}
Then review the printed diff file per the dotnet-code-review skill (Roslyn first via roslyn-query.py).
A violation of the conventions contract is at least Important. ${extra}
approved=true only when no critical or important findings remain. Give every finding a short stable id (F1, F2, …); when re-reviewing, use the ids you were given in addressed[] verbatim. If this is not a re-review, return addressed as an empty array.`

phase('Analyze')
const analysis = await agent(
  `${RULES_PREAMBLE}Plan file: ${plan}. Working directory: ${projectDir}.
   Run in Bash: ${SP_LOOKUP}; cd ${projectDir}; for every "### Task N" heading in the plan run "$SP/task-brief" ${plan} N
   and return the printed brief path for each task. For each task list the files it touches (from its Files block)
   and the ids it depends on. Report conflicts between tasks (same file, contradictory instructions) as strings.`,
  { schema: TASKS, label: 'analyze' })
if (!analysis) {
  log('analyze agent returned nothing')
  return { status: 'blocked', done, rulings, deferred, openQuestions: ['The plan could not be analysed — check the plan path and rerun.'], finalVerdict: null, range: '' }
}
const tasks = analysis.tasks
if (!tasks.length) {
  log('no "### Task N" headings found in the plan')
  return { status: 'blocked', done, rulings, deferred, openQuestions: [{ task: 0, question: 'The plan has no "### Task N" headings — is the path right?' }], finalVerdict: null, range: '' }
}
for (const c of analysis.conflicts) rulings.push({ stage: 'preflight', note: c })
log(`${tasks.length} tasks, ${analysis.conflicts.length} preflight conflicts`)

// The plan is reviewed by its own reviewer before any code exists; critical or important findings send it back to the author.
let planVerdict = null
if (!skipPlanReview) {
  phase('Plan review')
  planVerdict = await agent(
    `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}. Plan: ${plan}. ${spec ? 'Spec: ' + spec + '.' : 'No spec file was given: review against the plan\'s own Goal/Context sections.'}
     Review the plan per your agent instructions and return the JSON verdict.`,
    { agentType: AGENT.planReviewer, schema: PLAN_VERDICT, label: 'plan-review' })
  const blockingPlan = planVerdict ? planVerdict.findings.filter(f => f.severity !== 'minor') : []
  if (!planVerdict) rulings.push({ stage: 'plan-review', status: 'no_verdict' })
  if (blockingPlan.length) {
    log(`plan review: ${blockingPlan.length} blocking finding(s) — returning the plan to its author`)
    return { status: 'plan_rejected', done, rulings, deferred, openQuestions: blockingPlan.map(f => ({ task: f.task || 0, question: `[${f.id}] ${f.area}: ${f.issue}` })), planVerdict, finalVerdict: null, range: '' }
  }
  if (planVerdict) deferred.push(...planVerdict.findings.filter(f => f.severity === 'minor').map(f => ({ task: f.task || 0, file: plan, severity: 'minor', issue: `[plan ${f.id}] ${f.issue}` })))
}

const baseSha = await sha('base-sha')
let aborted = false

for (const t of tasks) {
  if (aborted) break
  let taskBase = await sha(`task${t.id}-base`)
  let report = null

  phase('Implement')
  for (let attempt = 0; attempt < 2 && !report; attempt++) {
    const r = await agent(
      `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}.
       Task ${t.id}: ${t.title}. Brief: ${t.briefPath}. Report file: ${projectDir}/.superpowers/sdd/task-${t.id}-report.md.
       ${answers[t.id] ? 'Answers to your earlier open questions: ' + JSON.stringify(answers[t.id]) : ''}
       ${attempt ? 'A prior run returned escalate_model; this run has higher effort — read the report file first.' : ''}`,
      { agentType: AGENT.implementer, schema: REPORT, label: `impl#${t.id}`, effort: attempt ? 'high' : undefined })
    if (r && r.status === 'escalate_model' && attempt === 0) { log(`task ${t.id}: escalate_model → retry with effort high`); continue }
    report = r
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

  const testsPrompt = (extra) => `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Cover the changes of task ${t.id} (${t.title}; files: ${t.files.join(', ')})
     with tests per the test conventions, run them, and commit as "${taskKey}: Add tests for ${t.title}". Return status and the literal Passed/Failed/Skipped line. ${extra}`
  phase('Tests')
  let tests = await agent(testsPrompt(''), { agentType: AGENT.tests, schema: TESTS_DONE, label: `tests#${t.id}` })
  if (!tests || tests.status !== 'done') {
    // Red tests are a symptom, not a task: diagnose to root cause, then hand the fix to the implementer once.
    phase('Debug')
    const diagnosis = await agent(
      `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task ${t.id}: ${t.title}. Brief: ${t.briefPath}. Implementer report: ${report.reportPath}.
       The tests-writer could not get the tests green: ${tests ? tests.summary : 'no report'}. Diagnose to root cause per your agent instructions, write ${projectDir}/.superpowers/sdd/task-${t.id}-diagnosis.md and return the DIAGNOSIS JSON.`,
      { agentType: AGENT.debugger, schema: DIAGNOSIS, label: `debug#${t.id}` })
    if (diagnosis && diagnosis.confidence !== 'low') {
      phase('Fix')
      const repair = await agent(
        `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}. Task ${t.id}: ${t.title}. Brief: ${t.briefPath}.
         Repair after diagnosis. Root cause: ${diagnosis.rootCause}. Fix brief: ${diagnosis.fixBrief}. Files: ${diagnosis.files.join(', ')}. Verify with: ${diagnosis.verification}${diagnosis.reproduction ? ' (reproduction test: ' + diagnosis.reproduction + ' — keep it, it must pass)' : ''}.
         Commit as "${taskKey}: Fix ${t.title} after diagnosis".`,
        { agentType: AGENT.implementer, schema: REPORT, label: `repair#${t.id}` })
      if (repair && repair.commits) report.commits.push(...repair.commits)
      phase('Tests')
      tests = await agent(testsPrompt(`A diagnosis-driven repair was just committed (${diagnosis.fixBrief}); re-run the suite and fill remaining gaps.`),
        { agentType: AGENT.tests, schema: TESTS_DONE, label: `tests#${t.id}.retry` })
    }
    rulings.push({ task: t.id, stage: 'debug', rootCause: diagnosis ? diagnosis.rootCause : 'debugger returned nothing', confidence: diagnosis ? diagnosis.confidence : 'none', testsAfter: tests ? tests.status : 'no_report' })
  }
  if (!tests || tests.status !== 'done') rulings.push({ task: t.id, stage: 'tests', status: tests ? tests.status : 'no_report', note: tests ? tests.summary : 'tests-writer returned nothing' })

  let feedback = []
  let stalled = 0
  let rounds = 0
  for (let round = 0; round <= maxFixRounds; round++) {
    const head = await sha(`task${t.id}-r${round}-head`)
    phase('Review')
    const verdict = await agent(
      reviewPrompt(taskBase, head, round
        ? `This is a scoped re-review of a fix round. Prior findings:\n${feedback.map(f => '- [' + f.id + '] ' + f.file + (f.line ? ':' + f.line : '') + ' — ' + f.issue).join('\n')}\nFirst verdict each prior finding as addressed true/false, then review only the fix diff.`
        : `Review against the brief ${t.briefPath}.`),
      { agentType: AGENT.reviewer, schema: VERDICT, label: `review#${t.id}.${round}`, effort: round ? 'low' : undefined })
    if (!verdict) {
      rulings.push({ task: t.id, stage: 'review', status: 'no_verdict', round })
      log(`task ${t.id}: reviewer returned nothing, treating as unstable`)
      rulings.push({ task: t.id, status: 'unstable', parked: feedback })
      break
    }

    const addressedIds = new Set((verdict.addressed || []).filter(a => a.addressed).map(a => a.id))
    const open = feedback.filter(f => !addressedIds.has(f.id))

    phase('Verify')
    const candidates = verdict.findings.filter(f => f.severity !== 'minor')
    deferred.push(...verdict.findings.filter(f => f.severity === 'minor').map(f => ({ task: t.id, ...f })))
    const votes = await parallel(candidates.map(f => () => agent(
      `${RULES_PREAMBLE}Working directory: ${projectDir}. Diff range ${taskBase}..${head}. Verify this finding: ${JSON.stringify(f)}`,
      { agentType: AGENT.verifier, schema: VERIFY, label: `verify#${t.id}.${round}`, effort: 'low' })))
    const blocking = [...candidates.filter((f, i) => votes[i] && votes[i].real), ...open.filter(o => !candidates.some(c => c.id === o.id))]
    candidates.forEach((f, i) => { if (!votes[i] || !votes[i].real) rulings.push({ task: t.id, stage: 'verify', noise: f, evidence: votes[i] ? votes[i].evidence : 'verifier returned nothing' }) })

    if (verdict.approved && blocking.length === 0) { done.push({ task: t.id, rounds, commits: report.commits }); log(`task ${t.id}: approved after ${rounds} fix round(s)`); break }
    if (blocking.length === 0) {
      rulings.push({ task: t.id, stage: 'review', round, status: 'not_approved_without_findings', note: 'reviewer returned approved=false with no critical/important findings' })
      done.push({ task: t.id, rounds, commits: report.commits })
      log(`task ${t.id}: reviewer withheld approval without actionable findings — recorded and moving on`)
      break
    }
    if (round === maxFixRounds) { rulings.push({ task: t.id, status: 'unstable', parked: blocking }); log(`task ${t.id}: fix cap reached, ${blocking.length} findings parked`); break }
    const closed = feedback.filter(f => addressedIds.has(f.id)).length
    stalled = feedback.length && closed === 0 ? stalled + 1 : 0
    if (stalled >= stallRounds) { rulings.push({ task: t.id, status: 'unstable', stalled: blocking }); log(`task ${t.id}: ${stallRounds} rounds without progress, stopping`); break }

    let diagnosisNote = ''
    if (stalled >= 1) {
      // A round that closed nothing means the implementer is fixing the wrong thing: diagnose before trying again.
      phase('Debug')
      const diagnosis = await agent(
        `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task ${t.id}: ${t.title}. Brief: ${t.briefPath}. Implementer report: ${report.reportPath}.
         The last fix round closed none of these review findings:\n${blocking.map(f => '- [' + f.id + '] ' + f.file + (f.line ? ':' + f.line : '') + ' — ' + f.issue).join('\n')}
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
    const fix = await agent(
      `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}. Task ${t.id}: ${t.title}. Brief: ${t.briefPath}.
       Fix round ${rounds}. Read your report file ${report.reportPath} first, then address exactly these findings:\n${blocking.map(f => '- [' + f.id + '] ' + f.file + (f.line ? ':' + f.line : '') + ' — ' + f.issue).join('\n')}
       ${diagnosisNote}
       Re-run the tests that cover the changed files. Commit as "${taskKey}: Address review findings for ${t.title}".
       ${escalate ? 'Previous rounds did not close these findings; read what was tried in the report and take a different approach.' : ''}`,
      { agentType: AGENT.implementer, schema: REPORT, label: `fix#${t.id}.${rounds}`, effort: escalate ? 'high' : undefined })
    if (!fix || (fix.status !== 'done' && fix.status !== 'done_with_concerns')) {
      rulings.push({ task: t.id, stage: 'fix', status: fix ? fix.status : 'no_report', concerns: fix ? fix.concerns : '' })
      openQuestions.push(...(((fix && fix.questions) || []).map(question => ({ task: t.id, question }))))
      aborted = true
      break
    }
    report.commits.push(...(fix.commits || []))
    taskBase = head
  }
}

const deferredUnique = deferred.filter((d, i) => deferred.findIndex(x => x.task === d.task && x.file === d.file && x.issue === d.issue) === i)
let finalVerdict = null
let finalHead = baseSha
if (!aborted) {
  finalHead = await sha('final-head')
  phase('Final review')
  finalVerdict = await agent(
    reviewPrompt(baseSha, finalHead, `Whole-branch review. Deferred minor findings to triage (promote only if they matter now): ${JSON.stringify(deferredUnique)}.`),
    { agentType: AGENT.reviewer, schema: VERDICT, label: 'final-review' })
  if (!finalVerdict) {
    rulings.push({ stage: 'final', status: 'no_verdict' })
  } else {
    const blocking = finalVerdict.findings.filter(f => f.severity !== 'minor')
    if (blocking.length) {
      phase('Fix')
      const fix = await agent(
        `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}. Final fix wave: address exactly these findings, re-run the covering tests, commit as "${taskKey}: Address final review findings".\n${blocking.map(f => '- [' + f.id + '] ' + f.file + (f.line ? ':' + f.line : '') + ' — ' + f.issue).join('\n')}`,
        { agentType: AGENT.implementer, schema: REPORT, label: 'final-fix' })
      if (!fix || (fix.status !== 'done' && fix.status !== 'done_with_concerns')) {
        rulings.push({ stage: 'final', status: fix ? fix.status : 'no_report', concerns: fix ? fix.concerns : '' })
      }
      finalHead = await sha('final-head-after-fix')
      phase('Final review')
      const recheck = await agent(
        reviewPrompt(baseSha, finalHead, `Scoped re-review: verdict each of these as addressed true/false, then review the fix diff only:\n${blocking.map(f => '- [' + f.id + '] ' + f.file + (f.line ? ':' + f.line : '') + ' — ' + f.issue).join('\n')}`),
        { agentType: AGENT.reviewer, schema: VERDICT, label: 'final-rereview', effort: 'low' })
      if (!recheck) {
        rulings.push({ stage: 'final', status: 'no_verdict' })
      } else {
        const recheckAddressed = new Set((recheck.addressed || []).filter(a => a.addressed).map(a => a.id))
        const stillOpen = blocking.filter(f => !recheckAddressed.has(f.id))
        const open = [...recheck.findings.filter(f => f.severity !== 'minor'), ...stillOpen.filter(s => !recheck.findings.some(f => f.id === s.id))]
        if (open.length) { rulings.push({ stage: 'final', status: 'unstable', parked: open }); log(`final review: ${open.length} findings still open`) }
        finalVerdict = recheck
      }
    }
  }
}

const status = aborted ? 'blocked' : (rulings.some(r => r.status === 'unstable') ? 'unstable' : 'done')
log(`dotnet-sdd finished: ${status}, ${done.length}/${tasks.length} tasks approved, ${deferredUnique.length} minors deferred`)
return { status, done, rulings, deferred: deferredUnique, openQuestions, planVerdict, finalVerdict, range: `${baseSha}..${finalHead}` }
