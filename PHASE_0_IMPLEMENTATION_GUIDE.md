# PHASE 0 Implementation Guide — DELTA Operating-System Architecture
## Weeks 1-2: Building the DELTA Terminal

**Objective:** Create the DELTA terminal that users can launch by typing `delta` and get a working finance intelligence interface.

**Timeline:** 2 weeks (14 days)
**Priority:** CRITICAL — This is the product face

---

## DAY 1: Project Setup & Terminal Entry Point

### Goal: Create the basic `delta` command that launches the terminal

### Tasks:

#### 1.1 Create CLI Directory Structure
```bash
mkdir -p cli
touch cli/__init__.py
```

#### 1.2 Create Terminal Entry Point
**File:** `cli/terminal.py`

```python
"""
DELTA Terminal Entry Point
Main entry point for the DELTA finance intelligence terminal.
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

from cli.repl import DeltaREPL
from cli.session_manager import SessionManager
from cli.audit_logger import AuditLogger
from config.config import load_config


class DeltaTerminal:
    """Main DELTA terminal class"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize terminal"""
        self.config = load_config(config_path)
        self.session = SessionManager(self.config)
        self.audit = AuditLogger(self.config)
        self.repl: Optional[DeltaREPL] = None
        
    def startup(self):
        """Execute startup sequence"""
        # Load configuration
        print("Loading configuration...")
        
        # Load user mandate
        print("Loading user mandate...")
        
        # Load portfolio context
        print("Loading portfolio context...")
        
        # Load provider configuration
        print("Loading provider configuration...")
        
        # Check data availability
        print("Checking data availability...")
        
        # Check model availability
        print("Checking model availability...")
        
        # Check broker status
        print("Checking broker status...")
        
        # Initialize REPL
        self.repl = DeltaREPL(self.session, self.audit)
        
    def run(self):
        """Run the terminal"""
        self.startup()
        self.repl.run()
        
    def shutdown(self):
        """Execute shutdown sequence"""
        print("Shutting down DELTA terminal...")
        self.session.cleanup()
        self.audit.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="DELTA Finance Intelligence Terminal")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--version", action="store_true", help="Show version")
    
    args = parser.parse_args()
    
    if args.version:
        print("DELTA Terminal v0.1.0")
        return
    
    try:
        terminal = DeltaTerminal(args.config)
        terminal.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        terminal.shutdown()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

#### 1.3 Update pyproject.toml
Add entry point for `delta` command:

```toml
[project.scripts]
delta = "cli.terminal:main"
```

#### 1.4 Test Basic Terminal
```bash
# Install in development mode
pip install -e .

# Test delta command
delta --version
```

**Expected Output:**
```
DELTA Terminal v0.1.0
```

---

## DAY 2: Interactive REPL

### Goal: Create the read-eval-print loop for the terminal

### Tasks:

#### 2.1 Create REPL Component
**File:** `cli/repl.py`

```python
"""
DELTA Interactive REPL
Read-eval-print loop for the DELTA terminal.
"""

import sys
from typing import Optional
from cli.session_manager import SessionManager
from cli.audit_logger import AuditLogger
from cli.command_parser import CommandParser
from cli.intent_resolver import IntentResolver
from cli.response_formatter import ResponseFormatter


class DeltaREPL:
    """DELTA interactive REPL"""
    
    def __init__(self, session: SessionManager, audit: AuditLogger):
        """Initialize REPL"""
        self.session = session
        self.audit = audit
        self.parser = CommandParser()
        self.resolver = IntentResolver()
        self.formatter = ResponseFormatter()
        self.running = False
        
    def display_banner(self):
        """Display welcome banner"""
        banner = """
╭─────────────────────────────────────────────────────────────╮
│                         DELTA                               │
│             Finance Intelligence & Trading OS              │
╰─────────────────────────────────────────────────────────────╯
"""
        print(banner)
        
    def display_prompt(self):
        """Display command prompt"""
        return "DELTA> "
        
    def read_input(self) -> str:
        """Read user input"""
        try:
            return input(self.display_prompt())
        except EOFError:
            return "exit"
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit")
            return ""
            
    def eval_input(self, user_input: str) -> str:
        """Evaluate user input"""
        if not user_input.strip():
            return ""
            
        # Log command
        self.audit.log_command(user_input)
        
        # Parse command
        command = self.parser.parse(user_input)
        
        # Resolve intent
        intent = self.resolver.resolve(command, self.session)
        
        # Execute intent (placeholder for now)
        response = f"Processed: {intent}"
        
        # Log response
        self.audit.log_response(response)
        
        return response
        
    def print_output(self, output: str):
        """Print output"""
        if output:
            print(output)
            
    def run(self):
        """Run REPL loop"""
        self.running = True
        self.display_banner()
        
        while self.running:
            try:
                user_input = self.read_input()
                
                if user_input.lower() in ["exit", "quit"]:
                    self.running = False
                    continue
                    
                output = self.eval_input(user_input)
                self.print_output(output)
                
            except Exception as e:
                print(f"Error: {e}")
                self.audit.log_error(e)
```

#### 2.2 Create Session Manager
**File:** `cli/session_manager.py`

```python
"""
Session Manager
Manage terminal session state and context.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import uuid


class SessionManager:
    """Manage terminal session"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize session"""
        self.config = config
        self.session_id = str(uuid.uuid4())
        self.start_time = datetime.now()
        self.context: Dict[str, Any] = {}
        self.history: list = []
        
    def get_session_id(self) -> str:
        """Get session ID"""
        return self.session_id
        
    def get_context(self, key: str) -> Optional[Any]:
        """Get context value"""
        return self.context.get(key)
        
    def set_context(self, key: str, value: Any):
        """Set context value"""
        self.context[key] = value
        
    def add_to_history(self, entry: str):
        """Add entry to history"""
        self.history.append(entry)
        
    def get_history(self) -> list:
        """Get history"""
        return self.history
        
    def cleanup(self):
        """Cleanup session"""
        self.context.clear()
        self.history.clear()
```

#### 2.3 Create Audit Logger
**File:** `cli/audit_logger.py`

```python
"""
Audit Logger
Log all terminal activity for audit trail.
"""

from typing import Dict, Any
from datetime import datetime
from pathlib import Path
import json


class AuditLogger:
    """Audit logger for terminal activity"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize audit logger"""
        self.config = config
        self.log_file = Path(config.get("audit_log", "audit.log"))
        self.entries: list = []
        
    def log_command(self, command: str):
        """Log command"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "command",
            "content": command
        }
        self.entries.append(entry)
        self._write_entry(entry)
        
    def log_response(self, response: str):
        """Log response"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "response",
            "content": response
        }
        self.entries.append(entry)
        self._write_entry(entry)
        
    def log_error(self, error: Exception):
        """Log error"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "error",
            "content": str(error)
        }
        self.entries.append(entry)
        self._write_entry(entry)
        
    def _write_entry(self, entry: Dict[str, Any]):
        """Write entry to log file"""
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
            
    def close(self):
        """Close audit logger"""
        # Flush any remaining entries
        pass
```

#### 2.4 Test REPL
```bash
# Run delta
delta

# Test basic interaction
DELTA> help
DELTA> test
DELTA> exit
```

**Expected Output:**
```
╭─────────────────────────────────────────────────────────────╮
│                         DELTA                               │
│             Finance Intelligence & Trading OS              │
╰─────────────────────────────────────────────────────────────╯

DELTA> help
Processed: Intent(type='help', params={})
DELTA> test
Processed: Intent(type='unknown', params={})
DELTA> exit
```

---

## DAY 3: Command Parser

### Goal: Parse both explicit commands and natural language input

### Tasks:

#### 3.1 Create Command Parser
**File:** `cli/command_parser.py`

```python
"""
Command Parser
Parse explicit commands and natural language input.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import re


@dataclass
class Command:
    """Parsed command"""
    type: str
    params: Dict[str, Any]
    raw: str


class CommandParser:
    """Parse commands"""
    
    # Explicit command patterns
    COMMAND_PATTERNS = {
        r"help": "help",
        r"status": "status",
        r"doctor": "doctor",
        r"setup": "setup",
        r"exit|quit": "exit",
        r"market\s*(today|week)?": "market",
        r"news\s*(today)?": "news",
        r"events": "events",
        r"regime": "regime",
        r"volatility": "volatility",
        r"analyze\s+(\w+)": "analyze",
        r"research": "research",
        r"opportunities": "opportunities",
        r"compare\s+(.+)": "compare",
        r"explain\s+(.+)": "explain",
        r"screen": "screen",
        r"today": "today",
        r"week": "week",
        r"month": "month",
        r"year": "year",
        r"longterm": "longterm",
        r"portfolio": "portfolio",
        r"exposure": "exposure",
        r"risk": "risk",
        r"rebalance": "rebalance",
        r"attribution": "attribution",
        r"positions": "positions",
        r"cash": "cash",
        r"performance": "performance",
        r"simulate": "simulate",
        r"stress": "stress",
        r"scenario": "scenario",
        r"whatif": "whatif",
        r"digital-twin": "digital_twin",
        r"order": "order",
        r"execute": "execute",
        r"cancel": "cancel",
        r"orders": "orders",
        r"fills": "fills",
        r"execution": "execution",
        r"brokers": "brokers",
        r"connect": "connect",
        r"disconnect": "disconnect",
        r"broker\s+status": "broker_status",
        r"broker\s+capabilities": "broker_capabilities",
        r"automation": "automation",
        r"automation\s+list": "automation_list",
        r"automation\s+create": "automation_create",
        r"automation\s+pause": "automation_pause",
        r"automation\s+resume": "automation_resume",
        r"automation\s+stop": "automation_stop",
        r"failures": "failures",
        r"experience": "experience",
        r"experiments": "experiments",
        r"benchmark": "benchmark",
        r"model-status": "model_status",
        r"stop": "stop",
        r"kill": "kill",
        r"emergency": "emergency",
    }
    
    def parse(self, user_input: str) -> Command:
        """Parse user input"""
        user_input = user_input.strip()
        
        # Try explicit command patterns
        for pattern, command_type in self.COMMAND_PATTERNS.items():
            match = re.match(pattern, user_input, re.IGNORECASE)
            if match:
                params = self._extract_params(match, command_type)
                return Command(type=command_type, params=params, raw=user_input)
        
        # Default to natural language
        return Command(type="natural_language", params={"query": user_input}, raw=user_input)
        
    def _extract_params(self, match: re.Match, command_type: str) -> Dict[str, Any]:
        """Extract parameters from match"""
        params = {}
        if match.groups():
            if command_type == "analyze":
                params["symbol"] = match.group(1)
            elif command_type == "compare":
                params["symbols"] = match.group(1).split()
            elif command_type == "explain":
                params["topic"] = match.group(1)
            elif command_type == "market":
                params["timeframe"] = match.group(1) if match.group(1) else "today"
            elif command_type == "news":
                params["timeframe"] = match.group(1) if match.group(1) else "today"
        return params
```

#### 3.2 Test Command Parser
```python
# Test in Python
from cli.command_parser import CommandParser

parser = CommandParser()

# Test explicit commands
print(parser.parse("help"))
print(parser.parse("market today"))
print(parser.parse("analyze AAPL"))
print(parser.parse("compare AAPL MSFT NVDA"))

# Test natural language
print(parser.parse("what should I trade today?"))
print(parser.parse("explain my portfolio risk"))
```

---

## DAY 4: Intent Resolver

### Goal: Resolve parsed commands to structured intents

### Tasks:

#### 4.1 Create Intent Resolver
**File:** `cli/intent_resolver.py`

```python
"""
Intent Resolver
Resolve parsed commands to structured intents.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from cli.command_parser import Command
from cli.session_manager import SessionManager


@dataclass
class Intent:
    """Structured intent"""
    type: str
    action: str
    params: Dict[str, Any]
    confidence: float


class IntentResolver:
    """Resolve intents from commands"""
    
    def __init__(self):
        """Initialize intent resolver"""
        self.intent_map = {
            "help": Intent(type="system", action="show_help", params={}, confidence=1.0),
            "status": Intent(type="system", action="show_status", params={}, confidence=1.0),
            "doctor": Intent(type="system", action="run_diagnostics", params={}, confidence=1.0),
            "setup": Intent(type="system", action="run_setup", params={}, confidence=1.0),
            "exit": Intent(type="system", action="exit", params={}, confidence=1.0),
            "market": Intent(type="market", action="show_market", params={}, confidence=1.0),
            "news": Intent(type="market", action="show_news", params={}, confidence=1.0),
            "analyze": Intent(type="research", action="analyze_asset", params={}, confidence=1.0),
            "portfolio": Intent(type="portfolio", action="show_portfolio", params={}, confidence=1.0),
            "risk": Intent(type="portfolio", action="show_risk", params={}, confidence=1.0),
            "today": Intent(type="decision", action="today_decisions", params={}, confidence=1.0),
            "week": Intent(type="decision", action="week_decisions", params={}, confidence=1.0),
        }
        
    def resolve(self, command: Command, session: SessionManager) -> Intent:
        """Resolve command to intent"""
        # Check if explicit command
        if command.type in self.intent_map:
            intent = self.intent_map[command.type]
            intent.params.update(command.params)
            return intent
        
        # Handle natural language
        if command.type == "natural_language":
            return self._resolve_natural_language(command, session)
        
        # Default to unknown
        return Intent(type="unknown", action="unknown", params=command.params, confidence=0.0)
        
    def _resolve_natural_language(self, command: Command, session: SessionManager) -> Intent:
        """Resolve natural language to intent"""
        query = command.params.get("query", "").lower()
        
        # Simple keyword matching (will be replaced with LLM in PHASE 1)
        if "trade" in query and "today" in query:
            return Intent(type="decision", action="today_decisions", params={}, confidence=0.8)
        elif "opportunit" in query and "week" in query:
            return Intent(type="decision", action="week_decisions", params={}, confidence=0.8)
        elif "portfolio" in query and "risk" in query:
            return Intent(type="portfolio", action="show_risk", params={}, confidence=0.8)
        elif "market" in query:
            return Intent(type="market", action="show_market", params={}, confidence=0.7)
        else:
            return Intent(type="unknown", action="unknown", params={"query": query}, confidence=0.5)
```

#### 4.2 Test Intent Resolver
```python
# Test in Python
from cli.command_parser import CommandParser
from cli.intent_resolver import IntentResolver
from cli.session_manager import SessionManager

parser = CommandParser()
resolver = IntentResolver()
session = SessionManager({})

# Test explicit commands
cmd = parser.parse("market today")
intent = resolver.resolve(cmd, session)
print(intent)

# Test natural language
cmd = parser.parse("what should I trade today?")
intent = resolver.resolve(cmd, session)
print(intent)
```

---

## DAY 5: Response Formatter

### Goal: Format responses for display

### Tasks:

#### 5.1 Create Response Formatter
**File:** `cli/response_formatter.py`

```python
"""
Response Formatter
Format responses for display in the terminal.
"""

from typing import Any, Dict, List
from cli.intent_resolver import Intent


class ResponseFormatter:
    """Format responses"""
    
    def format(self, intent: Intent, result: Any) -> str:
        """Format response based on intent"""
        if intent.type == "system":
            return self._format_system(intent, result)
        elif intent.type == "market":
            return self._format_market(intent, result)
        elif intent.type == "portfolio":
            return self._format_portfolio(intent, result)
        elif intent.type == "decision":
            return self._format_decision(intent, result)
        else:
            return self._format_unknown(intent, result)
            
    def _format_system(self, intent: Intent, result: Any) -> str:
        """Format system response"""
        if intent.action == "show_help":
            return self._format_help()
        elif intent.action == "show_status":
            return "System Status: OK"
        elif intent.action == "exit":
            return "Goodbye!"
        else:
            return str(result)
            
    def _format_market(self, intent: Intent, result: Any) -> str:
        """Format market response"""
        return f"Market Data: {result}"
        
    def _format_portfolio(self, intent: Intent, result: Any) -> str:
        """Format portfolio response"""
        return f"Portfolio: {result}"
        
    def _format_decision(self, intent: Intent, result: Any) -> str:
        """Format decision response"""
        return f"Decision: {result}"
        
    def _format_unknown(self, intent: Intent, result: Any) -> str:
        """Format unknown response"""
        return f"I understood: {intent.params.get('query', 'unknown')}"
        
    def _format_help(self) -> str:
        """Format help text"""
        help_text = """
DELTA Terminal Commands

Core Commands:
  help          Show this help
  status        Show system status
  doctor        Run diagnostics
  setup         Run initial setup
  exit          Exit terminal

Market Commands:
  market        Show market overview
  market today  Show today's market
  news          Show financial news
  events        Show market events
  regime        Show current regime

Research Commands:
  analyze SYM   Analyze specific asset
  research      Enter research mode
  opportunities Find opportunities

Horizon Commands:
  today         Today's decisions
  week          Weekly decisions
  month         Monthly decisions
  year          Yearly decisions

Portfolio Commands:
  portfolio     Show portfolio
  risk          Show portfolio risk
  exposure      Show exposure analysis

Simulation Commands:
  simulate      Run simulation
  stress        Stress test portfolio
  whatif        What-if analysis

Trading Commands:
  order         Place order
  execute       Execute trade
  orders        List orders

Broker Commands:
  brokers       List available brokers
  connect       Connect broker

Automation Commands:
  automation    Show automation status

Safety Commands:
  stop          Stop operations
  kill          Emergency kill
  emergency     Emergency mode

Natural Language:
  You can also ask questions like:
  - "What should I trade today?"
  - "Explain my portfolio risk"
  - "What changed in the market?"
"""
        return help_text
```

#### 5.2 Integrate Response Formatter into REPL
Update `cli/repl.py`:

```python
# In eval_input method, after resolving intent:
# Format response
response = self.formatter.format(intent, result)
```

#### 5.3 Test Response Formatter
```bash
delta
DELTA> help
DELTA> status
DELTA> market
```

---

## DAY 6: Domain Guard

### Goal: Enforce finance-only domain boundary

### Tasks:

#### 6.1 Create Domain Guard
**File:** `cli/domain_guard.py`

```python
"""
Domain Guard
Enforce finance-only domain boundary.
"""

from typing import List, Optional


class DomainGuard:
    """Finance-only domain guard"""
    
    # Finance domain keywords
    FINANCE_KEYWORDS = [
        "trade", "trading", "invest", "investment", "portfolio",
        "market", "stock", "bond", "option", "future", "forex",
        "risk", "return", "dividend", "earnings", "revenue",
        "price", "volatility", "liquidity", "leverage", "margin",
        "broker", "exchange", "order", "fill", "execution",
        "fundamental", "technical", "quantitative", "algorithm",
        "hedge", "arbitrage", "asset", "security", "instrument",
        "macro", "economic", "inflation", "interest", "rate",
        "sector", "industry", "index", "benchmark", "etf",
        "mutual fund", "hedge fund", "pe", "pb", "roe", "roa",
        "sharpe", "sortino", "var", "cvar", "drawdown",
        "rebalance", "attribution", "exposure", "concentration",
        "news", "event", "regime", "scenario", "stress",
        "backtest", "simulation", "forecast", "signal", "factor",
    ]
    
    # Out-of-domain keywords
    OUT_OF_DOMAIN_KEYWORDS = [
        "poem", "story", "joke", "recipe", "weather",
        "sports", "politics", "religion", "celebrity",
        "movie", "music", "game", "travel", "food",
    ]
    
    def is_finance_domain(self, query: str) -> bool:
        """Check if query is in finance domain"""
        query_lower = query.lower()
        
        # Check for explicit out-of-domain keywords
        for keyword in self.OUT_OF_DOMAIN_KEYWORDS:
            if keyword in query_lower:
                return False
        
        # Check for finance keywords
        for keyword in self.FINANCE_KEYWORDS:
            if keyword in query_lower:
                return True
        
        # Default to unknown (allow LLM to decide in PHASE 1)
        return True
        
    def get_domain_message(self) -> str:
        """Get domain boundary message"""
        return """
I am specialized for trading, investing, portfolio management,
financial research, risk, markets and execution.

I cannot help with requests outside the finance domain.
"""
```

#### 6.2 Integrate Domain Guard into Intent Resolver
Update `cli/intent_resolver.py`:

```python
from cli.domain_guard import DomainGuard

class IntentResolver:
    def __init__(self):
        # ... existing code ...
        self.domain_guard = DomainGuard()
        
    def resolve(self, command: Command, session: SessionManager) -> Intent:
        # Check domain for natural language
        if command.type == "natural_language":
            query = command.params.get("query", "")
            if not self.domain_guard.is_finance_domain(query):
                return Intent(
                    type="out_of_domain",
                    action="reject",
                    params={"message": self.domain_guard.get_domain_message()},
                    confidence=1.0
                )
        
        # ... existing resolution logic ...
```

#### 6.3 Test Domain Guard
```bash
delta
DELTA> write me a poem
DELTA> what should I trade today?
```

---

## DAY 7: Session State Management

### Goal: Implement comprehensive session state management

### Tasks:

#### 7.1 Enhance Session Manager
Update `cli/session_manager.py`:

```python
"""
Session Manager
Manage terminal session state and context.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import json
from pathlib import Path


class SessionManager:
    """Manage terminal session"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize session"""
        self.config = config
        self.session_id = str(uuid.uuid4())
        self.start_time = datetime.now()
        self.context: Dict[str, Any] = {
            "mandate": None,
            "portfolio": None,
            "market_state": None,
            "regime": None,
        }
        self.history: List[Dict[str, Any]] = []
        self.session_file = Path(config.get("session_file", "session.json"))
        
    def get_session_id(self) -> str:
        """Get session ID"""
        return self.session_id
        
    def get_context(self, key: str) -> Optional[Any]:
        """Get context value"""
        return self.context.get(key)
        
    def set_context(self, key: str, value: Any):
        """Set context value"""
        self.context[key] = value
        
    def update_context(self, updates: Dict[str, Any]):
        """Update multiple context values"""
        self.context.update(updates)
        
    def add_to_history(self, entry: Dict[str, Any]):
        """Add entry to history"""
        entry["timestamp"] = datetime.now().isoformat()
        self.history.append(entry)
        
    def get_history(self) -> List[Dict[str, Any]]:
        """Get history"""
        return self.history
        
    def get_last_n_commands(self, n: int) -> List[str]:
        """Get last n commands"""
        return [h.get("command", "") for h in self.history[-n:]]
        
    def save_session(self):
        """Save session to file"""
        session_data = {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "context": self.context,
            "history": self.history,
        }
        with open(self.session_file, "w") as f:
            json.dump(session_data, f, indent=2)
            
    def load_session(self) -> bool:
        """Load session from file"""
        if not self.session_file.exists():
            return False
            
        with open(self.session_file, "r") as f:
            session_data = json.load(f)
            
        self.session_id = session_data.get("session_id", self.session_id)
        self.context.update(session_data.get("context", {}))
        self.history = session_data.get("history", [])
        return True
        
    def cleanup(self):
        """Cleanup session"""
        self.save_session()
        self.context.clear()
        self.history.clear()
```

#### 7.2 Test Session Management
```python
# Test in Python
from cli.session_manager import SessionManager

session = SessionManager({})
session.set_context("mandate", {"capital": 100000})
session.add_to_history({"command": "market", "response": "OK"})
session.save_session()

# Load in new session
session2 = SessionManager({})
session2.load_session()
print(session2.get_context("mandate"))
print(session2.get_history())
```

---

## DAY 8: Audit Trail Enhancement

### Goal: Implement comprehensive audit logging

### Tasks:

#### 8.1 Enhance Audit Logger
Update `cli/audit_logger.py`:

```python
"""
Audit Logger
Log all terminal activity for audit trail.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import hashlib


class AuditLogger:
    """Audit logger for terminal activity"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize audit logger"""
        self.config = config
        self.log_dir = Path(config.get("audit_dir", "audit"))
        self.log_dir.mkdir(exist_ok=True)
        
        # Create session-specific log file
        session_id = config.get("session_id", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"delta_{session_id}_{timestamp}.log"
        
        self.entries: list = []
        self.sequence = 0
        
    def _get_sequence(self) -> int:
        """Get next sequence number"""
        self.sequence += 1
        return self.sequence
        
    def _compute_hash(self, entry: Dict[str, Any]) -> str:
        """Compute hash of entry"""
        entry_str = json.dumps(entry, sort_keys=True)
        return hashlib.sha256(entry_str.encode()).hexdigest()
        
    def log_command(self, command: str, session_id: str):
        """Log command"""
        entry = {
            "sequence": self._get_sequence(),
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "type": "command",
            "content": command,
            "hash": None  # Will be computed after content is set
        }
        entry["hash"] = self._compute_hash(entry)
        self.entries.append(entry)
        self._write_entry(entry)
        
    def log_response(self, response: str, session_id: str):
        """Log response"""
        entry = {
            "sequence": self._get_sequence(),
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "type": "response",
            "content": response,
            "hash": None
        }
        entry["hash"] = self._compute_hash(entry)
        self.entries.append(entry)
        self._write_entry(entry)
        
    def log_error(self, error: Exception, session_id: str):
        """Log error"""
        entry = {
            "sequence": self._get_sequence(),
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "type": "error",
            "content": str(error),
            "error_type": type(error).__name__,
            "hash": None
        }
        entry["hash"] = self._compute_hash(entry)
        self.entries.append(entry)
        self._write_entry(entry)
        
    def log_state_change(self, state_type: str, old_state: Any, new_state: Any, session_id: str):
        """Log state change"""
        entry = {
            "sequence": self._get_sequence(),
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "type": "state_change",
            "state_type": state_type,
            "old_state": str(old_state),
            "new_state": str(new_state),
            "hash": None
        }
        entry["hash"] = self._compute_hash(entry)
        self.entries.append(entry)
        self._write_entry(entry)
        
    def _write_entry(self, entry: Dict[str, Any]):
        """Write entry to log file"""
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
            
    def get_entries(self) -> list:
        """Get all entries"""
        return self.entries
        
    def close(self):
        """Close audit logger"""
        # Flush any remaining entries
        pass
```

#### 8.2 Integrate Enhanced Audit Logger
Update `cli/repl.py` to pass session_id to audit logger:

```python
# In eval_input method
self.audit.log_command(user_input, self.session.get_session_id())
# ...
self.audit.log_response(response, self.session.get_session_id())
```

#### 8.3 Test Audit Logging
```bash
delta
DELTA> help
DELTA> market
DELTA> exit

# Check audit log
cat audit/delta_*.log
```

---

## DAY 9: Tab Completion

### Goal: Implement tab completion for commands

### Tasks:

#### 9.1 Create Tab Completion
**File:** `cli/completion.py`

```python
"""
Tab Completion
Provide tab completion for commands.
"""

from typing import List, Optional
import re


class TabCompleter:
    """Tab completion for DELTA terminal"""
    
    COMMANDS = [
        "help", "status", "doctor", "setup", "exit",
        "market", "market today", "market week",
        "news", "news today",
        "events", "regime", "volatility",
        "analyze", "research", "opportunities",
        "compare", "explain", "screen",
        "today", "week", "month", "year", "longterm",
        "portfolio", "exposure", "risk", "rebalance",
        "attribution", "positions", "cash", "performance",
        "simulate", "stress", "scenario", "whatif", "digital-twin",
        "order", "execute", "cancel", "orders", "fills", "execution",
        "brokers", "connect", "disconnect",
        "broker status", "broker capabilities",
        "automation", "automation list", "automation create",
        "automation pause", "automation resume", "automation stop",
        "failures", "experience", "experiments", "benchmark", "model-status",
        "stop", "kill", "emergency",
    ]
    
    def complete(self, text: str, state: int) -> Optional[str]:
        """Complete command"""
        if state == 0:
            # First call: generate matches
            self.matches = [cmd for cmd in self.COMMANDS if cmd.startswith(text)]
        
        if state < len(self.matches):
            return self.matches[state]
        else:
            return None
```

#### 9.2 Integrate Tab Completion into REPL
Update `cli/repl.py` to use readline with tab completion:

```python
import readline
from cli.completion import TabCompleter

class DeltaREPL:
    def __init__(self, session: SessionManager, audit: AuditLogger):
        # ... existing code ...
        self.completer = TabCompleter()
        readline.set_completer(self.completer.complete)
        readline.parse_and_bind("tab: complete")
```

#### 9.3 Test Tab Completion
```bash
delta
DELTA> mar<TAB>
DELTA> market tod<TAB>
```

---

## DAY 10: Command History

### Goal: Implement command history with navigation

### Tasks:

#### 10.1 Enhance Session Manager for History
Update `cli/session_manager.py` to add history methods:

```python
def get_previous_command(self, index: int = -1) -> Optional[str]:
    """Get previous command from history"""
    if abs(index) > len(self.history):
        return None
    return self.history[index].get("command", "")

def search_history(self, pattern: str) -> List[str]:
    """Search command history"""
    pattern_lower = pattern.lower()
    return [
        h.get("command", "")
        for h in self.history
        if pattern_lower in h.get("command", "").lower()
    ]
```

#### 10.2 Integrate History into REPL
Update `cli/repl.py` to use readline history:

```python
class DeltaREPL:
    def __init__(self, session: SessionManager, audit: AuditLogger):
        # ... existing code ...
        self.history_file = Path(".delta_history")
        self._load_history()
        
    def _load_history(self):
        """Load command history from file"""
        if self.history_file.exists():
            readline.read_history_file(str(self.history_file))
            
    def _save_history(self):
        """Save command history to file"""
        readline.write_history_file(str(self.history_file))
        
    def add_to_history(self, command: str):
        """Add command to history"""
        readline.add_history(command)
        
    def run(self):
        """Run REPL loop"""
        # ... existing code ...
        try:
            self.running = True
            self.display_banner()
            
            while self.running:
                try:
                    user_input = self.read_input()
                    
                    if user_input.lower() in ["exit", "quit"]:
                        self.running = False
                        continue
                    
                    # Add to history
                    self.add_to_history(user_input)
                    
                    output = self.eval_input(user_input)
                    self.print_output(output)
                    
                except Exception as e:
                    print(f"Error: {e}")
                    self.audit.log_error(e, self.session.get_session_id())
        finally:
            self._save_history()
```

#### 10.3 Test Command History
```bash
delta
DELTA> help
DELTA> market
DELTA> portfolio
# Use arrow keys to navigate history
# Use Ctrl+R to search history
```

---

## DAY 11: Error Handling

### Goal: Implement comprehensive error handling

### Tasks:

#### 11.1 Create Error Handler
**File:** `cli/error_handler.py`

```python
"""
Error Handler
Handle errors gracefully in the terminal.
"""

from typing import Optional
import traceback


class DeltaError(Exception):
    """Base DELTA error"""
    pass


class ConfigurationError(DeltaError):
    """Configuration error"""
    pass


class DataError(DeltaError):
    """Data error"""
    pass


class ModelError(DeltaError):
    """Model error"""
    pass


class BrokerError(DeltaError):
    """Broker error"""
    pass


class RiskError(DeltaError):
    """Risk error"""
    pass


class ErrorHandler:
    """Handle errors gracefully"""
    
    def __init__(self, verbose: bool = False):
        """Initialize error handler"""
        self.verbose = verbose
        
    def handle(self, error: Exception) -> str:
        """Handle error and return user-friendly message"""
        if isinstance(error, DeltaError):
            return self._handle_delta_error(error)
        else:
            return self._handle_generic_error(error)
            
    def _handle_delta_error(self, error: DeltaError) -> str:
        """Handle DELTA-specific error"""
        error_type = type(error).__name__
        error_message = str(error)
        
        if isinstance(error, ConfigurationError):
            return f"Configuration Error: {error_message}\nPlease check your configuration file."
        elif isinstance(error, DataError):
            return f"Data Error: {error_message}\nPlease check your data sources."
        elif isinstance(error, ModelError):
            return f"Model Error: {error_message}\nPlease check your model configuration."
        elif isinstance(error, BrokerError):
            return f"Broker Error: {error_message}\nPlease check your broker connection."
        elif isinstance(error, RiskError):
            return f"Risk Error: {error_message}\nOperation blocked by risk firewall."
        else:
            return f"Error: {error_message}"
            
    def _handle_generic_error(self, error: Exception) -> str:
        """Handle generic error"""
        if self.verbose:
            return f"Error: {error}\n{traceback.format_exc()}"
        else:
            return f"Error: {error}\nUse 'delta doctor' for diagnostics."
```

#### 11.2 Integrate Error Handler into REPL
Update `cli/repl.py`:

```python
from cli.error_handler import ErrorHandler

class DeltaREPL:
    def __init__(self, session: SessionManager, audit: AuditLogger):
        # ... existing code ...
        self.error_handler = ErrorHandler(verbose=False)
        
    def run(self):
        """Run REPL loop"""
        # ... existing code ...
        try:
            user_input = self.read_input()
            # ... existing code ...
        except Exception as e:
            error_message = self.error_handler.handle(e)
            print(error_message)
            self.audit.log_error(e, self.session.get_session_id())
```

#### 11.3 Test Error Handling
```python
# Test in Python
from cli.error_handler import ErrorHandler, ConfigurationError

handler = ErrorHandler()
print(handler.handle(ConfigurationError("Config file not found")))
```

---

## DAY 12: Configuration Management

### Goal: Implement configuration loading and validation

### Tasks:

#### 12.1 Create Configuration Module
**File:** `config/config.py`

```python
"""
Configuration Management
Load and validate DELTA configuration.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import json


class Config:
    """DELTA configuration"""
    
    DEFAULT_CONFIG = {
        "session_file": "session.json",
        "audit_dir": "audit",
        "history_file": ".delta_history",
        "data_dir": "data",
        "model_dir": "models",
        "log_level": "INFO",
        "broker": {
            "default": "paper",
            "paper": {
                "enabled": True,
            },
        },
        "risk": {
            "max_position_size": 10000,
            "max_portfolio_risk": 0.02,
        },
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration"""
        self.config_path = config_path
        self.config = self.DEFAULT_CONFIG.copy()
        
        if config_path:
            self.load(config_path)
            
    def load(self, config_path: str):
        """Load configuration from file"""
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        if config_file.suffix in [".yaml", ".yml"]:
            with open(config_file, "r") as f:
                user_config = yaml.safe_load(f)
        elif config_file.suffix == ".json":
            with open(config_file, "r") as f:
                user_config = json.load(f)
        else:
            raise ValueError(f"Unsupported config file format: {config_file.suffix}")
        
        # Merge with default config
        self._merge_config(user_config)
        
    def _merge_config(self, user_config: Dict[str, Any]):
        """Merge user config with default config"""
        def merge(base: Dict, update: Dict) -> Dict:
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    base[key] = merge(base[key], value)
                else:
                    base[key] = value
            return base
        
        self.config = merge(self.config, user_config)
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        keys = key.split(".")
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
        
    def set(self, key: str, value: Any):
        """Set configuration value"""
        keys = key.split(".")
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        
    def validate(self) -> bool:
        """Validate configuration"""
        # Add validation logic
        return True


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration"""
    return Config(config_path)
```

#### 12.2 Create Default Configuration File
**File:** `config/default.yaml`

```yaml
# DELTA Default Configuration

session_file: session.json
audit_dir: audit
history_file: .delta_history
data_dir: data
model_dir: models
log_level: INFO

broker:
  default: paper
  paper:
    enabled: true

risk:
  max_position_size: 10000
  max_portfolio_risk: 0.02
```

#### 12.3 Test Configuration
```python
# Test in Python
from config.config import load_config

config = load_config("config/default.yaml")
print(config.get("broker.default"))
print(config.get("risk.max_position_size"))
```

---

## DAY 13: Integration Testing

### Goal: Integrate all components and test end-to-end

### Tasks:

#### 13.1 Create Integration Test
**File:** `tests/test_cli_integration.py`

```python
"""
CLI Integration Tests
Test the complete CLI integration.
"""

import pytest
from cli.terminal import DeltaTerminal
from cli.session_manager import SessionManager
from cli.audit_logger import AuditLogger
from cli.command_parser import CommandParser
from cli.intent_resolver import IntentResolver
from cli.response_formatter import ResponseFormatter
from cli.domain_guard import DomainGuard


def test_terminal_startup():
    """Test terminal startup"""
    terminal = DeltaTerminal()
    assert terminal.session is not None
    assert terminal.audit is not None


def test_command_parser():
    """Test command parser"""
    parser = CommandParser()
    
    # Test explicit commands
    cmd = parser.parse("help")
    assert cmd.type == "help"
    
    cmd = parser.parse("market today")
    assert cmd.type == "market"
    assert cmd.params["timeframe"] == "today"
    
    # Test natural language
    cmd = parser.parse("what should I trade today?")
    assert cmd.type == "natural_language"


def test_intent_resolver():
    """Test intent resolver"""
    parser = CommandParser()
    resolver = IntentResolver()
    session = SessionManager({})
    
    cmd = parser.parse("market today")
    intent = resolver.resolve(cmd, session)
    assert intent.type == "market"
    assert intent.action == "show_market"


def test_domain_guard():
    """Test domain guard"""
    guard = DomainGuard()
    
    assert guard.is_finance_domain("what should I trade today?") == True
    assert guard.is_finance_domain("write me a poem") == False


def test_response_formatter():
    """Test response formatter"""
    formatter = ResponseFormatter()
    
    from cli.intent_resolver import Intent
    intent = Intent(type="system", action="show_help", params={}, confidence=1.0)
    response = formatter.format(intent, None)
    assert "DELTA Terminal Commands" in response


def test_session_manager():
    """Test session manager"""
    session = SessionManager({})
    
    session.set_context("test", "value")
    assert session.get_context("test") == "value"
    
    session.add_to_history({"command": "test"})
    assert len(session.get_history()) == 1


def test_audit_logger():
    """Test audit logger"""
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"audit_dir": tmpdir, "session_id": "test"}
        audit = AuditLogger(config)
        
        audit.log_command("test command", "test_session")
        assert len(audit.get_entries()) == 1
```

#### 13.2 Run Integration Tests
```bash
pytest tests/test_cli_integration.py -v
```

---

## DAY 14: Documentation & Final Testing

### Goal: Document usage and perform final testing

### Tasks:

#### 14.1 Create CLI Documentation
**File:** `docs/CLI_USAGE.md`

```markdown
# DELTA Terminal Usage Guide

## Installation

```bash
pip install -e .
```

## Basic Usage

Launch the terminal:

```bash
delta
```

## Commands

### Core Commands

- `help` - Show help
- `status` - Show system status
- `doctor` - Run diagnostics
- `setup` - Run initial setup
- `exit` - Exit terminal

### Market Commands

- `market` - Show market overview
- `market today` - Show today's market
- `news` - Show financial news
- `events` - Show market events
- `regime` - Show current regime

### Research Commands

- `analyze SYM` - Analyze specific asset
- `research` - Enter research mode
- `opportunities` - Find opportunities

### Horizon Commands

- `today` - Today's decisions
- `week` - Weekly decisions
- `month` - Monthly decisions
- `year` - Yearly decisions

### Portfolio Commands

- `portfolio` - Show portfolio
- `risk` - Show portfolio risk
- `exposure` - Show exposure analysis

### Natural Language

You can also ask questions in natural language:

- "What should I trade today?"
- "Explain my portfolio risk"
- "What changed in the market?"

## Configuration

Configuration is loaded from `config/default.yaml` or a custom path specified with `--config`.

## Session Management

Session state is persisted to `session.json` and can be restored on restart.

## Audit Trail

All terminal activity is logged to the `audit/` directory for security and compliance.
```

#### 14.2 Final Testing
```bash
# Complete end-to-end test
delta

# Test all major commands
DELTA> help
DELTA> status
DELTA> market
DELTA> portfolio
DELTA> today
DELTA> exit

# Check audit log
ls audit/
cat audit/delta_*.log

# Check session
cat session.json

# Check history
cat .delta_history
```

#### 14.3 Verify Success Criteria
- [ ] User can type `delta` and get a working terminal
- [ ] Natural language queries are understood
- [ ] Explicit commands work
- [ ] Domain boundaries are enforced
- [ ] Session state persists
- [ ] Audit trail is complete
- [ ] Tab completion works
- [ ] Command history works
- [ ] Error handling is graceful
- [ ] Configuration is loaded correctly

---

## WEEK 2 SUMMARY

By the end of Week 2, you will have:

1. ✅ A working `delta` command that launches the terminal
2. ✅ Interactive REPL with prompt and banner
3. ✅ Command parser for explicit and natural language
4. ✅ Intent resolver that maps commands to actions
5. ✅ Response formatter for structured output
6. ✅ Domain guard enforcing finance-only boundary
7. ✅ Session manager with state persistence
8. ✅ Audit logger with comprehensive logging
9. ✅ Tab completion for commands
10. ✅ Command history with navigation
11. ✅ Error handling with user-friendly messages
12. ✅ Configuration management with validation
13. ✅ Integration tests
14. ✅ Documentation

**PHASE 0 Complete:** DELTA Operating-System Architecture is ready for PHASE 1.
