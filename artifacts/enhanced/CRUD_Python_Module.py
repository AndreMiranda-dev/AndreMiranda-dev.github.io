# This module provides secure CRUD operations and database analytics for the AAC animals collection
# Created by Andre Miranda

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


class AnimalShelterAggregationError(AnimalShelterError):
    """Raised when aggregation pipeline operations fail."""
    pass


class AnimalShelter(object):
    """
    Secure CRUD operations for the AAC 'animals' collection with safe operator support.

    This class encapsulates all database interactions, including:
    - Authentication
    - Query validation
    - CRUD operations
    - Rescue filter queries
    - Aggregation pipelines
    - Index and schema management
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
        "rescue_score",
    }

    SAFE_OPERATORS = {
        "$in", "$gte", "$lte", "$gt", "$lt", "$eq", "$ne", "$regex", "$options"
    }

    # ---------------------------------------------------------
    # INITIALIZATION
    # ---------------------------------------------------------
    # This function initializes the MongoDB connection and applies schema/index enhancements
    # Created by Andre Miranda
    def __init__(self, username: str, password: str):
        """Initialize MongoDB connection, authenticate, and apply schema/index enhancements."""
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

            # Apply schema validation and indexes as part of database enhancement
            self._apply_schema_validation()
            self._ensure_indexes()

        except PyMongoError as e:
            logger.exception("Error connecting to MongoDB")
            raise AnimalShelterConnectionError("Failed to connect to MongoDB.") from e

    # ---------------------------------------------------------
    # CONNECTION HEALTH CHECK
    # ---------------------------------------------------------
    # This function checks if the MongoDB connection is healthy
    # Created by Andre Miranda
    def is_connected(self) -> bool:
        """Return True if the MongoDB connection is active."""
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    # This function returns basic health information for diagnostics
    # Created by Andre Miranda
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
    # INTERNAL DATABASE ENHANCEMENTS
    # ---------------------------------------------------------
    # This function applies MongoDB JSON schema validation to the animals collection
    # Created by Andre Miranda
    def _apply_schema_validation(self) -> None:
        """Apply JSON schema validation to the animals collection."""
        try:
            validator = {
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": ["name", "animal_type", "breed", "outcome_type"],
                    "properties": {
                        "name": {"bsonType": "string"},
                        "animal_type": {"bsonType": "string"},
                        "breed": {"bsonType": "string"},
                        "outcome_type": {"bsonType": "string"},
                        "age_upon_outcome_in_weeks": {"bsonType": ["int", "double", "null"]},
                    }
                }
            }

            # Example comment: use collMod to update existing collection validator
            self.database.command({
                "collMod": self.COLLECTION_NAME,
                "validator": validator,
                "validationLevel": "moderate"
            })

            logger.info(
                "Schema validation applied to collection '%s'.",
                self.COLLECTION_NAME
            )
        except PyMongoError:
            # Example comment: schema validation may already exist or collMod may not be allowed
            logger.warning("Schema validation could not be applied (collMod may not be available).")

    # This function ensures indexes on frequently queried fields
    # Created by Andre Miranda
    def _ensure_indexes(self) -> None:
        """Ensure indexes on common query fields for performance."""
        index_fields = [
            "breed",
            "animal_type",
            "outcome_type",
            "age_upon_outcome_in_weeks",
            "sex_upon_outcome",
        ]

        for field in index_fields:
            try:
                self.collection.create_index(field)
                logger.info("Index ensured on field: %s", field)
            except PyMongoError:
                logger.warning("Failed to create index on field: %s", field)

    # ---------------------------------------------------------
    # INTERNAL VALIDATION HELPERS
    # ---------------------------------------------------------
    # This function validates query dictionaries and safe operators
    # Created by Andre Miranda
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

    # This function validates update dictionaries for allowed fields
    # Created by Andre Miranda
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
    # CRUD OPERATIONS
    # ---------------------------------------------------------
    # This function handles document creation in the animals collection
    # Created by Andre Miranda
    def create(self, data: Dict[str, Any]) -> bool:
        """Insert a document into the collection."""
        self._validate_update_values(data)

        if "name" not in data or not isinstance(data["name"], str):
            raise AnimalShelterValidationError("Missing required field: 'name' (must be a string).")

        if "animal_type" not in data or not isinstance(data["animal_type"], str):
            raise AnimalShelterValidationError("Missing required field: 'animal_type' (must be a string).")

        if "breed" not in data or not isinstance(data["breed"], str):
            raise AnimalShelterValidationError("Missing required field: 'breed' (must be a string).")

        if "outcome_type" not in data or not isinstance(data["outcome_type"], str):
            raise AnimalShelterValidationError("Missing required field: 'outcome_type' (must be a string).")

        try:
            result = self.collection.insert_one(data)
            logger.info("Document inserted with ID: %s", result.inserted_id)
            return result.acknowledged
        except PyMongoError as e:
            logger.exception("Error inserting document")
            raise AnimalShelterCrudError("Failed to insert document.") from e

        # Example comment: create returns True/False based on acknowledgment

    # This function handles reading documents based on a query
    # Created by Andre Miranda
    def read(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Read documents matching a query."""
        self._validate_query(query)
        try:
            return list(self.collection.find(query))
        except PyMongoError as e:
            logger.exception("Error reading documents")
            raise AnimalShelterCrudError("Failed to read documents.") from e

    # This function returns all documents in the animals collection
    # Created by Andre Miranda
    def read_all(self) -> List[Dict[str, Any]]:
        """Return all documents."""
        try:
            return list(self.collection.find({}))
        except PyMongoError as e:
            logger.exception("Error reading all documents")
            raise AnimalShelterCrudError("Failed to read all documents.") from e

    # This function updates documents matching a query
    # Created by Andre Miranda
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

    # This function deletes documents matching a query
    # Created by Andre Miranda
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
    # This function handles rescue filtering for water rescue
    # Created by Andre Miranda
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

    # This function handles rescue filtering for mountain/wilderness rescue
    # Created by Andre Miranda
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

    # This function handles rescue filtering for disaster/tracking rescue
    # Created by Andre Miranda
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
    # AGGREGATION PIPELINES (DATABASE ENHANCEMENT)
    # ---------------------------------------------------------
    # This function returns breed distribution using a MongoDB aggregation pipeline
    # Created by Andre Miranda
    def aggregate_breed_distribution(self) -> List[Dict[str, Any]]:
        """Aggregate breed distribution counts."""
        pipeline = [
            {"$group": {"_id": "$breed", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        try:
            return list(self.collection.aggregate(pipeline))
        except PyMongoError as e:
            logger.exception("Error running breed distribution aggregation")
            raise AnimalShelterAggregationError("Breed distribution aggregation failed.") from e

    # This function returns outcome statistics using a MongoDB aggregation pipeline
    # Created by Andre Miranda
    def aggregate_outcome_statistics(self) -> List[Dict[str, Any]]:
        """Aggregate outcome type statistics."""
        pipeline = [
            {"$group": {"_id": "$outcome_type", "total": {"$sum": 1}}},
            {"$sort": {"total": -1}}
        ]
        try:
            return list(self.collection.aggregate(pipeline))
        except PyMongoError as e:
            logger.exception("Error running outcome statistics aggregation")
            raise AnimalShelterAggregationError("Outcome statistics aggregation failed.") from e

    # This function returns age statistics using a MongoDB aggregation pipeline
    # Created by Andre Miranda
    def aggregate_age_statistics(self) -> List[Dict[str, Any]]:
        """Aggregate age statistics in weeks."""
        pipeline = [
            {
                "$match": {
                    "age_upon_outcome_in_weeks": {"$ne": None}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_weeks": {"$avg": "$age_upon_outcome_in_weeks"},
                    "min_weeks": {"$min": "$age_upon_outcome_in_weeks"},
                    "max_weeks": {"$max": "$age_upon_outcome_in_weeks"},
                }
            }
        ]
        try:
            return list(self.collection.aggregate(pipeline))
        except PyMongoError as e:
            logger.exception("Error running age statistics aggregation")
            raise AnimalShelterAggregationError("Age statistics aggregation failed.") from e

    # This function returns rescue availability statistics using a MongoDB aggregation pipeline
    # Created by Andre Miranda
    def aggregate_rescue_availability(self) -> List[Dict[str, Any]]:
        """Aggregate counts of animals by type and outcome."""
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "animal_type": "$animal_type",
                        "outcome_type": "$outcome_type"
                    },
                    "total": {"$sum": 1}
                }
            },
            {"$sort": {"total": -1}}
        ]
        try:
            return list(self.collection.aggregate(pipeline))
        except PyMongoError as e:
            logger.exception("Error running rescue availability aggregation")
            raise AnimalShelterAggregationError("Rescue availability aggregation failed.") from e
