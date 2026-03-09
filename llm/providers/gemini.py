from google import genai

from config import settings
from db.data import get_all_programs, get_all_tags
from db.session import get_db
from llm.schema import AnnouncementType, make_announcement_model

from ..base import BaseLLM

db = next(get_db())
tags = get_all_tags(db)
programs = get_all_programs(db)

if (not programs) or (not tags):
    raise Exception("Programs or Tags not loaded from DB.")

ResponseModel = make_announcement_model(programs, tags)


class GeminiExtractor(BaseLLM[ResponseModel]):
    response_model = ResponseModel

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.client = genai.Client(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
            vertexai=True,
        )
        self.model = model

        try:
            with open("base_prompt.txt", "r") as file:
                loaded_prompt = file.read().strip()

            if loaded_prompt:
                self.base_prompt = loaded_prompt
        except FileNotFoundError:
            self.base_prompt = ""

    def extract_announcements(self, content, url):
        prompt = f"Text Chunk:\n{content}\nSource URL: {url}"

        schema = self.response_model.model_json_schema()
        self._remove_additional_properties(schema)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "system_instruction": self.base_prompt,
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )

        result_json = self.response_model.model_validate_json(response.text or "")
        for announcement in result_json.announcements:
            if (
                announcement.announcement_type == AnnouncementType.admission_dates
                and announcement.application_deadline is None
            ):
                announcement.announcement_type = AnnouncementType.general
        return result_json

    @staticmethod
    def _remove_additional_properties(schema):
        if isinstance(schema, dict):
            schema.pop("additionalProperties", None)
            for value in schema.values():
                GeminiExtractor._remove_additional_properties(value)
        elif isinstance(schema, list):
            for item in schema:
                GeminiExtractor._remove_additional_properties(item)


if __name__ == "__main__":
    extractor = GeminiExtractor()

    # for model in extractor.client.models.list():
    #     print(model.name)

    test_content = "Menu Admission - MBA Admission – MBA MBA Admission Process 2026 The list of shortlisted candidates for interview is available here ( ). Last date of uploading the documents is 23:59 PM on 28 February 2026. The call letters for personal interviews will be sent to the shortlisted candidates by email. Shortlisting Criteria for MBA & MBA (Telecom) 2026-2028 is available here ( ) The last date for submission of the application form for MBA and MBA (Telecom) (Batch 2026–2028) has been extended to 1 February 2026, up to 23:59 hrs. The last date for MBA and MBA (Telecom) Admission for Batch 2026-2028 is 26th January 2026 Eligibility The candidates having the following qualifications are eligible to apply for admission to the MBA programme Masters in Business Administration (MBA) A Bachelor’s Degree or equivalent awarded by"
    test_url = "https://dms.iitd.ac.in/admission-mba"
    res = extractor.extract_announcements(
        test_content,
        test_url,
    )
    print(res.model_dump_json())
