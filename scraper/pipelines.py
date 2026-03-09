# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import json
import os


class SpiderSpecificOutputPipeline:
    """
    Pipeline that writes items to a specific output file based on spider name.
    Each spider's output will only go to its designated file.
    """

    def open_spider(self, spider):
        # Define output file name based on spider name
        self.output_files = {"uni": "uni.jsonl", "pages": "pages.jsonl"}

        # Get the output file for this spider
        self.file_name = self.output_files.get(spider.name)

        if self.file_name:
            # Open the file in write mode (overwriting previous content)
            self.file = open(self.file_name, "w", encoding="utf-8")

            # If the file is empty, make sure it exists with proper permissions
            if not os.path.exists(self.file_name):
                with open(self.file_name, "w") as f:
                    pass

    def close_spider(self, spider):
        if hasattr(self, "file") and self.file:
            self.file.close()

    def process_item(self, item, spider):
        if hasattr(self, "file") and self.file_name == self.output_files.get(
            spider.name
        ):
            # Only write to the file if it matches this spider's designated output
            line = json.dumps(dict(item), ensure_ascii=False) + "\n"
            self.file.write(line)
        return item
