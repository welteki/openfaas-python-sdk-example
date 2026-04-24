#!/usr/bin/env python3
"""End-to-end example: source to URL in a custom namespace.

This script demonstrates the full OpenFaaS Python SDK workflow:

  1. Create a custom namespace (tenant1)
  2. Create an API key secret in that namespace
  3. Build the greeter function from source via the Function Builder API
  4. Deploy the function into the namespace with the secret mounted
  5. Wait for the function to become ready
  6. Invoke the function with a Bearer token
  7. Stream the last 20 log lines
  8. Clean up: delete function, secret, and namespace

Prerequisites:
  - faas-cli templates pulled: faas-cli template store pull python3-http
  - Environment variables set (see README)
  - Payload secret file at /var/secrets/payload-secret

Usage:
    python e2e.py
"""

import os
import sys
import time
import uuid

from openfaas import BasicAuth, Client
from openfaas.builder import BuildConfig, FunctionBuilder, create_build_context, make_tar
from openfaas.exceptions import APIConnectionError, ForbiddenError, NotFoundError, UnauthorizedError
from openfaas.models import FunctionDeployment, FunctionNamespace, Secret

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GATEWAY_URL = os.environ.get("OPENFAAS_GATEWAY", "http://127.0.0.1:8080")
BUILDER_URL = os.environ.get("BUILDER_URL", "http://127.0.0.1:8081")
PAYLOAD_SECRET_PATH = os.environ.get("PAYLOAD_SECRET_PATH", "/var/secrets/payload-secret")

NAMESPACE = "tenant1"
FUNCTION_NAME = "greeter"
SECRET_NAME = "api-key"
IMAGE = "ttl.sh/greeter:1h"
PLATFORM = "linux/amd64"

BUILD_DIR = "./build"
TEMPLATE_DIR = "./template"
HANDLER_DIR = "./greeter"
TAR_PATH = "/tmp/greeter-build.tar"


def read_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Error: environment variable {name!r} is not set.", file=sys.stderr)
        sys.exit(1)
    return value


def read_file(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError as e:
        print(f"Error: could not read {path!r}: {e}", file=sys.stderr)
        sys.exit(1)


def wait_for_ready(client: Client, name: str, namespace: str, timeout: int = 120) -> None:
    """Poll get_function() until at least one replica is available."""
    print(f"  Waiting for {name!r} to become ready ", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            fn = client.get_function(name, namespace)
            if fn.available_replicas and fn.available_replicas >= 1:
                print(" ready.")
                return
        except NotFoundError:
            pass
        print(".", end="", flush=True)
        time.sleep(3)
    print()
    print(f"Error: timed out waiting for {name!r} to become ready.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    password = read_env("OPENFAAS_PASSWORD")
    hmac_secret = read_file(PAYLOAD_SECRET_PATH)

    if not os.path.isdir(TEMPLATE_DIR):
        print(
            f"Error: template directory {TEMPLATE_DIR!r} not found.\n"
            "Run: faas-cli template store pull python3-http",
            file=sys.stderr,
        )
        sys.exit(1)

    print("==> Connecting to OpenFaaS gateway")
    print(f"    Gateway : {GATEWAY_URL}")
    print(f"    Builder : {BUILDER_URL}")

    try:
        with Client(gateway_url=GATEWAY_URL, auth=BasicAuth("admin", password)) as client:

            # ------------------------------------------------------------------
            # 1. Create namespace
            # ------------------------------------------------------------------
            print(f"\n==> Creating namespace {NAMESPACE!r}")
            client.create_namespace(
                FunctionNamespace(
                    name=NAMESPACE,
                    labels={"managed-by": "openfaas-python-sdk-example"},
                )
            )
            print(f"    Namespace {NAMESPACE!r} created.")

            # ------------------------------------------------------------------
            # 2. Create secret
            # ------------------------------------------------------------------
            api_key = str(uuid.uuid4())
            print(f"\n==> Creating secret {SECRET_NAME!r} in namespace {NAMESPACE!r}")
            client.create_secret(Secret(name=SECRET_NAME, namespace=NAMESPACE, value=api_key))
            print(f"    Secret {SECRET_NAME!r} created.")

            # ------------------------------------------------------------------
            # 3. Build from source
            # ------------------------------------------------------------------
            print(f"\n==> Assembling build context for {FUNCTION_NAME!r}")
            context_path = create_build_context(
                function_name=FUNCTION_NAME,
                handler=HANDLER_DIR,
                language="python3-http",
                template_dir=TEMPLATE_DIR,
                build_dir=BUILD_DIR,
            )
            print(f"    Context path : {context_path}")

            config = BuildConfig(image=IMAGE, platforms=[PLATFORM])
            make_tar(TAR_PATH, context_path, config)
            print(f"    Tar archive  : {TAR_PATH}")

            print(f"\n==> Building image {IMAGE!r} via Function Builder")
            builder = FunctionBuilder(BUILDER_URL, hmac_secret=hmac_secret)
            final_result = None
            for result in builder.build_stream(TAR_PATH):
                for line in result.log:
                    print(f"    {line}")
                if result.status in ("success", "failed"):
                    final_result = result

            if final_result is None or final_result.status != "success":
                status = final_result.status if final_result else "unknown"
                print(f"Error: build {status}.", file=sys.stderr)
                sys.exit(1)
            print(f"    Build succeeded. Image: {final_result.image}")

            # ------------------------------------------------------------------
            # 4. Deploy function
            # ------------------------------------------------------------------
            print(f"\n==> Deploying {FUNCTION_NAME!r} into namespace {NAMESPACE!r}")
            spec = FunctionDeployment(
                service=FUNCTION_NAME,
                image=IMAGE,
                namespace=NAMESPACE,
                secrets=[SECRET_NAME],
            )
            client.deploy(spec)
            print(f"    Deployed {FUNCTION_NAME!r}.")

            # ------------------------------------------------------------------
            # 5. Wait for ready
            # ------------------------------------------------------------------
            print()
            wait_for_ready(client, FUNCTION_NAME, NAMESPACE)

            # ------------------------------------------------------------------
            # 6. Invoke with Bearer token
            # ------------------------------------------------------------------
            print(f"\n==> Invoking {FUNCTION_NAME!r} with Bearer token")
            resp = client.invoke_function(
                FUNCTION_NAME,
                namespace=NAMESPACE,
                method="GET",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            print(f"    Status : {resp.status_code}")
            print(f"    Body   : {resp.text}")

            # ------------------------------------------------------------------
            # 7. Stream logs
            # ------------------------------------------------------------------
            print(f"\n==> Streaming last 20 log lines for {FUNCTION_NAME!r}")
            for msg in client.get_logs(FUNCTION_NAME, NAMESPACE, tail=20):
                print(f"    [{msg.timestamp}] {msg.instance}: {msg.text}")

            # ------------------------------------------------------------------
            # 8. Clean up
            # ------------------------------------------------------------------
            print("\n==> Cleaning up")
            try:
                client.delete_function(FUNCTION_NAME, NAMESPACE)
                print(f"    Deleted function {FUNCTION_NAME!r}.")
            except NotFoundError:
                pass

            try:
                client.delete_secret(SECRET_NAME, NAMESPACE)
                print(f"    Deleted secret {SECRET_NAME!r}.")
            except NotFoundError:
                pass

            try:
                client.delete_namespace(NAMESPACE)
                print(f"    Deleted namespace {NAMESPACE!r}.")
            except NotFoundError:
                pass

    except UnauthorizedError:
        print("Error: unauthorized. Check your OPENFAAS_PASSWORD.", file=sys.stderr)
        sys.exit(1)
    except ForbiddenError:
        print("Error: insufficient permissions.", file=sys.stderr)
        sys.exit(1)
    except APIConnectionError as e:
        print(f"Error: could not reach the gateway: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
