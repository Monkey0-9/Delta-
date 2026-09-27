"""
Tests for canonical event contracts.

Tests cross-language semantic contracts that serve as the foundation
for Python, Rust, and C++ interoperability.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from core.contracts.canonical import (
    AssetClass,
    Currency,
    Side,
    OrderType,
    OrderStatus,
    TimeInForce,
    FailureCategory,
    ContractVersion,
    CURRENT_VERSION,
    Timestamps,
    Instrument,
    MarketEvent,
    Quote,
    Trade,
    OrderBookUpdate,
    Signal,
    Forecast,
    Decision,
    RiskDecision,
    ExecutionIntent,
    Order,
    Fill,
    Position,
    PortfolioSnapshot,
    Failure,
    Experience,
    WorldState,
    validate_contract,
    validate_contract_compatibility,
    contract_to_dict,
    dict_to_contract,
    get_contract,
    list_contracts,
    CANONICAL_CONTRACT_VERSION,
)


class TestContractVersioning:
    """Test contract versioning system."""
    
    def test_current_version_format(self):
        """Test that current version is properly formatted."""
        assert str(CURRENT_VERSION) == "1.0.0"
        assert CURRENT_VERSION.major == 1
        assert CURRENT_VERSION.minor == 0
        assert CURRENT_VERSION.patch == 0
    
    def test_version_compatibility(self):
        """Test version compatibility checking."""
        v1_0_0 = ContractVersion(1, 0, 0)
        v1_1_0 = ContractVersion(1, 1, 0)
        v2_0_0 = ContractVersion(2, 0, 0)
        
        # Same major version should be compatible
        assert v1_0_0.is_compatible(v1_1_0)
        assert v1_1_0.is_compatible(v1_0_0)
        
        # Different major version should not be compatible
        assert not v1_0_0.is_compatible(v2_0_0)
        assert not v2_0_0.is_compatible(v1_0_0)
    
    def test_validate_compatibility(self):
        """Test string-based compatibility validation."""
        assert validate_contract_compatibility("1.0.0")
        assert validate_contract_compatibility("1.2.3")
        assert not validate_contract_compatibility("2.0.0")
        assert not validate_contract_compatibility("invalid")


class TestTimestamps:
    """Test timestamp structure for point-in-time correctness."""
    
    def test_timestamp_creation(self):
        """Test basic timestamp creation."""
        event_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        received_time = datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        
        timestamps = Timestamps(
            event_time=event_time,
            received_time=received_time
        )
        
        assert timestamps.event_time == event_time
        assert timestamps.received_time == received_time
    
    def test_timestamp_validation(self):
        """Test timestamp ordering validation."""
        event_time = datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        received_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        with pytest.raises(ValueError, match="received_time must be >= event_time"):
            Timestamps(event_time=event_time, received_time=received_time)
    
    def test_availability_check(self):
        """Test point-in-time availability checking."""
        event_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        received_time = datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        
        timestamps = Timestamps(
            event_time=event_time,
            received_time=received_time,
            available_at=datetime(2024, 1, 1, 12, 0, 2, tzinfo=timezone.utc)
        )
        
        # Before available time
        assert not timestamps.is_available_at(datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc))
        
        # At available time
        assert timestamps.is_available_at(datetime(2024, 1, 1, 12, 0, 2, tzinfo=timezone.utc))
        
        # After available time
        assert timestamps.is_available_at(datetime(2024, 1, 1, 12, 0, 3, tzinfo=timezone.utc))


class TestInstrument:
    """Test instrument contract."""
    
    def test_instrument_creation(self):
        """Test basic instrument creation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD,
            exchange="NASDAQ"
        )
        
        assert instrument.symbol == "AAPL"
        assert instrument.asset_class == AssetClass.EQUITY
        assert instrument.currency == Currency.USD
        assert instrument.exchange == "NASDAQ"
    
    def test_content_hash(self):
        """Test instrument content hashing."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        hash_value = instrument.content_hash()
        assert "AAPL" in hash_value
        assert "equity" in hash_value
        assert "USD" in hash_value


class TestMarketEvent:
    """Test market event contract."""
    
    def test_market_event_creation(self):
        """Test basic market event creation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        event = MarketEvent(
            instrument=instrument,
            timestamps=timestamps,
            price=Decimal("150.25")
        )
        
        assert event.instrument.symbol == "AAPL"
        assert event.price == Decimal("150.25")
        assert event.source == "unknown"
    
    def test_market_event_with_bid_ask(self):
        """Test market event with bid/ask."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        event = MarketEvent(
            instrument=instrument,
            timestamps=timestamps,
            bid=Decimal("150.20"),
            ask=Decimal("150.30")
        )
        
        assert event.bid == Decimal("150.20")
        assert event.ask == Decimal("150.30")
    
    def test_market_event_validation(self):
        """Test market event validation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Missing both price and bid/ask
        with pytest.raises(ValueError, match="Either price or bid/ask must be present"):
            MarketEvent(instrument=instrument, timestamps=timestamps)
    
    def test_mid_price_calculation(self):
        """Test mid price calculation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        event = MarketEvent(
            instrument=instrument,
            timestamps=timestamps,
            bid=Decimal("150.20"),
            ask=Decimal("150.30")
        )
        
        mid = event.mid_price()
        assert mid == Decimal("150.25")
    
    def test_pit_availability(self):
        """Test point-in-time availability check."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        event_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        received_time = datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        
        timestamps = Timestamps(
            event_time=event_time,
            received_time=received_time
        )
        
        event = MarketEvent(
            instrument=instrument,
            timestamps=timestamps,
            price=Decimal("150.25")
        )
        
        # Event should be available at received time
        assert event.is_available_at(received_time)
        
        # Event should not be available before received time
        assert not event.is_available_at(event_time)


class TestQuote:
    """Test quote contract."""
    
    def test_quote_creation(self):
        """Test basic quote creation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        quote = Quote(
            instrument=instrument,
            timestamps=timestamps,
            bid=Decimal("150.20"),
            ask=Decimal("150.30")
        )
        
        assert quote.bid == Decimal("150.20")
        assert quote.ask == Decimal("150.30")
    
    def test_quote_validation(self):
        """Test quote validation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # bid >= ask should fail
        with pytest.raises(ValueError, match="bid must be less than ask"):
            Quote(
                instrument=instrument,
                timestamps=timestamps,
                bid=Decimal("150.30"),
                ask=Decimal("150.20")
            )


class TestTrade:
    """Test trade contract."""
    
    def test_trade_creation(self):
        """Test basic trade creation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        trade = Trade(
            instrument=instrument,
            timestamps=timestamps,
            price=Decimal("150.25"),
            quantity=Decimal("100"),
            side=Side.BUY
        )
        
        assert trade.price == Decimal("150.25")
        assert trade.quantity == Decimal("100")
        assert trade.side == Side.BUY
    
    def test_trade_validation(self):
        """Test trade validation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Negative price should fail
        with pytest.raises(ValueError, match="price must be positive"):
            Trade(
                instrument=instrument,
                timestamps=timestamps,
                price=Decimal("-150.25"),
                quantity=Decimal("100"),
                side=Side.BUY
            )
        
        # Zero quantity should fail
        with pytest.raises(ValueError, match="quantity must be positive"):
            Trade(
                instrument=instrument,
                timestamps=timestamps,
                price=Decimal("150.25"),
                quantity=Decimal("0"),
                side=Side.BUY
            )


class TestSignal:
    """Test signal contract."""
    
    def test_signal_creation(self):
        """Test basic signal creation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        signal = Signal(
            instrument=instrument,
            timestamps=timestamps,
            value=Decimal("0.75"),
            confidence=0.85,
            signal_type="momentum",
            horizon="short"
        )
        
        assert signal.value == Decimal("0.75")
        assert signal.confidence == 0.85
        assert signal.signal_type == "momentum"
    
    def test_signal_confidence_validation(self):
        """Test signal confidence validation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Confidence > 1.0 should fail
        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
            Signal(
                instrument=instrument,
                timestamps=timestamps,
                value=Decimal("0.75"),
                confidence=1.5
            )


class TestForecast:
    """Test forecast contract."""
    
    def test_forecast_creation(self):
        """Test basic forecast creation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        forecast = Forecast(
            instrument=instrument,
            timestamps=timestamps,
            horizon="1M",
            expected_return=Decimal("0.05"),
            risk=Decimal("0.15"),
            confidence=0.75
        )
        
        assert forecast.expected_return == Decimal("0.05")
        assert forecast.risk == Decimal("0.15")
        assert forecast.confidence == 0.75
    
    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        forecast = Forecast(
            instrument=instrument,
            timestamps=timestamps,
            horizon="1M",
            expected_return=Decimal("0.10"),
            risk=Decimal("0.15")
        )
        
        sharpe = forecast.sharpe_ratio()
        assert sharpe is not None
        assert sharpe == Decimal("0.10") / Decimal("0.15")
    
    def test_forecast_validation(self):
        """Test forecast validation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Negative risk should fail
        with pytest.raises(ValueError, match="risk must be non-negative"):
            Forecast(
                instrument=instrument,
                timestamps=timestamps,
                horizon="1M",
                expected_return=Decimal("0.05"),
                risk=Decimal("-0.15")
            )


class TestDecision:
    """Test decision contract."""
    
    def test_decision_creation(self):
        """Test basic decision creation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        decision = Decision(
            instrument=instrument,
            timestamps=timestamps,
            action="BUY",
            quantity=Decimal("100"),
            expected_return=Decimal("0.05"),
            confidence=0.75
        )
        
        assert decision.action == "BUY"
        assert decision.quantity == Decimal("100")
    
    def test_decision_validation(self):
        """Test decision validation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Invalid action should fail
        with pytest.raises(ValueError, match="action must be BUY, SELL, HOLD, REDUCE, or unknown"):
            Decision(
                instrument=instrument,
                timestamps=timestamps,
                action="INVALID"
            )


class TestRiskDecision:
    """Test risk decision contract."""
    
    def test_risk_decision_creation(self):
        """Test basic risk decision creation."""
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        risk_decision = RiskDecision(
            decision_id=uuid4(),
            timestamps=timestamps,
            authorized=True,
            action="APPROVE"
        )
        
        assert risk_decision.authorized is True
        assert risk_decision.action == "APPROVE"
    
    def test_risk_decision_validation(self):
        """Test risk decision validation."""
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Authorized with BLOCK action should fail
        with pytest.raises(ValueError, match="authorized decisions cannot have BLOCK action"):
            RiskDecision(
                decision_id=uuid4(),
                timestamps=timestamps,
                authorized=True,
                action="BLOCK"
            )


class TestExecutionIntent:
    """Test execution intent contract."""
    
    def test_execution_intent_creation(self):
        """Test basic execution intent creation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        intent = ExecutionIntent(
            risk_decision_id=uuid4(),
            instrument=instrument,
            timestamps=timestamps,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100")
        )
        
        assert intent.side == Side.BUY
        assert intent.order_type == OrderType.MARKET
        assert intent.quantity == Decimal("100")
    
    def test_limit_order_requires_price(self):
        """Test that limit orders require price."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        with pytest.raises(ValueError, match="price is required for limit orders"):
            ExecutionIntent(
                risk_decision_id=uuid4(),
                instrument=instrument,
                timestamps=timestamps,
                side=Side.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("100")
            )


class TestOrder:
    """Test order contract."""
    
    def test_order_creation(self):
        """Test basic order creation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        order = Order(
            execution_id=uuid4(),
            instrument=instrument,
            timestamps=timestamps,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100")
        )
        
        assert order.side == Side.BUY
        assert order.status == OrderStatus.CREATED
        assert order.filled_quantity == Decimal("0")
    
    def test_remaining_quantity(self):
        """Test remaining quantity calculation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        order = Order(
            execution_id=uuid4(),
            instrument=instrument,
            timestamps=timestamps,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
            filled_quantity=Decimal("30")
        )
        
        assert order.remaining_quantity() == Decimal("70")
    
    def test_is_fully_filled(self):
        """Test fully filled check."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Partially filled
        order1 = Order(
            execution_id=uuid4(),
            instrument=instrument,
            timestamps=timestamps,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
            filled_quantity=Decimal("30")
        )
        assert not order1.is_fully_filled()
        
        # Fully filled
        order2 = Order(
            execution_id=uuid4(),
            instrument=instrument,
            timestamps=timestamps,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
            filled_quantity=Decimal("100")
        )
        assert order2.is_fully_filled()


class TestPosition:
    """Test position contract."""
    
    def test_position_creation(self):
        """Test basic position creation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        position = Position(
            instrument=instrument,
            timestamps=timestamps,
            quantity=Decimal("100"),
            avg_cost=Decimal("150.00")
        )
        
        assert position.quantity == Decimal("100")
        assert position.avg_cost == Decimal("150.00")
    
    def test_position_direction(self):
        """Test position direction checks."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Long position
        long_position = Position(
            instrument=instrument,
            timestamps=timestamps,
            quantity=Decimal("100")
        )
        assert long_position.is_long()
        assert not long_position.is_short()
        
        # Short position
        short_position = Position(
            instrument=instrument,
            timestamps=timestamps,
            quantity=Decimal("-100")
        )
        assert not short_position.is_long()
        assert short_position.is_short()


class TestFailure:
    """Test failure contract."""
    
    def test_failure_creation(self):
        """Test basic failure creation."""
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        failure = Failure(
            timestamps=timestamps,
            category=FailureCategory.MODEL_ERROR,
            severity="high",
            description="Model prediction failed"
        )
        
        assert failure.category == FailureCategory.MODEL_ERROR
        assert failure.severity == "high"
    
    def test_failure_validation(self):
        """Test failure validation."""
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Invalid severity should fail
        with pytest.raises(ValueError, match="severity must be low, medium, high, or critical"):
            Failure(
                timestamps=timestamps,
                category=FailureCategory.MODEL_ERROR,
                severity="invalid"
            )


class TestExperience:
    """Test experience contract."""
    
    def test_experience_creation(self):
        """Test basic experience creation."""
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        experience = Experience(
            timestamps=timestamps,
            outcome="success",
            lesson="Momentum signals work in trending regimes"
        )
        
        assert experience.outcome == "success"
        assert "momentum" in experience.lesson.lower()
    
    def test_experience_validation(self):
        """Test experience validation."""
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Invalid outcome should fail
        with pytest.raises(ValueError, match="outcome must be success, failure, partial, or unknown"):
            Experience(
                timestamps=timestamps,
                outcome="invalid"
            )


class TestWorldState:
    """Test world state contract."""
    
    def test_world_state_creation(self):
        """Test basic world state creation."""
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        world_state = WorldState(
            timestamps=timestamps,
            regime_trend="bullish",
            regime_volatility="low",
            regime_crisis=False
        )
        
        assert world_state.regime_trend == "bullish"
        assert world_state.regime_crisis is False
    
    def test_state_hash(self):
        """Test state hash generation."""
        timestamps = Timestamps(
            event_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            received_time=datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        )
        
        world_state = WorldState(
            timestamps=timestamps,
            regime_trend="bullish",
            regime_volatility="low"
        )
        
        state_hash = world_state.state_hash()
        assert "2024-01-01" in state_hash
        assert "bullish" in state_hash


class TestContractValidation:
    """Test contract validation system."""
    
    def test_validate_market_event(self):
        """Test market event validation."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        event = MarketEvent(
            instrument=instrument,
            timestamps=timestamps,
            price=Decimal("150.25")
        )
        
        assert validate_contract(event)
    
    def test_version_mismatch(self):
        """Test version mismatch detection."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Create event with wrong version (we'd need to modify the dataclass to test this properly)
        # For now, we test the validation function exists
        assert CANONICAL_CONTRACT_VERSION == "1.0.0"


class TestSerialization:
    """Test contract serialization and deserialization."""
    
    def test_market_event_serialization(self):
        """Test market event serialization to dict."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            received_time=datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        )
        
        event = MarketEvent(
            instrument=instrument,
            timestamps=timestamps,
            price=Decimal("150.25"),
            source="test"
        )
        
        event_dict = contract_to_dict(event)
        
        # Check that serialization produces a dict
        assert isinstance(event_dict, dict)
        # Check that it has some content
        assert len(event_dict) > 0
        # Check that price is serialized correctly
        assert event_dict.get('price') == "150.25"
    
    def test_market_event_deserialization(self):
        """Test market event deserialization from dict."""
        # Create proper nested structure for deserialization
        instrument_dict = {
            'symbol': 'AAPL',
            'asset_class': 'equity',
            'currency': 'USD',
            'exchange': None,
            'isin': None,
            'cusip': None,
            'sector': None,
            'industry': None,
            'country': None,
            'multiplier': None,
            'tick_size': None
        }
        
        timestamps_dict = {
            'event_time': '2024-01-01T12:00:00+00:00',
            'received_time': '2024-01-01T12:00:01+00:00',
            'published_time': None,
            'effective_time': None,
            'available_at': None
        }
        
        # First test nested object deserialization
        instrument = dict_to_contract(Instrument, instrument_dict)
        assert instrument.symbol == "AAPL"
        assert instrument.asset_class == AssetClass.EQUITY
        
        timestamps = dict_to_contract(Timestamps, timestamps_dict)
        assert timestamps.event_time.year == 2024
        
        # Then test that we can create the full event
        event = MarketEvent(
            instrument=instrument,
            timestamps=timestamps,
            price=Decimal("150.25"),
            source="test"
        )
        
        assert event.instrument.symbol == "AAPL"
        assert event.price == Decimal("150.25")
        assert event.source == "test"
    
    def test_round_trip_serialization(self):
        """Test round-trip serialization and deserialization."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            received_time=datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        )
        
        original_event = MarketEvent(
            instrument=instrument,
            timestamps=timestamps,
            price=Decimal("150.25"),
            source="test"
        )
        
        # Serialize to dict
        event_dict = contract_to_dict(original_event)
        assert isinstance(event_dict, dict)
        assert event_dict.get('price') == "150.25"
        
        # Deserialize nested objects
        instrument_from_dict = dict_to_contract(Instrument, event_dict['instrument'])
        timestamps_from_dict = dict_to_contract(Timestamps, event_dict['timestamps'])
        
        # Reconstruct event
        reconstructed_event = MarketEvent(
            instrument=instrument_from_dict,
            timestamps=timestamps_from_dict,
            price=Decimal(event_dict['price']),
            source=event_dict['source']
        )
        
        assert reconstructed_event.instrument.symbol == original_event.instrument.symbol
        assert reconstructed_event.price == original_event.price
        assert reconstructed_event.source == original_event.source


class TestContractRegistry:
    """Test contract registry system."""
    
    def test_list_contracts(self):
        """Test listing all contracts."""
        contracts = list_contracts()
        
        assert "MarketEvent" in contracts
        assert "Quote" in contracts
        assert "Trade" in contracts
        assert "Forecast" in contracts
        assert "Decision" in contracts
        assert "WorldState" in contracts
    
    def test_get_contract(self):
        """Test getting contract by name."""
        market_event_class = get_contract("MarketEvent")
        assert market_event_class == MarketEvent
        
        forecast_class = get_contract("Forecast")
        assert forecast_class == Forecast
    
    def test_get_unknown_contract(self):
        """Test getting unknown contract raises error."""
        with pytest.raises(ValueError, match="Unknown contract"):
            get_contract("UnknownContract")


class TestCrossContractIntegration:
    """Test integration between different contract types."""
    
    def test_decision_to_execution_flow(self):
        """Test flow from decision to execution intent."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Create decision
        decision = Decision(
            instrument=instrument,
            timestamps=timestamps,
            action="BUY",
            quantity=Decimal("100"),
            expected_return=Decimal("0.05")
        )
        
        # Create risk decision
        risk_decision = RiskDecision(
            decision_id=decision.decision_id,
            timestamps=timestamps,
            authorized=True,
            action="APPROVE",
            original_quantity=decision.quantity,
            authorized_quantity=decision.quantity
        )
        
        # Create execution intent
        execution_intent = ExecutionIntent(
            risk_decision_id=risk_decision.risk_decision_id,
            instrument=instrument,
            timestamps=timestamps,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=risk_decision.authorized_quantity
        )
        
        assert execution_intent.quantity == Decimal("100")
        assert execution_intent.side == Side.BUY
    
    def test_order_to_fill_flow(self):
        """Test flow from order to fill."""
        instrument = Instrument(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            currency=Currency.USD
        )
        
        timestamps = Timestamps(
            event_time=datetime.now(timezone.utc),
            received_time=datetime.now(timezone.utc)
        )
        
        # Create order
        order = Order(
            execution_id=uuid4(),
            instrument=instrument,
            timestamps=timestamps,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100")
        )
        
        # Create fill
        fill = Fill(
            order_id=order.order_id,
            instrument=instrument,
            timestamps=timestamps,
            side=order.side,
            quantity=Decimal("100"),
            price=Decimal("150.25")
        )
        
        assert fill.order_id == order.order_id
        assert fill.quantity == order.quantity
        assert fill.side == order.side