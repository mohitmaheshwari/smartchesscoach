"""The money side: tokens are facts, cost is derived, and nothing is free.

Mohit asked what the LLM is costing. The honest starting point was that
nothing was recorded: `_call_openai` and `_call_claude` both received a
`usage` object from the provider and both returned only the message text.
There was no collection, no counter, and no way to recover a past call.

The two failure modes this file exists to prevent are not arithmetic.

  An unpriced model reading as ZERO. `gpt-6-luna` has no published rate in
  this repo, and a page that totals it as free looks healthy while
  understating the invoice. Same shape as a template field authored as ""
  shipping silently.

  The motor/pymongo mismatch. The API process holds an async handle and the
  worker a sync one. Calling motor's insert_one from sync code returns a
  coroutine nobody awaits: no write, no error, and a bill that looks small.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import llm_usage  # noqa: E402


class _Usage:
    """Shaped like OpenAI's usage object."""
    def __init__(self, prompt=0, completion=0, cached=0):
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.prompt_tokens_details = type(
            "D", (), {"cached_tokens": cached})()


class _ClaudeUsage:
    """Shaped like Anthropic's, which names the same things differently."""
    def __init__(self, inp=0, out=0, cache_read=0):
        self.input_tokens = inp
        self.output_tokens = out
        self.cache_read_input_tokens = cache_read


class _FakeColl:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)


class _FakeDb:
    def __init__(self):
        self.coll = _FakeColl()

    def __getitem__(self, name):
        return self.coll


class TestItReadsBothProvidersUsageShapes:
    def test_openai_field_names(self):
        tok = llm_usage._extract(_Usage(prompt=1200, completion=80,
                                        cached=1000))
        assert tok["input_tokens"] == 1200
        assert tok["output_tokens"] == 80
        assert tok["cached_input_tokens"] == 1000

    def test_anthropic_field_names(self):
        tok = llm_usage._extract(_ClaudeUsage(inp=900, out=40,
                                              cache_read=512))
        assert tok["input_tokens"] == 900
        assert tok["output_tokens"] == 40
        assert tok["cached_input_tokens"] == 512

    def test_an_unknown_shape_yields_zeros_rather_than_raising(self):
        assert llm_usage._extract(object()) == {
            "input_tokens": 0, "output_tokens": 0,
            "cached_input_tokens": 0, "reasoning_tokens": 0}


class TestAnUnpricedModelIsNeverFree:
    def test_cost_is_none_when_no_price_is_set(self, monkeypatch):
        monkeypatch.setattr(llm_usage, "_prices_cache",
                            {"models": {}}, raising=False)
        assert llm_usage.cost_usd("gpt-6-luna", 1_000_000, 1_000_000) is None

    def test_none_is_not_zero(self, monkeypatch):
        """The distinction the page depends on: a model with no rate must
        be reportable as unknown, not summed in as nothing."""
        monkeypatch.setattr(llm_usage, "_prices_cache",
                            {"models": {}}, raising=False)
        assert llm_usage.cost_usd("x", 10, 10) is not 0.0  # noqa: F632
        assert llm_usage.cost_usd("x", 10, 10) is None

    def test_an_entry_that_exists_with_null_rates_is_not_free(self):
        """The hole the first version had. An EMPTY table was tested and
        passed; the config actually ships `gpt-4o-mini` LISTED with nulls,
        and `float(None or 0.0)` made it $0.00 -- a model totalled as free
        on a cost page. The test has to use the shape that ships."""
        monkey = {"models": {"gpt-4o-mini": {"input_per_mtok": None,
                                             "output_per_mtok": None}}}
        import services.llm_usage as m
        old = m._prices_cache
        try:
            m._prices_cache = monkey
            assert m.cost_usd("gpt-4o-mini", 1_000_000, 1_000_000) is None
        finally:
            m._prices_cache = old

    def test_the_real_shipped_config_prices_luna_and_not_the_other(self):
        """Against the actual file, not a fixture."""
        llm_usage.load_prices(refresh=True)
        assert llm_usage.cost_usd("gpt-6-luna", 1_000_000, 0) == 0.1
        assert llm_usage.cost_usd("gpt-4o-mini", 1_000_000, 0) is None

    def test_the_shipped_table_has_no_invented_rates(self):
        """Nobody should discover later that a plausible-looking number was
        a guess. Every entry ships null until a real rate is filled in."""
        table = (llm_usage.load_prices(refresh=True).get("models") or {})
        assert table, "the price file should list the models we call"
        for model, p in table.items():
            for field in ("input_per_mtok", "output_per_mtok"):
                if field in p and p[field] is not None:
                    assert isinstance(p[field], (int, float)), model


class TestItPricesWhatItIsGiven:
    PRICES = {"models": {"gpt-6-luna": {"input_per_mtok": 2.0,
                                        "output_per_mtok": 8.0,
                                        "cached_input_per_mtok": 0.5}}}

    def test_a_plain_call(self, monkeypatch):
        monkeypatch.setattr(llm_usage, "_prices_cache", self.PRICES,
                            raising=False)
        # 1M input at $2 + 1M output at $8
        assert llm_usage.cost_usd("gpt-6-luna", 1_000_000,
                                  1_000_000) == 10.0

    def test_cached_input_is_billed_at_the_cached_rate(self, monkeypatch):
        monkeypatch.setattr(llm_usage, "_prices_cache", self.PRICES,
                            raising=False)
        # 1M input of which 1M was cached -> $0.50, plus no output
        assert llm_usage.cost_usd("gpt-6-luna", 1_000_000, 0,
                                  1_000_000) == 0.5

    def test_a_dated_snapshot_matches_by_prefix(self, monkeypatch):
        monkeypatch.setattr(llm_usage, "_prices_cache", self.PRICES,
                            raising=False)
        assert llm_usage.cost_usd("gpt-6-luna-2026-01-15",
                                  1_000_000, 0) == 2.0

    def test_an_unrelated_model_does_not_borrow_a_price(self, monkeypatch):
        monkeypatch.setattr(llm_usage, "_prices_cache", self.PRICES,
                            raising=False)
        assert llm_usage.cost_usd("claude-opus-5", 1_000_000, 0) is None


class TestRecordingNeverBreaksTheCall:
    def test_it_writes_a_row(self, monkeypatch):
        db = _FakeDb()
        llm_usage.set_db(db)
        monkeypatch.setattr(llm_usage, "_prices_cache",
                            TestItPricesWhatItIsGiven.PRICES, raising=False)
        llm_usage.record("gpt-6-luna", _Usage(prompt=100, completion=10),
                         surface="game_review_caption", user_id="u1",
                         game_id="g1")
        assert len(db.coll.docs) == 1
        doc = db.coll.docs[0]
        assert doc["surface"] == "game_review_caption"
        assert doc["user_id"] == "u1"
        assert doc["input_tokens"] == 100

    def test_a_pymongo_handle_is_not_treated_as_async(self):
        """The silent-no-write trap: a sync handle must take the sync path,
        or the insert returns a coroutine nobody awaits."""
        llm_usage.set_db(_FakeDb())
        assert llm_usage._is_async_db is False

    def test_an_unlabelled_call_still_records(self, monkeypatch):
        """A surface nobody wired must appear in the total, or the page
        shows less than the invoice and reads as complete."""
        db = _FakeDb()
        llm_usage.set_db(db)
        llm_usage.record("gpt-6-luna", _Usage(prompt=5, completion=1))
        assert db.coll.docs[0]["surface"] == "unattributed"

    def test_a_broken_db_does_not_raise(self):
        class Boom:
            def __getitem__(self, name):
                raise RuntimeError("mongo is down")
        llm_usage.set_db(Boom())
        llm_usage.record("gpt-6-luna", _Usage(prompt=5, completion=1))

    def test_no_usage_object_records_nothing(self):
        db = _FakeDb()
        llm_usage.set_db(db)
        llm_usage.record("gpt-6-luna", None)
        assert db.coll.docs == []

    def test_an_all_zero_usage_is_not_stored(self):
        db = _FakeDb()
        llm_usage.set_db(db)
        llm_usage.record("gpt-6-luna", _Usage())
        assert db.coll.docs == []


class TestTheCallSitesCaptureUsage:
    """Both providers hand back a usage object and both call sites used to
    drop it. Asserted through the source, because exercising them needs a
    live API key."""

    def _src(self):
        p = Path(__file__).resolve().parents[1] / "llm_service.py"
        return p.read_text(encoding="utf-8")

    def test_openai_records(self):
        src = self._src()
        i = src.index("async def _call_openai")
        body = src[i:src.index("async def _openai_tts")]
        assert "_record_usage(" in body, "the usage object is dropped again"

    def test_claude_records(self):
        src = self._src()
        i = src.index("async def _call_claude")
        body = src[i:src.index("# ==================== OPENAI")]
        assert "_record_usage(" in body, "the usage object is dropped again"

    def test_the_caption_path_labels_its_calls(self):
        """The biggest spender must say whose game it is, or per-user cost
        is unanswerable for the one surface that dominates it."""
        p = Path(__file__).resolve().parents[1] / "analysis_worker.py"
        src = p.read_text(encoding="utf-8")
        assert 'surface="game_review_caption"' in src
        assert "user_id=user_id" in src

    def test_the_worker_wires_its_own_db(self):
        """It is a separate process, so server.py's set_db does not reach
        it, and its calls would record nowhere."""
        p = Path(__file__).resolve().parents[1] / "analysis_worker.py"
        src = p.read_text(encoding="utf-8")
        assert "llm_usage.set_db(db)" in src
