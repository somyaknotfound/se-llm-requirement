"""Web interface (brief points 7, 16, 17 and 19).

    python -m src.app              # http://127.0.0.1:7860
    python -m src.app --share      # a temporary public HTTPS link (Colab)

Tabs:
  Sign in          password + TOTP one-time code; the session holds the user's roles
  Approval queue   the items routed to your roles; accept, reject, modify or regenerate
  Artefacts        the SRS, stories, registers and SDLC recommendation for a case
  Live interview   a real person answers the interaction agent as a stakeholder; the
                   transcript is masked, screened for injection and saved for extraction
  Survey           the System Usability Scale plus three usefulness items

Nothing is shown before sign-in. Every decision is recorded under the signed-in user
and the role they act in, and appended to the case's decision log.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from . import load_pipeline, store
from .approve import authenticate
from .cases import case_ids, case_out_dir, load_case
from .evaluate import SUS_ITEMS, _eval_dir
from .knowledge import load_stakeholder_templates

SUS_TEXT = [
    "I think that I would like to use this system frequently.",
    "I found the system unnecessarily complex.",
    "I thought the system was easy to use.",
    "I think that I would need the support of a technical person to be able to use this system.",
    "I found the various functions in this system were well integrated.",
    "I thought there was too much inconsistency in this system.",
    "I would imagine that most people would learn to use this system very quickly.",
    "I found the system very cumbersome to use.",
    "I felt very confident using the system.",
    "I needed to learn a lot of things before I could get going with this system.",
]
USEFULNESS = [
    "The questions the assistant asked were relevant to my role.",
    "The requirements generated captured what I said accurately.",
    "I would accept these requirements as a first draft to review.",
]
QUEUE_COLUMNS = ["id", "priority", "required_role", "item_type", "item_id", "reason"]


def _signed_in(session: dict[str, Any]) -> bool:
    return bool(session and session.get("user"))


def _state(case_id: str) -> dict[str, Any]:
    path = case_out_dir(case_id) / "state.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _item_detail(case_id: str, approval_id: str) -> str:
    run_dir = case_out_dir(case_id)
    queue = store.approvals(run_dir, status=None)
    row = queue[queue["id"] == approval_id]
    if row.empty:
        return f"No item {approval_id}."
    item = row.iloc[0]
    lines = [f"**{item['id']}** — {item['item_type']} for **{item['item_id']}** "
             f"(role: {item['required_role']}, status: {item['status']})", "", f"Reason: {item['reason']}"]
    reqs = {r["req_id"]: r for r in _state(case_id).get("requirements", [])}
    req = reqs.get(item["item_id"])
    if req:
        lines += ["", f"> {req['statement']}", "",
                  f"- Acceptance criteria: {req.get('acceptance_criteria', '')}",
                  f"- Sources: {', '.join(req.get('source_statement_ids', [])) or '—'}",
                  f"- Evidence: {', '.join(req.get('source_chunk_ids', [])) or '—'}",
                  f"- Regulations: {', '.join(req.get('regulations', [])) or '—'}",
                  f"- Confidence: {req.get('confidence')} {('— ' + req['confidence_reasons']) if req.get('escalate') else ''}"]
    return "\n".join(lines)


def _save_survey(role: str, sus: list[int], useful: list[int], comment: str) -> str:
    path = _eval_dir() / "survey_responses.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["at", "role", *[f"sus_{i}" for i in range(1, SUS_ITEMS + 1)],
                        *[f"useful_{i}" for i in range(1, len(USEFULNESS) + 1)], "comment"])
        w.writerow([datetime.now(timezone.utc).isoformat(), role, *sus, *useful, comment.strip()])
    score = sum((v - 1) if i % 2 == 0 else (5 - v) for i, v in enumerate(sus)) * 2.5
    return f"Thank you. Your SUS score is {score:.1f} / 100."


def build():
    import gradio as gr

    from .agents import AgentContext, Blackboard, StakeholderInteractionAgent
    from .orchestrator import public_case
    from .security import Vault, mask, quarantine

    templates = load_stakeholder_templates()
    cases = case_ids()

    with gr.Blocks(title="SE LLM-RE") as demo:
        session = gr.State({})
        gr.Markdown("# Requirements engineering assistant — e-prescribing case studies")

        with gr.Tab("Sign in"):
            user = gr.Textbox(label="User")
            password = gr.Textbox(label="Password", type="password")
            otp = gr.Textbox(label="One-time code from your authenticator app")
            sign_btn = gr.Button("Sign in", variant="primary")
            sign_msg = gr.Markdown()

            def sign_in(u, p, o):
                try:
                    roles = authenticate(u.strip(), p, o.strip())
                except PermissionError as exc:
                    return {}, f"**{exc}**"
                return {"user": u.strip(), "roles": roles}, f"Signed in as **{u}** — roles: {', '.join(roles)}"

            sign_btn.click(sign_in, [user, password, otp], [session, sign_msg])

        with gr.Tab("Approval queue"):
            q_case = gr.Dropdown(cases, label="Case", value=cases[0] if cases else None)
            q_load = gr.Button("Load my queue")
            q_table = gr.Dataframe(headers=QUEUE_COLUMNS, interactive=False, wrap=True)
            q_id = gr.Textbox(label="Approval id (e.g. APR-004)")
            q_show = gr.Button("Show item")
            q_detail = gr.Markdown()
            q_role = gr.Dropdown([], label="Act as role")
            q_decision = gr.Radio(sorted(store.DECISIONS), label="Decision")
            q_note = gr.Textbox(label="Note (required for regenerate)")
            q_text = gr.Textbox(label="Modified requirement text (required for modify)", lines=3)
            q_submit = gr.Button("Record decision", variant="primary")
            q_bulk_note = gr.Textbox(label="Bulk note: what you reviewed (required)")
            q_bulk = gr.Button("Accept every routine (normal-priority) item for this role")
            q_msg = gr.Markdown()

            def load_queue(case_id, sess):
                if not _signed_in(sess):
                    return pd.DataFrame(columns=QUEUE_COLUMNS), gr.update(choices=[]), "**Sign in first.**"
                frame = store.approvals(case_out_dir(case_id))
                frame = frame[frame["required_role"].isin(sess["roles"])][QUEUE_COLUMNS]
                return frame, gr.update(choices=sess["roles"], value=sess["roles"][0]), f"{len(frame)} pending"

            def show_item(case_id, approval_id, sess):
                if not _signed_in(sess):
                    return "**Sign in first.**"
                return _item_detail(case_id, approval_id.strip())

            def record(case_id, approval_id, decision, role, note, text, sess):
                if not _signed_in(sess):
                    return "**Sign in first.**", pd.DataFrame(columns=QUEUE_COLUMNS)
                if role not in sess["roles"]:
                    return "**Choose one of your roles.**", pd.DataFrame(columns=QUEUE_COLUMNS)
                try:
                    rec = store.decide(case_out_dir(case_id), approval_id.strip(), decision, sess["user"], role,
                                       note or "", text or "")
                    msg = f"Recorded **{rec['decision']}** on {rec['approval_id']} as {role}."
                except (KeyError, ValueError, PermissionError) as exc:
                    msg = f"**{exc}**"
                frame = store.approvals(case_out_dir(case_id))
                return msg, frame[frame["required_role"].isin(sess["roles"])][QUEUE_COLUMNS]

            def bulk(case_id, role, note, sess):
                if not _signed_in(sess) or role not in sess.get("roles", []):
                    return "**Sign in and choose one of your roles.**", pd.DataFrame(columns=QUEUE_COLUMNS)
                try:
                    done = store.decide_many(case_out_dir(case_id), "accept", sess["user"], role, note or "")
                    msg = f"Accepted {len(done)} routine item(s) as {role}. High-priority items remain."
                except ValueError as exc:
                    msg = f"**{exc}**"
                frame = store.approvals(case_out_dir(case_id))
                return msg, frame[frame["required_role"].isin(sess["roles"])][QUEUE_COLUMNS]

            q_load.click(load_queue, [q_case, session], [q_table, q_role, q_msg])
            q_bulk.click(bulk, [q_case, q_role, q_bulk_note, session], [q_msg, q_table])
            q_show.click(show_item, [q_case, q_id, session], [q_detail])
            q_submit.click(record, [q_case, q_id, q_decision, q_role, q_note, q_text, session], [q_msg, q_table])

        with gr.Tab("Artefacts"):
            a_case = gr.Dropdown(cases, label="Case", value=cases[0] if cases else None)
            a_name = gr.Dropdown([], label="Artefact")
            a_list = gr.Button("List artefacts")
            a_md = gr.Markdown()
            a_df = gr.Dataframe(interactive=False, wrap=True)

            def list_artefacts(case_id, sess):
                if not _signed_in(sess):
                    return gr.update(choices=[])
                names = sorted(p.name for p in (case_out_dir(case_id) / "artifacts").glob("*"))
                return gr.update(choices=names, value=names[0] if names else None)

            def open_artefact(case_id, name, sess):
                if not _signed_in(sess) or not name:
                    return "**Sign in first.**", pd.DataFrame()
                path = case_out_dir(case_id) / "artifacts" / name
                if path.suffix == ".csv":
                    return "", pd.read_csv(path)
                return path.read_text(encoding="utf-8"), pd.DataFrame()

            a_list.click(list_artefacts, [a_case, session], [a_name])
            a_name.change(open_artefact, [a_case, a_name, session], [a_md, a_df])

        with gr.Tab("Live interview"):
            gr.Markdown("Answer as the stakeholder you are. The agent asks role-specific questions, then "
                        "follows up where an answer is vague or incomplete. Answers are masked and screened "
                        "before anything is stored.")
            i_case = gr.Dropdown(cases, label="Case", value=cases[0] if cases else None)
            i_role = gr.Dropdown(sorted(templates["roles"]), label="Your role")
            i_start = gr.Button("Start interview", variant="primary")
            try:
                chat = gr.Chatbot(type="messages", height=380)
            except TypeError:  # Gradio 6 removed `type`: the messages format is the default
                chat = gr.Chatbot(height=380)
            i_answer = gr.Textbox(label="Your answer")
            i_send = gr.Button("Send")
            i_msg = gr.Markdown()
            interview = gr.State({})

            def context(case_id):
                from .llm import OllamaClient

                run_dir = case_out_dir(case_id) / "live"
                run_dir.mkdir(parents=True, exist_ok=True)
                return AgentContext(case=public_case(load_case(case_id)), board=Blackboard(),
                                    client=OllamaClient(), run_dir=run_dir, cfg=load_pipeline(), step="live_interview")

            def start(case_id, role, sess):
                if not _signed_in(sess):
                    return [], {}, "**Sign in first.**"
                agent = StakeholderInteractionAgent(context(case_id), templates)
                questions = agent.plan_questions({"id": "LIVE", "role": role})
                st = {"case": case_id, "role": role, "queue": questions, "i": 0, "round": 1,
                      "answers": [], "user": hashlib.sha256(sess["user"].encode()).hexdigest()[:10]}
                return [{"role": "assistant", "content": questions[0]["question"]}], st, ""

            def send(text, st, history):
                if not st:
                    return history, st, "", "Start an interview first."
                vault = Vault()
                masked, _ = mask(text, vault)
                clean, injections = quarantine(masked)
                q = st["queue"][st["i"]]
                st["answers"].append({"id": f"S-LIVE-{len(st['answers']) + 1:02d}", "stakeholder": "LIVE",
                                      "role": st["role"], "source_type": "interview", "round": st["round"],
                                      "topic": q.get("topic", ""), "question": q["question"], "text": clean,
                                      "follows_up": q.get("about_statement", ""),
                                      "screened": [f["kind"] for f in injections]})
                history = history + [{"role": "user", "content": text}]
                st["i"] += 1
                if st["i"] >= len(st["queue"]) and st["round"] == 1:
                    agent = StakeholderInteractionAgent(context(st["case"]), templates)
                    issues = agent.detect_issues(st["answers"])
                    st["queue"] = agent.plan_followups({"id": "LIVE", "role": st["role"]}, st["answers"], issues)
                    st["i"], st["round"] = 0, 2
                if st["i"] < len(st["queue"]):
                    history.append({"role": "assistant", "content": st["queue"][st["i"]]["question"]})
                    return history, st, "", ""
                out = case_out_dir(st["case"]) / "live_interviews"
                out.mkdir(parents=True, exist_ok=True)
                path = out / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{st['role']}.json"
                path.write_text(json.dumps({"role": st["role"], "user": st["user"], "statements": st["answers"]},
                                           indent=1), encoding="utf-8")
                history.append({"role": "assistant", "content": "Thank you — that is everything I needed."})
                return history, {}, "", (f"Saved {len(st['answers'])} statements to `{path.name}`. Run the "
                                         f"orchestrator with `--include-live` to extract requirements from them.")

            i_start.click(start, [i_case, i_role, session], [chat, interview, i_msg])
            i_send.click(send, [i_answer, interview, chat], [chat, interview, i_answer, i_msg])

        with gr.Tab("Survey"):
            s_role = gr.Dropdown(sorted(templates["roles"]), label="Your role")
            gr.Markdown("1 = strongly disagree, 5 = strongly agree")
            sus = [gr.Slider(1, 5, value=3, step=1, label=f"{i}. {t}") for i, t in enumerate(SUS_TEXT, start=1)]
            use = [gr.Slider(1, 5, value=3, step=1, label=t) for t in USEFULNESS]
            comment = gr.Textbox(label="Anything else?", lines=2)
            s_submit = gr.Button("Submit", variant="primary")
            s_msg = gr.Markdown()

            def submit(role, *vals):
                *scores, note = vals
                if not role:
                    return "**Choose your role.**"
                return _save_survey(role, [int(v) for v in scores[:SUS_ITEMS]],
                                    [int(v) for v in scores[SUS_ITEMS:]], note or "")

            s_submit.click(submit, [s_role, *sus, *use, comment], [s_msg])
    return demo


def main() -> int:
    ap = argparse.ArgumentParser(description="Web interface for interviews, approvals and artefacts")
    ap.add_argument("--share", action="store_true", help="create a temporary public HTTPS link")
    ap.add_argument("--port", type=int, default=7860)
    args = ap.parse_args()
    build().launch(share=args.share, server_port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
