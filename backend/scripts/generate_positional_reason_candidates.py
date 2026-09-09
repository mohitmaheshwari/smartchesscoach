#!/usr/bin/env python3
"""Generate and independently review positional-caption candidates.

This is an offline authoring tool. It ranks the two human-supplied exclusion
classes, writes exactly the requested exclusion counts, and keeps every result
as a non-authoritative candidate for admin review.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
from typing import Any

from openai import AsyncOpenAI


AUTHOR_SYSTEM = """You are a senior chess coach and evidence editor. Review positions for 900-1500 rated players.

You receive Stockfish 17.1 root alternatives, the forced continuation after the played move, and legal board facts. Use only that evidence. Do not invent a move, attack, defender, plan, or outcome.

For every position return:
- already_decided_score: 0-100. High only when the result was effectively settled before the move and teaching this choice would be noise.
- not_mistake_score: 0-100. High only when the played move remains a reasonable practical choice and the engine preference is too narrow to teach as a mistake.
- teaching_value_score: 0-100. High when the contrast gives a reusable lesson.
- concept_label: a plain headline, at most 8 words.
- canonical_concept_id: one supplied canonical ID, or null.
- better_move_fact: one concrete sentence starting with the supplied best SAN and naming a piece, square, pawn, file, rank, or king.
- played_move_fact: one concrete sentence starting with the supplied played SAN and naming the board consequence.
- contrast: one sentence explaining why the difference matters.
- transferable_lesson: one plain rule the player can apply in another game.
- caption: 2-3 connected sentences, 28-58 words, naming both supplied moves and the concrete reason.
- author_confidence: 0.00-1.00.
- evidence_refs: a non-empty list chosen only from board, root_1..root_5, played_line.

Voice rules: no engine scores, no vague "improves the position", no unexplained jargon, no generic praise, and no claim that centipawns equal captured material. Prefer named squares. If the evidence proves only a narrow comparison, write a narrow caption.

Return a JSON object with key reviews. Preserve each input id exactly."""


CRITIC_SYSTEM = """You are the independent chess-proof editor. Check each candidate only against the supplied legal board facts and Stockfish lines.

Reject or repair invented attacks, defenders, material wins, forced claims, vague plans, wrong perspective, illegal moves, unexplained jargon, and lessons unsupported by the contrast. The final caption must teach a 900-1500 player, name both supplied moves, explain the concrete board difference, and be 28-58 words. Keep claims narrow when the continuation proves only a narrow fact.

Return a JSON object with key reviews. For each input id return verdict (pass or fail), critic_confidence (0.00-1.00), issues (list), and final containing concept_label, canonical_concept_id, better_move_fact, played_move_fact, contrast, transferable_lesson, caption, and evidence_refs. Preserve each id exactly."""


FORBIDDEN = (
    "centipawn",
    "eval",
    "engine says",
    "improves the position",
    "weakens the position",
    "loses tempo",
    "key squares",
    "prophylaxis",
    "fianchetto",
    "zwischenzug",
    "zugzwang",
    "luft",
    "minority attack",
)
SQUARE_RE = re.compile(r"\b[a-h][1-8]\b", re.IGNORECASE)


def compact_position(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row["engine_evidence"]
    lines = []
    for index, line in enumerate(evidence["root_top_lines"], 1):
        lines.append(
            {
                "ref": f"root_{index}",
                "score_cp": line.get("score_cp"),
                "mate": line.get("mate"),
                "wdl": line.get("wdl"),
                "moves": line.get("pv_san"),
            }
        )
    played = evidence["played_line"]
    return {
        "id": row["candidate_id"],
        "fen": row["fen"],
        "side_to_move": row["side_to_move"],
        "phase": row["bucket"],
        "played_san": row["played_san"],
        "best_san": row["best_san"],
        "stored_best_is_fresh_best": evidence["stored_best_is_fresh_best"],
        "fresh_best_uci": evidence["fresh_best_uci"],
        "fresh_loss_cp": evidence["fresh_loss_cp"],
        "best_to_second_margin_cp": evidence["best_to_second_margin_cp"],
        "root_lines": lines,
        "played_line": {
            "ref": "played_line",
            "score_cp": played.get("score_cp"),
            "mate": played.get("mate"),
            "wdl": played.get("wdl"),
            "moves": played.get("pv_san"),
        },
        "board": row["board_evidence"],
        "already_explained_by": row.get("already_explained_by") or [],
    }


def clean_json(text: str) -> dict[str, Any]:
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    return json.loads(value)


async def model_json(
    client: AsyncOpenAI,
    semaphore: asyncio.Semaphore,
    *,
    model: str,
    system: str,
    payload: dict[str, Any],
    attempts: int = 6,
) -> dict[str, Any]:
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            async with semaphore:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(payload, separators=(",", ":"))},
                    ],
                    response_format={"type": "json_object"},
                    max_completion_tokens=12_000,
                    reasoning_effort="medium",
                )
            return clean_json(response.choices[0].message.content or "")
        except Exception as exc:
            error = exc
            await asyncio.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f"model call failed after {attempts} attempts: {error}")


def chunks(values: list[Any], size: int) -> list[list[Any]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def as_score(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def as_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def normalize_san(value: str) -> str:
    return re.sub(r"[+#?!]", "", str(value or "")).strip()


def deterministic_issues(row: dict[str, Any], final: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required = (
        "concept_label",
        "better_move_fact",
        "played_move_fact",
        "contrast",
        "transferable_lesson",
        "caption",
    )
    for field in required:
        if not str(final.get(field) or "").strip():
            issues.append(f"missing_{field}")
    text = " ".join(str(final.get(field) or "") for field in required)
    lower = text.lower()
    for phrase in FORBIDDEN:
        if phrase in lower:
            issues.append(f"forbidden_phrase:{phrase}")
    caption = str(final.get("caption") or "")
    words = re.findall(r"\b[\w'-]+\b", caption)
    if not 28 <= len(words) <= 58:
        issues.append(f"caption_word_count:{len(words)}")
    if normalize_san(row["played_san"]).lower() not in normalize_san(caption).lower():
        issues.append("caption_missing_played_move")
    if normalize_san(row["best_san"]).lower() not in normalize_san(caption).lower():
        issues.append("caption_missing_best_move")
    if not SQUARE_RE.search(text):
        issues.append("no_named_square")
    refs = final.get("evidence_refs") or []
    allowed_refs = {"board", "played_line", "root_1", "root_2", "root_3", "root_4", "root_5"}
    if not refs or any(ref not in allowed_refs for ref in refs):
        issues.append("invalid_evidence_refs")
    return sorted(set(issues))


async def run_batches(
    client: AsyncOpenAI,
    semaphore: asyncio.Semaphore,
    batches: list[list[dict[str, Any]]],
    *,
    model: str,
    system: str,
    kind: str,
) -> list[dict[str, Any]]:
    async def one(batch_no: int, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = await model_json(
            client,
            semaphore,
            model=model,
            system=system,
            payload={"positions": batch},
        )
        reviews = result.get("reviews")
        if not isinstance(reviews, list):
            raise RuntimeError(f"{kind} batch {batch_no} returned no reviews list")
        print(json.dumps({"stage": kind, "batch": batch_no, "batches": len(batches), "reviews": len(reviews)}), flush=True)
        return reviews

    tasks = [asyncio.create_task(one(index, batch)) for index, batch in enumerate(batches, 1)]
    nested = await asyncio.gather(*tasks)
    return [review for group in nested for review in group]


def select_targets(
    rows_by_id: dict[str, dict[str, Any]],
    authors: dict[str, dict[str, Any]],
    already_decided_count: int,
    not_mistake_count: int,
) -> tuple[dict[str, str], list[str]]:
    ids = list(rows_by_id)
    already = sorted(
        ids,
        key=lambda item: (
            as_score(authors[item].get("already_decided_score")),
            -as_score(authors[item].get("teaching_value_score")),
            rows_by_id[item]["engine_evidence"]["root_top_lines"][0]["wdl"].get("losses", 0),
        ),
        reverse=True,
    )[:already_decided_count]
    remaining = [item for item in ids if item not in set(already)]
    not_mistake = sorted(
        remaining,
        key=lambda item: (
            as_score(authors[item].get("not_mistake_score")),
            -as_score(authors[item].get("teaching_value_score")),
            -int(rows_by_id[item]["engine_evidence"].get("fresh_loss_cp") or 0),
        ),
        reverse=True,
    )[:not_mistake_count]
    dispositions = {item: "eligible_positional" for item in ids}
    dispositions.update({item: "already_decided" for item in already})
    dispositions.update({item: "not_mistake" for item in not_mistake})
    targets = [item for item in ids if dispositions[item] == "eligible_positional"]
    return dispositions, targets


def report_markdown(records: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    counts: dict[str, int] = {}
    for record in records:
        counts[record["disposition"]] = counts.get(record["disposition"], 0) + 1
    passed = sum(record.get("verification", {}).get("status") == "pass" for record in records)
    unresolved = sum(record.get("verification", {}).get("status") == "fail" for record in records)
    lines = [
        "# Positional caption generation report",
        "",
        f"Generated: {meta['generated_at']}",
        f"Model: `{meta['model']}`",
        f"Engine: `{meta['engine']}` at {meta['nodes_per_search']:,} nodes per search",
        "",
        "## Counts",
        "",
        f"- Total reviewed by the authoring pass: **{len(records)}**",
        f"- Caption targets: **{counts.get('eligible_positional', 0)}**",
        f"- Already decided: **{counts.get('already_decided', 0)}**",
        f"- Not a mistake: **{counts.get('not_mistake', 0)}**",
        f"- Independent verifier passed: **{passed}**",
        f"- Independent verifier unresolved: **{unresolved}**",
        "",
        "The 17/24 exclusions are evidence-ranked reconstructions because the live database stored the counts but not the 41 record identities. They remain review candidates, not runtime truth.",
        "",
        "## Caption candidates",
        "",
    ]
    for record in records:
        if record["disposition"] != "eligible_positional":
            continue
        final = record.get("final") or {}
        status = record.get("verification", {}).get("status", "fail")
        lines.extend(
            [
                f"### {record['candidate_id']} · {record['played_san']} → {record['best_san']} · {status}",
                "",
                str(final.get("caption") or ""),
                "",
            ]
        )
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--already-decided", type=int, default=17)
    parser.add_argument("--not-mistake", type=int, default=24)
    args = parser.parse_args()

    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = source["rows"]
    for row in rows:
        normalized = " ".join(row["fen"].split()[:4])
        identity = f"{normalized}|{row['played_uci']}|{row['best_uci']}"
        row["candidate_id"] = sha256(identity.encode("utf-8")).hexdigest()[:16]
    rows_by_id = {row["candidate_id"]: row for row in rows}
    compact_by_id = {key: compact_position(row) for key, row in rows_by_id.items()}

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=150.0)
    semaphore = asyncio.Semaphore(args.concurrency)
    author_reviews = await run_batches(
        client,
        semaphore,
        chunks(list(compact_by_id.values()), args.batch_size),
        model=args.model,
        system=AUTHOR_SYSTEM,
        kind="author",
    )
    authors = {str(review.get("id")): review for review in author_reviews}
    missing = sorted(set(rows_by_id) - set(authors))
    if missing:
        raise RuntimeError(f"authoring pass omitted {len(missing)} ids: {missing[:5]}")

    dispositions, target_ids = select_targets(
        rows_by_id,
        authors,
        args.already_decided,
        args.not_mistake,
    )
    critic_inputs = []
    for candidate_id in target_ids:
        critic_inputs.append(
            {
                **compact_by_id[candidate_id],
                "candidate": authors[candidate_id],
            }
        )
    critic_reviews = await run_batches(
        client,
        semaphore,
        chunks(critic_inputs, args.batch_size),
        model=args.model,
        system=CRITIC_SYSTEM,
        kind="critic",
    )
    critics = {str(review.get("id")): review for review in critic_reviews}
    missing_critics = sorted(set(target_ids) - set(critics))
    if missing_critics:
        raise RuntimeError(f"critic pass omitted {len(missing_critics)} ids: {missing_critics[:5]}")

    records: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    for candidate_id, row in rows_by_id.items():
        author = authors[candidate_id]
        disposition = dispositions[candidate_id]
        critic = critics.get(candidate_id)
        final = (critic or {}).get("final") or {
            key: author.get(key)
            for key in (
                "concept_label",
                "canonical_concept_id",
                "better_move_fact",
                "played_move_fact",
                "contrast",
                "transferable_lesson",
                "caption",
                "evidence_refs",
            )
        }
        issues = deterministic_issues(row, final) if disposition == "eligible_positional" else []
        critic_pass = bool(critic and critic.get("verdict") == "pass")
        confidence = min(
            as_confidence(author.get("author_confidence")),
            as_confidence((critic or {}).get("critic_confidence")),
        ) if critic else as_confidence(author.get("author_confidence"))
        status = (
            "pass"
            if disposition == "eligible_positional" and critic_pass and not issues and confidence >= 0.75
            else "fail"
            if disposition == "eligible_positional"
            else "not_applicable"
        )
        records.append(
            {
                "candidate_id": candidate_id,
                "position_fingerprint": sha256(
                    f"{' '.join(row['fen'].split()[:4])}|{row['played_uci']}|{row['best_uci']}".encode("utf-8")
                ).hexdigest(),
                "fen": " ".join(row["fen"].split()[:4]),
                "game_id": row.get("game_id"),
                "move_number": row.get("move_number"),
                "side_to_move": row.get("side_to_move"),
                "bucket": row.get("bucket"),
                "played_san": row.get("played_san"),
                "played_uci": row.get("played_uci"),
                "best_san": row.get("best_san"),
                "best_uci": row.get("best_uci"),
                "disposition": disposition,
                "author_scores": {
                    "already_decided": as_score(author.get("already_decided_score")),
                    "not_mistake": as_score(author.get("not_mistake_score")),
                    "teaching_value": as_score(author.get("teaching_value_score")),
                },
                "author": author,
                "critic": critic,
                "final": final,
                "verification": {
                    "status": status,
                    "confidence": confidence,
                    "critic_verdict": (critic or {}).get("verdict"),
                    "critic_issues": (critic or {}).get("issues") or [],
                    "deterministic_issues": issues,
                    "engine": row["engine_evidence"]["engine"],
                    "nodes_per_search": row["engine_evidence"]["nodes_per_search"],
                    "author_model": args.model,
                    "critic_model": args.model if critic else None,
                },
                "engine_evidence": row["engine_evidence"],
                "board_evidence": row["board_evidence"],
                "caption_eligible": False,
                "tracker_eligible": False,
                "generated_at": now,
            }
        )

    meta = {
        "schema_version": "positional_caption_candidates.v1",
        "generated_at": now,
        "model": args.model,
        "engine": rows[0]["engine_evidence"]["engine"] if rows else None,
        "nodes_per_search": rows[0]["engine_evidence"]["nodes_per_search"] if rows else None,
        "requested_exclusions": {
            "already_decided": args.already_decided,
            "not_mistake": args.not_mistake,
        },
        "runtime_authority": False,
    }
    Path(args.output).write_text(json.dumps({"meta": meta, "records": records}, indent=2), encoding="utf-8")

    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer)
    writer.writerow(
        [
            "candidate_id",
            "disposition",
            "verification_status",
            "confidence",
            "game_id",
            "move_number",
            "played_san",
            "best_san",
            "concept_label",
            "caption",
            "deterministic_issues",
        ]
    )
    for record in records:
        final = record.get("final") or {}
        writer.writerow(
            [
                record["candidate_id"],
                record["disposition"],
                record["verification"]["status"],
                record["verification"]["confidence"],
                record.get("game_id"),
                record.get("move_number"),
                record.get("played_san"),
                record.get("best_san"),
                final.get("concept_label"),
                final.get("caption"),
                ";".join(record["verification"]["deterministic_issues"]),
            ]
        )
    Path(args.csv_output).write_text(csv_buffer.getvalue(), encoding="utf-8")
    Path(args.report_output).write_text(report_markdown(records, meta), encoding="utf-8")

    print(
        json.dumps(
            {
                "total": len(records),
                "targets": len(target_ids),
                "already_decided": sum(r["disposition"] == "already_decided" for r in records),
                "not_mistake": sum(r["disposition"] == "not_mistake" for r in records),
                "passed": sum(r["verification"]["status"] == "pass" for r in records),
                "failed": sum(r["verification"]["status"] == "fail" for r in records),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
