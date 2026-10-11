# CRUD Python
# CRUD_Python_Module.py

import os
import logging
from typing import List, Dict, Any
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# ---------------------------------------------------------
# LOGGING CONFIGURATION
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AnimalShelter")


# ---------------------------------------------------------
# CUSTOM EXCEPTIONS
# ---------------------------------------------------------
class AnimalShelterError(Exception):
    """Base exception for all AnimalShelter-related errors."""
    pass


class AnimalShelterValidationError(AnimalShelterError):
    """Raised when validation fails."""
    pass


class AnimalShelterConnectionError(AnimalShelterError):
    """Raised when MongoDB connection fails."""
    pass


class AnimalShelterCrudError(AnimalShelterError):
    """Raised when a CRUD operation fails."""
    pass


class AnimalShelterRescueFilterError(AnimalShelterError):
    """Raised when rescue filter logic fails."""
    pass


class AnimalShelterAnalyticsError(AnimalShelterError):
    """Raised when aggregation/analytics operations fail."""
    pass


class AnimalShelter(object):
    """
    Secure CRUD operations for the AAC 'animals' collection with safe operator support.

    This class encapsulates all database interactions, including:
    - Authentication
    - Query validation
    - CRUD operations
    - Rescue filter queries
    - Database analytics (aggregation pipelines, indexes, validation)
    """

    # ---------------------------------------------------------
    # CONFIGURATION
    # ---------------------------------------------------------
    HOST = os.getenv("MONGO_HOST", "localhost")
    PORT = int(os.getenv("MONGO_PORT", "27017"))
    DB_NAME = os.getenv("MONGO_DB_NAME", "aac")
    COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "animals")

    ALLOWED_FIELDS = {
        "name",
        "animal_id",
        "animal_type",
        "breed",
        "color",
        "date_of_birth",
        "datetime",
        "monthyear",
        "sex_upon_outcome",
        "age_upon_outcome",
        "age_upon_outcome_in_weeks",
        "outcome_type",
        "outcome_subtype",
        "location_lat",
        "location_long",
        "notes",
        "list_field",
        "dict_field",
        "numeric_field",
        "rescue_score",  # allow scoring field if persisted later
    }

    SAFE_OPERATORS = {
        "$in", "$gte", "$lte", "$gt", "$lt", "$eq", "$ne", "$regex", "$options"
    }

    INDEX_FIELDS = [
        "breed",
        "animal_type",
        "outcome_type",
        "age_upon_outcome_in_weeks",
    ]

    # ---------------------------------------------------------
    # INITIALIZATION
    # ---------------------------------------------------------
    def __init__(self, username: str, password: str):
        """Initialize MongoDB connection and authenticate."""
        if not username or not isinstance(username, str):
            raise AnimalShelterValidationError("Username must be a non-empty string.")

        if not password or not isinstance(password, str):
            raise AnimalShelterValidationError("Password must be a non-empty string.")

        try:
            uri = (
                f"mongodb://{username}:{password}@{self.HOST}:{self.PORT}/"
                f"?authSource={self.DB_NAME}"
            )

            self.client = MongoClient(uri)
            self.client.admin.command("ping")

            self.database = self.client[self.DB_NAME]
            if self.COLLECTION_NAME not in self.database.list_collection_names():
                raise AnimalShelterConnectionError(
                    f"Collection '{self.COLLECTION_NAME}' does not exist in database '{self.DB_NAME}'."
                )

            self.collection = self.database[self.COLLECTION_NAME]

            logger.info(
                "Connection Successful → Authenticated as '%s' | Database: '%s' | Collection: '%s'",
                username, self.DB_NAME, self.COLLECTION_NAME
            )

            # Ensure indexes and schema validation are applied
            self._ensure_indexes()
            self._ensure_schema_validation()

        except PyMongoError as e:
            logger.exception("Error connecting to MongoDB")
            raise AnimalShelterConnectionError("Failed to connect to MongoDB.") from e

    # ---------------------------------------------------------
    # CONNECTION HEALTH CHECK
    # ---------------------------------------------------------
    def is_connected(self) -> bool:
        """Return True if the MongoDB connection is active."""
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def health(self) -> Dict[str, Any]:
        """Return basic health information about the database connection."""
        return {
            "host": self.HOST,
            "port": self.PORT,
            "database": self.DB_NAME,
            "collection": self.COLLECTION_NAME,
            "connected": self.is_connected()
        }

    # ---------------------------------------------------------
    # INTERNAL VALIDATION HELPERS
    # ---------------------------------------------------------
    def _validate_query(self, query: Dict[str, Any]):
        """Validate query fields and safe operators."""
        if not isinstance(query, dict):
            raise AnimalShelterValidationError("Query must be a dictionary.")

        if not query:
            return  # allow empty query for read_all()

        for key, value in query.items():
            if key.startswith("$"):
                if key not in self.SAFE_OPERATORS:
                    raise AnimalShelterValidationError(f"MongoDB operator '{key}' is not allowed.")
                continue

            if key not in self.ALLOWED_FIELDS:
                raise AnimalShelterValidationError(f"Field '{key}' is not allowed in queries.")

            if isinstance(value, dict):
                for op in value.keys():
                    if op not in self.SAFE_OPERATORS:
                        raise AnimalShelterValidationError(f"Operator '{op}' is not allowed.")

    def _validate_update_values(self, new_values: Dict[str, Any]):
        """Validate update fields and safe operators."""
        if not isinstance(new_values, dict):
            raise AnimalShelterValidationError("Update values must be a dictionary.")

        if not new_values:
            raise AnimalShelterValidationError("Update values cannot be empty.")

        for key in new_values.keys():
            if key.startswith("$"):
                raise AnimalShelterValidationError("Update cannot contain MongoDB operators directly.")

            if key not in self.ALLOWED_FIELDS:
                raise AnimalShelterValidationError(f"Field '{key}' is not allowed in updates.")

    # ---------------------------------------------------------
    # INDEX MANAGEMENT
    # ---------------------------------------------------------
    def _ensure_indexes(self):
        """
        Create indexes on frequently queried fields to improve performance.

        Indexes:
        - breed
        - animal_type
        - outcome_type
        - age_upon_outcome_in_weeks
        """
        try:
            for field in self.INDEX_FIELDS:
                logger.info("Ensuring index on field: %s", field)
                self.collection.create_index(field)
        except PyMongoError as e:
            logger.exception("Error creating indexes")
            raise AnimalShelterAnalyticsError("Failed to create indexes.") from e

    # ---------------------------------------------------------
    # SCHEMA VALIDATION
    # ---------------------------------------------------------
    def _ensure_schema_validation(self):
        """
        Apply MongoDB JSON schema validation to enforce basic data integrity.

        Required fields:
        - name (string)
        - animal_type (string)
        - outcome_type (string)
        """
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "animal_type", "outcome_type"],
                "properties": {
                    "name": {"bsonType": "string"},
                    "animal_type": {"bsonType": "string"},
                    "breed": {"bsonType": ["string", "null"]},
                    "age_upon_outcome_in_weeks": {"bsonType": ["int", "double", "null"]},
                    "outcome_type": {"bsonType": "string"},
                    "location_lat": {"bsonType": ["double", "null"]},
                    "location_long": {"bsonType": ["double", "null"]},
                }
            }
        }

        try:
            logger.info("Applying schema validation to collection '%s'", self.COLLECTION_NAME)
            self.database.command({
                "collMod": self.COLLECTION_NAME,
                "validator": validator,
                "validationLevel": "moderate",
                "validationAction": "warn",
            })
        except PyMongoError as e:
            logger.exception("Error applying schema validation")
            raise AnimalShelterAnalyticsError("Failed to apply schema validation.") from e

    # ---------------------------------------------------------
    # CRUD OPERATIONS
    # ---------------------------------------------------------
    def create(self, data: Dict[str, Any]) -> bool:
        """Insert a document into the collection."""
        self._validate_update_values(data)

        if "name" not in data or not isinstance(data["name"], str):
            raise AnimalShelterValidationError("Missing required field: 'name' (must be a string).")

        try:
            result = self.collection.insert_one(data)
            logger.info("Document inserted with ID: %s", result.inserted_id)
            return result.acknowledged
        except PyMongoError as e:
            logger.exception("Error inserting document")
            raise AnimalShelterCrudError("Failed to insert document.") from e

    def read(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Read documents matching a query."""
        self._validate_query(query)
        try:
            return list(self.collection.find(query))
        except PyMongoError as e:
            logger.exception("Error reading documents")
            raise AnimalShelterCrudError("Failed to read documents.") from e

    def read_all(self) -> List[Dict[str, Any]]:
        """Return all documents."""
        try:
            return list(self.collection.find({}))
        except PyMongoError as e:
            logger.exception("Error reading all documents")
            raise AnimalShelterCrudError("Failed to read all documents.") from e

    def update(self, query: Dict[str, Any], new_values: Dict[str, Any]) -> int:
        """Update documents matching a query."""
        self._validate_query(query)
        self._validate_update_values(new_values)

        try:
            result = self.collection.update_many(query, {"$set": new_values})
            logger.info("Documents modified: %s", result.modified_count)
            return result.modified_count
        except PyMongoError as e:
            logger.exception("Error updating documents")
            raise AnimalShelterCrudError("Failed to update documents.") from e

    def delete(self, query: Dict[str, Any]) -> int:
        """Delete documents matching a query."""
        self._validate_query(query)
        try:
            result = self.collection.delete_many(query)
            logger.info("Documents deleted: %s", result.deleted_count)
            return result.deleted_count
        except PyMongoError as e:
            logger.exception("Error deleting documents")
            raise AnimalShelterCrudError("Failed to delete documents.") from e

    # ---------------------------------------------------------
    # RESCUE FILTER QUERIES
    # ---------------------------------------------------------
    def filter_water_rescue(self) -> List[Dict[str, Any]]:
        """Return dogs suitable for Water Rescue using regex breed matching."""
        try:
            query = {
                "breed": {"$regex": r"(labrador|lab|chesapeake|newfoundland)", "$options": "i"},
                "sex_upon_outcome": "Intact Female",
                "age_upon_outcome_in_weeks": {"$gte": 26, "$lte": 156}
            }
            return self.read(query)
        except Exception as e:
            raise AnimalShelterRescueFilterError("Water rescue filter failed.") from e

    def filter_mountain_rescue(self) -> List[Dict[str, Any]]:
        """Return dogs suitable for Mountain/Wilderness Rescue using regex breed matching."""
        try:
            query = {
                "breed": {"$regex": r"(german|shepherd|malamute|sheepdog|husky|rottweiler)", "$options": "i"},
                "sex_upon_outcome": "Intact Male",
                "age_upon_outcome_in_weeks": {"$gte": 26, "$lte": 156}
            }
            return self.read(query)
        except Exception as e:
            raise AnimalShelterRescueFilterError("Mountain rescue filter failed.") from e

    def filter_disaster_rescue(self) -> List[Dict[str, Any]]:
        """Return dogs suitable for Disaster/Tracking Rescue using regex breed matching."""
        try:
            query = {
                "breed": {
                    "$regex": r"(doberman|pinscher|german|shepherd|golden|retriever|bloodhound|rottweiler)",
                    "$options": "i"
                },
                "sex_upon_outcome": "Intact Male",
                "age_upon_outcome_in_weeks": {"$gte": 20, "$lte": 300}
            }
            return self.read(query)
        except Exception as e:
            raise AnimalShelterRescueFilterError("Disaster rescue filter failed.") from e

    # ---------------------------------------------------------
    # AGGREGATION PIPELINES (DATABASE ANALYTICS)
    # ---------------------------------------------------------
    def aggregate_breed_distribution(self, match_filter: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """
        Return breed distribution using a MongoDB aggregation pipeline.

        Optional:
        - match_filter: a validated query dict to restrict the dataset (e.g., only dogs).
        """
        try:
            pipeline: List[Dict[str, Any]] = []

            if match_filter:
                self._validate_query(match_filter)
                pipeline.append({"$match": match_filter})

            pipeline.extend([
                {"$group": {"_id": "$breed", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ])

            logger.info("Running breed distribution aggregation pipeline.")
            return list(self.collection.aggregate(pipeline))
        except (PyMongoError, AnimalShelterValidationError) as e:
            logger.exception("Error aggregating breed distribution")
            raise AnimalShelterAnalyticsError("Failed to aggregate breed distribution.") from e

    def aggregate_outcome_distribution(self, match_filter: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """
        Return outcome distribution (e.g., Adoption, Transfer, etc.) using aggregation.
        """
        try:
            pipeline: List[Dict[str, Any]] = []

            if match_filter:
                self._validate_query(match_filter)
                pipeline.append({"$match": match_filter})

            pipeline.extend([
                {"$group": {"_id": "$outcome_type", "total": {"$sum": 1}}},
                {"$sort": {"total": -1}}
            ])

            logger.info("Running outcome distribution aggregation pipeline.")
            return list(self.collection.aggregate(pipeline))
        except (PyMongoError, AnimalShelterValidationError) as e:
            logger.exception("Error aggregating outcome distribution")
            raise AnimalShelterAnalyticsError("Failed to aggregate outcome distribution.") from e

    def aggregate_age_statistics(self, match_filter: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """
        Return basic age statistics (min, max, average) for age_upon_outcome_in_weeks.
        """
        try:
            pipeline: List[Dict[str, Any]] = []

            if match_filter:
                self._validate_query(match_filter)
                pipeline.append({"$match": match_filter})

            pipeline.extend([
                {
                    "$group": {
                        "_id": None,
                        "min_age_weeks": {"$min": "$age_upon_outcome_in_weeks"},
                        "max_age_weeks": {"$max": "$age_upon_outcome_in_weeks"},
                        "avg_age_weeks": {"$avg": "$age_upon_outcome_in_weeks"},
                    }
                }
            ])

            logger.info("Running age statistics aggregation pipeline.")
            return list(self.collection.aggregate(pipeline))
        except (PyMongoError, AnimalShelterValidationError) as e:
            logger.exception("Error aggregating age statistics")
            raise AnimalShelterAnalyticsError("Failed to aggregate age statistics.") from e

    def aggregate_rescue_availability(self) -> List[Dict[str, Any]]:
        """
        Return rescue availability statistics grouped by animal_type and outcome_type.
        """
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": {
                            "animal_type": "$animal_type",
                            "outcome_type": "$outcome_type",
                        },
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"count": -1}}
            ]

            logger.info("Running rescue availability aggregation pipeline.")
            return list(self.collection.aggregate(pipeline))
        except PyMongoError as e:
            logger.exception("Error aggregating rescue availability")
            raise AnimalShelterAnalyticsError("Failed to aggregate rescue availability.") from e
