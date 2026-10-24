from uuid import uuid4

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient

from tests.unit.test_api_routes import _auth_headers, _sqlite_api


@pytest.mark.asyncio
@pytest.mark.parametrize('game,count', [('blackjack', 3), ('holdem', 6)])
async def test_tables_complete_authenticated_http_round(game, count):
    async with (_sqlite_api(), AsyncClient(transport=ASGITransport(app=app),
                                         base_url='http://test') as client):
        room_id = None
        users = list(range(78001, 78001 + count))
        for user in users:
            if game == 'blackjack' and room_id:
                response = await client.post(f'/api/v1/rooms/{room_id}/join',
                    headers=_auth_headers(user), json={'action_id': str(uuid4())})
            else:
                data = {'game_type': game, 'mode': 'table' if game == 'blackjack' else 'pvp',
                        'action_id': str(uuid4())}
                if game == 'holdem':
                    data.update(buy_in=100, table_capacity=6)
                response = await client.post('/api/v1/rooms', headers=_auth_headers(user), json=data)
            assert response.status_code == 200, response.text
            if room_id:
                assert response.json()['room_id'] == room_id
            room_id = response.json()['room_id']

        async def snapshot(user):
            response = await client.get(f'/api/v1/rooms/{room_id}', headers=_auth_headers(user))
            assert response.status_code == 200, response.text
            return response.json()

        async def action(user, name, **payload):
            view = await snapshot(user)
            response = await client.post(f'/api/v1/rooms/{room_id}/actions',
                headers=_auth_headers(user), json={'action_id': str(uuid4()),
                'expected_state_version': view['state_version'],
                'payload': {'action': name, **payload}})
            assert response.status_code == 200, response.text

        seats = {(await snapshot(user))['public_state']['viewer_seat']: user for user in users}
        if game == 'blackjack':
            for user in users:
                await action(user, 'ready', bet=25)
            await action(users[0], 'start')
        for _ in range(40):
            view = await snapshot(users[0])
            public = view['public_state']
            assert 'deck' not in str(public)
            if public['phase'] == 'settled':
                break
            seat = public['active_seat' if game == 'blackjack' else 'current_seat']
            await action(seats[seat], 'stand' if game == 'blackjack' else 'fold')
        else:
            pytest.fail('table did not finish')
        assert len(public['players']) == count
        if game == 'holdem':
            payouts = 0
            for user in users:
                response = await client.get('/api/v1/holdem/history', headers=_auth_headers(user))
                assert response.status_code == 200, response.text
                payouts += response.json()['items'][0]['payout']
            assert payouts == 100 * count
