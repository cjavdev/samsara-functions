import os
import samsara
import datetime
from typing import List, Dict, Any


def get_recent_issues(client: samsara.SamsaraClient, days: int = 7) -> List[Dict[str, Any]]:
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    issues = client.list_issues({
        "status": "open",
        "startTime": start_date,
    })
    return issues


def assign_issue(client: samsara.SamsaraClient, issue_id: str, maintenance_manager_id: str):
    return client.update_issue(issue_id, {
        "assignedTo": {
            "id": maintenance_manager_id,
            "type": "user"
        },
        "status": "inProgress"
    })


def main(event, _):
    function = samsara.Function()
    secrets = function.secrets().load()
    api_key = secrets.get("SAMSARA_KEY")
    if not api_key:
        import dotenv

        dotenv.load_dotenv()
        api_key = os.getenv("SAMSARA_KEY")

    client = samsara.SamsaraClient(api_key)

    maintenance_manager_id = event.get("maintenance_manager_id")

    # Get all open issues
    issues = get_recent_issues(client)

    # For each issue auto assign it to the maintenance manager
    for issue in issues:
        print(f"Assigning issue {issue.get('id')} to {maintenance_manager_id}")
        assign_issue(client, issue.get("id"), maintenance_manager_id)


if __name__ == "__main__":
    main({"maintenance_manager_id": "1238599"}, None)
