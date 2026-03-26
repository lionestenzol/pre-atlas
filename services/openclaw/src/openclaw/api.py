"""OpenClaw REST API — FastAPI on port 3004."""
import structlog
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from openclaw.config import config
from openclaw.channels.base import Channel, ChannelType, Command, Message
from openclaw.channels.telegram import TelegramChannel
from openclaw.channels.slack import SlackChannel
from openclaw.channels.discord import DiscordChannel
from openclaw.skills.status import handle_status
from openclaw.skills.brief import handle_brief
from openclaw.skills.fest import handle_fest
from openclaw.skills.simulate import handle_simulate
from openclaw.skills.approve import handle_approve
from openclaw.scheduler import DailyScheduler

log = structlog.get_logger()

app = FastAPI(
    title="OpenClaw",
    version="0.1.0",
    description="Multi-channel messaging gateway for the Mosaic platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Channel registry
channels: dict[str, Channel] = {
    "telegram": TelegramChannel(),
    "slack": SlackChannel(),
    "discord": DiscordChannel(),
}

# Skill registry
SKILLS = {
    "status": Command(name="status", description="System status", handler=handle_status),
    "brief": Command(name="brief", description="Daily brief", handler=handle_brief),
    "fest": Command(name="fest", description="Festival progress", handler=handle_fest),
    "simulate": Command(name="simulate", description="Start simulation", handler=handle_simulate),
    "approve": Command(name="approve", description="Approve item", handler=handle_approve),
}

# Scheduler
scheduler = DailyScheduler(channels=list(channels.values()))


class NotifyRequest(BaseModel):
    text: str
    channel: str | None = None  # None = all channels
    chat_id: str = ""


@app.get("/api/v1/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "service": "openclaw",
    }


@app.get("/api/v1/channels")
async def list_channels():
    """List all channels and their connection status."""
    return {
        "channels": [
            {
                "name": name,
                "type": ch.channel_type.value,
                "connected": ch.connected,
            }
            for name, ch in channels.items()
        ]
    }


@app.post("/api/v1/notify")
async def notify(req: NotifyRequest):
    """Send a notification to one or all channels."""
    results = {}

    if req.channel:
        ch = channels.get(req.channel)
        if not ch:
            raise HTTPException(status_code=404, detail=f"Channel '{req.channel}' not found")
        ok = await ch.send_message(req.text, chat_id=req.chat_id)
        results[req.channel] = ok
    else:
        for name, ch in channels.items():
            if ch.connected:
                ok = await ch.send_message(req.text, chat_id=req.chat_id)
                results[name] = ok

    return {"sent": results}


@app.get("/api/v1/skills")
async def list_skills():
    """List available skills."""
    return {
        "skills": [
            {"name": cmd.name, "description": cmd.description}
            for cmd in SKILLS.values()
        ]
    }


@app.post("/api/v1/skills/{skill_name}")
async def execute_skill(skill_name: str, text: str = ""):
    """Execute a skill command programmatically."""
    cmd = SKILLS.get(skill_name)
    if not cmd or not cmd.handler:
        raise HTTPException(status_code=404, detail=f"Skill '/{skill_name}' not found")

    message = Message(text=text)
    result = await cmd.handler(message)
    return {"skill": skill_name, "result": result}
