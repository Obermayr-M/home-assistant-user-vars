# Garage request example

This example demonstrates one possible consumer of User Variables:

1. A logged-in user toggles a personal `garage_request`.
2. The toggle script validates User → Person → Device Tracker → position.
3. A central automation processes all active requests every 10 seconds.
4. Expired requests are cleared.
5. When a requesting Person reaches the configured radius, a placeholder garage-opening script is called and the single-use request is cleared.

## Required setup

Create a Boolean definition in **User Variables → Configure**:

```text
Key: garage_request
Name: Garage Request
Type: Boolean
Default: false
```

Create two UI helpers:

```text
input_number.garage_request_radius       # metres, for example 75
input_number.garage_request_timeout      # minutes, for example 60
```

Replace these placeholders before use:

```text
script.open_garage_door
script.notify_garage_request_user
```

The example does not grant access rights. Add your own authorization checks, gate state validation, cooldown, location accuracy threshold, and fault handling before operating real equipment.
