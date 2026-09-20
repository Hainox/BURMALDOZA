from burmaldoza_domain.games.blackjack import Card

from devtools.monte_carlo.holdem import run_holdem_simulation


def c(rank: str, suit: str) -> Card:
    return Card(rank, suit)


def test_holdem_equity_simulation_is_reproducible() -> None:
    hero = (c("A", "spades"), c("K", "spades"))
    villain_range = ((c("Q", "clubs"), c("Q", "diamonds")),)
    board = (c("2", "hearts"), c("7", "clubs"), c("9", "diamonds"))

    first = run_holdem_simulation(hero, villain_range, board, trials=1000, seed=42)
    second = run_holdem_simulation(hero, villain_range, board, trials=1000, seed=42)

    assert first == second
    assert first.trials == 1000
    assert 0 <= first.win_rate <= 1
    assert 0 <= first.tie_rate <= 1
    assert 0 <= first.loss_rate <= 1
    assert first.win_rate + first.tie_rate + first.loss_rate == 1
