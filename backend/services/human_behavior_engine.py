"""Provider-neutral access to a human-behaviour model.

ChessGuru must never depend on one research model. Maia-3 is the strongest
published option and is AGPL-3.0, which is unusable inside a hosted product;
Maia-2 and Otter are both MIT. That situation will keep changing, so the rest
of the codebase talks to HumanBehaviorEngine and never to a provider directly.

What this layer is for -- and not for:
  Stockfish  decides whether a move is good.        (objective truth)
  Detectors  decide what mechanism went wrong.      (chess semantics)
  THIS       says how likely a human of a given     (population prior)
             strength is to choose a move.

A provider must therefore never be consulted for correctness. Its output
ranks moves that Stockfish has ALREADY judged acceptable; used alone it will
happily rank a popular blunder first.

Providers are optional imports: an unavailable model degrades to None rather
than breaking analysis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class MoveContext:
    """Everything any current or future provider might condition on.

    Deliberately richer than Maia-2 needs, so adding a context-aware provider
    (Otter uses history and clock) requires no call-site changes.
    """
    fen: str
    player_elo: int
    opponent_elo: int
    time_control: str = "600+0"
    history_uci: Sequence[str] = field(default_factory=tuple)
    clock_seconds: Optional[int] = None
    clock_fraction: Optional[float] = None
    move_number: Optional[int] = None


@dataclass(frozen=True)
class MoveDistribution:
    """A provider's answer for one position."""
    provider: str
    provider_version: str
    probabilities: Mapping[str, float]      # uci -> probability

    def probability_of(self, uci: str) -> Optional[float]:
        return self.probabilities.get(uci)

    def top(self, k: int = 5) -> List[tuple]:
        return sorted(self.probabilities.items(), key=lambda kv: -kv[1])[:k]

    def human_surprise(self, uci: str) -> Optional[float]:
        """-log P(move). High means comparable players rarely choose it.

        Returns None rather than infinity for an unlisted move: absence from a
        truncated top-k list is not evidence the move is never played.
        """
        p = self.probability_of(uci)
        if p is None or p <= 0:
            return None
        return -math.log(p)


class HumanBehaviorProvider:
    """Interface every provider implements."""

    name = "abstract"
    version = "0"

    def available(self) -> bool:
        raise NotImplementedError

    def predict(self, ctx: MoveContext, top_k: int = 10) -> Optional[MoveDistribution]:
        raise NotImplementedError

    def predict_across_elos(
        self, ctx: MoveContext, elos: Sequence[int], uci: str
    ) -> Dict[int, Optional[float]]:
        """P(uci) as the player's rating varies -- the developmental curve."""
        out: Dict[int, Optional[float]] = {}
        for elo in elos:
            probe = MoveContext(
                fen=ctx.fen, player_elo=int(elo), opponent_elo=ctx.opponent_elo,
                time_control=ctx.time_control, history_uci=ctx.history_uci,
                clock_seconds=ctx.clock_seconds, clock_fraction=ctx.clock_fraction,
                move_number=ctx.move_number,
            )
            dist = self.predict(probe)
            out[int(elo)] = dist.probability_of(uci) if dist else None
        return out


class OtterProvider(HumanBehaviorProvider):
    """Otter (MIT). Conditions on move history and clock as well as Elo."""

    name = "otter"

    def __init__(self, device: str = "cpu") -> None:
        self._device = device
        self._model: Any = None
        self.version = "otter-chess"

    def available(self) -> bool:
        try:
            import otter_chess  # noqa: F401
            return True
        except ImportError:
            return False

    def _load(self) -> Any:
        if self._model is None:
            from otter_chess import OtterModel
            self._model = OtterModel(device=self._device)
        return self._model

    def predict(self, ctx: MoveContext, top_k: int = 10) -> Optional[MoveDistribution]:
        if not self.available():
            return None
        kwargs: Dict[str, Any] = {
            "fen": ctx.fen,
            "player_elo": int(ctx.player_elo),
            "opponent_elo": int(ctx.opponent_elo),
            "time_control": ctx.time_control,
            "top_k": top_k,
        }
        if ctx.history_uci:
            kwargs["history_moves"] = list(ctx.history_uci)
        if ctx.clock_fraction is not None:
            kwargs["clock_fraction"] = float(ctx.clock_fraction)
        elif ctx.clock_seconds is not None:
            kwargs["time_remaining"] = int(ctx.clock_seconds)
        # _load() must stay INSIDE the guard: weight download, disk, and OOM
        # failures all surface there, and an unavailable model must degrade to
        # None rather than break the analysis pipeline.
        try:
            raw = self._load().predict(**kwargs)
        except Exception:
            return None
        probs = _normalise_provider_output(raw)
        if not probs:
            return None
        return MoveDistribution(self.name, self.version, probs)


class Maia2Provider(HumanBehaviorProvider):
    """Maia-2 (MIT). Position + both Elos; no history or clock conditioning."""

    name = "maia2"

    def __init__(self, model_type: str = "rapid", device: str = "cpu") -> None:
        self._model_type = model_type
        self._device = device
        self._model: Any = None
        self._prepared: Any = None
        self.version = f"maia2-{model_type}"

    def available(self) -> bool:
        try:
            import maia2  # noqa: F401
            return True
        except ImportError:
            return False

    def _load(self):
        if self._model is None:
            from maia2 import model as maia_model, inference
            self._model = maia_model.from_pretrained(
                type=self._model_type, device=self._device)
            self._prepared = inference.prepare()
        return self._model, self._prepared

    def predict(self, ctx: MoveContext, top_k: int = 10) -> Optional[MoveDistribution]:
        if not self.available():
            return None
        try:
            from maia2 import inference
            model, prepared = self._load()
            raw = inference.inference_each(
                model, prepared, ctx.fen,
                int(ctx.player_elo), int(ctx.opponent_elo),
            )
        except Exception:
            return None
        probs = _normalise_provider_output(raw)
        if not probs:
            return None
        return MoveDistribution(self.name, self.version, probs)


def _normalise_provider_output(raw: Any) -> Dict[str, float]:
    """Coerce a provider's return value into {uci: probability}.

    Providers differ in shape (dict of dicts, list of dicts, bare mapping), so
    this stays defensive rather than assuming one contract.
    """
    if raw is None:
        return {}
    # Maia-2's inference_each returns (move_probs, win_probability); the
    # second element is not a move distribution and must not be flattened in.
    if (
        isinstance(raw, tuple)
        and len(raw) == 2
        and isinstance(raw[0], Mapping)
        and isinstance(raw[1], (int, float))
    ):
        return _normalise_provider_output(raw[0])
    if isinstance(raw, Mapping):
        for key in ("move_probs", "probabilities", "moves", "policy", "top_moves"):
            if key in raw:
                return _normalise_provider_output(raw[key])
        out: Dict[str, float] = {}
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, (int, float)):
                out[k] = float(v)
        return out
    if isinstance(raw, (list, tuple)):
        out = {}
        for item in raw:
            if isinstance(item, Mapping):
                uci = item.get("uci") or item.get("move")
                p = item.get("probability", item.get("prob", item.get("p")))
                if isinstance(uci, str) and isinstance(p, (int, float)):
                    out[uci] = float(p)
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                uci, p = item
                if isinstance(uci, str) and isinstance(p, (int, float)):
                    out[uci] = float(p)
        return out
    return {}


def get_providers(device: str = "cpu") -> List[HumanBehaviorProvider]:
    """Every provider that can actually run here."""
    return [p for p in (Maia2Provider(device=device), OtterProvider(device=device))
            if p.available()]
