export const meta = {
  name: 'architecture-design',
  description: 'Design pipeline: drivers → current-state C4 → three lens proposals → judge panel → threat model → data review; after approval, ADRs and a spec for writing-plans',
  whenToUse: 'From the dotnet-feature skill on the architectural path, or directly for a design question. First run without approvedProposalId (read-only); second run with it (writes ADRs and the spec).',
  phases: [
    { title: 'Drivers' },
    { title: 'Context', detail: 'current-state C4 per project, merged' },
    { title: 'Proposals', detail: 'three lenses in parallel' },
    { title: 'Judge', detail: 'panel, refutation, synthesis' },
    { title: 'Threats' },
    { title: 'Data' },
    { title: 'Critic' },
    { title: 'Record', detail: 'ADRs and spec, after approval' },
  ],
}

const PREFIX = 'agentic-sdd-flow:'
const AGENT = {
  simplicity: PREFIX + 'design-simplicity',
  scalability: PREFIX + 'design-scalability',
  boundaries: PREFIX + 'design-boundaries',
  judge: PREFIX + 'design-judge',
  security: PREFIX + 'security-auditor',
  migration: PREFIX + 'migration-reviewer',
}
const RULES_PREAMBLE = 'Read the plugin rules contract (rules/RULES-CONTRACT.md under the agentic-sdd-flow plugin root, or the <rules-contract> block already in your context) before anything else. The architecture-design skill and its references live under <plugin root>/skills/architecture-design/.\n'

const { brief, projects, nfrs = '', workDir, adrDir, specsDir, judges = 3, approvedProposalId, slug } = args
const FOCI = ['fit', 'simplicity', 'operations', 'data-safety', 'conformance']

const DRIVER = { type: 'object', required: ['id', 'theme', 'statement', 'criticality', 'evidence'],
  properties: { id: { type: 'string' }, theme: { type: 'string' }, statement: { type: 'string' },
    criticality: { enum: ['must', 'should', 'could'] }, evidence: { enum: ['measured', 'stated', 'assumed'] } } }
const DRIVERS = { type: 'object', required: ['artifact', 'drivers', 'openQuestions'],
  properties: { artifact: { type: 'string' }, drivers: { type: 'array', items: DRIVER }, openQuestions: { type: 'array', items: { type: 'string' } } } }
const ARTIFACT = { type: 'object', required: ['artifact', 'summary'], properties: { artifact: { type: 'string' }, summary: { type: 'string' } } }
const DECISION = { type: 'object', required: ['id', 'topic', 'choice', 'alternatives', 'reopenTrigger'],
  properties: { id: { type: 'string' }, topic: { type: 'string' }, choice: { type: 'string' },
    alternatives: { type: 'array', items: { type: 'string' } }, reopenTrigger: { type: 'string' }, origin: { type: 'string' } } }
const PROPOSAL = { type: 'object', required: ['id', 'lens', 'title', 'summary', 'decisions', 'driversAddressed', 'driversUnaddressed', 'risks', 'estimate', 'artifact'],
  properties: { id: { type: 'string' }, lens: { type: 'string' }, title: { type: 'string' }, summary: { type: 'string' },
    decisions: { type: 'array', items: DECISION },
    driversAddressed: { type: 'array', items: { type: 'string' } },
    driversUnaddressed: { type: 'array', items: { type: 'string' } },
    risks: { type: 'array', items: { type: 'object', required: ['id', 'description', 'mitigation'],
      properties: { id: { type: 'string' }, description: { type: 'string' }, mitigation: { type: 'string' } } } },
    estimate: { type: 'object', required: ['effortDays', 'blastRadius', 'newInfrastructure'],
      properties: { effortDays: { type: 'number' }, blastRadius: { enum: ['low', 'medium', 'high'] }, newInfrastructure: { type: 'array', items: { type: 'string' } } } },
    artifact: { type: 'string' } } }
const SCORE = { type: 'object', required: ['proposalId', 'fit', 'simplicity', 'blastRadius', 'dataSafety', 'opsCost', 'conformance', 'total', 'rationale'],
  properties: { proposalId: { type: 'string' }, fit: { type: 'integer' }, simplicity: { type: 'integer' }, blastRadius: { type: 'integer' },
    dataSafety: { type: 'integer' }, opsCost: { type: 'integer' }, conformance: { type: 'integer' }, total: { type: 'integer' }, rationale: { type: 'string' } } }
const JUDGMENT = { type: 'object', required: ['focus', 'scores', 'winnerId', 'concerns'],
  properties: { focus: { type: 'string' }, scores: { type: 'array', items: SCORE }, winnerId: { type: 'string' }, concerns: { type: 'array', items: { type: 'string' } } } }
const REFUTATION = { type: 'object', required: ['holds', 'objections'],
  properties: { holds: { type: 'boolean' }, objections: { type: 'array', items: { type: 'object', required: ['id', 'severity', 'claim', 'evidence'],
    properties: { id: { type: 'string' }, severity: { enum: ['critical', 'important', 'minor'] }, claim: { type: 'string' }, evidence: { type: 'string' }, borrowFrom: { type: 'string' } } } } } }
const SYNTHESIS = { type: 'object', required: ['winnerId', 'runnerUpId', 'incorporated', 'decisionTable', 'openDecisions', 'artifact'],
  properties: { winnerId: { type: 'string' }, runnerUpId: { type: 'string' },
    incorporated: { type: 'array', items: { type: 'object', required: ['from', 'decisionId', 'what'], properties: { from: { type: 'string' }, decisionId: { type: 'string' }, what: { type: 'string' } } } },
    decisionTable: { type: 'array', items: DECISION }, openDecisions: { type: 'array', items: { type: 'string' } }, artifact: { type: 'string' } } }
const THREATS = { type: 'object', required: ['artifact', 'threats'],
  properties: { artifact: { type: 'string' }, threats: { type: 'array', items: { type: 'object', required: ['id', 'category', 'component', 'severity', 'mitigation'],
    properties: { id: { type: 'string' }, category: { type: 'string' }, component: { type: 'string' }, severity: { enum: ['critical', 'important', 'minor'] }, mitigation: { type: 'string' } } } } } }
const DATA = { type: 'object', required: ['artifact', 'status', 'findings', 'sequence'],
  properties: { artifact: { type: 'string' }, status: { enum: ['APPROVED', 'CHANGES_REQUESTED', 'BLOCKED'] },
    findings: { type: 'array', items: { type: 'object', required: ['id', 'severity', 'issue'], properties: { id: { type: 'string' }, severity: { enum: ['critical', 'important', 'minor'] }, issue: { type: 'string' } } } },
    sequence: { type: 'array', items: { type: 'string' } } } }
const CRITIC = { type: 'object', required: ['artifact', 'unanswered'],
  properties: { artifact: { type: 'string' }, unanswered: { type: 'array', items: { type: 'object', required: ['driverId', 'gap'], properties: { driverId: { type: 'string' }, gap: { type: 'string' } } } } } }
const ADRS = { type: 'object', required: ['paths'], properties: { paths: { type: 'array', items: { type: 'string' } } } }
const SPEC = { type: 'object', required: ['path', 'selfReview'], properties: { path: { type: 'string' }, selfReview: { type: 'string' } } }

const projectList = projects.map(p => `${p.name} (dir ${p.dir}, solution ${p.solution})`).join('; ')
const common = `${RULES_PREAMBLE}Brief: ${brief}\nNFRs: ${nfrs || 'none stated'}\nProjects: ${projectList}\nWork directory (create it if missing): ${workDir}\n`

phase('Drivers')
const drivers = await agent(
  `${common}Read <plugin root>/skills/architecture-design/references/baseline-builder.md and nfr-capture.md. Build the driver register (ids DR1…) from the brief and NFRs; mark evidence as measured/stated/assumed. Write ${workDir}/00-drivers.md in the baseline-builder Output Contract and return the JSON.`,
  { schema: DRIVERS, label: 'drivers' })
if (!drivers) { log('drivers agent returned nothing'); return { status: 'blocked', workDir, drivers: null, proposals: [], decision: null, threats: null, data: null, unanswered: [], adrPaths: [], specPath: '' } }
log(`${drivers.drivers.length} drivers, ${drivers.openQuestions.length} open questions`)

phase('Context')
const contextResults = await parallel(projects.map(p => () => agent(
  `${common}Document the current-state architecture of project ${p.name} only. Read <plugin root>/skills/architecture-design/references/current-architecture.md and c4-model.md. Use Roslyn: roslyn-query.py ${p.solution} get_project_graph (an empty graph is a mis-bind — retry with the explicit path), get_endpoint_map, get_di_registrations, get_nuget_packages; grep for message contracts, cache keys, gRPC services, connection strings (names only, never values). Write ${workDir}/01-context-${p.name}.md as a C4 container/component description with an evidence table, and return the JSON.`,
  { schema: ARTIFACT, label: `context:${p.name}` })))
const contexts = contextResults.filter(Boolean)
const merged = await agent(
  `${common}Merge these per-project context documents into one current-state C4 (context + containers, and components for the projects the brief touches): ${contexts.filter(Boolean).map(c => c.artifact).join(', ')}. Keep the evidence tables. Write ${workDir}/01-current-c4.md and return the JSON.`,
  { schema: ARTIFACT, label: 'context:merge' })
const currentC4 = merged ? merged.artifact : `${workDir}/01-current-c4.md`

phase('Proposals')
const lensPrompt = `${common}Drivers: ${drivers.artifact}. Current state: ${currentC4}. Produce your lens proposal per your agent instructions and return the JSON.`
const proposalResults = await parallel([
  () => agent(lensPrompt, { agentType: AGENT.simplicity, schema: PROPOSAL, label: 'lens:simplicity' }),
  () => agent(lensPrompt, { agentType: AGENT.scalability, schema: PROPOSAL, label: 'lens:scalability' }),
  () => agent(lensPrompt, { agentType: AGENT.boundaries, schema: PROPOSAL, label: 'lens:boundaries' }),
])
const proposals = proposalResults.filter(Boolean)
if (proposals.length < 2) { log(`only ${proposals.length} proposal(s) returned — cannot judge`); return { status: 'blocked', workDir, drivers, proposals, decision: null, threats: null, data: null, unanswered: [], adrPaths: [], specPath: '' } }
log(`${proposals.length} proposals: ${proposals.map(p => p.id).join(', ')}`)

phase('Judge')
const panelSize = Math.max(3, Math.min(5, judges))
const proposalFiles = proposals.map(p => `${p.id}: ${p.artifact}`).join('; ')
const judgments = (await parallel(FOCI.slice(0, panelSize).map(focus => () => agent(
  `${common}Mode: score. Focus: ${focus}. Drivers: ${drivers.artifact}. Current state: ${currentC4}. Proposals: ${proposalFiles}. Score every proposal per your rubric and return the JUDGMENT JSON.`,
  { agentType: AGENT.judge, schema: JUDGMENT, label: `judge:${focus}` })))).filter(Boolean)
const tally = {}
for (const j of judgments) for (const s of j.scores) tally[s.proposalId] = (tally[s.proposalId] || 0) + s.total
const ranked = proposals.map(p => p.id).sort((a, b) => (tally[b] || 0) - (tally[a] || 0))
log(`panel totals: ${ranked.map(id => id + '=' + (tally[id] || 0)).join(', ')}`)
const refutation = await agent(
  `${common}Mode: refute. Focus: fit. Winner: ${ranked[0]} (${proposals.find(p => p.id === ranked[0]).artifact}). Other proposals: ${proposalFiles}. Drivers: ${drivers.artifact}. Current state: ${currentC4}. Try to break the winner and return the REFUTATION JSON.`,
  { agentType: AGENT.judge, schema: REFUTATION, label: 'judge:refute', effort: 'high' })
const winnerHolds = !refutation || refutation.holds
if (!winnerHolds) log(`refutation broke ${ranked[0]}: ${refutation.objections.filter(o => o.severity === 'critical').map(o => o.claim).join(' | ')}`)
const decision = await agent(
  `${common}Mode: synthesise. Panel ranking: ${ranked.join(' > ')} (totals ${JSON.stringify(tally)}). Judgments: ${JSON.stringify(judgments)}. Refutation of ${ranked[0]}: ${JSON.stringify(refutation)}${winnerHolds ? '' : ' — the winner did not hold; start from ' + (ranked[1] || ranked[0])}. Proposals: ${proposalFiles}. Write ${workDir}/03-decision.md and return the SYNTHESIS JSON.`,
  { agentType: AGENT.judge, schema: SYNTHESIS, label: 'judge:synthesise' })
if (!decision) { log('synthesis returned nothing'); return { status: 'blocked', workDir, drivers, proposals, decision: null, threats: null, data: null, unanswered: [], adrPaths: [], specPath: '' } }
const winner = proposals.find(p => p.id === decision.winnerId) || proposals[0]

phase('Threats')
const threats = await agent(
  `${common}Mode: audit (read-only). Threat-model the winning design ${winner.id} (${winner.artifact}, decision ${decision.artifact}) against the current state ${currentC4}. Load <plugin root>/skills/stride-threat-model/SKILL.md and threat-mitigation-mapping/SKILL.md; verify entry points with roslyn-query.py <solution> get_endpoint_map and get_di_registrations for the projects touched. Write ${workDir}/04-threat-model.md and return the JSON (ids T1…, severity critical/important/minor).`,
  { agentType: AGENT.security, schema: THREATS, label: 'threats' })

phase('Data')
const data = await agent(
  `${common}Review the data model and migration implications of ${winner.id} (${winner.artifact}, decisions ${decision.artifact}) against the current state ${currentC4}. Deploy-window matrix, backfills, indexes on hot tables, rollback. Use the postgres-mcp / mssql-mcp tools when their environment is set; otherwise say "schema source: repository". Write ${workDir}/05-data-migration.md and return the JSON (ids M1…).`,
  { agentType: AGENT.migration, schema: DATA, label: 'data' })

phase('Critic')
const critic = await agent(
  `${common}Completeness critic. Drivers: ${drivers.artifact}. Decision: ${decision.artifact}. Threats: ${threats ? threats.artifact : 'none'}. Data: ${data ? data.artifact : 'none'}. For every driver, find where the winning design answers it; list the drivers with no answer or a hand-wave. Write ${workDir}/06-completeness.md and return the JSON.`,
  { schema: CRITIC, label: 'critic', effort: 'low' })
const unanswered = critic ? critic.unanswered : []
log(`critic: ${unanswered.length} unanswered driver(s)`)

if (!approvedProposalId) {
  log(`architecture-design proposed ${decision.winnerId} (runner-up ${decision.runnerUpId}); awaiting approval`)
  return { status: 'proposed', workDir, drivers, proposals, decision, threats, data, unanswered, adrPaths: [], specPath: '' }
}
if (approvedProposalId !== decision.winnerId) log(`user approved ${approvedProposalId} instead of the panel winner ${decision.winnerId}`)
const approved = proposals.find(p => p.id === approvedProposalId) || winner

phase('Record')
const adrs = await agent(
  `${common}Approved design: ${approved.id} (${approved.artifact}); decision table: ${JSON.stringify(decision.decisionTable)}. Read <plugin root>/skills/architecture-design/references/decision-recorder.md, adr-madr.md and adr-process.md. Write one MADR-format ADR per decision-table row into ${adrDir} (create it if missing) named NNNN-<slug>.md continuing the highest existing number there; status Proposed; include the reopen trigger. Return the JSON with the paths.`,
  { schema: ADRS, label: 'adrs' })
const spec = await agent(
  `${common}Assemble the design spec for ${approved.id}. Inputs: ${approved.artifact}, ${decision.artifact}, ${threats ? threats.artifact : 'no threat model'}, ${data ? data.artifact : 'no data review'}, ${critic ? critic.artifact : ''}, ADRs: ${adrs ? adrs.paths.join(', ') : 'none'}. Read <plugin root>/skills/architecture-design/references/migration-planner.md and diagram-builder.md, and the "Spec format" section of <plugin root>/skills/architecture-design/SKILL.md. Write ${specsDir}/<today>-${slug}-design.md (create the directory if missing; take today's date from \`date +%F\`). Then self-review it for placeholders, contradictions and unanswered drivers (${JSON.stringify(unanswered)}) and fix inline. Return the JSON with the path and a one-paragraph self-review.`,
  { schema: SPEC, label: 'spec' })
log(`architecture-design recorded: ${adrs ? adrs.paths.length : 0} ADR(s), spec ${spec ? spec.path : 'missing'}`)
return { status: spec ? 'recorded' : 'blocked', workDir, drivers, proposals, decision, threats, data, unanswered, adrPaths: adrs ? adrs.paths : [], specPath: spec ? spec.path : '' }
