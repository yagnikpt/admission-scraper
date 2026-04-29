import logging

import pandas as pd
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from db.models import Institute, Program, State, Tag
from db.session import get_db
from db.utils import get_all_states, normalize_state_name, split_content

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_institutes(db: Session):
    # Load sites data
    # Load data from multiple CSV files
    csv_files = [
        "data/central_uni.csv",
        "data/state_uni.csv",
        "data/private_uni.csv",
        # "data/deemed_to_be.csv",
    ]

    # Combine all CSV files into a single DataFrame
    dataframes = []
    for file in csv_files:
        try:
            temp_df = pd.read_csv(file)
            dataframes.append(temp_df)
            logger.info(f"Successfully loaded {file}")
        except Exception as e:
            logger.error(f"Error loading {file}: {str(e)}")

    # Concatenate all dataframes
    if dataframes:
        df = pd.concat(dataframes, ignore_index=True)
        logger.info(f"Total records loaded: {len(df)}")
    else:
        logger.error("No data loaded from CSV files")
        df = pd.DataFrame()  # Empty DataFrame as fallback
    data = df.to_dict(orient="records")

    # Load states data and create a mapping of state names to state_ids
    states_df = pd.DataFrame(get_all_states(db))

    # Create both regular and normalized mappings for better matching
    state_name_to_id_map = dict(zip(states_df["name"], states_df["state_id"]))
    normalized_state_map = {
        normalize_state_name(name): id
        for name, id in zip(states_df["name"], states_df["state_id"])
    }

    # Map state names to state_ids for each site
    data_with_state_id = []
    unmatched_states = set()

    for site in data:
        state_name = site["state"]

        # Try direct match first
        state_id = state_name_to_id_map.get(state_name)

        # If direct match fails, try normalized match
        if not state_id:
            normalized_name = normalize_state_name(state_name)
            state_id = normalized_state_map.get(normalized_name)

            # Additional loose matching for common variations
            if not state_id:
                # Try partial matching for longer state names
                for db_state, db_id in normalized_state_map.items():
                    # Check if one is a substring of the other (in either direction)
                    if (
                        normalized_name in db_state or db_state in normalized_name
                    ) and len(db_state) > 3:
                        state_id = db_id
                        logger.info(
                            f"Partial match found: '{state_name}' matched with '{db_state}'"
                        )
                        break

        if state_id:
            site_with_state_id = site.copy()
            site_with_state_id["state_id"] = state_id
            data_with_state_id.append(site_with_state_id)
        else:
            unmatched_states.add(state_name)
            logger.warning(
                f"State '{state_name}' not found in states mapping for site: {site['name_of_the_university']}"
            )

    if unmatched_states:
        logger.warning(f"Unmatched states: {', '.join(sorted(unmatched_states))}")

    logger.info(
        f"Processed {len(data_with_state_id)} out of {len(data)} sites with valid state IDs"
    )

    unique_data = []
    seen_urls = set()
    duplicate_urls = set()

    for site in data_with_state_id:
        url = str(site["url"]).strip()
        if url in seen_urls:
            duplicate_urls.add(url)
            continue

        site_with_clean_url = site.copy()
        site_with_clean_url["url"] = url
        seen_urls.add(url)
        unique_data.append(site_with_clean_url)

    if duplicate_urls:
        logger.warning(
            f"Skipping {len(data_with_state_id) - len(unique_data)} duplicate institute URLs: "
            f"{', '.join(sorted(duplicate_urls))}"
        )

    existing_websites = set()
    if unique_data:
        existing_websites = {
            website
            for (website,) in db.query(Institute.website)
            .filter(Institute.website.in_([site["url"] for site in unique_data]))
            .all()
        }

    if existing_websites:
        logger.info(
            f"Skipping {len(existing_websites)} institutes that already exist in the database"
        )

    new_data = [site for site in unique_data if site["url"] not in existing_websites]
    spiltted_data = split_content(new_data)

    try:
        for batch in spiltted_data:
            sites = []
            for site in batch:
                website = Institute(
                    name=site["name_of_the_university"],
                    website=site["url"],
                    state_id=site["state_id"],
                )
                sites.append(website)
            db.add_all(sites)
        db.commit()
        logger.info(f"Successfully added {len(new_data)} institutes to the database")

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating site: {str(e)}")
        raise ValueError(f"Value already exists: {str(e)}")

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating site: {str(e)}")
        raise Exception(f"Database error: {str(e)}")


def seed_states(db: Session):
    states = pd.read_json("seed_data/states.json")
    states = states.to_dict(orient="records")

    try:
        existing_states = {
            value
            for row in db.query(State.name, State.abbreviation).all()
            for value in row
        }
        added_count = 0

        for state in states:
            if (
                state["name"] in existing_states
                or state["abbreviation"] in existing_states
            ):
                continue

            state_instance = State(
                name=state["name"],
                abbreviation=state["abbreviation"],
            )
            db.add(state_instance)
            existing_states.update((state["name"], state["abbreviation"]))
            added_count += 1
        db.commit()
        logger.info(f"Successfully added {added_count} states to the database")
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating state: {str(e)}")
        raise ValueError(f"Value already exists: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating state: {str(e)}")
        raise Exception(f"Database error: {str(e)}")


def seed_programs(db: Session):
    programs = pd.read_json("seed_data/programs.json")
    programs = programs.to_dict(orient="records")

    try:
        existing_program_names = {name for (name,) in db.query(Program.name).all()}
        added_count = 0

        for program in programs:
            if program["name"] in existing_program_names:
                continue

            program_instance = Program(
                name=program["name"],
                description=program["description"],
                degree_level=program["degree_level"],
                duration_months=program["duration_months"],
            )
            db.add(program_instance)
            existing_program_names.add(program["name"])
            added_count += 1
        db.commit()
        logger.info(f"Successfully added {added_count} programs to the database")
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating program: {str(e)}")
        raise ValueError(f"Value already exists: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating program: {str(e)}")
        raise Exception(f"Database error: {str(e)}")


def seed_tags(db: Session):
    tags = pd.read_json("seed_data/tags.json")
    tags = tags.to_dict(orient="records")

    try:
        existing_tag_names = {name for (name,) in db.query(Tag.name).all()}
        added_count = 0

        for tag in tags:
            if tag["name"] in existing_tag_names:
                continue

            tag_instance = Tag(name=tag["name"])
            db.add(tag_instance)
            existing_tag_names.add(tag["name"])
            added_count += 1
        db.commit()
        logger.info(f"Successfully added {added_count} tags to the database")
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating tag: {str(e)}")
        raise ValueError(f"Value already exists: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating tag: {str(e)}")
        raise Exception(f"Database error: {str(e)}")


if __name__ == "__main__":
    db = next(get_db())
    seed_states(db)
    seed_programs(db)
    seed_tags(db)
    seed_institutes(db)
    pass
