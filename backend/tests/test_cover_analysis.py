"""Unit tests for LLM cover analysis with mocked backends."""

from app.pipeline import cover_analysis
from app.pipeline.cover_analysis import CoverAnalysis, CoverAnalysisBackend, OpenAICompatibleCoverBackend


class _StubBackend(CoverAnalysisBackend):
    """Returns queued results in order; raising entries simulate bad JSON."""

    def __init__(self, results: list[CoverAnalysis | Exception]) -> None:
        self._results = list(results)
        self.calls = 0

    def analyze(self, image_png: bytes) -> CoverAnalysis:
        self.calls += 1
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class TestAnalyzeCover:
    def test_happy_path(self) -> None:
        expected = CoverAnalysis(is_cover=True, title="Sefiller", author="Victor Hugo", confidence=0.9)
        backend = _StubBackend([expected])
        assert cover_analysis.analyze_cover(backend, b"png") == expected

    def test_invalid_json_retries_once_then_falls_back(self) -> None:
        backend = _StubBackend([ValueError("bad json"), ValueError("bad json again")])
        result = cover_analysis.analyze_cover(backend, b"png")
        assert backend.calls == 2  # initial attempt + one retry
        assert result == CoverAnalysis()  # neutral fallback, job not killed

    def test_retry_succeeds_after_one_failure(self) -> None:
        good = CoverAnalysis(is_cover=True, confidence=0.7)
        backend = _StubBackend([ValueError("bad json"), good])
        assert cover_analysis.analyze_cover(backend, b"png") == good


class TestPickBestCover:
    def test_picks_highest_confidence_valid_cover(self) -> None:
        backend = _StubBackend(
            [
                CoverAnalysis(is_cover=True, title="A", confidence=0.5),
                CoverAnalysis(is_cover=True, title="B", confidence=0.9),
                CoverAnalysis(is_cover=False),
            ]
        )
        image, analysis = cover_analysis.pick_best_cover(backend, [b"a", b"b", b"c"])
        assert image == b"b"
        assert analysis.title == "B"

    def test_falls_back_to_first_candidate_when_none_valid(self) -> None:
        backend = _StubBackend([CoverAnalysis(is_cover=False)] * 2)
        image, analysis = cover_analysis.pick_best_cover(backend, [b"first", b"second"])
        assert image == b"first"
        assert analysis == CoverAnalysis()

    def test_empty_candidates(self) -> None:
        backend = _StubBackend([])
        image, analysis = cover_analysis.pick_best_cover(backend, [])
        assert image is None
        assert backend.calls == 0
