import numpy as np

from ozbet.agents.market import shin
from ozbet.research import model_eval as M


def test_shin_vector_matches_scalar():
    odds = np.array([[1.6, 4.2, 5.25], [2.9, 3.3, 2.5]])
    v = M.shin_v(odds)
    for row, o in zip(v, odds):
        assert np.allclose(row, shin(list(o)), atol=1e-6)


def test_shin_inverse_roundtrip_and_margin():
    p = np.array([[0.5, 0.3, 0.2], [0.55, 0.45, 0.0][:2] + [0.0]])[:1]
    o = M.shin_inverse(p, 0.20)
    assert abs((1 / o).sum() - 1.20) < 1e-6
    assert np.allclose(M.shin_v(o), p, atol=1e-4)


def test_probs_sum_and_ou():
    p, po = M.probs(np.array([1.5, 0.8]), np.array([1.1, 1.9]), np.array([-0.05, -0.05]))
    assert np.allclose(p.sum(1), 1)
    assert p[0, 0] > p[0, 2] and p[1, 2] > p[1, 0]
    assert ((po > 0) & (po < 1)).all()


def test_stack_recovers_market_when_market_is_truth():
    rng = np.random.default_rng(1)
    q = rng.dirichlet([4, 3, 3], 3000)
    y = np.array([rng.choice(3, p=r) for r in q])
    noise = rng.dirichlet([3, 3, 3], 3000)
    th, _ = M.stack_fit(noise, q, np.abs(q[:, 0] - q[:, 2]), y)
    assert abs(th[2]) < 0.2 and 0.7 < th[4] < 1.3
