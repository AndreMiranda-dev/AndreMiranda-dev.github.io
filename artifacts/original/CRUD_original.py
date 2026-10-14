# Project Two Andre Miranda
# CRUD_Python_Module.py

from pymongo import MongoClient
from pymongo.errors import PyMongoError


class AnimalShelter(object):
    """Secure CRUD operations for the AAC 'animals' collection with safe operator support."""

    # ---------------------------------------------------------
    # CONFIGURATION
    # ---------------------------------------------------------
    HOST = "localhost"
    PORT = 27017
    DB_NAME = "aac"
    COLLECTION_NAME = "animals"

    # Allowed document fields
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
        "numeric_field"
    }

    # Safe MongoDB operators
    SAFE_OPERATORS = {
        "$in", "$gte", "$lte", "$gt", "$lt", "$eq", "$ne", "$regex", "$options"

    }

    def __init__(self, username, password):
        """Initialize MongoDB connection and authenticate."""
        if not username or not isinstance(username, str):
            raise ValueError("Username must be a non-empty string.")

        if not password or not isinstance(password, str):
            raise ValueError("Password must be a non-empty string.")

        try:
            # Establish authenticated connection
            self.client = MongoClient(
                f"mongodb://{username}:{password}@{self.HOST}:{self.PORT}/?authSource={self.DB_NAME}"
            )
            self.client.admin.command("ping")  # Connection test

            # Validate database and collection
            self.database = self.client[self.DB_NAME]
            if self.COLLECTION_NAME not in self.database.list_collection_names():
                raise RuntimeError(
                    f"Collection '{self.COLLECTION_NAME}' does not exist in database '{self.DB_NAME}'."
                )

            self.collection = self.database[self.COLLECTION_NAME]

            print(
                f"[Connection Successful] Authenticated as '{username}' → "
                f"Database: '{self.DB_NAME}', Collection: '{self.COLLECTION_NAME}'"
            )

        except PyMongoError as e:
            print("Error connecting to MongoDB:", e)
            raise

    # ---------------------------------------------------------
    # INTERNAL VALIDATION HELPERS
    # ---------------------------------------------------------
    def _validate_query(self, query):
        """Validate query fields and safe operators."""
        if not isinstance(query, dict):
            raise TypeError("Query must be a dictionary.")

        if not query:
            return  # allow empty query for read_all()

        for key, value in query.items():

            # Operator case
            if key.startswith("$"):
                if key not in self.SAFE_OPERATORS:
                    raise ValueError(f"MongoDB operator '{key}' is not allowed.")
                continue

            # Field case
            if key not in self.ALLOWED_FIELDS:
                raise ValueError(f"Field '{key}' is not allowed in queries.")

            # If value is a dict, validate nested operators
            if isinstance(value, dict):
                for op in value.keys():
                    if op not in self.SAFE_OPERATORS:
                        raise ValueError(f"Operator '{op}' is not allowed.")

    def _validate_update_values(self, new_values):
        """Validate update fields and safe operators."""
        if not isinstance(new_values, dict):
            raise TypeError("Update values must be a dictionary.")

        if not new_values:
            raise ValueError("Update values cannot be empty.")

        for key in new_values.keys():
            if key.startswith("$"):
                raise ValueError("Update cannot contain MongoDB operators directly.")

            if key not in self.ALLOWED_FIELDS:
                raise ValueError(f"Field '{key}' is not allowed in updates.")

    # ---------------------------------------------------------
    # CRUD OPERATIONS
    # ---------------------------------------------------------
    def create(self, data):
        """Insert a document into the collection."""
        if not isinstance(data, dict) or not data:
            raise ValueError("Data must be a non-empty dictionary.")

        # Required field validation
        if "name" not in data or not isinstance(data["name"], str):
            raise ValueError("Missing required field: 'name' (must be a string).")

        try:
            result = self.collection.insert_one(data)
            return result.acknowledged
        except PyMongoError as e:
            print("Error inserting document:", e)
            return False

    def read(self, query):
        """Read documents matching a query."""
        self._validate_query(query)
        try:
            return list(self.collection.find(query))
        except PyMongoError as e:
            print("Error reading documents:", e)
            return []

    def read_all(self):
        """Return all documents."""
        try:
            return list(self.collection.find({}))
        except PyMongoError as e:
            print("Error reading all documents:", e)
            return []

    def update(self, query, new_values):
        """Update documents matching a query."""
        self._validate_query(query)
        self._validate_update_values(new_values)

        try:
            result = self.collection.update_many(query, {"$set": new_values})
            return result.modified_count
        except PyMongoError as e:
            print("Error updating documents:", e)
            return 0

    def delete(self, query):
        """Delete documents matching a query."""
        self._validate_query(query)
        try:
            result = self.collection.delete_many(query)
            return result.deleted_count
        except PyMongoError as e:
            print("Error deleting documents:", e)
            return 0

    # ---------------------------------------------------------
    # RESCUE FILTER QUERIES
    # Based on the "Rescue Type & Preferred Dog Breeds" table
    # from the Dashboard Specification Document.
    # ---------------------------------------------------------

    def filter_water_rescue(self):
        """Return dogs suitable for Water Rescue using regex breed matching."""
        query = {
            "breed": {
                "$regex": r"(labrador|lab|chesapeake|newfoundland)",
                "$options": "i"
            },
            "sex_upon_outcome": "Intact Female",
            "age_upon_outcome_in_weeks": {"$gte": 26, "$lte": 156}
        }
        return self.read(query)

    def filter_mountain_rescue(self):
        """Return dogs suitable for Mountain/Wilderness Rescue using regex breed matching."""
        query = {
            "breed": {
                "$regex": r"(german|shepherd|malamute|sheepdog|husky|rottweiler)",
                "$options": "i"
            },
            "sex_upon_outcome": "Intact Male",
            "age_upon_outcome_in_weeks": {"$gte": 26, "$lte": 156}
        }
        return self.read(query)

    def filter_disaster_rescue(self):
        """Return dogs suitable for Disaster/Tracking Rescue using regex breed matching."""
        query = {
            "breed": {
                "$regex": r"(doberman|pinscher|german|shepherd|golden|retriever|bloodhound|rottweiler)",
                "$options": "i"
            },
            "sex_upon_outcome": "Intact Male",
            "age_upon_outcome_in_weeks": {"$gte": 20, "$lte": 300}
        }
        return self.read(query)
