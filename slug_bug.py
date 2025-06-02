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
  print("Media retrieval response:")
  print(response.json())
  return response.json()


def get_media_retrieval(media_retrieval_id):
  response = requests.get(
    f'{base_url}/cameras/media/retrieval?retrievalId={media_retrieval_id}',
    headers={
      'Authorization': f'Bearer {os.environ["SAMSARA_KEY"]}'
    }
  )
  print("Media retrieval response:")
  print(response.json())
  return response.json()


def main(event, _):
  # Convert milliseconds timestamp to RFC 3339 format
  # alertIncidentTime is 10 seconds before the button was clicked.
  # The video runs 30 seconds long (until 20 seconds after the button was clicked)
  alert_at = timestamp_to_datetime(int(event['alertIncidentTime']))
  asset_id = event['assetId']

  # Retrieve images at 3 different times: 3 seconds before, 1 second after, and 3 seconds after.
  offsets = [7, 11, 14]
  for offset in offsets:
    capture_at = alert_at + datetime.timedelta(seconds=offset)
    media_retrieval_response = create_media_retreival(capture_at, asset_id)
    media_retrieval_id = media_retrieval_response['data']['retrievalId']

  media_retrieval_response = create_media_retreival(capture_at, asset_id)
  # media_retrieval_id = 'e9cc6cb5-8040-4579-b780-00736b29942e'
  print(f"Media retrieval ID: {media_retrieval_id}")
  media_retrieval_response = get_media_retrieval(media_retrieval_id)
  print(json.dumps(media_retrieval_response, indent=2))

  # Download the image
  if media_retrieval_response['data']['media'][0]['status'] == 'available':
    image_url = media_retrieval_response['data']['media'][0]['urlInfo']['url']
    print(f"Image URL: {image_url}")
    print(f"Downloading image to image-{alert_at}.jpg")
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
        "prompt": (None, "")
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

    # Get the location of the vehicle:
    # Get the vehicle location from Samsara API
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
      'alertConfigurationId': 'c1d30986-6c74-4077-a1c1-7bc3779641fd',
      'alertIncidentTime': '1748874830839',
      'assetId': '281474994182986',
      'driverId': ''
    }
    main(event, None)
