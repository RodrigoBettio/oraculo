import pytest
from unittest.mock import patch, AsyncMock
from starlette.testclient import TestClient
from web.app import app, save_agent
from ingestion.study_queue import StudyQueueManager, QueueItem
from models.agent import AgentProfile
from config import settings

def test_enqueue_batch_multi_agent():
    client = TestClient(app)
    agent1 = AgentProfile(id='agente_teste_1', name='Agente 1', role='Dev')
    agent2 = AgentProfile(id='agente_teste_2', name='Agente 2', role='Arquiteto')
    save_agent(agent1)
    save_agent(agent2)

    try:
        fake_groups = [{'id': 101, 'title': 'Curso TS'}]
        with patch('web.app.TelegramManager.list_groups_in_folder', new_callable=AsyncMock) as mock_list, \
             patch('ingestion.study_queue.StudyQueueManager.enqueue_multiple_groups', new_callable=AsyncMock) as mock_enq:
            mock_list.return_value = fake_groups
            mock_enq.return_value = ['item1', 'item2']

            res = client.post('/api/study/groups/batch', json={
                'agent_ids': ['agente_teste_1', 'agente_teste_2'],
                'group_ids': [101],
                'tier': 'audio_only',
                'only_pending': True
            })
            assert res.status_code == 200
            data = res.json()
            assert data['agents_count'] == 2
            assert mock_enq.call_count == 2
    finally:
        from config import settings
        for aid in ['agente_teste_1', 'agente_teste_2']:
            f = settings.AGENTS_DIR / f"{aid}.json"
            if f.exists():
                f.unlink()

def test_load_balancer_single_agent_concurrency():
    qm = StudyQueueManager()
    qm.queue.clear()
    qm.active_items.clear()
    original_db_get_all = qm._db_get_all
    qm._db_get_all = lambda: list(qm.queue)

    try:
        for i in range(5):
            item = QueueItem(
                agent_id='bruno',
                agent_name='Bruno',
                group_id=101,
                group_name='Curso TypeScript',
                message_id=100 + i,
                file_name=f'aula_{i}.mp4',
                tier='audio_only',
                status='queued'
            )
            qm.queue.append(item)

        status = qm.get_status()
        assert status['queue_count'] == 5
        assert status['max_workers'] == qm.max_workers
    finally:
        qm._db_get_all = original_db_get_all
