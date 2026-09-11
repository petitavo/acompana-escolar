from datetime import timedelta
from types import SimpleNamespace
from sqlalchemy import select
from app.db import SessionLocal, now
from app.school_db import Notification, Institution, Membership, PushToken
from app.notifications import send_email, dispatch
from test_journeys import setup, enroll, post


def test_smtp_handoff_contains_no_clinical_payload(monkeypatch):
    import socketserver, threading
    received = []
    class SMTP(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(b'220 fixture.local ESMTP\r\n')
            while line := self.rfile.readline():
                command = line.upper()
                if command.startswith(b'DATA'):
                    self.wfile.write(b'354 send\r\n')
                    data = b''
                    while (line := self.rfile.readline()) != b'.\r\n':
                        if not line: return
                        data += line
                    received.append(data)
                    self.wfile.write(b'250 accepted\r\n')
                elif command.startswith(b'QUIT'):
                    self.wfile.write(b'221 bye\r\n'); return
                else:
                    self.wfile.write(b'250 OK\r\n')
    with socketserver.TCPServer(('127.0.0.1', 0), SMTP) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        monkeypatch.setenv('SMTP_HOST', '127.0.0.1'); monkeypatch.setenv('SMTP_PORT', str(server.server_address[1]))
        monkeypatch.setenv('SMTP_SECURITY', 'test_plain'); monkeypatch.setenv('SMTP_FROM', 'fixture@example.test')
        monkeypatch.delenv('SMTP_USER', raising=False)
        try:
            send_email('recipient@example.test', SimpleNamespace(id='fixture-id', detail={'score': 27, 'name': 'PRIVATE-NAME'}))
        finally:
            server.shutdown(); thread.join()
    assert len(received) == 1
    assert b'PRIVATE-NAME' not in received[0] and b'score' not in received[0]
    assert b'recipient@example.test' in received[0]


def test_email_retries_after_push_acceptance_without_resending_push(client, monkeypatch, tmp_path):
    c = client; inv, cfg = setup(c, False); phone = enroll(c, inv)
    c.headers['authorization'] = 'Bearer ' + phone['token']; post(c, '/me/support')
    with SessionLocal.begin() as db:
        n = db.scalar(select(Notification).where(Notification.kind == 'case')); nid = n.id
        inst = db.scalar(select(Institution)); inst.settings = {**inst.settings, 'external_notifications_authorized': True}
        member = db.scalar(select(Membership).where(Membership.user_id == n.recipient_id))
        member.preferences = {'notification_email': 'fixture@example.test'}
        db.add(PushToken(owner_id=n.recipient_id, token_hash='fixture-hash', token='fixture-token'))
    credentials = tmp_path/'fixture.json'; credentials.write_text('{}')
    for k, v in {'FCM_SERVICE_ACCOUNT': str(credentials), 'ALLOW_EXTERNAL_NOTIFICATIONS': 'true', 'SMTP_HOST': '127.0.0.1', 'SMTP_FROM': 'fixture@example.test'}.items():
        monkeypatch.setenv(k, v)
    calls = {'push': 0, 'email': 0}
    def push(*args): calls['push'] += 1; return 'fixture-receipt'
    def email(*args):
        calls['email'] += 1
        if calls['email'] == 1: raise OSError('fixture outage')
        return 'fixture-receipt'
    monkeypatch.setattr('app.notifications.send_push', push); monkeypatch.setattr('app.notifications.send_email', email)
    at = now()
    with SessionLocal.begin() as db:
        dispatch(db, at)
        n = db.get(Notification, nid)
        assert n.state == 'sent'
        assert n.detail['channels']['email']['state'] == 'retry_pending'
    with SessionLocal.begin() as db:
        dispatch(db, at + timedelta(minutes=6))
        n = db.get(Notification, nid)
        assert n.state == 'sent'  # Never fabricate a device receipt.
        assert n.detail['channels']['email']['state'] == 'accepted'
    assert calls == {'push': 1, 'email': 2}
