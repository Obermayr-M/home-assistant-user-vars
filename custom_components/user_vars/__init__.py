"""User Variables integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .store import UserVarsStore

_LOGGER = logging.getLogger(__name__)

SERVICE_SET = "set"
SERVICE_TOGGLE = "toggle"
SERVICE_CLEAR = "clear"
SERVICE_GET = "get"
SERVICE_LIST_VALUES = "list_values"
SERVICE_CLEAR_FOR_USER = "clear_for_user"

ATTR_KEY = "key"
ATTR_VALUE = "value"
ATTR_USER_ID = "user_id"

SET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_KEY): vol.All(str, vol.Length(min=1)),
        vol.Required(ATTR_VALUE): vol.Any(
            bool,
            int,
            float,
            str,
        ),
    }
)

KEY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_KEY): vol.All(str, vol.Length(min=1)),
    }
)

USER_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_USER_ID): vol.All(
            str,
            vol.Length(min=1),
        ),
        vol.Required(ATTR_KEY): vol.All(
            str,
            vol.Length(min=1),
        ),
    }
)


def _require_user_id(call: ServiceCall) -> str:
    """Return the calling user ID or raise an error."""

    user_id = call.context.user_id

    if user_id is None:
        raise ServiceValidationError(
            "The action requires a Home Assistant user context. "
            "Call it directly from a logged-in user's dashboard."
        )

    return user_id


async def _require_admin_or_internal(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Require an administrator or an internal service call."""

    user_id = call.context.user_id

    # Time-based automations and other internal calls can have no user context.
    if user_id is None:
        return

    user = await hass.auth.async_get_user(user_id)

    if user is None or not user.is_admin:
        raise ServiceValidationError(
            "This action requires a Home Assistant administrator."
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up User Variables from a config entry."""

    store = UserVarsStore(hass)
    await store.async_load()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = store

    async def handle_set(call: ServiceCall) -> ServiceResponse:
        """Set a variable for the calling user."""

        user_id = _require_user_id(call)

        key: str = call.data[ATTR_KEY]
        value: Any = call.data[ATTR_VALUE]

        try:
            await store.async_set_user_value(
                user_id=user_id,
                key=key,
                value=value,
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

        _LOGGER.info(
            "User variable '%s' set for user '%s'",
            key,
            user_id,
        )

        return {
            "user_id": user_id,
            "key": key,
            "value": store.get_user_value(user_id, key),
        }

    async def handle_toggle(call: ServiceCall) -> ServiceResponse:
        """Toggle a boolean variable for the calling user."""

        user_id = _require_user_id(call)
        key: str = call.data[ATTR_KEY]

        definition = store.get_definition(key)

        if definition is None:
            raise ServiceValidationError(
                f"Unknown user variable: {key}"
            )

        if definition.get("type") != "boolean":
            raise ServiceValidationError(
                f"Variable '{key}' is not boolean and cannot be toggled"
            )

        try:
            current_value = store.get_user_value(user_id, key)

            if not isinstance(current_value, bool):
                raise ServiceValidationError(
                    f"Variable '{key}' does not currently contain "
                    "a boolean value"
                )

            new_value = not current_value

            await store.async_set_user_value(
                user_id=user_id,
                key=key,
                value=new_value,
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

        _LOGGER.info(
            "User variable '%s' toggled to '%s' for user '%s'",
            key,
            new_value,
            user_id,
        )

        return {
            "user_id": user_id,
            "key": key,
            "value": new_value,
        }

    async def handle_clear(call: ServiceCall) -> ServiceResponse:
        """Clear a variable for the calling user."""

        user_id = _require_user_id(call)
        key: str = call.data[ATTR_KEY]

        try:
            await store.async_clear_user_value(
                user_id=user_id,
                key=key,
            )

            effective_value = store.get_user_value(user_id, key)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

        _LOGGER.info(
            "User variable '%s' cleared for user '%s'",
            key,
            user_id,
        )

        return {
            "user_id": user_id,
            "key": key,
            "value": effective_value,
        }

    async def handle_get(call: ServiceCall) -> ServiceResponse:
        """Get a variable for the calling user."""

        user_id = _require_user_id(call)
        key: str = call.data[ATTR_KEY]

        try:
            value = store.get_user_value(user_id, key)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

        user_data = store.data.get("users", {}).get(user_id, {})
        stored_data = user_data.get(key)

        is_default = stored_data is None

        return {
            "user_id": user_id,
            "key": key,
            "value": value,
            "is_default": is_default,
            "updated_at": (
                stored_data.get("updated_at")
                if stored_data is not None
                else None
            ),
        }

    async def handle_list_values(
        call: ServiceCall,
    ) -> ServiceResponse:
        """List explicitly stored values for one variable."""

        await _require_admin_or_internal(hass, call)

        key: str = call.data[ATTR_KEY]

        try:
            values = store.get_values_for_key(key)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

        return {
            "key": key,
            "count": len(values),
            "values": values,
        }

    async def handle_clear_for_user(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Clear a variable for a specific user."""

        await _require_admin_or_internal(hass, call)

        user_id: str = call.data[ATTR_USER_ID]
        key: str = call.data[ATTR_KEY]

        user = await hass.auth.async_get_user(user_id)

        if user is None:
            raise ServiceValidationError(
                f"Unknown Home Assistant user: {user_id}"
            )

        try:
            await store.async_clear_user_value(
                user_id=user_id,
                key=key,
            )

            effective_value = store.get_user_value(
                user_id,
                key,
            )

        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

        _LOGGER.info(
            "User variable '%s' cleared for user '%s' "
            "by administrative action",
            key,
            user_id,
        )

        return {
            "user_id": user_id,
            "key": key,
            "value": effective_value,
        }


    hass.services.async_register(
        DOMAIN,
        SERVICE_SET,
        handle_set,
        schema=SET_SCHEMA,
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TOGGLE,
        handle_toggle,
        schema=KEY_SCHEMA,
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR,
        handle_clear,
        schema=KEY_SCHEMA,
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET,
        handle_get,
        schema=KEY_SCHEMA,
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_VALUES,
        handle_list_values,
        schema=KEY_SCHEMA,
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_FOR_USER,
        handle_clear_for_user,
        schema=USER_KEY_SCHEMA,
        supports_response=True,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload User Variables."""

    for service in (
        SERVICE_SET,
        SERVICE_TOGGLE,
        SERVICE_CLEAR,
        SERVICE_GET,
        SERVICE_LIST_VALUES,
        SERVICE_CLEAR_FOR_USER,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)

    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop(entry.entry_id, None)

    if not domain_data:
        hass.data.pop(DOMAIN, None)

    return True