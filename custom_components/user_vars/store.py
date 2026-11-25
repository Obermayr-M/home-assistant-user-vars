"""Persistent storage for User Variables."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


DEFAULT_DATA: dict[str, Any] = {
    "definitions": {},
    "users": {},
}


class UserVarsStore:
    """Store user-specific variables persistently."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""

        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
        )

        self.data: dict[str, Any] = {}

    async def async_load(self) -> None:
        """Load data from persistent storage."""

        stored_data = await self._store.async_load()

        if stored_data is None:
            self.data = deepcopy(DEFAULT_DATA)
            await self.async_save()
            return

        self.data = stored_data
        self.data.setdefault("definitions", {})
        self.data.setdefault("users", {})

    async def async_save(self) -> None:
        """Save data to persistent storage."""

        await self._store.async_save(self.data)

    def get_definition(self, key: str) -> dict[str, Any] | None:
        """Return a variable definition."""

        return self.data["definitions"].get(key)

    def validate_value(self, key: str, value: Any) -> Any:
        """Validate a value against its variable definition."""

        definition = self.get_definition(key)

        if definition is None:
            raise ValueError(f"Unknown user variable: {key}")

        variable_type = definition.get("type")

        if variable_type == "boolean":
            if isinstance(value, bool):
                return value

            if isinstance(value, str):
                normalized = value.strip().lower()

                if normalized == "true":
                    return True

                if normalized == "false":
                    return False

            raise ValueError(
                f"Variable '{key}' requires a boolean value"
            )

        if variable_type == "string":
            if not isinstance(value, str):
                raise ValueError(
                    f"Variable '{key}' requires a string value"
                )
            return value

        if variable_type == "integer":
            # bool is a subclass of int in Python, therefore reject it.
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"Variable '{key}' requires an integer value"
                )
            return value

        if variable_type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(
                    f"Variable '{key}' requires a numeric value"
                )
            return value

        raise ValueError(
            f"Unsupported type '{variable_type}' for variable '{key}'"
        )

    def get_user_value(
        self,
        user_id: str,
        key: str,
    ) -> Any:
        """Return a user value or the variable default."""

        definition = self.get_definition(key)

        if definition is None:
            raise ValueError(f"Unknown user variable: {key}")

        user_data = self.data["users"].get(user_id, {})

        if key in user_data:
            return user_data[key]["value"]

        return definition.get("default")

    def get_values_for_key(
        self,
        key: str,
    ) -> list[dict[str, Any]]:
        """Return all explicitly stored user values for a variable."""

        if self.get_definition(key) is None:
            raise ValueError(
                f"Unknown user variable: {key}"
            )

        result: list[dict[str, Any]] = []

        users = self.data.get("users", {})

        for user_id, user_data in users.items():
            stored_data = user_data.get(key)

            if stored_data is None:
                continue

            result.append(
                {
                    "user_id": user_id,
                    "value": stored_data.get("value"),
                    "updated_at": stored_data.get("updated_at"),
                }
            )

        return result

    async def async_set_user_value(
        self,
        user_id: str,
        key: str,
        value: Any,
    ) -> None:
        """Set a validated value for one user."""

        value = self.validate_value(key, value)

        users = self.data.setdefault("users", {})
        user_data = users.setdefault(user_id, {})

        user_data[key] = {
            "value": value,
            "updated_at": datetime.now().astimezone().isoformat(),
        }

        await self.async_save()

    async def async_clear_user_value(
        self,
        user_id: str,
        key: str,
    ) -> None:
        """Remove an explicit user value."""

        if self.get_definition(key) is None:
            raise ValueError(f"Unknown user variable: {key}")

        users = self.data.setdefault("users", {})
        user_data = users.get(user_id)

        if not user_data or key not in user_data:
            return

        del user_data[key]

        if not user_data:
            del users[user_id]

        await self.async_save()
        
    async def async_add_definition(
        self,
        key: str,
        name: str,
        variable_type: str,
        default: Any,
    ) -> None:
        """Add a new variable definition."""

        key = key.strip().lower()

        if not key:
            raise ValueError("Variable key must not be empty")

        if not key.replace("_", "").isalnum():
            raise ValueError(
                "Variable key may only contain letters, numbers, "
                "and underscores"
            )

        definitions = self.data.setdefault("definitions", {})

        if key in definitions:
            raise ValueError(
                f"Variable '{key}' already exists"
            )

        if variable_type not in {
            "boolean",
            "string",
            "integer",
            "number",
        }:
            raise ValueError(
                f"Unsupported variable type: {variable_type}"
            )

        temporary_definition = {
            "name": name.strip() or key,
            "type": variable_type,
            "default": default,
        }

        definitions[key] = temporary_definition

        try:
            validated_default = self.validate_value(key, default)
        except ValueError:
            del definitions[key]
            raise

        definitions[key]["default"] = validated_default

        await self.async_save()

    async def async_update_definition(
        self,
        key: str,
        name: str,
        default: Any,
    ) -> None:
        """Update the name and default value of a definition."""

        definition = self.get_definition(key)

        if definition is None:
            raise ValueError(
                f"Unknown user variable: {key}"
            )

        old_name = definition.get("name")
        old_default = definition.get("default")

        definition["name"] = name.strip() or key
        definition["default"] = default

        try:
            validated_default = self.validate_value(
                key,
                default,
            )
        except ValueError:
            definition["name"] = old_name
            definition["default"] = old_default
            raise

        definition["default"] = validated_default

        await self.async_save()

    async def async_delete_definition(
        self,
        key: str,
    ) -> None:
        """Delete a definition and all related user values."""

        definitions = self.data.setdefault(
            "definitions",
            {},
        )

        if key not in definitions:
            raise ValueError(
                f"Unknown user variable: {key}"
            )

        del definitions[key]

        users = self.data.setdefault("users", {})

        empty_users: list[str] = []

        for user_id, user_data in users.items():
            user_data.pop(key, None)

            if not user_data:
                empty_users.append(user_id)

        for user_id in empty_users:
            del users[user_id]

        await self.async_save()