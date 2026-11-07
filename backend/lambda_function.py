import base64
import json
import logging

import boto3
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1",
    config=Config(
        connect_timeout=3,
        read_timeout=20,
        retries={"total_max_attempts": 1}
    )
)

SYSTEM_PROMPT = """
You are CloudTech, a helpful IT help desk assistant.
Provide concise, practical troubleshooting guidance in plain text.
Give up to five numbered steps, starting with simple checks.
Ask one clarifying question when useful.
Never request passwords or secrets.
Do not recommend disabling security controls or destructive actions.
Do not claim you inspected or fixed the user's computer.
Stay focused on IT support.
"""


def respond(status, data):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data)
    }


def lambda_handler(event, context):
    try:
        raw_body = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        body = json.loads(raw_body)
    except (ValueError, TypeError, UnicodeError):
        return respond(400, {"error": "Send a valid JSON body."})

    message = body.get("message") if isinstance(body, dict) else None

    if not isinstance(message, str) or not message.strip():
        return respond(400, {"error": "Enter a message."})

    if len(message) > 4000:
        return respond(400, {"error": "Keep your message under 4,000 characters."})

    try:
        result = bedrock.converse(
            modelId="amazon.nova-micro-v1:0",
            system=[{"text": SYSTEM_PROMPT}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": message.strip()}]
                }
            ],
            inferenceConfig={
                "maxTokens": 400,
                "temperature": 0.3
            }
        )

        answer = "\n".join(
            block["text"]
            for block in result["output"]["message"]["content"]
            if "text" in block
        )

        if not answer.strip():
            raise ValueError("Bedrock returned no text.")

        return respond(200, {"answer": answer})

    except Exception:
        logger.exception("Bedrock request failed")
        return respond(
            502,
            {"error": "AI support is temporarily unavailable. Please try again."}
        )
