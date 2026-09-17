from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)


SECRET_ENV_MAP = {
    "ohip_gateway_url": "OHIP_GATEWAY_URL",
    "ohip_streaming_ws_url": "OHIP_STREAMING_WS_URL",
    "ohip_token_url": "OHIP_TOKEN_URL",
    "ohip_application_key": "OHIP_APPLICATION_KEY",
    "ohip_client_id": "OHIP_CLIENT_ID",
    "ohip_client_secret": "OHIP_CLIENT_SECRET",
    "ohip_enterprise_id": "OHIP_ENTERPRISE_ID",
    "ohip_scope": "OHIP_SCOPE",
    "ohip_chain_code": "OHIP_CHAIN_CODE",
    "ohip_hotel_ids": "OHIP_HOTEL_IDS",
    "ohip_external_system_code": "OHIP_EXTERNAL_SYSTEM_CODE",
}


def load_secret_into_environment(secret_id: str | None, region: str) -> None:
    if not secret_id:
        return
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_id)
    raw_secret = response.get("SecretString")
    if not raw_secret:
        raise RuntimeError(f"Secret {secret_id} has no SecretString")
    payload: dict[str, Any] = json.loads(raw_secret)
    for secret_key, env_key in SECRET_ENV_MAP.items():
        value = payload.get(secret_key)
        if value is not None and env_key not in os.environ:
            os.environ[env_key] = str(value)
    logger.info("loaded OHIP secret from Secrets Manager", extra={"secret_id": secret_id})
