import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import psycopg
import redis
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from redis.backoff import NoBackoff
from redis.retry import Retry
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

class ClickEvent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    event_id: UUID
    schema_version: int = Field(strict=True, ge=1, le=1)
    occurred_at: AwareDatetime
    session_id: str = Field(min_length=1, max_length=128)
    page: str = Field(min_length=1, max_length=2048)
    element_id: str = Field(min_length=1, max_length=128)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = redis.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=False,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
        retry=Retry(NoBackoff(), 0),
    )
    app.state.redis = client
    try:
        yield
    finally:
        client.close()


app = FastAPI(lifespan=lifespan)


@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(Path(__file__).with_name("index.html"), media_type="text/html")


@app.get("/stats/clicks")
def click_stats():
    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"], autocommit=True, connect_timeout=5
        ) as connection:
            rows = connection.execute(
                "SELECT element_id, COUNT(*) FROM click_events "
                "GROUP BY element_id ORDER BY element_id"
            ).fetchall()
    except (psycopg.Error, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Click statistics are unavailable.",
        ) from exc
    return [{"element_id": element_id, "count": count} for element_id, count in rows]


@app.post("/events/click", status_code=status.HTTP_202_ACCEPTED)
def post_click(event: ClickEvent, request: Request):
    payload = event.model_dump_json().encode("utf-8")
    try:
        entry_id = request.app.state.redis.xadd(
            "events:clicks:v1", {"payload": payload}
        )
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable; click event could not be acknowledged.",
        ) from exc
    return {"event_id": str(event.event_id), "stream_entry_id": entry_id.decode("utf-8")}
