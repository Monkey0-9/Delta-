# DELTA OS - Institutional Quantitative Trading Operating System

A professional-grade trading terminal and quantitative research platform designed for institutional traders, quantitative researchers, and sophisticated investors.

## Features

- **OpenCode-Style CLI**: Lightning-fast slash commands with fuzzy autocomplete
- **Multi-Model AI Gateway**: Hot-swap between Qwen, Claude, Gemini, GPT-4o, DeepSeek, and custom models
- **Tri-Tier Fail-Soft Data**: Yahoo Finance, FRED macro, Google News with zero-crash guarantee
- **Universal Broker Support**: Paper engine, Alpaca, IBKR, and extensible custom adapters
- **Quantitative Analytics**: VWAP bands, Kelly sizing, VaR/CVaR, volume profile
- **AES-256 Credential Vault**: Zero-knowledge encrypted storage for API keys
- **Triple-Layer Kill Switch**: Emergency order cancellation and position liquidation
- **Plugin Architecture**: Extensible system for custom models, brokers, and data providers

## Installation

```bash
# Clone repository
git clone https://github.com/your-org/delta-os.git
cd delta-os

# Install dependencies
pip install -r requirements.txt

# Initialize configuration
python -m delta.core.config init

# Launch DELTA OS
python -m delta.cli.app
```

## Quick Start

```bash
# Launch the terminal
python -m delta.cli.app

# Configure credentials
DELTA > /auth wizard

# Get a quote
DELTA > /quote NVDA

# View macro regime
DELTA > /macro yields

# Switch AI model
DELTA > /model switch qwen-3.6

# Track a stock
DELTA > /track add NVDA
```

## Architecture

```
Delta/
├── cli/           # OpenCode-style interactive TUI
├── core/          # Foundation & security subsystem
├── data/          # Tri-tier resilient market data engine
├── models/        # Multi-model AI gateway
├── quant/         # Institutional analytics & signals
└── trading/       # Broker abstraction & execution
```

## Free Tier Options

DELTA OS supports zero-cost trading and research:

- **Models**: Ollama (local), vLLM, HuggingFace Free, Groq Free
- **Brokers**: Paper engine (built-in), Alpaca Paper
- **Data**: Yahoo Finance, FRED, Google Finance News

## Plugin System

Add custom providers via plugin architecture:

```python
# ~/.delta/plugins/models/custom_provider.py
from delta.models.base_provider import BaseModelProvider

class CustomProvider(BaseModelProvider):
    def generate(self, prompt: str) -> str:
        # Your implementation
        pass
```

## Security

- AES-256-GCM encryption for all credentials
- PBKDF2 key derivation (600,000 rounds)
- Zero plaintext storage of API keys
- SHA-256 audit ledger for compliance

## License

Proprietary - Institutional Use Only

## Support

For institutional support: delta-support@institution.com
