import csv
import json
import os
import requests
from urllib.parse import unquote

def invoke(action, **params):
    """Helper function to call AnkiConnect."""
    request_json = json.dumps({'action': action, 'version': 6, 'params': params})
    response = requests.post('http://127.0.0.1:8765', data=request_json)
    response.raise_for_status()
    result = response.json()
    if len(result) != 2:
        raise Exception('response has an unexpected number of fields')
    if 'error' not in result:
        raise Exception('response is missing required error field')
    if 'result' not in result:
        raise Exception('response is missing required result field')
    if result['error'] is not None:
        raise Exception(result['error'])
    return result['result']

def main():
    """Main function to update Anki cards."""
    # Read the transcriptions and map text to audio file paths
    text_to_audio = {}
    with open('transcriptions.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            filepath, text = row
            # Normalize text: lowercase and remove punctuation
            normalized_text = text.lower().strip(" .?!")
            # Get the base filename for the [sound:...] tag
            filename = os.path.basename(filepath)
            text_to_audio[normalized_text] = filename

    # Find notes in the specified deck
    query = '"deck:Korean::HTSK Vocab - Unit 2"'
    note_ids = invoke('findNotes', query=query)
    notes_info = invoke('notesInfo', notes=note_ids)

    updates = []
    for note in notes_info:
        try:
            korean_text = note['fields']['Korean']['value']
            # Normalize for matching
            normalized_korean = korean_text.lower().strip(" .?!")

            if normalized_korean in text_to_audio:
                sound_filename = text_to_audio[normalized_korean]
                # Check if the sound field is already set
                current_sound_field = note['fields'].get('Sound', {}).get('value', '')
                new_sound_tag = f'[sound:{sound_filename}]'

                if current_sound_field != new_sound_tag:
                    update = {
                        'id': note['noteId'],
                        'fields': {
                            'Sound': new_sound_tag
                        }
                    }
                    updates.append(update)
        except KeyError:
            # This can happen if a note doesn't have a "Korean" field.
            print(f"Skipping note {note['noteId']} due to missing 'Korean' field.")
            continue

    if updates:
        print(f"Updating {len(updates)} notes...")
        invoke('updateNoteFields', notes=updates)
        print("Anki notes updated successfully.")
    else:
        print("No notes needed updating.")

if __name__ == "__main__":
    main()
