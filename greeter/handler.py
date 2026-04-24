import json
import os


def handle(event, context):
    """Greeter function.

    Reads an API key from the OpenFaaS secret mounted at
    /var/openfaas/secrets/api-key and validates the Authorization
    Bearer token supplied by the caller.

    Returns:
        200  {"message": "Hello from OpenFaaS!"}  — token matches the secret
        401  {"error": "Unauthorized"}             — token missing or wrong
    """
    secret_path = "/var/openfaas/secrets/api-key"
    try:
        with open(secret_path) as f:
            api_key = f.read().strip()
    except OSError:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Secret not available"}),
            "headers": {"Content-Type": "application/json"},
        }

    auth_header = event.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Unauthorized"}),
            "headers": {"Content-Type": "application/json"},
        }

    token = auth_header[len("Bearer "):]
    if token != api_key:
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Unauthorized"}),
            "headers": {"Content-Type": "application/json"},
        }

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Hello from OpenFaaS!"}),
        "headers": {"Content-Type": "application/json"},
    }
