// NOT a standalone script (`node --check` fails by design): this file runs inside an agent-runner harness that injects `agent`, `parallel`, and `log`.
/*
 * anti-slop-frontier — a weekly frontier scan for AI-writing tells.
 *
 * WHAT THIS IS
 *   A small agent-workflow harness. It fans out several research agents in
 *   parallel, each on a distinct angle, against the newest available sources,
 *   then synthesizes their findings into an updated "anti-slop" guardrail and
 *   diffs it against your committed baseline. The point is to stay at the
 *   frontier: the lexical tells of AI prose rot fast (last year's banned-word
 *   list is stale this year), so a guardrail you wrote once quietly decays.
 *   Run this weekly, or before any big batch of writing, to refresh it.
 *
 * WHY A WORKFLOW AND NOT A PROMPT
 *   Running the angles in parallel keeps each agent focused on one lens and
 *   avoids one giant prompt that averages everything into mush. The schema
 *   forces every agent to return the same shape (findings + concrete rules +
 *   before/after + sources) so the synthesis step has clean inputs.
 *
 * THE FIFTH ANGLE (voice-tailored) — POINT IT AT YOUR OWN CORPUS
 *   The first four angles are generic craft research. The fifth grounds the
 *   guardrail in *your* actual writing so the advice protects your register
 *   instead of flattening it. It reads a voice-corpus file whose path you
 *   control. By default it looks for `config/voice-corpus.md`; override with
 *   the VOICE_CORPUS_PATH environment variable. If the file is absent the
 *   angle degrades gracefully to generic voice-protection advice. See
 *   docs/guides/voice-corpus-architecture.md for how to build that corpus and
 *   config/voice-corpus.example.md for a starter template.
 *
 * HARNESS CONTRACT
 *   This file assumes an agent-runner that injects `agent`, `parallel`, and
 *   `log` into scope and honors the exported `meta`. Adapt the three helper
 *   calls to whatever runner you use; the shape of the workflow is the reusable
 *   part.
 */

export const meta = {
  name: 'anti-slop-frontier',
  description:
    'Weekly frontier scan: AI-slop markers + anti-slop writing craft (5 angles), synthesize a guardrail, highlight what is NEW vs the committed baseline.',
  whenToUse:
    'Run weekly (or before a big writing batch) to keep your anti-slop guardrail current. After it returns, save the synthesis alongside your dated frontier notes and fold substantial findings into your baseline guide.',
  phases: [
    { title: 'Research', detail: '5 parallel agents, distinct angles, latest sources' },
    { title: 'Synthesize', detail: 'consolidate + diff against the baseline guardrail' },
  ],
}

// Where the voice-tailored (5th) angle reads your real writing samples from.
// Override with VOICE_CORPUS_PATH; defaults to the repo-relative template target.
const VOICE_CORPUS_PATH =
  (typeof process !== 'undefined' && process.env && process.env.VOICE_CORPUS_PATH) ||
  'config/voice-corpus.md'

// Every research agent returns this exact shape so the synthesis has clean inputs.
const FINDER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['angle', 'key_findings', 'concrete_rules', 'before_after', 'sources'],
  properties: {
    angle: { type: 'string' },
    key_findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['finding', 'why_it_matters'],
        properties: { finding: { type: 'string' }, why_it_matters: { type: 'string' } },
      },
    },
    concrete_rules: { type: 'array', items: { type: 'string' } },
    before_after: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['slop', 'fixed'],
        properties: { slop: { type: 'string' }, fixed: { type: 'string' } },
      },
    },
    sources: { type: 'array', items: { type: 'string' } },
  },
}

// Four fixed generic angles + one voice-tailored angle that reads your corpus.
const ANGLES = [
  {
    key: 'linguistic-markers',
    prompt: `Research the LINGUISTIC MARKERS that make text detectably AI-generated, newest sources first (search the current year plus the last 12 months: detection research, stylometry, ChatGPT-tell catalogs, "AI slop" journalism). Focus on observable STRUCTURAL tells (low information density, "not just X but Y", rule-of-three, manufactured significance, participial significance-tails, low burstiness, over-signposting) and note which LEXICAL tells have decayed or newly emerged this year. Return findings + mechanical rules + before/after + sources.`,
  },
  {
    key: 'anti-slop-craft',
    prompt: `Research the WRITING CRAFT that makes prose read human and genuine — anti-slop editing techniques, newest sources first. Subtraction, concrete specifics, burstiness, point of view, cutting openers and closers, voice, show-the-seams honesty. Translate each into a mechanical, executable move. Return findings + rules + before/after + sources.`,
  },
  {
    key: 'cover-letter-tells',
    prompt: `Research what hiring managers and recruiters flag as AI-written in COVER LETTERS and application open-question answers, newest sources first (recruiter surveys, hiring blogs, ATS and detector usage this year). Generic enthusiasm, job-description mirroring, adjective lists, fit-assertion closers; and what makes a short letter land. Return findings + rules + before/after + sources.`,
  },
  {
    key: 'detectors-and-stylometry',
    prompt: `Research how AI-text DETECTORS and stylometry work (perplexity, burstiness, n-grams) and what it implies for human-reading prose, newest sources first. Be honest about detector unreliability and false-positive rates; extract the structural signal and turn it into writing guidance, not detector-gaming. Return findings + rules + before/after + sources.`,
  },
  {
    key: 'voice-tailored',
    prompt: `Produce a TAILORED anti-slop guardrail grounded in the writer's REAL voice. Read the voice corpus at "${VOICE_CORPUS_PATH}" (and any GOLD sample files it points to). If that file does not exist, say so and fall back to generic voice-protection advice. From the corpus, identify what PROTECTS the author's register (for example: parentheticals, doubt sitting beside competence, deflating closers, jagged sentence rhythm, concrete vignettes over adjectives) and describe exactly how an AI draft betrays that register (smoother, more evenly enthusiastic, flatter rhythm). Return findings + rules + before/after + sources (the corpus files count as sources).`,
  },
]

const finds = (
  await parallel(
    ANGLES.map((a) => () =>
      agent(a.prompt, {
        label: `research:${a.key}`,
        phase: 'Research',
        schema: FINDER_SCHEMA,
      }).catch(() => null)
    )
  )
).filter(Boolean)
log(`${finds.length}/${ANGLES.length} research angles returned`)

const synthesis = await agent(
  `Synthesize these anti-slop research angles into an updated guardrail. Bias hard toward SUBTRACTION (shorter, plainer, more specific).\n\nNEW RESEARCH (JSON):\n${JSON.stringify(
    finds,
    null,
    2
  )}\n\nReturn markdown with:\n1. WHAT'S NEW THIS WEEK — bullets for any new tell, decayed tell, or rule that a standard baseline would not already contain. If nothing material changed, say so plainly.\n2. The full updated guardrail: ranked slop tells, mechanical passes, application-specific rules, a voice-protection section grounded in the corpus findings, and an editing protocol.\nKeep it tight. Return ONLY markdown.`,
  { label: 'synthesize', phase: 'Synthesize' }
)

return { synthesis, angles_returned: finds.length }
