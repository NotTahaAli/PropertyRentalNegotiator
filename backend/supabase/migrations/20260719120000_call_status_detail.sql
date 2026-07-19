-- Structured detail for the negotiator's explicit log_call_status tool call.
-- outcome itself stays a free text column (no check constraint, matches the
-- existing style) so the taxonomy in app.agent_factory.CALL_OUTCOMES can grow
-- without a migration.
alter table calls add column callback_at text;
alter table calls add column callback_note text;
