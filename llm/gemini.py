from google import genai
from dotenv import load_dotenv
import os
import json
from db.data import get_all_programs, get_all_tags
from db.session import get_db

load_dotenv()

db = next(get_db())
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
base_prompt = ""
programs = get_all_programs(db)
tags = get_all_tags(db)

try:
    with open("base_prompt.txt", "r") as file:
        loaded_prompt = file.read().strip()

    # Add base prompt as system message if it exists and isn't empty
    if loaded_prompt:
        base_prompt = loaded_prompt
except FileNotFoundError:
    # If file doesn't exist, continue with the default system message
    pass


def extract_with_gemini(content, url):
    """
    Extracts announcements from the given content and URL using Gemini API.

    Args:
        content (str): The content to analyze.
        url (str): The source URL of the content.

    Returns:
        dict: The extracted announcements in JSON format.
    """
    prompt = f"Text Chunk:\n{content}\nSource URL: {url}"

    if (not programs) or (not tags):
        raise Exception("Programs or Tags not loaded from DB.")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "system_instruction": base_prompt,
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "object",
                "properties": {
                    "announcements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["title", "content", "announcement_type"],
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "Title of the announcement",
                                },
                                "content": {
                                    "type": "string",
                                    "description": "Main text content of the announcement",
                                },
                                "published_date": {
                                    "type": "string",
                                    "format": "date-time",
                                    "description": "Date when the announcement was published (YYYY-MM-DD)",
                                    "nullable": True,
                                },
                                "application_open_date": {
                                    "type": "string",
                                    "format": "date-time",
                                    "description": "Date when applications open (YYYY-MM-DD)",
                                    "nullable": True,
                                },
                                "application_deadline": {
                                    "type": "string",
                                    "format": "date-time",
                                    "description": "Application deadline date (YYYY-MM-DD)",
                                    "nullable": True,
                                },
                                "term": {
                                    "type": "string",
                                    "description": "Academic term referenced (e.g., 'Fall 2025')",
                                    "nullable": True,
                                },
                                "contact_info": {
                                    "type": "string",
                                    "description": "Contact information provided in the announcement",
                                    "nullable": True,
                                },
                                "announcement_type": {
                                    "type": "string",
                                    "enum": [
                                        "admission_dates",
                                        "contact_info",
                                        "exam_info",
                                        "result_info",
                                        "general",
                                    ],
                                    "description": "Type of announcement",
                                },
                                "programs_courses": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": list(map(lambda x: x.name, programs)),
                                        "description": "Names of programs or courses related to the announcement",
                                    },
                                },
                                "tags": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": list(map(lambda x: x.name, tags)),
                                        "description": "Tags related to the announcement",
                                    },
                                    "description": "List of tags associated with the announcement",
                                },
                            },
                        },
                    }
                },
            },
        },
    )

    response_text = response.text
    if response_text is None:
        return {}
    result_json = json.loads(response_text)
    if "announcements" in result_json:
        for announcement in result_json["announcements"]:
            if (
                announcement.get("announcement_type") == "admission_dates"
                and announcement.get("application_deadline") is None
            ):
                announcement["announcement_type"] = "general"
    return result_json
