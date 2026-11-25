"""Config flow for User Variables."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .store import UserVarsStore


VARIABLE_TYPES = {
    "boolean": "Boolean",
    "string": "String",
    "integer": "Integer",
    "number": "Number",
}

MANAGEMENT_ACTIONS = {
    "add_variable": "Add variable",
    "edit_variable": "Edit variable",
    "delete_variable": "Delete variable",
    "about": "About",
}


def _convert_default_value(
    variable_type: str,
    value: Any,
) -> Any:
    """Convert the default value entered in the UI."""

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
            "Boolean default must be true or false"
        )

    if variable_type == "integer":
        if isinstance(value, bool):
            raise ValueError(
                "Integer default must be a whole number"
            )

        try:
            return int(value)
        except (TypeError, ValueError) as err:
            raise ValueError(
                "Integer default must be a whole number"
            ) from err

    if variable_type == "number":
        if isinstance(value, bool):
            raise ValueError(
                "Number default must be numeric"
            )

        try:
            return float(value)
        except (TypeError, ValueError) as err:
            raise ValueError(
                "Number default must be numeric"
            ) from err

    if variable_type == "string":
        return str(value)

    raise ValueError(
        f"Unsupported variable type: {variable_type}"
    )


class UserVarsConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for User Variables."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Create the single User Variables instance."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="User Variables",
            data={},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""

        return UserVarsOptionsFlow()


class UserVarsOptionsFlow(config_entries.OptionsFlow):
    """Manage User Variables definitions."""

    def __init__(self) -> None:
        """Initialize the options flow."""

        self._selected_key: str | None = None

    def _get_store(self) -> UserVarsStore:
        """Return the store for the config entry."""

        return self.hass.data[DOMAIN][
            self.config_entry.entry_id
        ]

    def _definition_choices(self) -> dict[str, str]:
        """Return variable definitions for selection forms."""

        store = self._get_store()
        definitions = store.data.get("definitions", {})

        return {
            key: f"{definition.get('name', key)} ({key})"
            for key, definition in definitions.items()
        }

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Show the variable management form."""

        if user_input is not None:
            action = user_input["action"]

            if action == "add_variable":
                return await self.async_step_add_variable()

            if action == "edit_variable":
                return await self.async_step_select_edit_variable()

            if action == "delete_variable":
                return await self.async_step_select_delete_variable()

            if action == "about":
                return await self.async_step_about()

        schema = vol.Schema(
            {
                vol.Required(
                    "action",
                    default="add_variable",
                ): vol.In(MANAGEMENT_ACTIONS),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

    async def async_step_add_variable(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Add a variable definition."""

        errors: dict[str, str] = {}

        if user_input is not None:
            key = user_input["key"].strip().lower()
            name = user_input["name"].strip()
            variable_type = user_input["type"]
            raw_default = user_input["default"]

            try:
                default = _convert_default_value(
                    variable_type,
                    raw_default,
                )

                await self._get_store().async_add_definition(
                    key=key,
                    name=name,
                    variable_type=variable_type,
                    default=default,
                )

            except ValueError as err:
                if "already exists" in str(err):
                    errors["key"] = "variable_already_exists"
                else:
                    errors["base"] = "invalid_variable"

            else:
                return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required("key"): str,
                vol.Required("name"): str,
                vol.Required(
                    "type",
                    default="boolean",
                ): vol.In(VARIABLE_TYPES),
                vol.Required(
                    "default",
                    default="false",
                ): str,
            }
        )

        return self.async_show_form(
            step_id="add_variable",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_select_edit_variable(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Select a variable to edit."""

        choices = self._definition_choices()

        if not choices:
            return self.async_abort(
                reason="no_variables"
            )

        if user_input is not None:
            self._selected_key = user_input["key"]
            return await self.async_step_edit_variable()

        schema = vol.Schema(
            {
                vol.Required("key"): vol.In(choices),
            }
        )

        return self.async_show_form(
            step_id="select_edit_variable",
            data_schema=schema,
        )

    async def async_step_edit_variable(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Edit a variable definition."""

        if self._selected_key is None:
            return await self.async_step_init()

        store = self._get_store()
        definition = store.get_definition(
            self._selected_key
        )

        if definition is None:
            return self.async_abort(
                reason="variable_not_found"
            )

        errors: dict[str, str] = {}
        variable_type = definition["type"]

        if user_input is not None:
            try:
                default = _convert_default_value(
                    variable_type,
                    user_input["default"],
                )

                await store.async_update_definition(
                    key=self._selected_key,
                    name=user_input["name"],
                    default=default,
                )

            except ValueError:
                errors["base"] = "invalid_variable"

            else:
                self._selected_key = None
                return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(
                    "name",
                    default=definition.get(
                        "name",
                        self._selected_key,
                    ),
                ): str,
                vol.Required(
                    "default",
                    default=str(
                        definition.get("default", "")
                    ).lower(),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="edit_variable",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "key": self._selected_key,
                "type": variable_type,
            },
        )

    async def async_step_select_delete_variable(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Select a variable to delete."""

        choices = self._definition_choices()

        if not choices:
            return self.async_abort(
                reason="no_variables"
            )

        if user_input is not None:
            self._selected_key = user_input["key"]
            return await self.async_step_delete_variable()

        schema = vol.Schema(
            {
                vol.Required("key"): vol.In(choices),
            }
        )

        return self.async_show_form(
            step_id="select_delete_variable",
            data_schema=schema,
        )

    async def async_step_delete_variable(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Confirm and delete a variable."""

        if self._selected_key is None:
            return await self.async_step_init()

        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input["confirm"]:
                errors["base"] = "delete_not_confirmed"
            else:
                try:
                    await self._get_store().async_delete_definition(
                        self._selected_key
                    )
                except ValueError:
                    errors["base"] = "invalid_variable"
                else:
                    self._selected_key = None
                    return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(
                    "confirm",
                    default=False,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="delete_variable",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "key": self._selected_key,
            },
        )

    async def async_step_about(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Show information about User Variables."""

        if user_input is not None:
            return await self.async_step_init()

        store = self._get_store()

        definitions_count = len(
            store.data.get("definitions", {})
        )

        users_count = len(
            store.data.get("users", {})
        )

        return self.async_show_form(
            step_id="about",
            data_schema=vol.Schema({}),
            description_placeholders={
                "version": "0.1.0",
                "author": "Markus Obermayr",
                "github": "@Obermayr-M",
                "license": "MIT",
                "definitions": str(definitions_count),
                "users": str(users_count),
            },
        )
