"""Update Slack profile fields via users.profile.set."""

from __future__ import annotations

import json
import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_logger = logging.getLogger(__name__)


def describe_slack_token_user(*, client: WebClient) -> str:
    """Brief non-secret WHO for this token (:func:`auth.test`)."""
    try:
        payload = client.auth_test()
    except SlackApiError as exc:
        err = (
            exc.response.get("error", "unknown_error")
            if exc.response is not None
            else "unknown_error"
        )
        return f"auth.test failed ({err})"
    user_id = payload.get("user_id", "?")
    handle = payload.get("user", "?")
    team_domain = payload.get("team", "?")
    return (
        f"login={handle!r} user_id={user_id!r} "
        f"workspace_subdomain={team_domain!r}"
    )


def set_profile_title(*, client: WebClient, title: str) -> None:
    """Set the authenticated user's job title (`title` in the Slack profile).

    Slack recommends ``POST`` with JSON containing a nested ``profile`` object;
    plain form-urlencoded alone can behave poorly with Unicode on some setups.
    """
    try:
        payload = client.users_profile_set(profile={"title": title})
    except SlackApiError as exc:
        err = (
            exc.response.get("error", "unknown_error")
            if exc.response is not None
            else "unknown_error"
        )
        rm = exc.response.get("response_metadata", {}) if exc.response else {}
        extra = rm.get("messages") if isinstance(rm, dict) else rm
        msg = f"Slack users.profile.set failed: {err} metadata={extra!r}"
        raise RuntimeError(msg) from exc

    warns = payload.get("response_metadata", {}).get("messages")
    if warns:
        _logger.warning("Slack users.profile.set warnings: %s", warns)
    prof_any = payload.get("profile") or {}
    if isinstance(prof_any, str):
        prof_any = json.loads(prof_any)
    if isinstance(prof_any, dict):
        got_raw = prof_any.get("title", "")
        req = (title or "").strip()
        got = got_raw.strip() if isinstance(got_raw, str) else ""
        if got != req:
            _logger.warning(
                "Slack ok:true but title %r != sent %r. Compare "
                "auth.test user to edited profile; HR/SCIM; admin blocks.",
                got,
                req,
            )
        elif got:
            _logger.info(
                "Slack users.profile.set ok; profile title stored as %r",
                got,
            )
