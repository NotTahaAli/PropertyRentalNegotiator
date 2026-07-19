alter table dealers add column status text not null default 'active'
  check (status in ('active', 'declined'));
