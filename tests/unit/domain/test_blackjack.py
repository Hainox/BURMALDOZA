from dataclasses import replace

import pytest
from burmaldoza_domain.core import InvalidActionError
from burmaldoza_domain.games.blackjack import (
    BlackjackPhase,
    BlackjackRules,
    BlackjackState,
    Card,
    apply_action,
    deal_initial,
    hand_value,
    settle_blackjack,
)
from burmaldoza_domain.rng import SeededRandomSource

RULES = BlackjackRules()


def card(rank: str, suit: str = "spades") -> Card:
    return Card(rank=rank, suit=suit)


def state(
    player_cards: tuple[Card, ...],
    dealer_cards: tuple[Card, ...],
    deck: tuple[Card, ...] = (),
    *,
    phase: BlackjackPhase = BlackjackPhase.PLAYER_TURN,
    bet: int = 25,
    dealer_hole_hidden: bool = True,
) -> BlackjackState:
    return BlackjackState(
        phase=phase,
        bet=bet,
        player_cards=player_cards,
        dealer_cards=dealer_cards,
        dealer_hole_hidden=dealer_hole_hidden,
        player_total=hand_value(player_cards).total,
        dealer_total=hand_value(dealer_cards).total,
        state_version=0,
        ruleset_version="blackjack-gfl-skeleton-1",
        deck=deck,
        player_natural_blackjack=len(player_cards) == 2 and hand_value(player_cards).total == 21,
    )


def test_hand_value_fixtures_cover_aces_blackjack_hard_21_and_bust() -> None:
    assert hand_value((card("A"), card("6"))).total == 17
    assert hand_value((card("A"), card("A"), card("5"))).soft is True
    assert hand_value((card("A"), card("6"), card("10"))).total == 17
    assert hand_value((card("A"), card("K"))).is_blackjack is True
    assert hand_value((card("10"), card("5"), card("6"))).total == 21
    assert hand_value((card("K"), card("9"), card("5"))).is_bust is True


def test_deal_initial_uses_one_deck_and_hides_dealer_hole_card() -> None:
    dealt = deal_initial(25, SeededRandomSource(42), RULES)

    assert len(dealt.player_cards) == 2
    assert len(dealt.dealer_cards) == 2
    assert len(dealt.deck) == 48
    assert dealt.dealer_hole_hidden is True


def test_hit_adds_exactly_one_card() -> None:
    current = state((card("5"), card("6")), (card("10"), card("7")), (card("2"),))

    transition = apply_action(current, "hit", SeededRandomSource(1), RULES)

    assert len(transition.state.player_cards) == 3
    assert transition.state.player_cards[-1] == card("2")
    assert transition.state.state_version == 1


def test_stand_reveals_hole_and_enters_dealer_resolution() -> None:
    current = state((card("10"), card("6")), (card("10"), card("6")), (card("5"),))

    transition = apply_action(current, "stand", SeededRandomSource(1), RULES)

    assert transition.state.phase is BlackjackPhase.DEALER_RESOLUTION
    assert transition.state.dealer_hole_hidden is False
    assert transition.state.dealer_total == 21


def test_double_doubles_stake_and_allows_one_additional_card() -> None:
    current = state((card("5"), card("6")), (card("10"), card("7")), (card("5"),))

    transition = apply_action(current, "double", SeededRandomSource(1), RULES)

    assert transition.state.bet == 50
    assert len(transition.state.player_cards) == 3
    assert transition.state.doubled is True
    assert transition.state.phase is BlackjackPhase.DEALER_RESOLUTION


def test_dealer_soft_17_stands_when_rules_require_it() -> None:
    current = state((card("10"), card("7")), (card("A"), card("6")), ())

    transition = apply_action(current, "stand", SeededRandomSource(1), RULES)

    assert transition.state.dealer_total == 17
    assert len(transition.state.dealer_cards) == 2


def test_settlement_covers_blackjack_push_and_bust() -> None:
    blackjack = replace(
        state((card("A"), card("K")), (card("10"), card("9")), phase=BlackjackPhase.DEALER_RESOLUTION),
        dealer_hole_hidden=False,
    )
    push = replace(
        state((card("10"), card("7")), (card("10"), card("7")), phase=BlackjackPhase.DEALER_RESOLUTION),
        dealer_hole_hidden=False,
    )
    bust = replace(
        state((card("K"), card("9"), card("5")), (card("10"), card("7")), phase=BlackjackPhase.SETTLED),
        dealer_hole_hidden=False,
    )

    assert settle_blackjack(blackjack, RULES).result == "blackjack"
    assert settle_blackjack(blackjack, RULES).payout == 62
    assert settle_blackjack(push, RULES).result == "push"
    assert settle_blackjack(push, RULES).payout == 25
    assert settle_blackjack(bust, RULES).result == "loss"
    assert settle_blackjack(bust, RULES).payout == 0


def test_actions_after_settlement_are_rejected() -> None:
    current = state(
        (card("10"), card("7")),
        (card("10"), card("7")),
        phase=BlackjackPhase.SETTLED,
        dealer_hole_hidden=False,
    )

    with pytest.raises(InvalidActionError):
        apply_action(current, "hit", SeededRandomSource(1), RULES)
