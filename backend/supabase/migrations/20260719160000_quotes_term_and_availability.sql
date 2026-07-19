-- K10: whole-term cost + delivery-date confirmation
-- Both columns are nullable — additive migration, no data transformation needed.

alter table quotes add column if not exists total_term numeric;
alter table quotes add column if not exists available_from date;
