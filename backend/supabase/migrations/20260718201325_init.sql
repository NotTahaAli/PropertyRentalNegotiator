create extension if not exists pgcrypto;

create table specs (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  vertical text not null,
  status text not null,
  spec_json jsonb not null,
  benchmark_json jsonb,
  confirmed boolean not null default false
);

create table dealers (
  id uuid primary key default gen_random_uuid(),
  spec_id uuid not null references specs(id) on delete cascade,
  name text not null,
  persona text not null,
  phone_label text,
  source text
);

create table calls (
  id uuid primary key default gen_random_uuid(),
  spec_id uuid not null references specs(id) on delete cascade,
  dealer_id uuid not null references dealers(id) on delete cascade,
  round int not null,
  status text not null,
  started_at timestamptz,
  ended_at timestamptz,
  recording_url text,
  transcript_json jsonb,
  outcome text
);

create table quotes (
  id uuid primary key default gen_random_uuid(),
  call_id uuid not null references calls(id) on delete cascade,
  dealer_id uuid not null references dealers(id) on delete cascade,
  monthly_rent numeric not null,
  advance_months numeric,
  commission numeric,
  maintenance numeric,
  annual_increment_pct numeric,
  other_fees jsonb,
  total_first_year numeric not null,
  binding boolean not null default false,
  notes text,
  flagged boolean not null default false,
  flag_reason text
);

create index dealers_spec_id_idx on dealers(spec_id);
create index calls_spec_id_idx on calls(spec_id);
create index calls_dealer_id_idx on calls(dealer_id);
create index quotes_call_id_idx on quotes(call_id);
create index quotes_dealer_id_idx on quotes(dealer_id);
