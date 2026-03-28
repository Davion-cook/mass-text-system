#!/usr/bin/env python3
"""
Mass Text System - Built using techniques from
'Network Programmability and Automation, 2nd Edition'

Key techniques applied:
- YAML for config & data (Ch.8 Data Formats)
- Jinja2 for message templating (Ch.9 Templates)
- ThreadPoolExecutor for parallelization (Ch.6 Python)
- HTTP APIs via Requests library (Ch.10 Network APIs)
- Source of truth pattern (Ch.14 Automation Architecture)
"""

import os
import re
import sys
import time
import logging
import argparse
import concurrent.futures
from pathlib import Path

import yaml
import requests
from jinja2 import Environment, FileSystemLoader


# ---------------------------------------------------------------------------
# Configuration loader — YAML as source of truth (Ch.8, Ch.14)
# ---------------------------------------------------------------------------

def load_yaml(file_path):
    """Load and parse a YAML file (Ch.8 - Data Formats)."""
    with open(file_path, "r") as fh:
        return yaml.safe_load(fh)


def resolve_env_vars(config):
    """Replace ${ENV_VAR} placeholders with environment variable values."""
    if isinstance(config, dict):
        return {k: resolve_env_vars(v) for k, v in config.items()}
    if isinstance(config, list):
        return [resolve_env_vars(i) for i in config]
    if isinstance(config, str) and config.startswith("${") and config.endswith("}"):
        var_name = config[2:-1]
        return os.environ.get(var_name, "")
    return config


def load_config(config_path="config.yaml"):
    """Load system configuration from YAML source of truth."""
    raw = load_yaml(config_path)
    return resolve_env_vars(raw)


# ---------------------------------------------------------------------------
# Contacts loader — source of truth (Ch.14)
# ---------------------------------------------------------------------------

def load_contacts(contacts_path, groups=None):
    """Load contacts from YAML, optionally filtering by group names."""
    data = load_yaml(contacts_path)
    all_groups = data.get("groups", {})

    if groups:
        selected = []
        for group_name in groups:
            if group_name in all_groups:
                selected.extend(all_groups[group_name])
            else:
                logging.warning("Group '%s' not found in contacts file", group_name)
        return selected

    # If no groups specified, return all contacts
    contacts = []
    for members in all_groups.values():
        contacts.extend(members)
    return contacts


# ---------------------------------------------------------------------------
# Template engine — Jinja2 (Ch.9)
# ---------------------------------------------------------------------------

def render_message(template_dir, template_name, context):
    """Render a message using Jinja2 templates (Ch.9 - Templates).

    Uses FileSystemLoader and Environment just like the book demonstrates
    for rendering configuration templates from files.
    """
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_name)
    return template.render(context).strip()


# ---------------------------------------------------------------------------
# SMS provider abstraction — API layer (Ch.10)
# ---------------------------------------------------------------------------

class SMSProvider:
    """Base class for SMS providers."""

    def send(self, to_number, message):
        raise NotImplementedError


class TwilioProvider(SMSProvider):
    """Send SMS via Twilio REST API using the Requests library (Ch.10)."""

    def __init__(self, account_sid, auth_token, from_number, api_url):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.api_url = api_url

    def send(self, to_number, message):
        url = f"{self.api_url}/Accounts/{self.account_sid}/Messages.json"
        payload = {
            "To": to_number,
            "From": self.from_number,
            "Body": message,
        }
        resp = requests.post(
            url,
            data=payload,
            auth=(self.account_sid, self.auth_token),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


class VonageProvider(SMSProvider):
    """Send SMS via Vonage (Nexmo) REST API (Ch.10)."""

    def __init__(self, api_key, api_secret, from_number, **_kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        self.from_number = from_number

    def send(self, to_number, message):
        url = "https://rest.nexmo.com/sms/json"
        payload = {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "to": to_number,
            "from": self.from_number,
            "text": message,
        }
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()


class MockProvider(SMSProvider):
    """Mock provider for testing — no real SMS sent."""

    def send(self, to_number, message):
        logging.info("[MOCK] -> %s: %s", to_number, message[:80])
        return {"status": "mock_sent", "to": to_number}


def create_provider(config):
    """Factory to create the right SMS provider from config."""
    provider_cfg = config["provider"]
    name = provider_cfg["name"]

    if name == "twilio":
        return TwilioProvider(
            account_sid=provider_cfg["account_sid"],
            auth_token=provider_cfg["auth_token"],
            from_number=provider_cfg["from_number"],
            api_url=provider_cfg["api_url"],
        )
    elif name == "vonage":
        return VonageProvider(
            api_key=provider_cfg["account_sid"],
            api_secret=provider_cfg["auth_token"],
            from_number=provider_cfg["from_number"],
        )
    elif name == "mock":
        return MockProvider()
    else:
        raise ValueError(f"Unknown provider: {name}")


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_phone(number):
    """Validate E.164 phone number format."""
    return bool(E164_PATTERN.match(number))


# ---------------------------------------------------------------------------
# Core send engine — parallelized with ThreadPoolExecutor (Ch.6)
# ---------------------------------------------------------------------------

def send_single(provider, contact, message, retry_attempts, retry_delay):
    """Send a single SMS with retry logic and exponential backoff."""
    phone = contact["phone"]
    name = contact.get("name", "Unknown")

    if not validate_phone(phone):
        return {"contact": name, "phone": phone, "status": "invalid_number"}

    for attempt in range(1, retry_attempts + 1):
        try:
            result = provider.send(phone, message)
            return {"contact": name, "phone": phone, "status": "sent", "result": result}
        except requests.exceptions.RequestException as exc:
            logging.warning(
                "Attempt %d/%d failed for %s: %s", attempt, retry_attempts, name, exc
            )
            if attempt < retry_attempts:
                time.sleep(retry_delay * (2 ** (attempt - 1)))  # exponential backoff

    return {"contact": name, "phone": phone, "status": "failed"}


def send_mass_text(config, contacts, template_name, template_vars):
    """Send texts to all contacts using parallel workers (Ch.6).

    Uses concurrent.futures.ThreadPoolExecutor exactly as demonstrated
    in the book's parallelization section (Example 6-11).
    """
    messaging_cfg = config["messaging"]
    max_workers = messaging_cfg["max_concurrent"]
    rate_limit = messaging_cfg["rate_limit_per_second"]
    retry_attempts = messaging_cfg["retry_attempts"]
    retry_delay = messaging_cfg["retry_delay_seconds"]
    template_dir = config["templates"]["directory"]

    provider = create_provider(config)

    results = []
    delay_between = 1.0 / rate_limit if rate_limit > 0 else 0

    # Parallelize sending with ThreadPoolExecutor (Ch.6, Example 6-11)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}

        for i, contact in enumerate(contacts):
            # Render personalized message via Jinja2 (Ch.9)
            context = {**template_vars, **contact}
            message = render_message(template_dir, template_name, context)

            future = executor.submit(
                send_single, provider, contact, message, retry_attempts, retry_delay
            )
            futures[future] = contact

            # Rate limiting between submissions
            if delay_between and i < len(contacts) - 1:
                time.sleep(delay_between)

        # Collect results as they complete (Ch.6)
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                logging.info(
                    "Result: %s -> %s", result["contact"], result["status"]
                )
            except Exception as exc:
                contact = futures[future]
                logging.error("Unexpected error for %s: %s", contact.get("name"), exc)
                results.append({
                    "contact": contact.get("name"),
                    "phone": contact.get("phone"),
                    "status": "error",
                })

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(results):
    """Print a summary of the send operation."""
    sent = sum(1 for r in results if r["status"] == "sent")
    failed = sum(1 for r in results if r["status"] == "failed")
    invalid = sum(1 for r in results if r["status"] == "invalid_number")
    errors = sum(1 for r in results if r["status"] == "error")
    total = len(results)

    print(f"\n{'='*50}")
    print(f" Mass Text Report")
    print(f"{'='*50}")
    print(f" Total:   {total}")
    print(f" Sent:    {sent}")
    print(f" Failed:  {failed}")
    print(f" Invalid: {invalid}")
    print(f" Errors:  {errors}")
    print(f"{'='*50}\n")


# ---------------------------------------------------------------------------
# CLI entry point — argument parsing (Ch.6)
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Mass Text System - Send SMS at scale"
    )
    parser.add_argument(
        "-c", "--config", default="config.yaml",
        help="Path to YAML config file (default: config.yaml)",
    )
    parser.add_argument(
        "-g", "--groups", nargs="+",
        help="Contact groups to send to (default: all)",
    )
    parser.add_argument(
        "-t", "--template", default=None,
        help="Jinja2 template name (default: from config)",
    )
    parser.add_argument(
        "-b", "--body", default="",
        help="Message body to pass into the template",
    )
    parser.add_argument(
        "-s", "--sender", default="Mass Text System",
        help="Sender name for template rendering",
    )
    parser.add_argument(
        "--priority", default="normal", choices=["normal", "high"],
        help="Message priority level",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Use mock provider regardless of config",
    )
    return parser.parse_args()


def setup_logging(config):
    log_cfg = config.get("logging", {})
    log_file = log_cfg.get("file", "logs/mass_text.log")
    log_level = getattr(logging, log_cfg.get("level", "INFO"))

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file),
        ],
    )


def main():
    args = parse_args()

    # Load YAML configuration — source of truth (Ch.14)
    config = load_config(args.config)
    setup_logging(config)

    # Override provider for dry-run
    if args.dry_run:
        config["provider"]["name"] = "mock"

    # Load contacts from YAML source of truth
    contacts_file = config["contacts"]["file"]
    contacts = load_contacts(contacts_file, args.groups)

    if not contacts:
        logging.error("No contacts found. Check groups or contacts file.")
        sys.exit(1)

    logging.info("Loaded %d contacts", len(contacts))

    # Determine template
    template_name = args.template or config["templates"]["default"]

    # Template variables
    template_vars = {
        "sender": args.sender,
        "body": args.body,
        "priority": args.priority,
    }

    # Send messages in parallel (Ch.6)
    results = send_mass_text(config, contacts, template_name, template_vars)

    # Report
    print_report(results)


if __name__ == "__main__":
    main()
