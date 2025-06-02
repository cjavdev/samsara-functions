import csv
import requests
import datetime
import os
import pytz

from samsara import Samsara
# from tabulate import tabulate
from collections import defaultdict


def get_vehicle_stats_history(start_at_str, end_at_str, types):
    # url = f"https://api.samsara.com/fleet/vehicles/stats/history"
    # headers = {
    #     "Authorization": f"Bearer {os.environ['SAMSARA_KEY']}",
    #     "Accept": "application/json"
    # }
    # params = {
    #     "startTime": start_at_str,
    #     "endTime": end_at_str,
    #     "types": types
    # }

    # all_data = []
    # while True:
    #     response = requests.get(url, headers=headers, params=params)
    #     response.raise_for_status()
    #     data = response.json()
    #     all_data.extend(data.get('data', []))
    #     if 'pagination' in data and data['pagination'].get('hasNextPage'):
    #         params['after'] = data['pagination']['endCursor']
    #     else:
    #         break
    # return all_data
    # client = Samsara(token=os.environ['SAMSARA_KEY'])
    client = Samsara(token=os.getenv('SAMSARA_KEY'))

    for address in client.addresses.list():
        print(address.id, address.formatted_address)

    # result = client.vehicles.stats.history(start_time=start_at_str, end_time=end_at_str, types=types)
    # print(result)
    # return result
    # print(client.vehicles.stats_history(start_at_str, end_at_str, types))


def filter_data(data_array):
    eastern = pytz.timezone('US/Eastern')
    filtered_data = []

    for vehicle_data in data_array:
        vehicle_id = vehicle_data.get('id', 'Unknown ID')
        vehicle_name = vehicle_data.get('name', f'Vehicle {vehicle_id}')
        filtered_vehicle_data = {
            'id': vehicle_id,
            'name': vehicle_name,
            'gpsOdometerMeters': [],
            'engineStates': [],
            'gpsDistanceMeters': []
        }

        for entry in vehicle_data.get('gpsOdometerMeters', []):
            if 'time' not in entry:
                continue
            try:
                time_str = entry['time'].replace('Z', '+00:00')
                dt = datetime.datetime.fromisoformat(time_str)
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)
                dt_eastern = dt.astimezone(eastern)
            except ValueError:
                print(f"Warning: Invalid date format: {entry['time']}")
                continue
            if not (dt_eastern.weekday() < 5 and 8 <= dt_eastern.hour < 17):
                filtered_entry = {'time': entry['time']}
                if 'value' in entry:
                    filtered_entry['value'] = entry['value']
                filtered_vehicle_data['gpsOdometerMeters'].append(filtered_entry)
        filtered_data.append(filtered_vehicle_data)
    return filtered_data

def calculate_total_miles(vehicle_data):
    odometer_readings = vehicle_data.get('gpsOdometerMeters', [])
    if not odometer_readings:
        return 0

    odometer_readings.sort(key=lambda x: x['time'])
    first_reading = odometer_readings[0].get('value')
    last_reading = odometer_readings[-1].get('value')

    if first_reading is None or last_reading is None:
        return 0

    total_meters = last_reading - first_reading
    total_miles = total_meters * 0.000621371

    return total_miles


def create_summary_table(filtered_data, start_time, end_time, csv_file_path="vehicle_summary.csv"):
    vehicle_totals = defaultdict(float)
    vehicle_names = {}
    for vehicle_data in filtered_data:
        vehicle_id = vehicle_data.get('id', 'Unknown ID')
        vehicle_name = vehicle_data.get('name', 'Unknown Vehicle')
        vehicle_names[vehicle_id] = vehicle_name
        total_miles = calculate_total_miles(vehicle_data)
        vehicle_totals[vehicle_id] += total_miles

    table_data = []
    for vehicle_id, total_miles in vehicle_totals.items():
        end_ms = int(end_time.timestamp() * 1000)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        report_url = f"https://cloud.samsara.com/o/{ORGANIZATION_ID}/fleet/reports/activity/report?vehicle_id={vehicle_id}&end_ms={end_ms}&duration={duration_ms}"
        table_data.append([vehicle_names[vehicle_id], vehicle_id, f"{total_miles:.2f}", report_url])

    headers = ["Vehicle Name", "Vehicle ID", "Total Miles (Filtered)", "Report URL"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(table_data)
    print(f"Data exported to {csv_file_path}")


def main():
    end_at = datetime.datetime.now(datetime.timezone.utc)
    start_at = end_at - datetime.timedelta(days=7)
    end_at_str = end_at.isoformat().replace('+00:00', 'Z')
    start_at_str = start_at.isoformat().replace('+00:00', 'Z')

    types = "gpsOdometerMeters"
    try:
        stats_history = get_vehicle_stats_history(start_at_str, end_at_str, types)
        # filtered_data = filter_data(stats_history)
        # create_summary_table(filtered_data, start_at, end_at)
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response content: {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()