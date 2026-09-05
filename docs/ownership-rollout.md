# Ownership Backfill and Contract Rollout

Phase 10B exists for databases that contain documents or query history created before user
authentication was introduced. Fresh databases receive required ownership automatically and do
not need a data backfill.

## Safety properties

- The command requires an explicit Supabase Auth user UUID. No owner is hard-coded.
- Dry-run is the default and performs no writes.
- Apply mode updates only rows whose ownership is currently null.
- Apply mode locks the document and query tables and commits all assignments in one transaction.
- An unknown owner, conflicting document-scoped query, or failed post-write verification rolls
  the transaction back.
- Existing storage paths are not moved. The dry run reports legacy documents without matching
  private-bucket metadata so those objects can be investigated separately.

## Fresh or reset local database

No backfill is needed. `make db-reset` applies both ownership migrations and creates only the
owned synthetic seed record. The contract migration makes both ownership columns required.

You can confirm the final state with the deterministic seed user's UUID:

```bash
CLAIM_OWNER_ID=00000000-0000-4000-8000-000000000001 make auth-ownership-dry-run
```

The expected ownerless document and query counts are zero. Do not run apply mode merely to make
the output look successful; it should be used only when the dry run reports intended legacy rows.

## Existing database rollout

Treat this as an expand–backfill–contract deployment, not one blind migration push.

1. Take and verify a database backup using the environment's normal managed-backup process.
2. Apply `20260905020000_add_authentication_and_ownership.sql` and deploy the ownership-aware API.
   Do not apply the contract migration yet.
3. Create or select the operator's real Supabase Auth account. Copy its immutable user UUID from
   the Authentication users view; do not use an email address as the ownership key.
4. Point `DATABASE_URL` at the intended database and run the read-only inspection:

   ```bash
   DATABASE_URL='<direct-postgres-url>' \
   CLAIM_OWNER_ID='<operator-user-uuid>' \
   make auth-ownership-dry-run
   ```

5. Confirm the document and query counts match the known pre-authentication corpus. Investigate
   any mismatched scoped queries or missing storage metadata before continuing.
6. Run the same operation in apply mode:

   ```bash
   DATABASE_URL='<direct-postgres-url>' \
   CLAIM_OWNER_ID='<operator-user-uuid>' \
   make auth-ownership-apply
   ```

7. Run the dry run again. Ownerless and mismatched counts must all be zero.
8. Sign in as that operator and confirm the legacy documents are visible and their detail pages
   load successfully.
9. Apply `20260905020100_enforce_document_ownership.sql`. For the local stack, `make db-migrate`
   applies pending migrations without erasing accounts or documents. For a hosted stack, use the
   reviewed migration process for that environment. The migration independently aborts if
   ownerless or mismatched records remain, makes ownership non-null, and adds a database-level
   same-owner constraint for document-scoped queries.

Keep the direct database URL out of shell history when practical and never paste it into issues,
logs, or commits.

## Recovery

Before the contract migration, apply mode can be rolled back from the verified backup. After the
contract migration, do not set ownership back to null: restore the backup or perform an explicit
owner-to-owner reassignment in a reviewed maintenance transaction. Storage objects are untouched
by this command, so a database restore must be paired with the environment's corresponding
storage recovery procedure when object metadata or files also changed.
