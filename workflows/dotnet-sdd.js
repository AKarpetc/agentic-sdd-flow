export const meta = {
  name: 'dotnet-sdd',
  description: 'Execute an implementation plan in a .NET repository: implement, test, review, verify findings, bounded fix loop, final review',
  whenToUse: 'After brainstorming + writing-plans produced a plan file for a .NET project. Usually launched by the dotnet-feature skill.',
  phases: [
    { title: 'Analyze', detail: 'split the plan into task briefs' },
    { title: 'Implement' },
    { title: 'Tests' },
    { title: 'Review' },
    { title: 'Verify', detail: 'findings-verifier filters noise' },
    { title: 'Fix' },
    { title: 'Final review' },
  ],
}

// Plugin agents resolve by bare name; a namespace prefix is not accepted.
const PREFIX = ''
const AGENT = {
  implementer: PREFIX + 'dotnet-implementer',
  tests: PREFIX + 'tests-writer',
  reviewer: PREFIX + 'code-reviewer',
  verifier: PREFIX + 'findings-verifier',
}
// The default workflow agent does not receive the injected contract, so every prompt asks for it explicitly.
const RULES_PREAMBLE = 'Read the plugin rules contract (rules/RULES-CONTRACT.md under the agentic-sdd-flow plugin root, or the <rules-contract> block already in your context) before anything else.\n'

const SP_LOOKUP = 'SP=$(ls -d ~/.claude/plugins/cache/*/superpowers/*/skills/subagent-driven-development/scripts 2>/dev/null | sort -V | tail -1)'

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
  type: 'object', required: ['file', 'severity', 'issue'],
  properties: {
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
      type: 'object', required: ['issue', 'addressed'],
      properties: { issue: { type: 'string' }, addressed: { type: 'boolean' } } } },
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
const TESTS_DONE = {
  type: 'object', required: ['status', 'summary'],
  properties: { status: { enum: ['done', 'done_with_concerns', 'blocked'] }, summary: { type: 'string' } },
}

const { project, projectDir, plan, taskKey, maxFixRounds = 5, stallRounds = 2, answers = {} } = args
const rulings = [], deferred = [], done = [], openQuestions = []

const sha = (label) => agent(
  `Run \`git -C ${projectDir} rev-parse HEAD\` and return the SHA.`,
  { schema: SHA, effort: 'low', label, phase: 'Analyze' }).then(r => (r && r.sha) || 'unknown')

const reviewPrompt = (base, head, extra) => `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}.
Run in Bash: ${SP_LOOKUP}; cd ${projectDir}; "$SP/review-package" ${plan} ${base} ${head}
Then review the printed diff file per the dotnet-code-review skill (Roslyn first via roslyn-query.py).
A violation of the conventions contract is at least Important. ${extra}
approved=true only when no critical or important findings remain. Return findings with file, line, severity, issue.
If this is not a re-review, return addressed as an empty array.`

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
for (const c of analysis.conflicts) rulings.push({ stage: 'preflight', note: c })
log(`${tasks.length} tasks, ${analysis.conflicts.length} preflight conflicts`)

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
       ${Object.keys(answers).length ? 'Answers to earlier open questions: ' + JSON.stringify(answers) : ''}
       ${attempt ? 'A prior run returned escalate_model; this run has higher effort — read the report file first.' : ''}`,
      { agentType: AGENT.implementer, schema: REPORT, label: `impl#${t.id}`, effort: attempt ? 'high' : undefined })
    if (r && r.status === 'escalate_model' && attempt === 0) { log(`task ${t.id}: escalate_model → retry with effort high`); continue }
    report = r
  }
  if (!report || report.status === 'blocked' || report.status === 'needs_context' || report.status === 'escalate_model') {
    const status = report ? report.status : 'blocked'
    rulings.push({ task: t.id, status, concerns: report ? report.concerns : 'agent returned no report' })
    openQuestions.push(...((report && report.questions) || []))
    log(`task ${t.id}: ${status} — stopping for user input`)
    aborted = true
    break
  }
  if (report.status === 'done_with_concerns') rulings.push({ task: t.id, status: 'done_with_concerns', concerns: report.concerns })

  phase('Tests')
  const tests = await agent(
    `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Cover the changes of task ${t.id} (${t.title}; files: ${t.files.join(', ')})
     with tests per the test conventions, run them, and commit as "${taskKey}: Add tests for ${t.title}". Return status and the literal Passed/Failed/Skipped line.`,
    { agentType: AGENT.tests, schema: TESTS_DONE, label: `tests#${t.id}` })
  if (!tests || tests.status !== 'done') rulings.push({ task: t.id, stage: 'tests', status: tests ? tests.status : 'no_report', note: tests ? tests.summary : 'tests-writer returned nothing' })

  let feedback = []
  let stalled = 0
  let rounds = 0
  for (let round = 0; round <= maxFixRounds; round++) {
    const head = await sha(`task${t.id}-r${round}-head`)
    phase('Review')
    const verdict = await agent(
      reviewPrompt(taskBase, head, round
        ? `This is a scoped re-review of a fix round. Prior findings:\n${feedback.map(f => '- ' + f.file + ': ' + f.issue).join('\n')}\nFirst verdict each prior finding as addressed true/false, then review only the fix diff.`
        : `Review against the brief ${t.briefPath}.`),
      { agentType: AGENT.reviewer, schema: VERDICT, label: `review#${t.id}.${round}`, effort: round ? 'low' : undefined })
    if (!verdict) {
      rulings.push({ task: t.id, stage: 'review', status: 'no_verdict', round })
      log(`task ${t.id}: reviewer returned nothing, treating as unstable`)
      rulings.push({ task: t.id, status: 'unstable', parked: feedback })
      break
    }

    phase('Verify')
    const candidates = verdict.findings.filter(f => f.severity !== 'minor')
    deferred.push(...verdict.findings.filter(f => f.severity === 'minor').map(f => ({ task: t.id, ...f })))
    const votes = await parallel(candidates.map(f => () => agent(
      `${RULES_PREAMBLE}Working directory: ${projectDir}. Diff range ${taskBase}..${head}. Verify this finding: ${JSON.stringify(f)}`,
      { agentType: AGENT.verifier, schema: VERIFY, label: `verify#${t.id}.${round}`, effort: 'low' })))
    const blocking = candidates.filter((f, i) => votes[i] && votes[i].real)
    candidates.forEach((f, i) => { if (!votes[i] || !votes[i].real) rulings.push({ task: t.id, stage: 'verify', noise: f, evidence: votes[i] ? votes[i].evidence : 'verifier returned nothing' }) })

    if (blocking.length === 0) { done.push({ task: t.id, rounds, commits: report.commits }); log(`task ${t.id}: approved after ${rounds} fix round(s)`); break }
    if (round === maxFixRounds) { rulings.push({ task: t.id, status: 'unstable', parked: blocking }); log(`task ${t.id}: fix cap reached, ${blocking.length} findings parked`); break }
    const addressedIssues = new Set((verdict.addressed || []).filter(a => a.addressed).map(a => a.issue))
    const closed = feedback.filter(f => addressedIssues.has(f.issue)).length
    stalled = feedback.length && closed === 0 ? stalled + 1 : 0
    if (stalled >= stallRounds) { rulings.push({ task: t.id, status: 'unstable', stalled: blocking }); log(`task ${t.id}: ${stallRounds} rounds without progress, stopping`); break }

    phase('Fix')
    feedback = blocking
    rounds = round + 1
    const escalate = rounds >= 4
    const fix = await agent(
      `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}. Task ${t.id}: ${t.title}. Brief: ${t.briefPath}.
       Fix round ${rounds}. Read your report file ${report.reportPath} first, then address exactly these findings:\n${blocking.map(f => '- ' + f.file + (f.line ? ':' + f.line : '') + ' — ' + f.issue).join('\n')}
       Re-run the tests that cover the changed files. Commit as "${taskKey}: Address review findings for ${t.title}".
       ${escalate ? 'Previous rounds did not close these findings; read what was tried in the report and take a different approach.' : ''}`,
      { agentType: AGENT.implementer, schema: REPORT, label: `fix#${t.id}.${rounds}`, effort: escalate ? 'high' : undefined })
    if (!fix || (fix.status !== 'done' && fix.status !== 'done_with_concerns')) {
      rulings.push({ task: t.id, stage: 'fix', status: fix ? fix.status : 'no_report', concerns: fix ? fix.concerns : '' })
      openQuestions.push(...((fix && fix.questions) || []))
      aborted = true
      break
    }
    report.commits.push(...(fix.commits || []))
    taskBase = head
  }
}

let finalVerdict = null
let finalHead = baseSha
if (!aborted) {
  finalHead = await sha('final-head')
  phase('Final review')
  finalVerdict = await agent(
    reviewPrompt(baseSha, finalHead, `Whole-branch review. Deferred minor findings to triage (promote only if they matter now): ${JSON.stringify(deferred)}.`),
    { agentType: AGENT.reviewer, schema: VERDICT, label: 'final-review' })
  if (!finalVerdict) {
    rulings.push({ stage: 'final', status: 'no_verdict' })
  } else {
    const blocking = finalVerdict.findings.filter(f => f.severity !== 'minor')
    if (blocking.length) {
      phase('Fix')
      const fix = await agent(
        `${RULES_PREAMBLE}Working directory: ${projectDir}. Project: ${project}. Task key: ${taskKey}. Final fix wave: address exactly these findings, re-run the covering tests, commit as "${taskKey}: Address final review findings".\n${blocking.map(f => '- ' + f.file + ' — ' + f.issue).join('\n')}`,
        { agentType: AGENT.implementer, schema: REPORT, label: 'final-fix' })
      if (!fix || (fix.status !== 'done' && fix.status !== 'done_with_concerns')) {
        rulings.push({ stage: 'final', status: fix ? fix.status : 'no_report', concerns: fix ? fix.concerns : '' })
      }
      finalHead = await sha('final-head-after-fix')
      phase('Final review')
      const recheck = await agent(
        reviewPrompt(baseSha, finalHead, `Scoped re-review: verdict each of these as addressed true/false, then review the fix diff only:\n${blocking.map(f => '- ' + f.file + ': ' + f.issue).join('\n')}`),
        { agentType: AGENT.reviewer, schema: VERDICT, label: 'final-rereview', effort: 'low' })
      if (!recheck) {
        rulings.push({ stage: 'final', status: 'no_verdict' })
      } else {
        const open = recheck.findings.filter(f => f.severity !== 'minor')
        if (open.length) { rulings.push({ stage: 'final', status: 'unstable', parked: open }); log(`final review: ${open.length} findings still open`) }
        finalVerdict = recheck
      }
    }
  }
}

const status = aborted ? 'blocked' : (rulings.some(r => r.status === 'unstable') ? 'unstable' : 'done')
log(`dotnet-sdd finished: ${status}, ${done.length}/${tasks.length} tasks approved, ${deferred.length} minors deferred`)
return { status, done, rulings, deferred, openQuestions, finalVerdict, range: `${baseSha}..${finalHead}` }
