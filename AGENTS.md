# DELTA OS - Development Guide

## Project Overview

DELTA OS is an institutional-grade quantitative trading operating system designed for professional traders, quantitative researchers, and sophisticated investors.

## Architecture

```
Delta/
├── cli/                    # OpenCode-style interactive TUI
│   ├── app.py            # Main CLI application
│   ├── completer.py      # Command autocomplete
│   ├── status_bar.py     # Status bar component
│   ├── formatter.py      # Rich formatting utilities
│   └── commands/         # Modular command handlers
├── core/                  # Foundation & security
│   ├── config.py         # Configuration management
│   ├── vault.py          # AES-256 encrypted credential vault
│   ├── events.py         # Event bus
│   ├── plugin_manager.py # Plugin system
│   ├── registry.py       # Model/broker registries
│   ├── anti_tilt.py      # Behavioral safeguards
│   └── audit.py          # Compliance ledger
├── data/                  # Market data engine
│   ├── router.py         # Fail-soft data router
│   ├── cache.py          # LRU cache
│   └── providers/        # Data providers
├── models/                # AI gateway
│   ├── router.py         # Multi-model router
│   └── providers/        # Model providers
├── quant/                 # Analytics engine
│   ├── vwap.py           # VWAP & bands
│   ├── risk_engine.py    # Risk calculations
│   └── sentiment_nlp.py  # Sentiment analysis
└── trading/               # Execution layer
    ├── broker_base.py    # Broker abstraction
    ├── order_types.py    # Order models
    ├── risk_governor.py  # Pre-trade risk checks
    ├── kill_switch.py    # Emergency controls
    └── adapters/         # Broker implementations
```

## Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize configuration
python -m delta.core.config init

# Run the CLI
python -m delta.cli.app
```

## Key Components

### Configuration System
- Centralized config in `~/.delta/config.yaml`
- Environment variable support
- Plugin-friendly architecture

### Credential Vault
- AES-256-GCM encryption
- PBKDF2 key derivation (600,000 rounds)
- Zero plaintext storage

### Plugin System
- Drop-in providers in `~/.delta/plugins/`
- Hot-reloading support
- Registry-based discovery

### Data Router
- Tri-tier failover architecture
- LRU caching with TTL
- Synthetic fallback for offline mode

### Model Gateway
- Multi-provider support (Ollama, Groq, OpenAI, etc.)
- Hot-swapping capability
- Role-based routing

### Risk Engine
- Kelly Criterion position sizing
- VaR/CVaR calculations
- Pre-trade governance

## Adding Custom Providers

### Custom Model Provider

1. Create file in `~/.delta/plugins/models/`
2. Inherit from `BaseModelProvider`
3. Implement required methods
4. Register in registry

### Custom Broker Adapter

1. Create file in `~/.delta/plugins/brokers/`
2. Inherit from `UniversalBrokerAdapter`
3. Implement required methods
4. Register in registry

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=delta

# Run specific test
pytest tests/test_vault.py
```

## Building

```bash
# Build package
python setup.py sdist bdist_wheel

# Install locally
pip install -e .
```

## Free Tier Options

DELTA OS supports zero-cost operation:

- **Models**: Ollama (local), Groq (free tier), HuggingFace (free tier)
- **Brokers**: Paper engine (built-in), Alpaca Paper
- **Data**: Yahoo Finance (free), FRED (free), Google News (free)

## Security Considerations

- All credentials encrypted with AES-256-GCM
- Audit trail for compliance
- Kill switch for emergency situations
- Anti-tilt behavioral safeguards

## Performance

- Sub-100ms quote latency
- LRU caching for frequently accessed data
- Async I/O throughout
- Zero-copy operations where possible

## Troubleshooting

### Vault Issues
- Delete `~/.delta/vault.bin` and `~/.delta/vault.salt` to reset
- Reinitialize with `/auth wizard`

### Model Connection Issues
- Check API key configuration
- Verify endpoint accessibility
- Check rate limits

### Data Provider Issues
- Verify network connectivity
- Check API key validity
- Review cache settings

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit pull request

## License

Proprietary - Institutional Use Only
