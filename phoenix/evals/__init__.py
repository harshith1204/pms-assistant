"""No-op Phoenix evals shims."""

class _BaseEval:
    async def async_evaluate(self, **kwargs):
        class _R:
            score = 0.5
        return _R()


class RelevanceEvaluator(_BaseEval):
    pass


class QAEvaluator(_BaseEval):
    pass


class ToxicityEvaluator(_BaseEval):
    pass

