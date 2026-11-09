from dataclasses import asdict

from fastapi import APIRouter, Request

from bussola.api.ai_review import line_links, link_targets
from bussola.api.compare import code_range
from bussola.api.deps import ContextDep, repo_of, resolve_revision
from bussola.api.descriptions import ai_provider, ai_runner
from bussola.api.schemas import AiChatIn, AiChatMessageOut, AiChatSnippetOut, AiReviewLinkOut, AiReviewLookupOut
from bussola.api.state import app_state
from bussola.config import load_repo_config
from bussola.review.ai_chat import ASSISTANT, USER, ChatQuestion, answer_chat, chat_snippet
from bussola.review.context import ReviewContext
from bussola.review.repos import open_repo
from bussola.review.review_tools import SIDES, ReviewTools
from bussola.storage.models import AiChatMessage

router = APIRouter(tags=["ai-chat"])


@router.get("/reviews/{review_id}/ai-chat")
def list_chat(context: ContextDep) -> list[AiChatMessageOut]:
    return _messages_out(context, context.store.ai_chat.messages(context.review.id))


@router.post("/reviews/{review_id}/ai-chat")
def send_chat(context: ContextDep, body: AiChatIn, request: Request) -> list[AiChatMessageOut]:
    state = app_state(request)
    provider = ai_provider(state, context, body.target)
    revision = resolve_revision(context, None)
    snippets = [chat_snippet(code_range(context, item)) for item in body.snippets]
    git_repo = open_repo(repo_of(context))
    ignore = load_repo_config(git_repo.root).ignore
    history = context.store.ai_chat.messages(context.review.id)
    snapshots = context.store.reviews.snapshots(revision.id)
    context.store.commit()
    with state.ai_calls.start(body.call_id) as cancellation:
        tools = ReviewTools(git_repo, revision, snapshots, state.navigator, ignore, cancellation)
        reply = answer_chat(context, ai_runner(state, provider), tools, ChatQuestion(body.message, snippets, history))
    review_id = context.review.id
    question = context.store.ai_chat.add(AiChatMessage(review_id, USER, body.message, [asdict(snippet) for snippet in snippets]))
    answer = AiChatMessage(review_id, ASSISTANT, reply.answer, lookups=reply.lookups, provider_label=provider.label, model=provider.model)
    answer = context.store.ai_chat.add(answer)
    context.store.commit()
    return _messages_out(context, [question, answer])


@router.delete("/reviews/{review_id}/ai-chat")
def clear_chat(context: ContextDep) -> list[AiChatMessageOut]:
    context.store.ai_chat.clear(context.review.id)
    context.store.commit()
    return []


def _messages_out(context: ReviewContext, messages: list[AiChatMessage]) -> list[AiChatMessageOut]:
    links = line_links(context, [message.body for message in messages if message.role == ASSISTANT])
    return [_message_out(message, _links_in(message, links)) for message in messages]


def _links_in(message: AiChatMessage, links: list[AiReviewLinkOut]) -> list[AiReviewLinkOut]:
    if message.role != ASSISTANT:
        return []
    targets = {(SIDES[name], path, line) for name, path, line in link_targets(message.body)}
    return [link for link in links if (link.side, link.path, link.line) in targets]


def _message_out(message: AiChatMessage, links: list[AiReviewLinkOut]) -> AiChatMessageOut:
    return AiChatMessageOut(
        id=message.id,
        role=USER if message.role == USER else ASSISTANT,
        body=message.body,
        snippets=[AiChatSnippetOut.model_validate(snippet) for snippet in message.snippets],
        lookups=[AiReviewLookupOut.model_validate(lookup) for lookup in message.lookups],
        links=links,
        provider_label=message.provider_label,
        model=message.model,
        created_at=message.created_at,
    )
