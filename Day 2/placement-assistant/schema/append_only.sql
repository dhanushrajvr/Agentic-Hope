-- TODO (lab 2): make SQLite itself refuse UPDATE and DELETE on message.
CREATE TRIGGER IF NOT EXISTS message_no_update
BEFORE UPDATE ON message
BEGIN
  SELECT RAISE(ABORT, 'messages are append-only; UPDATE is forbidden');
END;

CREATE TRIGGER IF NOT EXISTS message_no_delete
BEFORE DELETE ON message
BEGIN
  SELECT RAISE(ABORT, 'messages are append-only; DELETE is forbidden');
END;