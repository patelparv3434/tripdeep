create table if not exists public.tripdeep_users (
  id bigserial primary key,
  document jsonb not null
);
create table if not exists public.tripdeep_trips (
  id bigserial primary key,
  document jsonb not null
);
create table if not exists public.tripdeep_agent_executions (
  id bigserial primary key,
  document jsonb not null
);
create table if not exists public.tripdeep_documents (
  id bigserial primary key,
  document jsonb not null
);
create table if not exists public.tripdeep_reproduction_cases (
  id bigserial primary key,
  document jsonb not null
);
create table if not exists public.tripdeep_audit_logs (
  id bigserial primary key,
  document jsonb not null
);

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'tripdeep_users',
    'tripdeep_trips',
    'tripdeep_agent_executions',
    'tripdeep_documents',
    'tripdeep_reproduction_cases',
    'tripdeep_audit_logs'
  ]
  loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('revoke all on table public.%I from anon, authenticated', table_name);
  end loop;
end
$$;
