"""
Standalone Azure OpenAI connection tester.
Run from the project folder:

    python test_azure.py

Fill in your credentials below, or pass them as command-line args:

    python test_azure.py --endpoint "https://..." --key "abc123" --deployment "gpt-4o" --version "2024-10-21"
"""
import argparse
import sys
import logging

# ─── Credentials — edit these or use --args ──────────────────────────────────
DEFAULT_ENDPOINT   = ""   # e.g. https://demodigitizer.services.ai.azure.com/
DEFAULT_API_KEY    = ""   # Key 1 or Key 2 from Azure Portal
DEFAULT_DEPLOYMENT = ""   # Deployment name from Azure AI Foundry → Deployments
DEFAULT_VERSION    = "2024-10-21"
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/azure_test.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("azure_test")


def parse_args():
    p = argparse.ArgumentParser(description="Test Azure OpenAI connection")
    p.add_argument("--endpoint",   default=DEFAULT_ENDPOINT)
    p.add_argument("--key",        default=DEFAULT_API_KEY)
    p.add_argument("--deployment", default=DEFAULT_DEPLOYMENT)
    p.add_argument("--version",    default=DEFAULT_VERSION)
    return p.parse_args()


def normalise_endpoint(endpoint: str) -> str:
    """Strip any path suffix — keep only scheme + host."""
    from urllib.parse import urlparse
    p = urlparse(endpoint.strip())
    return f"{p.scheme}://{p.netloc}/"


def run_test(endpoint: str, api_key: str, deployment: str, api_version: str):
    log.info("=" * 60)
    log.info("Azure OpenAI Connection Test")
    log.info("=" * 60)

    # ── 1. Show what we received ──────────────────────────────────
    log.info(f"Raw endpoint   : {endpoint!r}")
    normalised = normalise_endpoint(endpoint)
    log.info(f"Normalised     : {normalised!r}")
    log.info(f"Deployment     : {deployment!r}")
    log.info(f"API version    : {api_version!r}")
    log.info(f"API key (first 8): {api_key[:8]}..." if len(api_key) > 8 else "API key: (too short!)")

    # ── 2. DNS check ──────────────────────────────────────────────
    log.info("-" * 40)
    log.info("Step 1: DNS resolution")
    from urllib.parse import urlparse
    import socket
    host = urlparse(normalised).hostname or ""
    try:
        ip = socket.gethostbyname(host)
        log.info(f"  ✓ {host} resolved to {ip}")
    except socket.gaierror as e:
        log.error(f"  ✗ DNS FAILED for {host!r}: {e}")
        log.error("  → Check your endpoint hostname is correct")
        return False

    # ── 3. HTTPS reachability ─────────────────────────────────────
    log.info("-" * 40)
    log.info("Step 2: HTTPS connectivity")
    import httpx
    try:
        r = httpx.get(normalised, timeout=8)
        log.info(f"  ✓ HTTP {r.status_code} from {normalised}")
    except Exception as e:
        log.warning(f"  ⚠ HTTPS GET failed (may be normal for auth-required endpoints): {e}")

    # ── 4. List available deployments via REST ───────────────────
    log.info("-" * 40)
    log.info("Step 3a: Listing deployments via REST API")
    import httpx as _httpx
    for ver in ["2024-10-21", "2024-06-01", "2024-02-01"]:
        try:
            url = f"{normalised}openai/deployments?api-version={ver}"
            r = _httpx.get(url, headers={"api-key": api_key}, timeout=8)
            if r.status_code == 200:
                data = r.json()
                names = [d.get("id") or d.get("model") for d in data.get("data", [])]
                log.info(f"  ✓ Found deployments (api-version={ver}): {names}")
                if names:
                    log.info(f"  → Use one of these as your Deployment Name: {names}")
                    break
            else:
                log.warning(f"  ✗ {r.status_code}: {r.text[:200]}")
        except Exception as e:
            log.warning(f"  Could not list deployments: {e}")

    # ── 5. Try every supported API version ───────────────────────
    versions_to_try = [
        api_version,
        "2024-10-21",
        "2024-06-01",
        "2024-05-01-preview",
        "2024-02-01",
        "2025-01-01-preview",
    ]
    # deduplicate while preserving order
    seen = set()
    versions_to_try = [v for v in versions_to_try if not (v in seen or seen.add(v))]

    log.info("-" * 40)
    log.info(f"Step 3: Trying {len(versions_to_try)} API versions with deployment {deployment!r}")

    from openai import AzureOpenAI

    success_version = None
    for ver in versions_to_try:
        log.info(f"  Trying api_version={ver!r} ...")
        try:
            client = AzureOpenAI(
                api_key=api_key,
                azure_endpoint=normalised,
                api_version=ver,
            )
            response = client.chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": "Say the word OK and nothing else."}],
                max_tokens=5,
                temperature=0,
            )
            answer = response.choices[0].message.content.strip()
            tokens = response.usage.total_tokens if response.usage else "?"
            log.info(f"  ✓ SUCCESS with api_version={ver!r}")
            log.info(f"    Model replied: {answer!r}  (tokens used: {tokens})")
            success_version = ver
            break
        except Exception as e:
            err = str(e)
            # Shorten very long error messages
            short = err[:300] + "..." if len(err) > 300 else err
            log.warning(f"  ✗ FAILED with {ver!r}: {short}")

    # ── 5. Summary ────────────────────────────────────────────────
    log.info("=" * 60)
    if success_version:
        log.info("✓ CONNECTION SUCCESSFUL")
        log.info(f"  Use these settings in PLM Digitizer:")
        log.info(f"    Endpoint   : {normalised}")
        log.info(f"    Deployment : {deployment}")
        log.info(f"    API version: {success_version}")
        log.info("=" * 60)
        return True
    else:
        log.error("✗ ALL VERSIONS FAILED")
        log.error("  Things to check:")
        log.error("  1. Deployment name — go to Azure AI Foundry → Deployments tab")
        log.error("     and copy the exact name from the 'Name' column")
        log.error("  2. API key — use Key 1 or Key 2 from Azure Portal →")
        log.error("     Your resource → Keys and Endpoint")
        log.error("  3. Endpoint — use the base URL, e.g.")
        log.error("     https://YOUR-RESOURCE.openai.azure.com/")
        log.error("     or https://YOUR-RESOURCE.services.ai.azure.com/")
        log.error(f"  Full log saved to: data/azure_test.log")
        log.info("=" * 60)
        return False


if __name__ == "__main__":
    args = parse_args()

    # Prompt for any missing values
    endpoint   = args.endpoint   or input("Endpoint URL  : ").strip()
    api_key    = args.key        or input("API Key       : ").strip()
    deployment = args.deployment or input("Deployment name: ").strip()
    version    = args.version

    if not endpoint or not api_key or not deployment:
        print("ERROR: endpoint, key and deployment are all required.")
        sys.exit(1)

    ok = run_test(endpoint, api_key, deployment, version)
    sys.exit(0 if ok else 1)
