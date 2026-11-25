# Contributing

Thank you for considering a contribution.

## Before opening a pull request

1. Open an issue describing the bug or proposed behavior.
2. Keep the integration generic. Application-specific workflows belong in `examples/`.
3. Do not include real Home Assistant user IDs, addresses, coordinates, access-control entities, logs, or `.storage` content.
4. Preserve backward compatibility with existing storage whenever possible.
5. Update `README.md`, translations, and `CHANGELOG.md` when behavior changes.

## Validation

```bash
python3 -m py_compile custom_components/user_vars/*.py
python3 -m json.tool custom_components/user_vars/manifest.json >/dev/null
python3 -m json.tool custom_components/user_vars/strings.json >/dev/null
python3 -m json.tool custom_components/user_vars/translations/de.json >/dev/null
python3 -m json.tool custom_components/user_vars/translations/en.json >/dev/null
```

Test changes in a non-production Home Assistant instance before using them in access-control or safety-related automations.
