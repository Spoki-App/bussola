from rtool.review.anchoring import reanchor_threads
from rtool.review.revisions import RevisionHook

REVISION_HOOKS: tuple[RevisionHook, ...] = (reanchor_threads,)
