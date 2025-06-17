# Called when entering a geofence for a JobSite
# Fetch an image of the house from the JobSite
# Upload the image to OpenAI for a paint suggestion image back
# Send the image back to the client

import datetime
import requests
import base64
import os
import json

base_url = 'https://api.samsara.com'


def timestamp_to_datetime(timestamp_ms):
  """Convert a timestamp in milliseconds to a datetime object in UTC timezone"""
  return datetime.datetime.fromtimestamp(timestamp_ms / 1000, tz=datetime.timezone.utc)


def create_media_retreival(alert_at, asset_id):
  response = requests.post(
    f'{base_url}/cameras/media/retrieval',
    headers={
      'Authorization': f'Bearer {os.environ["SAMSARA_KEY"]}'
    },
    json={
      'startTime': alert_at.isoformat(),
      'endTime': alert_at.isoformat(),
      'vehicleId': asset_id,
      'mediaType': 'image',
      'inputs': ['dashcamRoadFacing']
    }
  )
  return response.json()


def get_media_retrieval(media_retrieval_id):
  response = requests.get(
    f'{base_url}/cameras/media/retrieval?retrievalId={media_retrieval_id}',
    headers={
      'Authorization': f'Bearer {os.environ["SAMSARA_KEY"]}'
    }
  )
  return response.json()


def main(event, _):
  # # Convert milliseconds timestamp to RFC 3339 format
  alert_at = event['alertIncidentTime']
  capture_at = timestamp_to_datetime(int(alert_at)) + datetime.timedelta(seconds=11)
  asset_id = event['assetId']

  media_retrieval_response = create_media_retreival(capture_at, asset_id)
  media_retrieval_id = media_retrieval_response['data']['retrievalId']
  media_retrieval_response = get_media_retrieval(media_retrieval_id)

  # Download the image
  if media_retrieval_response['data']['media'][0]['status'] == 'available':
    image_url = media_retrieval_response['data']['media'][0]['urlInfo']['url']

    # Download the image
    response = requests.get(image_url)
    with open(f'image-{alert_at}.jpg', 'wb') as f:
      f.write(response.content)

    print("Generating a paint suggestion...")

    # Make the API request to OpenAI for image editing
    openai_response = requests.post(
      "https://api.openai.com/v1/images/edits",
      headers={
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"
      },
      files={
        "image[]": ("image.jpg", open("image.jpg", "rb"), "image/jpeg"),
        "model": (None, "gpt-image-1"),
        "prompt": (None, "Generate an image of this building with a new paint job with a modern popular color to send the home owner inspiration and a quote to paint the exterior of their home. Remove the surrounding vehicle details captured from the dashcam.")
      },
      verify=False  # Disable SSL certificate verification
    )

    # Parse the response and save the image
    if openai_response.status_code == 200:
      response_data = openai_response.json()
      if response_data.get('data') and len(response_data['data']) > 0:
        # Decode base64 image data and save to file
        image_data = base64.b64decode(response_data['data'][0]['b64_json'])
        file_name = f'paint-suggestion-{alert_at}.png'
        with open(file_name, 'wb') as f:
          f.write(image_data)
        print(f"Successfully generated and saved the edited image as {file_name}")
      else:
        print("No image data found in the response")
    else:
      print(f"Error: API request failed with status code {openai_response.status_code}")
      print(openai_response.text)

    # Get the vehicle location from the Samsara API
    location_response = requests.get(
      f'{base_url}/fleet/vehicles/locations',
      headers={
        'Authorization': f'Bearer {os.environ["SAMSARA_KEY"]}',
        'accept': 'application/json'
      },
      params={
        'time': capture_at.isoformat(),
        'vehicleIds': asset_id
      }
    )

    if location_response.status_code == 200:
      location_data = location_response.json()
      if location_data.get('data') and len(location_data['data']) > 0:
        address = location_data['data'][0]['location']['reverseGeo']['formattedLocation']
        print(f"Vehicle location: {address}")
    else:
      print(f"Error: Location API request failed with status code {location_response.status_code}")
      print(location_response.text)
  else:
    print("No media found")


if __name__ == "__main__":
    event = {
      'SamsaraFunctionTriggerSource': 'alert',
      'alertConfigurationId': '486d566a-c164-4527-998f-7b859b995dcf',
      'alertIncidentTime': '1747913819184',
      'assetId': '281474994182986',
      'driverId': ''
    }
    main(event, None)
