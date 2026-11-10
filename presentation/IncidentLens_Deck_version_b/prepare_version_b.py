"""Prepare evidence-based image jobs; this script never draws slide images."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / 'origin_image/slide_04.png'

def asset(name, role):
    return {'path': str(ROOT / 'assets' / name), 'role': 'strict input asset: ' + role,
            'fidelity': 'Preserve supplied content, labels, values, axes, colors and relationships. Do not synthesize a replacement.'}

def page(n, title, role, points, composition, *, images=None, extra='', approved=False):
    return {'number': n, 'title': title, 'role': role,
            'intent': composition, 'key_points': points,
            'local_context': {'page_specific_instructions': extra},
            'layout': {'composition': composition,
                       'variation_rule': 'Use the approved visual identity, with a layout specific to this page. Do not repeat the architecture sample or create identical card grids.'},
            'required_images': images or [],
            'constraints': ['English only. Every title, label, caption and note must be English.',
                            'Arial throughout slide-authored text. Use the approved restrained size hierarchy, especially small gray footer notes.',
                            'No slide number, watermark, invented logo or invented data.',
                            'The title and all supplied key points must appear, with orderly wrapping and no overlaps.',
                            'Create a NEW complete slide from the style reference. Do not retain the sample architecture text or layout on unrelated pages.'],
            'sample_approved': approved}

slides = [
page(1, 'IncidentLens', 'cover', [
    'Evidence-driven multi-agent incident investigation',
    'COMP5584: Large Language Models for Agents',
    'Final Group Project, Group 5',
    'YANG Ziting 25050315G; MA Jiyuan 25116696G',
    'Song Xiaowen 25058859G; Zhang Boxin 25054717G',
    'YE Mingxi 25065994G; WANG Huixuechun 25064113G'],
    'A restrained academic cover on white. Use the supplied institution logo at upper right, a red vertical accent and a medium-sized Arial Bold project name on the left. Place the subtitle below, then course/group and six members in an aligned two-column list. Do not turn the title into a giant marketing headline.',
    images=[asset('polyu_logo_stacked.png', 'PolyU symbol and English university wordmark')],
    extra='The user requires an English-only deck. Crop only the Chinese text line from the supplied bilingual logo, retaining the complete emblem and English wordmark. Do not redraw or invent the logo. This language adaptation overrides preserving the Chinese line. No other institution identity. No presentation date is known, so do not invent a date.'),
page(2, 'Incident diagnosis requires evidence across sources', 'problem', [
    'Logs: error chronology and propagation',
    'Metrics: affected services and saturation',
    'Database: connections, locks and slow queries',
    'Changes: deployments, configuration and onset',
    'A supported mechanism needs cross-source and temporal corroboration.'],
    'A four-column scientific evidence matrix, each source with a small line icon and one short explanation. Below, converge the four sources toward a shared mechanism-and-time question. Keep the bottom conclusion modest, not an oversized banner.',
    extra='This is a conceptual illustration, not real incident evidence. Do not fabricate logs, telemetry values or a diagnosis.'),
page(3, 'Can coordination improve diagnosis within a fixed budget?', 'research question', [
    'Produce an auditable diagnosis or an appropriate abstention.',
    'Specialists investigate source-specific questions with bounded tools.',
    'A coordinator allocates tasks from the current evidence gap.',
    'Compare quality and resource use across four matched architectures.'],
    'One central research question, followed by a horizontal link between evidence specialization, shared investigation state and measured outcomes. Use plenty of alignment and a concise scope note, avoiding repeated three-card UI panels.',
    extra='Small gray scope note: Synthetic development cases; read-only investigation; no production changes. Multi-agent specialization and coordination are the design rationale, not proof of a universal advantage.'),
page(4, 'Dynamic coordinates specialists through shared evidence', 'architecture', [
    'Coordinator assigns 1-2 specialist tasks per round.',
    'Merge validates local findings and publishes shared evidence.',
    'Shared hypotheses guide replanning.',
    'Deterministic FinalizeGate controls acceptance.'],
    'Reuse the user-approved architecture sample unchanged.', approved=True),
page(5, 'Each specialist has a bounded tool scope', 'roles and permissions', [
    'Coordinator: decide tasks and next steps; no evidence tools.',
    'Logs: query_logs. Metrics: query_metrics and get_dependencies.',
    'Database: read-only get_db_* tools. Changes: query_changes and get_config_diff.',
    'Verifier: fetch already-published evidence by ID.',
    'A task can narrow role authority. Single receives the investigator-tool union.'],
    'An academic three-column matrix: Role, Main question, Read-only tools. Rows for Coordinator, Logs, Metrics, Database, Changes and Verifier. Put Single comparison and permission ceiling in one small note below.',
    extra='Main questions respectively: What next? What failed first? What is saturated? Is the database exhausted or blocked? What changed near onset? Does published evidence support the candidate? Small gray qualification: Equivalent-tool benchmark configuration may grant database access to Metrics. Role ceilings and task scopes remain enforced.'),
page(6, 'Tasks and findings update one shared investigation state', 'communication protocol', [
    'Task: role, scope, question and expected discriminator.',
    'Finding: observed record IDs and hypothesis updates.',
    'Merge is the only publication boundary for shared findings.',
    'Stable hypothesis IDs retain evidence across rounds.',
    'Completed scopes, duplicate-task checks and budgets bound the loop.'],
    'Show a typed task packet on the left, a specialist response packet on the right, and a shared evidence/hypothesis board beneath. Use a clear four-step read/assign/investigate/merge cycle rather than duplicating the overall architecture.',
    extra='Packet fields are structural examples, not a real trace. Specialists return local proposals, not direct shared-state writes. The board is not an LLM agent. Do not invent specific case findings.'),
page(7, 'Deterministic checks control conclusion acceptance', 'grounding method', [
    'Citations must belong to the evidence actually observed.',
    'Support spans source paths and includes a cause-specific discriminator.',
    'Impact and corroboration must be temporally compatible.',
    'Contradictions and observed competing mechanisms can block acceptance.',
    'Acceptance yields RESOLVED. Insufficient evidence can yield INCONCLUSIVE.'],
    'A vertical acceptance checklist beside a compact candidate/evidence diagram. Distinguish observed citations, mechanism and temporal corroboration. End with a small decision panel instead of five large cards.',
    extra='Important routing: a rejected gate may cause replanning while budget remains. Do not draw every rejection directly into INCONCLUSIVE. Small gray qualification: Structural provenance checks do not establish human-verified semantic support. No confidence score decides acceptance.'),
page(8, 'One implementation supports live runs and recorded replay', 'implementation', [
    'Python, LangGraph StateGraph and Pydantic contracts.',
    'One investigation service behind CLI and Web.',
    'Offline Mock and configured real-model providers.',
    'Saved artifacts: trace.json, result.json and report.md.',
    'Recorded replay loads saved state without graph, tool or provider calls.'],
    'A compact layered implementation diagram. Top row CLI / Web, middle investigation service and typed state, bottom provider plus read-only tools and saved artifacts. A separate replay lane reads the saved trace.',
    extra='Do not display old test counts as current verification. No production integrations or automatic remediation execution.'),
page(9, 'The dashboard exposes decisions, evidence and outcomes', 'system demonstration', [
    'Inspect task assignments and observed evidence.',
    'Follow hypothesis updates and the final gate decision.',
    'Open the cited report or explain missing evidence.',
    'Shown example: Mock provider, recorded replay.'],
    'Use the supplied genuine dashboard screenshot as the dominant figure, about three-quarters of the content width, preserving its visible state and labels. A narrow right column provides only three short demonstration cues. No invented UI.',
    images=[asset('demo_console.png', 'actual recorded replay dashboard screenshot')],
    extra='Preserve MOCK and RECORDED REPLAY, 4/6 rounds, and other screenshot values. This is not a live production screen. Do not claim this screenshot is the old demo-live-20261102 trace or a stock four-round run. Crop only outer blank space if necessary; keep screenshot identity/status and core workflow visible. Any display labels in the screenshot remain intact.'),
page(10, 'Four architectures share one evaluation protocol', 'evaluation design', [
    'Single; Fixed-4; Dynamic; Dynamic with verifier.',
    '36 synthetic development cases: 29 identifiable, 7 requiring abstention.',
    'One model and one repeat: 144 slots.',
    'Matched public evidence, configured tools, budgets and model settings.',
    'Quality success retains technical failures in the denominator.'],
    'Four miniature architecture schematics in one row, followed by a clean experimental-design strip showing 36 cases times four variants equals 144 slots. Place metrics/denominator explanation below at body size, not giant numerals.',
    extra='Small gray model note: Recorded model: auto/deepseek-v4.1-flash via local gateway. Labels provisional; development-visible. Single self-review uses one identity. Fixed-4 uses one four-specialist batch. Dynamic adapts tasks per round. Verifier is a separate ablation of Dynamic.'),
page(11, 'Dynamic achieved 33 quality successes out of 36 slots', 'quality evidence', [
    'Dynamic: 27 correct roots + 6 correct abstentions = 33 quality successes.',
    'Three technical failures stay in its 36-slot denominator.',
    '27/27 root correctness is conditional on completed identifiable cases.'],
    'A large unchanged source bar chart fills the central width. Beneath it, one short arithmetic explanation and a small denominator note. Avoid a second copy of the table or three oversized KPI cards.',
    images=[asset('chart_quality.png', 'quality-success chart, including technical failures in denominator')],
    extra='Chart values must remain Single 32/36, Fixed-4 22/36, Dynamic 33/36, Dynamic + Verifier 30/36. Do not replace, redraw, truncate, recolor or alter bars or labels. Small gray footer: Development-visible synthetic batch; provisional labels; one model, one repeat.'),
page(12, 'Dynamic used fewer tokens than Single in this batch', 'resource evidence and ablation', [
    'Dynamic vs Single: 39.3% fewer tokens and 39.4% less latency.',
    'Verifier vs Dynamic: 56.7% more tokens, with no observed quality gain.',
    'Averages cover technically completed runs.'],
    'Use the original two-panel tokens and latency chart as the dominant source figure. Add two restrained comparison callouts beneath, at ordinary body size. A small gray note carries the evidence boundary.',
    images=[asset('chart_cost.png', 'two-panel per-completed-run tokens and latency chart')],
    extra='Do not alter the source chart. Precise averages: Single 245971 tokens / 680.9 s; Fixed-4 58042 / 196.3 s; Dynamic 149216 / 412.9 s; Verifier 233772 / 503.8 s. Chart rounds values intentionally. Small gray footer: Descriptive differences; one model, one repeat; no significance or USD-cost claim.'),
page(13, 'Identifiable misses ended in INCONCLUSIVE', 'failure analysis', [
    '144 slots: 136 completed and 8 technical failures.',
    'Completed runs: 117 quality successes and 19 identifiable misses.',
    'All 19 identifiable misses ended INCONCLUSIVE.',
    'The scorer found 0 wrongly named root causes in this batch.',
    'Observed quality failure: over-abstention reduces useful coverage.'],
    'A labeled outcome decomposition: 144 splits into 136 completed and 8 technical failures; 136 splits into 117 quality successes and 19 over-abstentions. Use modest numerical labels and an explanatory line, not huge KPI tiles.',
    extra='The categories partition slots. Technical failures must stay separate from wrong abstentions. Do not claim hallucinations were eliminated or semantic correctness proven. Candidate labels remain provisional.'),
page(14, 'The evidence supports a bounded development study', 'validity and limitations', [
    'Synthetic, development-visible cases.',
    'Candidate labels pending independent review.',
    'One model and one repeat.',
    'No blind test, human semantic audit or significance test.',
    'Next validation: independent labels, repeated/multi-model runs and realistic telemetry.'],
    'A plain academic validity table linking each study boundary with its next validation step. Four aligned rows, restrained red emphasis on the boundary labels, and no wall of disclaimer text.',
    extra='Do not imply independent validation has already happened, that production performance was measured, or that a verifier can never help.'),
page(15, 'Evidence discipline makes incident investigations auditable', 'conclusion and Q&A', [
    'Bounded roles and shared state make the collaboration inspectable.',
    'Deterministic gates define when a root cause can be accepted.',
    'Dynamic had the highest quality success count in this development batch.',
    'Next priorities: independent evaluation and better identifiable-case coverage.',
    'Thank you. Questions?'],
    'An academic conclusion page, three concise evidence-linked statements in a clean vertical sequence and one next-priority line. Use a small Questions prompt, not a giant decorative thank-you screen. Echo the red vertical title accent of the approved sample.'),
page(16, 'Backup: Decision semantics and termination', 'backup state semantics', [
    'INVESTIGATE: assign scoped specialist work.',
    'FINALIZE: request checks on a selected hypothesis.',
    'ABSTAIN: stop with insufficient evidence.',
    'RESOLVED requires an accepted cited root cause.',
    'INCONCLUSIVE may carry an unconfirmed leading explanation.'],
    'A compact state/decision mapping with a clear separation between coordinator choices, runtime acceptance and report status. A small bottom band explains termination categories.',
    extra='Small gray note: Evidence insufficiency is normal abstention; BUDGET_EXHAUSTED and unrecoverable execution errors are runtime failures. All terminal paths pass through stop before reporting. A provisional explanation must never be labeled confirmed root cause.'),
page(17, 'Backup: Metrics use different eligible denominators', 'backup metrics table', [
    'Quality and technical completion use all 36 slots per architecture.',
    'Root correctness uses completed identifiable cases.',
    'Correct abstention uses completed abstention cases.'],
    'A complete four-row academic results table with columns Architecture, Technical, Root correct, Abstain, Quality. Below it show a compact Dynamic denominator example. Use ordinary small table text and gray footnotes.',
    extra='Exact table: Single | 35/36 | 25/28 | 7/7 | 32/36; Fixed-4 | 34/36 | 15/27 | 7/7 | 22/36; Dynamic | 33/36 | 27/27 | 6/6 | 33/36; Dynamic with verifier | 34/36 | 23/27 | 7/7 | 30/36. Emphasize Dynamic row subtly in pale red. Example: 27 correct roots + 6 correct abstentions + 3 technical failures = 36 slots. Small note: Quality successes = 33/36, not 27/27.'),
page(18, 'Backup: Paired outcomes and difficulty levers', 'backup paired evidence', [
    'Dynamic vs Single: 3 wins, 2 losses, 31 ties.',
    'Dynamic vs Fixed-4: 12 wins, 1 loss, 23 ties.',
    'Dynamic vs verifier: 5 wins, 2 losses, 29 ties.'],
    'Use the unchanged source heatmap as the main figure on the left. A narrow right area presents the three paired win/loss/tie counts. Keep the title and small descriptive-evidence note consistent with the sample.',
    images=[asset('chart_levers.png', 'difficulty-lever heatmap with exact eligible counts')],
    extra='Preserve every heatmap cell, row, column, denominator and color. Rows: Competing 6/7,4/7,7/7,6/7; Counterfactual 5/6,3/6,6/6,4/6; Standard 6/7,3/7,6/7,6/7; Boundary 6/7,4/7,6/7,5/7; Missing discr. 7/7,7/7,6/7,7/7; Misleading 2/2,1/2,2/2,2/2. Columns Single, Fixed-4, Dynamic, Dynamic+Verifier. Small gray note: Paired counts are descriptive; statistical significance was not established.'),
page(19, 'Backup: Technical failures and evidence exhaustion', 'backup diagnostic analysis', [
    '8 technical failures: 6 structured-output failures and 2 identity mismatches.',
    'Evidence-exhaustion stops: 27/144 in the hardened 8-round protocol.',
    'Dynamic: 6 stops, all correct abstentions.',
    'Verifier: 11 stops, including 4 identifiable losses.',
    'Single: 10 stops, including 3 identifiable losses.'],
    'Two aligned diagnostic panels: technical failure counts on the left and a compact evidence-exhaustion table on the right. Clearly separate technical errors from guard-related coverage losses.',
    extra='Exact table: Dynamic 6 stops / 0 identifiable losses; Verifier 11 / 4; Single 10 / 3; Fixed-4 0 / 0. Small gray notes: Stock 4-round budget differs from the 8-round benchmark protocol. Earlier replay-estimated token savings are not a newly measured execution result. Do not attribute causation to architecture from failure counts.'),
page(20, 'Backup: Public evidence access and replay remain constrained', 'backup security', [
    'Public-file allowlist and role-scoped read-only tools.',
    'Frozen contexts prevent task authority escalation.',
    'An actual-query ledger binds citations to observed records.',
    'Merge validates findings before shared publication.',
    'Replay is confined to results/trace.json paths and checks companion identities.'],
    'Two clean trust-boundary diagrams: Runtime evidence access on the left and Recorded replay on the right. Annotate the specific implemented boundaries in short English phrases.',
    extra='The replay path means trace.json files located within results/, not a single literal file results/trace.json. Display this as results/**/trace.json if needed. Private evaluator oracles are for scoring and not runtime evidence. Replay does not execute the graph/tools/provider. No claim of complete security against every attack.'),
page(21, 'Backup: The demonstration can run offline', 'backup reproducibility', [
    'Validate data, run Dynamic with Mock, then replay the saved trace.',
    'Outputs: trace.json, result.json and report.md.',
    'The dashboard and CLI use the same saved artifacts.',
    'A real-provider evaluation is separate from an offline Mock demonstration.'],
    'A simple numbered reproducibility sequence with three short command lines in Arial, not a tiny full installation transcript. Show saved artifacts alongside the replay step.',
    extra='Exact commands: python -m incident_lens.cli validate-data; python -m incident_lens.cli run --case incident_001 --provider mock --variant dynamic --cache-mode off --out results/demo; python -m incident_lens.cli replay --trace results/demo/trace.json. Wrap the run command across readable lines if needed; never invent flags. Small gray note: Start from the documented installed environment; real provider configuration is separate.')
]

spec = {
 'deck_name': ROOT.name, 'language': 'English',
 'goal': 'A 15-slide English COMP5584 group presentation plus six Q&A backup slides, explaining implemented multi-agent collaboration and bounded measured evidence.',
 'selected_image_backend': 'built-in image tool', 'max_concurrent_slides': 3,
 'execution_mode': 'single agent; user AGENTS.md forbids inferring subagent authorization from skill advice. Parent /root directly calls the same backend and uses bundled dispatch/result scripts transparently.',
 'sample_generation_method': {
   'backend_used': 'built-in image tool', 'tool_name': 'image_gen__imagegen', 'mode': 'edit',
   'prompt_source': 'sample_size_revision.draft.txt',
   'approved_sample_path': str(SAMPLE), 'size': '16:9 landscape; approved raster 1672x941',
   'model_version': 'not exposed; user accepted this limitation',
   'quality': 'not exposed by backend',
   'input_context_preparation': 'view_image local reference/required assets; image_gen with referenced_image_paths',
   'handoff_rule': 'Use built-in image_gen with referenced images, edit/recompose into a complete new slide. No local slide drawing or overlays.'},
 'approved_style_reference': {'path': str(SAMPLE), 'role': 'approved style-only reference', 'fidelity': 'Match Arial typography sizes, palette, restrained notes and academic visual identity. Do not copy content/layout.'},
 'style': {
   'name': 'PolyU red academic defense, Arial with restrained notes',
   'visual_direction': 'Use the approved sample as style identity. White canvas, red left title accent and fine red rule; vary body layout by role. Academic evidence-first communication. No giant type or marketing layouts.',
   'color_palette': '#9A0907 primary, #F7E9E8 pale red, #003070 secondary, #1D1D1F ink, #E8E9EF neutral, #666666 notes.',
   'typography': 'Arial Bold title about 28-30pt, subtitle 16-18pt, main labels/body 14-16pt, supporting 12-14pt. Footer notes and legend 10-11pt, medium gray, regular weight. These are visual targets on 13.333 x 7.5 inch canvas. Never enlarge notes to fill empty space. No serif type in authored text.',
   'finish': 'Clean, disciplined and flat. No 3D, clip art, robots, watermark or decorative photos. Diagram boxes/arrows only where informative.'},
 'deck_context': {
   'source_summary': 'IncidentLens is a research/teaching prototype for read-only software incident investigation. Dynamic is the primary architecture, with a tool-free coordinator and four scoped specialists, deterministic Merge and FinalizeGate, shared evidence and stable hypotheses. Verifier is an ablation, not the default.',
   'evidence_boundary': '36 synthetic development-visible cases, provisional labels, one real-model repeat, 144 slots across four variants. Quality retains technical failures. Differences descriptive, no blind test, significance claim, human semantic audit or production generalization.',
   'measured_model': 'auto/deepseek-v4.1-flash through local gateway; distinct from the image backend used to make this deck.',
   'canonical_terms': ['Dynamic','Single','Fixed-4','Dynamic with verifier','Merge','FinalizeGate','RESOLVED','INCONCLUSIVE','PLAN_ONLY']},
 'slides': slides
}
(ROOT/'deck_spec.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
speech=(ROOT/'speech.draft.md').read_text(encoding='utf-8')
speech=speech.replace('Verbatim Presenter Script (Draft)', 'Verbatim Presenter Script')
speech=speech.replace('This English draft covers all 21 approved outline slides.', 'This English script covers all 21 presentation slides.')
speech=speech.replace('Final wording will be checked against the generated slides before it is copied into each slide\'s PowerPoint speaker notes.', 'Each slide\'s spoken talk track is also embedded in the PowerPoint speaker notes.')
(ROOT/'speech.md').write_text(speech,encoding='utf-8')
print('Wrote deck_spec.json and speech.md for 21 slides.')
