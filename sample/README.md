# `parisbibpy` Live Sample Scripts

These sample scripts run directly against the live Paris Public Libraries portal ([bibliotheques.paris.fr](https://bibliotheques.paris.fr)).

## Authentication Setup

The sample scripts automatically read credentials from:
1. Environment variables: `PARISBIB_USERNAME` and `PARISBIB_PASSWORD`
2. A `.env` file in the project root
3. Interactive terminal prompt if neither is set

### Option A: Set Environment Variables (Recommended)
```bash
# Windows PowerShell
$env:PARISBIB_USERNAME="22272392XXXXXX"
$env:PARISBIB_PASSWORD="YOUR_PIN"
```

### Option B: Use a `.env` file
Create a `.env` file in the repository root:
```ini
PARISBIB_USERNAME=22272392XXXXXX
PARISBIB_PASSWORD=YOUR_PIN
```

### Option C: Interactive Prompt
Simply run any script without configuration, and you will be prompted securely for your card number and PIN.

---

## Running the Samples

```bash
# 1. Single-glance family metrics & urgent loans
uv run python sample/01_family_overview.py

# 2. Multi-dimensional grouping (per family member, per document type, per library)
uv run python sample/02_grouping_and_dimensions.py

# 3. Trip prioritizer & packing list for library branch visits
uv run python sample/03_plan_library_trips.py

# 4. Reservations & shelf pickup alerts
uv run python sample/04_reservations_and_alerts.py

# 5. Batch renewals across all family accounts
uv run python sample/05_batch_renewals.py
```
