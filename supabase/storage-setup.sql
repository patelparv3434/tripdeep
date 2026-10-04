insert into storage.buckets (id, name, public, file_size_limit)
values ('tripdeep-documents', 'tripdeep-documents', false, 10485760)
on conflict (id) do update
set public = false, file_size_limit = 10485760;

drop policy if exists "Users can read their own Tripdeep documents" on storage.objects;
create policy "Users can read their own Tripdeep documents"
on storage.objects
for select
to authenticated
using (
  bucket_id = 'tripdeep-documents'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);

drop policy if exists "Users can upload their own Tripdeep documents" on storage.objects;
create policy "Users can upload their own Tripdeep documents"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'tripdeep-documents'
  and (storage.foldername(name))[1] = (select auth.uid())::text
);
