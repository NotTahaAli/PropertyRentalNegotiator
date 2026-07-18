-- Pre-multi-tenant seed data has no owner; safe to drop in this dev project.
delete from specs;

alter table specs
  add column user_id uuid not null references auth.users(id) on delete cascade;

create index specs_user_id_idx on specs(user_id);
