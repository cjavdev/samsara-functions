import datetime
import requests
import base64
import os
import json

from db import DB

base_url = 'https://api.samsara.com'
db_name = "slug_bug"


def timestamp_to_datetime(timestamp_ms):
  """Convert a timestamp in milliseconds to a datetime object in UTC timezone"""
  return datetime.datetime.fromtimestamp(timestamp_ms / 1000, tz=datetime.timezone.utc)


def create_media_retreival(alert_at, asset_id):
  # If we've already created a media retrieval for this asset and alert time, return the existing one.
  db = DB(name=db_name)
  if db.get(f'media_retrieval_{asset_id}_{alert_at.isoformat()}'):
    print(f"Media retrieval already exists for {asset_id} at {alert_at.isoformat()}")
    return db.get(f'media_retrieval_{asset_id}_{alert_at.isoformat()}')

  print(f"Creating media retrieval for {asset_id} at {alert_at.isoformat()}")
  # Otherwise, create a new media retrieval request.
  response = requests.post(
    f'{base_url}/cameras/media/retrieval',
    headers={
      'Authorization': f'Bearer {os.getenv("SAMSARA_KEY")}'
    },
    json={
      'startTime': alert_at.isoformat(),
      'endTime': alert_at.isoformat(),
      'vehicleId': asset_id,
      'mediaType': 'image',
      'inputs': ['dashcamRoadFacing']
    }
  )
  retrieval = response.json()['data']
  print(f"Media retrieval with ID {retrieval['retrievalId']} created for {asset_id} at {alert_at.isoformat()}")
  db.set(f'media_retrieval_{asset_id}_{alert_at.isoformat()}', retrieval)
  print("Media retrieval in db:")
  print(db.get(f'media_retrieval_{asset_id}_{alert_at.isoformat()}'))
  return retrieval


def get_media_retrieval(media_retrieval_id):
  response = requests.get(
    f'{base_url}/cameras/media/retrieval?retrievalId={media_retrieval_id}',
    headers={
      'Authorization': f'Bearer {os.environ["SAMSARA_KEY"]}'
    }
  )
  print(response)
  return response.json()['data']['media'][0]


def get_available_slug_bug_rounds():
  """ Check to see if all media retrievals are ready.

  If all are available, add it to the list and return.
  """
  db = DB(name=db_name)
  keys = db.list_keys()
  slug_bug_keys = []
  for key in keys:
    if key.startswith('slug_bug_'):
      slug_bug_keys.append(key)

  slug_bug_rounds = []
  for key in slug_bug_keys:
    slug_bug = db.get(key)
    if slug_bug['status'] == 'pending':
      print(f"Slug bug checker found for {slug_bug['asset_id']} at {slug_bug['alert_time']}. Starting...")
      slug_bug = check_media_retrieval_status(slug_bug)
      db.set(key, slug_bug)

      if slug_bug['status'] == 'available':
        # Pass all images to OpenAI to check for slug bugs in the images.
        slug_bug_rounds.append(slug_bug)

  return slug_bug_rounds


def identify_slug_bugs(slug_bug):
  user_content = [{
    "type": "input_text",
    "text": "Identify slug bugs in the images."
  }]
  for media_item in slug_bug['media']:
    user_content.append({
      "type": "input_image",
      "image_url": media_item['urlInfo']['url']
    })

  # Make the API request to OpenAI for image editing
  openai_response = requests.post(
    "https://api.openai.com/v1/responses",
    headers={
      "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
      "Content-Type": "application/json"
    },
    data=json.dumps({
      "model": "gpt-4.1-mini",
      "input": [{
        "role": "user",
        "content": user_content
      }],
      "text": {
        "format": {
          "type": "json_schema",
          "name": "slug_bug_evaluation",
          "schema": {
            "type": "object",
            "properties": {
              "color": {
                "type": ["string", "null"],
                "description": "The color of the slug bug.",
                "enum": ["n/a", "Red", "Green", "Blue", "Yellow", "Purple", "Orange", "Pink", "Brown", "Gray", "Black", "White"]
              },
              "has_slug_bug": {
                "type": "boolean",
                "description": "Whether the image has a VW bug or VW beetle in it or not."
              }
            },
            "required": ["color", "has_slug_bug"],
            "additionalProperties": False
          },
          "strict": True
        }
      }
    }),
    verify=False
  )

  json_response = openai_response.json()
  result = json.loads(json_response['output'][0]['content'][0]['text'])
  return result['color'], result['has_slug_bug']

def notify_players(color):
  players = [52514325]

  response = requests.post(
    "https://api.samsara.com/v1/fleet/messages",
    json={
      "driverIds": players,
      "text": f"Slug Bug {color}! 🤜"
    },
    headers={
      "Authorization": f"Bearer {os.environ['SAMSARA_KEY']}"
    }
  )
  print(f"Notifying players of slug bug {color}!")
  print(response.json())


def mark_slug_bug_round_as_done(slug_bug_round):
  print(f"Marking slug bug round as done: {slug_bug_round}")
  db = DB(name=db_name)
  key = f"slug_bug_{slug_bug_round['asset_id']}_{slug_bug_round['alert_time']}"
  db.set(key, {
    **slug_bug_round,
    'status': 'done'
  })


def check_media_retrieval_status(slug_bug):
  media = slug_bug['media']
  updated_media = []
  slug_bug['status'] = 'available'

  for media_item in media:
    media_retrieval = get_media_retrieval(media_item['retrievalId'])
    updated_media.append(media_item | media_retrieval)
    if media_retrieval['status'] != 'available':
      print(f"Media retrieval {media_item['retrievalId']} is not available")
      slug_bug['status'] = 'pending'
    else:
      print(f"Media retrieval {media_item['retrievalId']} is available")

  slug_bug['media'] = updated_media
  return slug_bug


# Entry point for part 1: On Driver Recorded event, create retrieval requests
# for images around the time the button was clicked.
def start(event, _):
  db = DB(name=db_name)

  # alertIncidentTime is 10 seconds before the button was clicked.
  # The video runs 30 seconds (until 20 seconds after the button was clicked)
  alert_time = event['alertIncidentTime']
  alert_at = timestamp_to_datetime(int(alert_time))
  asset_id = event['assetId']

  if db.get(f'slug_bug_{asset_id}_{alert_time}'):
    print(f"Slug bug checker already exists for {asset_id} at {alert_time}")
    return

  # Retrieve road facing images at 3 different times: 3 seconds before, 1 second
  # after, and 3 seconds after clicking the button.
  offsets = [14, 11, 7]
  media = []
  for offset in offsets:
    capture_at = alert_at + datetime.timedelta(seconds=offset)
    media_retrieval = create_media_retreival(capture_at, asset_id)
    media.append(media_retrieval)

  # Write to db and wait for the media retrieval to be available.
  db.set(f'slug_bug_{asset_id}_{alert_time}', {
    'media': media,
    'alert_at': alert_at.isoformat(),
    'asset_id': asset_id,
    'alert_time': alert_time,
    'status': 'pending'
  })


# Entry point for part 2: On a timer, check the status of the media retrievals
# and identify slug bugs in the images if they are available.
def check(event, _):
  slug_bug_rounds = get_available_slug_bug_rounds()
  if len(slug_bug_rounds) == 0:
    print("No slug bug round media is available, yet.")
    return

  for slug_bug_round in slug_bug_rounds:
    color, found = identify_slug_bugs(slug_bug_round)
    if found:
      print(f"Slug Bug {color}! 🤜")
      notify_players(color)
    else:
      print("No slug bug found.")

    mark_slug_bug_round_as_done(slug_bug_round)



if __name__ == "__main__":
    event = {
      'SamsaraFunctionTriggerSource': 'alert',
      'alertConfigurationId': 'c1d30986-6c74-4077-a1c1-7bc3779641fd',
      'alertIncidentTime': '1748874830839',
      'assetId': '281474994182986',
      'driverId': ''
    }
    # start(event, None)
    check()