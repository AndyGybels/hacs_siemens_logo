# Development

## Project structure

```
hacs_siemens_logo/
├── custom_components/siemens_logo/
│   ├── __init__.py          # LogoConnection, async_setup_entry, service actions
│   ├── config_flow.py       # UI setup/options/reconfigure flows
│   ├── const.py             # Constants, VM maps, address utilities
│   ├── coordinator.py       # DataUpdateCoordinator (polling)
│   ├── entity.py            # Shared LogoEntity base class
│   ├── binary_sensor.py
│   ├── button.py
│   ├── number.py
│   ├── sensor.py
│   ├── switch.py
│   ├── manifest.json
│   ├── services.yaml
│   └── strings.json
├── tests/
│   ├── conftest.py
│   ├── test_const.py
│   ├── test_config_flow.py
│   ├── test_init.py
│   ├── test_switch.py
│   └── test_button.py
├── wiki/
├── .github/workflows/tests.yml
├── pytest.ini
├── requirements_test.txt
└── README.md
```

## Running the tests

```bash
pip install -r requirements_test.txt
pytest tests/ -v
```

The test suite does not require a physical PLC or the native `snap7` library — both are stubbed out in `conftest.py`.

## GitHub Actions

Tests run automatically on every push and pull request via `.github/workflows/tests.yml`.
