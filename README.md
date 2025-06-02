# Example Samsara Functions

A collection of examples showing how to use Samsara Functions.

## Before you begin

You'll need some credentials configured to run the examples. Some of the
examples require a Samsara API key and others have credentials for using various
APIs and services.


At a minimum, you'll need to set the `SAMSARA_API_KEY` environment variable to
your Samsara API key.

```bash
cp .env.example .env
```

Update `.env` with your credentials.

## Installing dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```


## Logging - Log

The "hello, world" of Samsara Functions.

See [log.py](./log.py) for a simple logging function to test output.

## Use event parameters - Assign an issue to a manager

This example demonstrates how to handle parameters set on the function
configuration. Automatically assign all new issues to a maintenance manager.

See [auto_assign_issue.py](./auto_assign_issue.py).

## Shedule function executions - Generate a daily report and email to executives

