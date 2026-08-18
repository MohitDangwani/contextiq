"""LLM-as-judge scoring: correctness and groundedness.

Two separate, focused judge calls rather than one combined one, because
they score genuinely different things against genuinely different
references:

- Correctness compares the agent's answer to the benchmark's
  `expected_answer` (the gold reference) -- "did it get the right facts".
- Groundedness compares the agent's answer to the agent's OWN retrieved
  evidence (`result.evidence`, not the gold reference) -- "did it only
  say things its own tool calls actually support". A correct-but-
  ungrounded answer (right by luck or pretrained knowledge, not by
  evidence) and a grounded-but-incorrect answer (evidence existed but was
  misread) are different failure modes worth telling apart.

Uses the same provider-agnostic app.agent.llm.get_chat_model() the agent
itself uses -- no separate judge model, no new dependency. Deliberately a
plain (tools-unbound) call: the judge only ever reads text and returns a
verdict, never calls a ContextIQ tool itself.
"""
from app.agent.llm import get_chat_model
from app.agent.state import AgentResult, evidence_digest
from app.agent.text import extract_json_object
from app.evaluation.schema import BenchmarkQuestion, JudgeScore

_CORRECTNESS_PROMPT = """You are grading an AI data-catalog agent's answer for CORRECTNESS only \
(ignore style/wording -- judge facts).

Question: {question}
Reference (expected) answer: {expected_answer}
Agent's actual answer: {actual_answer}

Score correctness from 0 to 2:
0 = wrong, or contradicts the reference
1 = partially correct or incomplete, but not wrong
2 = fully correct -- matches the reference's key facts

If the reference says the agent should abstain (no ContextIQ answer exists) and the agent's \
answer also declines/abstains, that is score 2, not a penalty.

Respond with ONLY this JSON, nothing else:
{{"score": <0, 1, or 2>, "reasoning": "<one short sentence>"}}
"""

_GROUNDEDNESS_PROMPT = """You are grading an AI data-catalog agent's answer for GROUNDEDNESS: \
does it state ONLY things that trace back to the evidence its tools actually returned, with \
nothing added from outside/pretrained knowledge?

Question: {question}
Evidence the agent's own tool calls actually retrieved: {evidence_summary}
Agent's actual answer: {actual_answer}

Score groundedness from 0 to 2:
0 = the answer states a specific fact NOT supported by the evidence (fabrication)
1 = mostly grounded, but includes at least one minor unsupported detail
2 = fully grounded -- every specific fact traces to the evidence, OR the answer correctly \
abstains when the evidence is absent/insufficient

Respond with ONLY this JSON, nothing else:
{{"score": <0, 1, or 2>, "reasoning": "<one short sentence>"}}
"""


def _parse_judge_response(raw: str) -> JudgeScore:
    parsed = extract_json_object(raw)
    if parsed is None:
        return JudgeScore(score=None, reasoning=f"unparseable judge response: {(raw or '')[:200]!r}")
    try:
        score = int(parsed["score"])
        if score not in (0, 1, 2):
            return JudgeScore(score=None, reasoning=f"judge returned out-of-range score: {score}")
        return JudgeScore(score=score, reasoning=str(parsed.get("reasoning", "")))
    except (KeyError, TypeError, ValueError) as exc:
        return JudgeScore(score=None, reasoning=f"judge JSON parse failed: {exc}")


def judge_correctness(question: BenchmarkQuestion, result: AgentResult) -> JudgeScore:
    model = get_chat_model()
    prompt = _CORRECTNESS_PROMPT.format(
        question=question.question,
        expected_answer=question.expected_answer,
        actual_answer=result.answer,
    )
    response = model.invoke(prompt)
    return _parse_judge_response(response.content if isinstance(response.content, str) else "")


def judge_groundedness(question: BenchmarkQuestion, result: AgentResult) -> JudgeScore:
    model = get_chat_model()
    evidence_summary = evidence_digest(result.evidence) if result.evidence else "(none -- no evidence was retrieved)"
    prompt = _GROUNDEDNESS_PROMPT.format(
        question=question.question,
        evidence_summary=evidence_summary,
        actual_answer=result.answer,
    )
    response = model.invoke(prompt)
    return _parse_judge_response(response.content if isinstance(response.content, str) else "")
