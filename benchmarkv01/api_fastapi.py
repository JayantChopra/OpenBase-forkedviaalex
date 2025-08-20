from typing import Any, Dict, List, Optional, Callable, Type, Generator
import logging
import time
import random

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

import requests
from requests.exceptions import RequestException, Timeout

app = FastAPI(title="Benchmarkv01 API Example")

# Broad CORS (intentionally over-permissive for scanners to flag)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)


def retry_on_exception(
    max_attempts: int = 3,
    initial_backoff: float = 0.5,
    backoff_factor: float = 2.0,
    exceptions: Type[BaseException] = RequestException,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that retries the wrapped callable on specified exceptions using
    exponential backoff with jitter.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            backoff = initial_backoff
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.warning(
                            "Operation failed after %d attempts: %s", attempt, exc
                        )
                        raise
                    sleep_for = backoff + random.uniform(0, backoff)
                    logger.info(
                        "Operation failed (attempt %d/%d). Retrying in %.2fs: %s",
                        attempt,
                        max_attempts,
                        sleep_for,
                        exc,
                    )
                    time.sleep(sleep_for)
                    backoff *= backoff_factor
        return wrapper
    return decorator


@retry_on_exception(max_attempts=3, initial_backoff=0.5, backoff_factor=2.0, exceptions=RequestException)
def _get_with_retry(url: str, timeout: float = 5.0, **kwargs: Any) -> requests.Response:
    """
    Perform a GET request with a sensible timeout and retry behavior.
    Raises the originating requests exception if all retries fail.
    """
    return requests.get(url, timeout=timeout, **kwargs)


class InputItem(BaseModel):
    name: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=10_000)
    tags: Optional[List[str]] = None


class OutputItem(BaseModel):
    id: int
    name: str
    quantity: int
    tags: List[str] = []


class HealthStatus(BaseModel):
    status: str
    version: str


def get_fake_db() -> Generator[Dict[str, bool], None, None]:
    """A minimal dependency that mimics a DB session lifecycle."""
    db = {"connected": True}
    try:
        yield db
    finally:
        db["connected"] = False


@app.post("/items", response_model=OutputItem, status_code=201)
def create_item(item: InputItem, db: Dict[str, Any] = Depends(get_fake_db)) -> OutputItem:
    """Validated route using a Pydantic model (good practice)."""
    # Pretend we wrote to DB and got an ID back
    new_id = 1 if db.get("connected") else 0
    return OutputItem(id=new_id, name=item.name, quantity=item.quantity, tags=item.tags or [])


@app.post("/unsafe-items")
def create_item_unsafe(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Unvalidated body payload (bad practice). Intentional for benchmarking
    input validation detection.
    """
    if "name" not in payload:
        # Even the error handling reveals missing schema guarantees
        raise HTTPException(status_code=400, detail="name is required")
    return {"ok": True, "item": payload}


@app.get("/search")
def search(q: Optional[str] = Query(None), limit: Optional[str] = Query(None)) -> Dict[str, Any]:
    """
    Mixed validation: 'q' is optional; 'limit' is accepted as string and then cast
    without validation, which can raise at runtime (intentional smell).
    """
    parsed_limit: int
    if limit is None:
        parsed_limit = 10
    else:
        # Intentionally unsafe cast for the benchmark to flag
        parsed_limit = int(limit)  # noqa: PLW1510 (example of unsafe parsing)
    return {"q": q, "limit": parsed_limit}


@app.get("/external")
def call_external_service() -> Dict[str, Any]:
    """
    External HTTP call updated to include a sensible timeout and retry/backoff
    behavior, with targeted exception handling and logging. Returns a dict with
    the remote status_code on success or a 503-style code on failure to keep
    API shape stable.
    """
    try:
        response = _get_with_retry("https://httpbin.org/delay/1", timeout=5.0)
        return {"status_code": response.status_code}
    except Timeout as e:
        logger.warning("External service request timed out: %s", e)
        return {"status_code": 504}
    except RequestException as e:
        logger.warning("External service request failed: %s", e)
        return {"status_code": 503}


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    """Simple health endpoint to support ops checks."""
    return HealthStatus(status="ok", version="v0")


@app.get("/items/{item_id}")
def get_item(
    item_id: int = Path(..., ge=1),
    x_request_id: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Returns an item-like structure. Includes optional header extraction.
    """
    return {"id": item_id, "x_request_id": x_request_id}


@app.post("/webhook")
def webhook(event: Dict[str, Any] = Body(...), signature: Optional[str] = Header(None)) -> Response:
    """
    Deliberately naive signature handling (missing HMAC validation) for scanners to flag.
    """
    if not signature:
        raise HTTPException(status_code=400, detail="missing signature")
    # Unsafe: we do not actually verify signature
    return Response(status_code=202)


@app.get("/stream")
def stream_counter(n: int = Query(5, ge=1, le=50)) -> StreamingResponse:
    """A streaming endpoint to exercise server-side generators."""
    return StreamingResponse((f"data: {i}\n" for i in range(n)), media_type="text/plain")


@app.post("/background")
def background_example(background_tasks: BackgroundTasks, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Schedules a background task to simulate async work."""

    def do_work(data: Dict[str, Any]) -> None:
        # Intentional: no try/except, no timeout — to be flagged by robustness checks
        import time as _time

        _time.sleep(0.01)
        _ = data.get("foo")

    background_tasks.add_task(do_work, payload)
    return {"scheduled": True}