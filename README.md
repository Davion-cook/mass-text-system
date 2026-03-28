# Mass Text System

A lightweight, scalable SMS automation platform built with Python — no paid APIs required. Designed to help small organizations reach their audience and maintain consistent communication without expensive tools like Twilio or enterprise messaging platforms.

---

## The Problem

Small organizations, churches, community groups, coaching staffs, and local nonprofits  need a reliable way to send text messages to their members. Most solutions charge per message or require monthly subscriptions. For small communities, that cost adds up fast for something that should be simple.

## The Solution

This system sends real SMS text messages through free email-to-SMS carrier gateways (every major US carrier supports this). You write your message, pick your group, and the system handles the rest — personalized messages, parallel delivery, and automatic retries — all from the command line.

---

## Concepts and Technologies Applied

This project was built using principles from *Network Programmability and Automation* (O'Reilly, 2nd Edition) and applies several industry-standard software engineering patterns used across production systems at scale.

### Source of Truth Architecture

All contacts and system configuration live in structured YAML files that serve as the single source of truth. This pattern is widely used in infrastructure-as-code platforms (Kubernetes, Terraform, Ansible) where system state is declared in version-controlled files rather than scattered across databases or UI settings. Changes are trackable, reviewable, and reproducible — the same principles behind GitOps workflows at companies managing thousands of services.

### Template-Driven Message Rendering (Jinja2)

Messages are rendered through Jinja2, the same templating engine that powers Flask, Ansible playbooks, and dbt data transformations. Each contact receives a personalized message generated from a shared template, separating content logic from delivery logic. This is the same separation-of-concerns principle used in frontend frameworks (React components, Django templates) and email marketing platforms, but applied here at the infrastructure layer.

### Concurrent Execution with ThreadPoolExecutor

Messages are sent in parallel using Python's `concurrent.futures.ThreadPoolExecutor`. Rather than sending messages one at a time (which would take minutes for a large list), the system distributes work across a configurable pool of worker threads. This is the same concurrency model used in web servers handling simultaneous requests, API clients making batch calls, and data pipelines processing records in parallel. The implementation includes rate limiting to avoid overwhelming carrier gateways.

### Exponential Backoff and Retry Logic

Transient failures (network timeouts, temporary server errors) are handled with automatic retries using exponential backoff — the same strategy used by AWS SDKs, Google Cloud client libraries, and HTTP clients in distributed systems. Each retry waits progressively longer (2s, 4s, 8s) to avoid flooding a recovering service, a pattern critical in any system that communicates over a network.

### Provider Abstraction Pattern

The SMS delivery layer uses a provider abstraction (base class with interchangeable implementations). Swapping from the email gateway to a future provider means writing one new class — the rest of the system doesn't change. This is the Strategy pattern in practice, the same approach used in payment processing systems (Stripe/PayPal/Square behind one interface), cloud storage libraries, and notification services.

### Configuration via Environment Variables

Sensitive credentials (email, password) are injected through environment variables and resolved at runtime, never hardcoded in source files. This follows the Twelve-Factor App methodology used in modern cloud-native deployments, ensuring secrets stay out of version control and can be rotated without code changes.

### Containerized Deployment (Docker)

The system includes a Dockerfile for consistent, reproducible deployment. The same code runs identically on any machine with Docker installed — no dependency conflicts, no "works on my machine" issues. This is the standard packaging approach for microservices, CI/CD pipelines, and cloud deployments.

### Build Automation (Makefile)

Common tasks (install, test, run, build) are centralized in a Makefile, providing a consistent developer interface regardless of the underlying toolchain. This is the same approach used in large-scale open source projects and monorepos to standardize workflows across teams.

---

## How to Use It

### What You Need

- A computer with **Python 3.8+** installed
- A **Gmail account**
- Your contacts' **phone numbers** and **carriers** (AT&T, T-Mobile, Verizon, etc.)

### Step 1: Download the Project

Open your terminal (Command Prompt on Windows, Terminal on Mac/Linux) and run:

```bash
git clone https://github.com/Davion-cook/mass-text-system.git
cd mass-text-system
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs two small libraries: one for reading YAML files and one for message templates.

### Step 3: Set Up Your Gmail App Password

You cannot use your regular Gmail password. You need an **App Password**:

1. Go to https://myaccount.google.com/apppasswords
2. Sign in to your Google account
3. If prompted, enable **2-Step Verification** first at https://myaccount.google.com/signinoptions/twosv
4. Go back to App Passwords and generate one for "Mail"
5. Google will show you a **16-character code** (like `abcd efgh ijkl mnop`) — save this

### Step 4: Set Your Credentials

**On Mac/Linux:**
```bash
export EMAIL_ADDRESS="youremail@gmail.com"
export EMAIL_PASSWORD="abcdefghijklmnop"
```

**On Windows (Command Prompt):**
```cmd
set EMAIL_ADDRESS=youremail@gmail.com
set EMAIL_PASSWORD=abcdefghijklmnop
```

### Step 5: Add Your Contacts

Open `contacts.yaml` in any text editor and add your people:

```yaml
groups:
  volunteers:
    - name: "Maria Garcia"
      phone: "+15551234567"
      carrier: "att"
      role: "coordinator"

    - name: "James Williams"
      phone: "+15559876543"
      carrier: "tmobile"
      role: "volunteer"

  leadership:
    - name: "Sarah Chen"
      phone: "+15555551234"
      carrier: "verizon"
      role: "director"
```

**Supported carriers:** `att`, `tmobile`, `verizon`, `sprint`, `cricket`, `metro`, `boost`, `uscellular`, `mint`, `visible`, `xfinity`, `fi`

**Phone number format:** Always start with `+1` followed by the 10-digit number. Example: `+15551234567`

### Step 6: Test It (Dry Run)

This simulates sending without actually texting anyone:

```bash
python3 mass_text.py --dry-run -b "Meeting tomorrow at 6pm" -g volunteers
```

You should see a report showing all messages would have been sent successfully.

### Step 7: Send for Real

```bash
python3 mass_text.py -b "Meeting tomorrow at 6pm" -g volunteers
```

That's it. Everyone in the "volunteers" group gets a personalized text.

### More Examples

```bash
# Text everyone in all groups
python3 mass_text.py -b "Happy New Year!"

# Text multiple groups at once
python3 mass_text.py -b "Practice cancelled" -g volunteers leadership

# Use the alert template for urgent messages
python3 mass_text.py -t alert.j2 -b "Building evacuation — exit now" --priority high

# Custom sender name
python3 mass_text.py -b "Bake sale this Saturday" -s "Community Center"
```

### How to Find Someone's Carrier

If you don't know a contact's carrier, you can ask them directly, or:
- Check https://freecarrierlookup.com — enter their phone number and it tells you the carrier

---

## Project Structure

```
mass-text-system/
  mass_text.py        # Main application
  config.yaml         # System settings (rate limits, SMTP config)
  contacts.yaml       # Your contacts organized by group
  requirements.txt    # Python dependencies
  Makefile            # Shortcut commands (make dry-run, make install)
  Dockerfile          # Container deployment
  templates/
    default.j2        # Standard message template
    alert.j2          # Urgent/priority message template
  logs/
    mass_text.log     # Delivery log
```

---

## What's Next

Building a **web-based UI** so anyone in your organization can send messages from a browser — no terminal required. The goal is a simple dashboard where you can pick a group, type a message, and hit send.

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3 | Core language |
| smtplib | Email-to-SMS delivery (built into Python) |
| Jinja2 | Message personalization |
| PyYAML | Configuration and contact management |
| ThreadPoolExecutor | Parallel message delivery |
| Docker | Containerized deployment |
| Make | Build automation |
