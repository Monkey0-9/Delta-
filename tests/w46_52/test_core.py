from datetime import (
    datetime,
    timezone,
    timedelta,
)

from data.pit.factory import (
    MarketEvent,
    PITFactory,
)

from world.state import (
    WorldState,
    WorldStateStore,
)

from research.validation.purged import (
    LabelInterval,
    PurgedTimeSeriesSplit,
)

from research.statistics.advanced import (
    max_drawdown,
    newey_west_mean_tstat,
    benjamini_hochberg,
)

from finance_model.datasets.factory import (
    FinanceExample,
    FinanceDatasetFactory,
)

from finance_model.finbench import (
    BenchCase,
    FINBench,
)


UTC = timezone.utc


def test_pit_excludes_late_publication():

    events = [

        MarketEvent(
            "a",
            "AAPL",
            datetime(
                2026,
                1,
                1,
                tzinfo=UTC,
            ),
            datetime(
                2026,
                1,
                1,
                1,
                tzinfo=UTC,
            ),
            "source",
            100,
        ),

        MarketEvent(
            "b",
            "AAPL",
            datetime(
                2026,
                1,
                1,
                2,
                tzinfo=UTC,
            ),
            datetime(
                2026,
                1,
                1,
                5,
                tzinfo=UTC,
            ),
            "source",
            101,
        ),
    ]

    snapshot = PITFactory().build(
        events,
        datetime(
            2026,
            1,
            1,
            3,
            tzinfo=UTC,
        ),
    )

    assert [
        event.event_id
        for event in snapshot.events
    ] == ["a"]


def test_world_state_reproducible():

    arguments = dict(
        state_id="state",
        version=1,
        timestamp=datetime(
            2026,
            1,
            1,
            tzinfo=UTC,
        ),
        prices={
            "AAPL": 100
        },
        positions={
            "AAPL": 1
        },
        features={
            "momentum": 0.1
        },
        regime="RISK_ON",
        source_hash="abc",
    )

    a = WorldState.create(
        **arguments
    )

    b = WorldState.create(
        **arguments
    )

    assert (
        a.state_hash
        == b.state_hash
    )


def test_world_state_collision():

    store = WorldStateStore()

    first = WorldState.create(
        state_id="state",
        version=1,
        timestamp=datetime(
            2026,
            1,
            1,
            tzinfo=UTC,
        ),
        prices={
            "AAPL": 100
        },
        positions={},
        features={},
        regime="NORMAL",
        source_hash="a",
    )

    second = WorldState.create(
        state_id="state",
        version=1,
        timestamp=datetime(
            2026,
            1,
            1,
            tzinfo=UTC,
        ),
        prices={
            "AAPL": 101
        },
        positions={},
        features={},
        regime="NORMAL",
        source_hash="b",
    )

    store.put(first)

    try:
        store.put(second)
        assert False
    except ValueError:
        pass


def test_purging():

    t = datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
    )

    intervals = [
        LabelInterval(
            t + timedelta(days=i),
            t + timedelta(days=i + 2),
        )
        for i in range(10)
    ]

    splits = list(
        PurgedTimeSeriesSplit(
            n_splits=2
        ).split(intervals)
    )

    train, test = splits[0]

    assert not (
        set(train)
        & set(test)
    )


def test_statistics():

    assert (
        max_drawdown(
            [0.10, -0.20, 0.10]
        )
        < 0
    )

    assert (
        newey_west_mean_tstat(
            [
                0.01,
                0.02,
                0.015,
                0.01,
                0.02,
            ]
        )
        > 0
    )


def test_benjamini_hochberg():

    qvalues = benjamini_hochberg(
        [
            0.001,
            0.02,
            0.8,
        ]
    )

    assert (
        qvalues[0]
        <= qvalues[1]
        <= qvalues[2]
    )


def test_dataset_fingerprint():

    example = FinanceExample(
        example_id="example-1",
        task="risk",
        prompt="What is portfolio risk?",
        target="Use evidence.",
        evidence_ids=("source-1",),
        asof=(
            "2026-01-01T00:00:00+00:00"
        ),
        asset="AAPL",
        label="WAIT",
    )

    factory = FinanceDatasetFactory(
        "w50-v1"
    )

    assert (
        factory.fingerprint(
            [example]
        )
        ==
        factory.fingerprint(
            [example]
        )
    )


def test_finbench():

    benchmark = FINBench(
        [
            BenchCase(
                case_id="risk-1",
                domain="risk",
                prompt="What action?",
                expected="WAIT",
                required_terms=(
                    "wait",
                ),
            )
        ]
    )

    results = benchmark.run(
        lambda _: "WAIT"
    )

    assert results[0].passed

    assert (
        benchmark.aggregate(
            results
        )["pass_rate"]
        == 1.0
    )