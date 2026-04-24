# OpenFaaS Python SDK — End-to-End Example

This repository contains a complete end-to-end example for the [OpenFaaS Python SDK](https://github.com/openfaas/python-sdk). It walks through the full workflow of going from source code to a running, authenticated function in a custom namespace — entirely from Python.

For a detailed explanation of each step, see the accompanying blog post: [Automate OpenFaaS from Python with the new SDK](https://www.openfaas.com/blog/python-sdk/).

## What this example demonstrates

- Creating a custom **namespace** (`tenant1`) via the SDK
- Creating a **secret** (an API key) in that namespace via the SDK
- **Building** a function container image from source using the [Function Builder API](https://docs.openfaas.com/openfaas-pro/builder/)
- **Deploying** the function into the custom namespace with the secret mounted
- **Invoking** the function — showing both an unauthenticated (`401`) and authenticated (`200`) request
- **Streaming logs** from the running function
- **Cleaning up** all created resources

### The `greeter` function

The `greeter` function reads an API key from an OpenFaaS secret mounted at `/var/openfaas/secrets/api-key`. On each request it checks the `Authorization: Bearer <token>` header:

- Token matches the secret → `200 {"message": "Hello from OpenFaaS!"}`
- Token missing or wrong → `401 {"error": "Unauthorized"}`

This is a realistic pattern for lightweight API key authentication in a serverless function.

## Prerequisites

- Python 3.10+
- [`faas-cli`](https://github.com/openfaas/faas-cli) installed
- Access to an OpenFaaS gateway with the Function Builder enabled
- A container registry the builder can push to (this example uses [ttl.sh](https://ttl.sh) — no credentials required, images expire after 1 hour)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/welteki/openfaas-python-sdk-example
cd openfaas-python-sdk-example
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

The SDK is installed directly from the GitHub repository until it is published to PyPI.

### 3. Pull the function template

The `template/` directory is not committed to this repository. Pull the `python3-http` template with `faas-cli` before running the example:

```bash
faas-cli template store pull python3-http
```

### 4. Set environment variables

| Variable | Default | Description |
|---|---|---|
| `OPENFAAS_PASSWORD` | — | **Required.** OpenFaaS gateway admin password |
| `OPENFAAS_GATEWAY` | `http://127.0.0.1:8080` | Gateway URL |
| `BUILDER_URL` | `http://127.0.0.1:8081` | Function Builder URL |
| `PAYLOAD_SECRET_PATH` | `/var/secrets/payload-secret` | Path to the builder HMAC payload secret |

```bash
export OPENFAAS_PASSWORD=your-password
```

The builder HMAC secret is read from a file. You can retrieve it from your cluster with:

```bash
kubectl get secret -n openfaas payload-secret \
    -o jsonpath='{.data.payload-secret}' | base64 --decode \
    | sudo tee /var/secrets/payload-secret
```

### 5. Run the example

```bash
python e2e.py
```

The script prints progress at each step and exits with a non-zero status code if anything goes wrong.

## Project structure

```
openfaas-python-sdk-example/
├── README.md
├── requirements.txt       # SDK dependency (installed from GitHub)
├── stack.yml              # faas-cli stack file for the greeter function
├── e2e.py                 # End-to-end orchestration script
└── greeter/
    └── handler.py         # Function handler — bearer token auth against secret
```

## License

MIT
